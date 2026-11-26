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
    """Keep the latest verify result; a BROKEN result gates the API, a later OK clears it."""
    was = state.chain_ok
    state.chain_ok = ok
    state.chain_checked_at = monotonic()
    if not ok and was is not False:
        state.alert("audit chain verify is BROKEN; the API answers 503 until a verify passes")


def chain_ready(state: AppState) -> bool:
    """A fresh check now: the last 1000 rows plus the anchor must verify."""
    with state.chain_lock:
        with connect(state.settings.database_url) as conn:
            ok, _ = audit.verify(conn, state.settings.audit_anchor_path, tail=1000)
        record_chain(state, ok)
    return ok


def chain_status(state: AppState) -> bool:
    """The cached verify result; a new check runs at most once every CHAIN_RECHECK_SECONDS, so an
    unauthenticated caller of /ready cannot trigger more work."""
    if state.chain_ok is not None and monotonic() - state.chain_checked_at < CHAIN_RECHECK_SECONDS:
        return state.chain_ok
    return chain_ready(state)


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
    if not state.store_lost:
        state.reconciled.set()


def _reconcile_loop(state: AppState, stop: threading.Event) -> None:
    """Run the sweep until it succeeds once, so a database or engine that is still starting
    delays readiness instead of leaving the API half-ready for good."""
    while not state.reconciled.is_set() and not stop.is_set():
        try:
            reconcile_once(state)
            if not state.reconciled.is_set():
                stop.wait(RECONCILE_RETRY_SECONDS)  # the engine store is lost: look again later
        except Exception:
            logger.exception("reconcile failed; trying again")
            stop.wait(RECONCILE_RETRY_SECONDS)


def _anchor_loop(state: AppState, stop: threading.Event) -> None:
    while not stop.wait(ANCHOR_INTERVAL_SECONDS):
        try:
            healthy = chain_ready(state)
        except Exception:
            logger.exception("periodic audit verify failed")
            continue
        if healthy:
            _write_anchor(state)


def _write_anchor(state: AppState) -> None:
    try:
        with connect(state.settings.database_url) as conn:
            audit.write_anchor(conn, state.settings.audit_anchor_path)
    except Exception:
        logger.exception("anchor write failed")


def create_app(
    settings: Settings | None = None,
    engine: EngineGateway | None = None,
    clock: Callable[[], datetime] = utc_now,
) -> FastAPI:
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
            chain_ready(state)
        except Exception:
            logger.exception("startup audit check failed")
        thread = threading.Thread(target=_anchor_loop, args=(state, stop), daemon=True)
        thread.start()
        sweeper = threading.Thread(target=_reconcile_loop, args=(state, stop), daemon=True)
        sweeper.start()
        try:
            yield
        finally:
            stop.set()
            if state.chain_ok is not False:
                _write_anchor(state)

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
            and state.chain_ok is False
            and (request.method, request.url.path) not in GATE_EXEMPT
        ):
            return JSONResponse(ApiError("NOT_READY").body(), status_code=503)
        return await call_next(request)

    for module in (auth, cases, links, queue, graph, access, admin, changes, audit_routes):
        app.include_router(module.router)
    context.check_route_inventory(app)
    return app


app = create_app()
