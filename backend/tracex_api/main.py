"""The FastAPI application: routes, handlers, startup checks and the audit anchor loop."""

import logging
import threading
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import datetime
from time import monotonic
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from tracex_api import audit, context
from tracex_api.config import ConfigError, Settings
from tracex_api.context import AppState, Ctx, RouteSpec, utc_now
from tracex_api.db import connect
from tracex_api.engine_bridge import EngineGateway, reconcile
from tracex_api.errors import ApiError
from tracex_api.explanation_check import load_schema
from tracex_api.routers import (
    access,
    admin,
    audit_routes,
    auth,
    cases,
    changes,
    graph,
    links,
    queue,
)

logger = logging.getLogger(__name__)
ANCHOR_INTERVAL_SECONDS = 60
CHAIN_RECHECK_SECONDS = 60
GATE_EXEMPT = {("GET", "/health"), ("GET", "/ready"), ("POST", "/audit/verify")}
RECONCILE_RETRY_SECONDS = 5


def _engine_for(settings: Settings) -> EngineGateway:
    if settings.neo4j_uri:
        return EngineGateway.from_neo4j(
            settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password
        )
    return EngineGateway.in_memory()


def record_chain(state: AppState, ok: bool) -> None:
    """Keep the latest verify result. The API serves only while the latest result is OK; the first
    result that is not OK raises the alert once, and a later OK clears it."""
    was = state.chain_ok
    state.chain_ok = ok
    state.chain_checked_at = monotonic()
    if not ok and was is not False:
        state.alert("audit chain verify is BROKEN; the API answers 503 until a verify passes")


def check_chain(state: AppState, *, anchor: bool = False) -> bool:
    """A fresh check now: the last 1000 rows plus the anchor must verify. Any exception counts as
    not OK. With `anchor`, a passing check also anchors the row it checked, under the same lock;
    a failing or raising check never writes an anchor."""
    with state.chain_lock:
        try:
            with connect(state.settings.database_url) as conn:
                result = audit.verify_checked(conn, state.settings.audit_anchor_path, tail=1000)
            record_chain(state, result.ok)
        except Exception:
            logger.exception("audit verify failed; treating the chain as BROKEN")
            record_chain(state, False)
            return False
        if result.ok and anchor:
            try:
                audit.anchor_checked(state.settings.audit_anchor_path, result)
            except OSError:
                logger.exception("anchor write failed")
    return result.ok


def chain_status(state: AppState) -> bool:
    """The cached verify result; a new check runs at most once every CHAIN_RECHECK_SECONDS, so an
    unauthenticated caller of /ready cannot trigger more work."""
    if state.chain_ok is not None and monotonic() - state.chain_checked_at < CHAIN_RECHECK_SECONDS:
        return state.chain_ok
    return check_chain(state)


def startup_anchor(state: AppState) -> None:
    """A log that holds only its first row gets its first anchor now; later rows need one."""
    with connect(state.settings.database_url) as conn:
        head = conn.execute("SELECT max(seq) AS m FROM audit_log").fetchone()
        if (head is None or (head["m"] or 0) <= 1) and audit.read_anchor(
            state.settings.audit_anchor_path
        ) is None:
            audit.write_anchor(conn, state.settings.audit_anchor_path)


def reconcile_once(state: AppState) -> None:
    """The startup sweep (architecture section 2): the API reports ready only after it ran."""
    with connect(state.settings.database_url) as conn:
        who = conn.execute(
            "SELECT current_user AS name, rolsuper FROM pg_roles WHERE rolname = current_user"
        ).fetchone()
        if who is None or who["rolsuper"]:
            raise ConfigError("DATABASE_URL must be the tracex_api login, never a superuser")
        counts = reconcile(Ctx.for_system(state, conn))
    logger.info("reconcile finished", extra={"counts": counts})
    if not state.store_lost and not state.withdrawals_deferred:
        state.reconciled.set()


def _reconcile_loop(state: AppState, stop: threading.Event) -> None:
    """Run the sweep until it succeeds once, so a database or engine that is still starting
    delays readiness instead of leaving the API half-ready for good. A lost engine store ends the
    loop: the alert stays and /ready stays 503 until an operator restores the store and restarts
    the API (the runbook recovery); nothing resumes withdrawals on its own."""
    while not state.reconciled.is_set() and not stop.is_set():
        try:
            reconcile_once(state)
        except Exception:
            logger.exception("reconcile failed; trying again")
        if state.store_lost:
            logger.error("engine store is lost; restore it and restart the API")
            return
        if not state.reconciled.is_set():
            stop.wait(RECONCILE_RETRY_SECONDS)


def _anchor_loop(state: AppState, stop: threading.Event) -> None:
    while not stop.wait(ANCHOR_INTERVAL_SECONDS):
        check_chain(state, anchor=True)


def create_app(
    settings: Settings | None = None,
    engine: EngineGateway | None = None,
    clock: Callable[[], datetime] = utc_now,
) -> FastAPI:
    load_schema()  # a missing contract file stops the API from starting
    stop = threading.Event()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if not hasattr(app.state, "tracex"):
            try:
                loaded = Settings.from_env()
            except ConfigError:
                # Not configured: /health answers, /ready says 503 and every other route fails
                # closed with INTERNAL until the environment is complete.
                logger.exception("settings are incomplete; the API is not ready")
                yield
                return
            app.state.tracex = AppState(loaded, clock, engine or _engine_for(loaded))
        state: AppState = app.state.tracex
        try:
            startup_anchor(state)
        except Exception:
            logger.exception("startup anchor failed")
        check_chain(state)  # records BROKEN on any failure; the gate stays shut until it passes
        thread = threading.Thread(target=_anchor_loop, args=(state, stop), daemon=True)
        thread.start()
        sweeper = threading.Thread(target=_reconcile_loop, args=(state, stop), daemon=True)
        sweeper.start()
        try:
            yield
        finally:
            stop.set()
            check_chain(state, anchor=True)  # fresh check; anchors only when it passes

    app = FastAPI(title="TraceX API", lifespan=lifespan)
    context.install(app)
    if settings is not None:
        app.state.tracex = AppState(settings, clock, engine or _engine_for(settings))

    context.ROUTES.append(RouteSpec("GET", "/health", "public probe", "NONE"))
    context.ROUTES.append(RouteSpec("GET", "/ready", "public probe", "NONE"))

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready", response_model=None)
    def ready() -> Any:
        state: AppState | None = getattr(app.state, "tracex", None)
        try:
            ok = state is not None and state.reconciled.is_set() and chain_status(state)
        except Exception:
            logger.exception("readiness check failed")
            ok = False
        if not ok:
            return JSONResponse(ApiError("NOT_READY").body(), status_code=503)
        return {"status": "ok"}

    @app.middleware("http")
    async def audit_gate(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        state: AppState | None = getattr(app.state, "tracex", None)
        if (
            state is not None
            and state.chain_ok is not True
            and (request.method, request.url.path) not in GATE_EXEMPT
        ):
            return JSONResponse(ApiError("NOT_READY").body(), status_code=503)
        return await call_next(request)

    for module in (auth, cases, links, queue, graph, access, admin, changes, audit_routes):
        app.include_router(module.router)
    context.check_route_inventory(app)
    return app


app = create_app()
