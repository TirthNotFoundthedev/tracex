"""The FastAPI application: routes, handlers, startup checks and the audit anchor loop."""

import logging
import threading
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI
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
RECONCILE_RETRY_SECONDS = 5


def _engine_for(settings: Settings) -> EngineGateway:
    if settings.neo4j_uri:
        return EngineGateway.from_neo4j(
            settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password
        )
    return EngineGateway.in_memory()


def chain_ready(state: AppState) -> bool:
    """Startup and /ready: the last 1000 rows plus the anchor must verify."""
    with connect(state.settings.database_url) as conn:
        ok, _ = audit.verify(conn, state.settings.audit_anchor_path, tail=1000)
    return ok


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
        thread = threading.Thread(target=_anchor_loop, args=(state, stop), daemon=True)
        thread.start()
        sweeper = threading.Thread(target=_reconcile_loop, args=(state, stop), daemon=True)
        sweeper.start()
        try:
            yield
        finally:
            stop.set()
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
            ok = state is not None and state.reconciled.is_set() and chain_ready(state)
        except Exception:
            logger.exception("readiness check failed")
            ok = False
        if not ok:
            return JSONResponse(ApiError("NOT_READY").body(), status_code=503)
        return {"status": "ok"}

    for module in (auth, cases, links, queue, graph, access, admin, changes, audit_routes):
        app.include_router(module.router)
    context.check_route_inventory(app)
    return app


app = create_app()
