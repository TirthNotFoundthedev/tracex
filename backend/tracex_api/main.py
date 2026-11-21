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
from tracex_api.config import Settings
from tracex_api.context import AppState, RouteSpec, utc_now
from tracex_api.db import connect
from tracex_api.engine_bridge import EngineGateway
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
            loaded = Settings.from_env()
            app.state.tracex = AppState(loaded, clock, engine or _engine_for(loaded))
        state: AppState = app.state.tracex
        thread = threading.Thread(target=_anchor_loop, args=(state, stop), daemon=True)
        thread.start()
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
            ok = state is not None and chain_ready(state)
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
