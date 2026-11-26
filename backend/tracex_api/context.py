"""Request context, authentication, the route registry and the error handlers.

Every route is declared with `endpoint(...)`, which records its policy and audit event (R1, W6)
and wraps the handler: it checks the role gate, runs the handler, appends the queued audit rows
as the last step before the commit (W1, W2), and turns `ApiError` into the response, writing the
W3 rows (denials, auth failures) in their own transaction after the business transaction has
been rolled back.
"""

import functools
import ipaddress
import json
import logging
import threading
import uuid
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from tracex_api import audit
from tracex_api.audit import Actor, AuditEvent
from tracex_api.config import Settings
from tracex_api.db import Conn, Row, connect, many, need, one
from tracex_api.errors import ApiError
from tracex_api.policy import CaseFact, Principal
from tracex_api.security import TokenError, decode_token, keyed_hash, well_formed_uuid

if TYPE_CHECKING:
    from tracex_api.engine_bridge import EngineGateway

logger = logging.getLogger(__name__)

ALL_OFFICERS = frozenset({"JUNIOR", "INVESTIGATOR", "SUPERVISOR", "SENIOR"})
EVERY_ROLE = ALL_OFFICERS | {"ADMIN"}


@dataclass(frozen=True)
class Policy:
    """Who reaches the handler. Roles outside `allow` get `outside`: 404 where the caller must
    not learn the thing exists (case data for ADMIN), 403 where it is a plain role gate."""

    name: str
    allow: frozenset[str]
    outside: int = 403


OFFICER = Policy("officer: case data", ALL_OFFICERS, outside=404)
ANY_USER = Policy("any authenticated user", EVERY_ROLE)
ADMIN_ONLY = Policy("admin only", frozenset({"ADMIN"}))
ADMIN_HIDDEN = Policy("admin only; officers see 404", frozenset({"ADMIN"}), outside=404)
SENIOR_ONLY = Policy("senior only", frozenset({"SENIOR"}))
SENIOR_OR_ADMIN = Policy("senior or admin", frozenset({"SENIOR", "ADMIN"}))
SUPERVISOR_UP = Policy("supervisor, senior, admin", frozenset({"SUPERVISOR", "SENIOR", "ADMIN"}))
PUBLIC = Policy("public", EVERY_ROLE)


@dataclass(frozen=True)
class RouteSpec:
    method: str
    path: str
    policy: str
    audit_event: str


ROUTES: list[RouteSpec] = []


@dataclass
class AppState:
    settings: Settings
    clock: Callable[[], datetime]
    engine: "EngineGateway"
    alerts: list[str] = field(default_factory=list)
    reconciled: threading.Event = field(default_factory=threading.Event)
    store_lost: bool = False
    withdrawals_deferred: bool = False  # a match run was RUNNING during the sweep
    stale_runs_handled: bool = False  # interrupt_stale_runs ran once in this process
    chain_ok: bool | None = None  # latest audit verify; None until the first one ran
    chain_checked_at: float = 0.0
    chain_lock: threading.Lock = field(default_factory=threading.Lock)

    def now(self) -> datetime:
        return self.clock()

    def alert(self, message: str) -> None:
        """Divergence and reconcile alerts: logged as errors and kept for the operator view."""
        if message not in self.alerts[-3:]:
            self.alerts.append(message)
        logger.error("alert: %s", message)


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class Ctx:
    """One request: its connection, its caller and the audit rows queued for the commit."""

    def __init__(self, request: Request, state: AppState, conn: Conn) -> None:
        self.request = request
        self.state = state
        self.conn = conn
        self.principal: Principal | None = None
        self.request_id = str(uuid.uuid4())
        self.pending: list[AuditEvent] = []
        self._cases: dict[str, CaseFact] = {}

    @classmethod
    def for_system(cls, state: AppState, conn: Conn) -> "Ctx":
        """A request-less context for work the process starts itself (startup reconcile)."""
        scope: dict[str, Any] = {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [],
            "client": None,
            "query_string": b"",
        }
        return cls(Request(scope), state, conn)

    # time ---------------------------------------------------------------------------------
    def now(self) -> datetime:
        return self.state.now()

    # caller -------------------------------------------------------------------------------
    @property
    def me(self) -> Principal:
        self.principal = need(self.principal)
        return self.principal

    def actor(self) -> Actor:
        if self.principal is None:
            return audit.ANONYMOUS
        return Actor(
            "USER", self.principal.user_id, self.principal.role, self.principal.district_id
        )

    def client_ip(self) -> str | None:
        host = self.request.client.host if self.request.client else None
        try:
            return str(ipaddress.ip_address(host)) if host else None
        except ValueError:
            return None

    # case facts ---------------------------------------------------------------------------
    def case_facts(self, case_ids: Sequence[str]) -> dict[str, CaseFact]:
        missing = [c for c in set(case_ids) if c not in self._cases]
        if missing:
            for row in many(
                self.conn,
                "SELECT id, district_id FROM cases WHERE id = ANY(%s)",
                ([uuid.UUID(c) for c in missing],),
            ):
                self._cases[str(row["id"])] = CaseFact(str(row["id"]), str(row["district_id"]))
        return {c: self._cases[c] for c in case_ids if c in self._cases}

    def refs(self, case_ids: Sequence[str]) -> list[dict[str, str]]:
        facts = self.case_facts(list(dict.fromkeys(case_ids)))
        return [
            {"case_id": f.case_id, "district_id": f.district_id}
            for f in sorted(facts.values(), key=lambda f: f.case_id)
        ]

    # audit --------------------------------------------------------------------------------
    def event(
        self,
        event_type: str,
        *,
        refs: Sequence[str] = (),
        target_type: str | None = None,
        target_id: str | None = None,
        detail: dict[str, Any] | None = None,
        reason_code: str | None = None,
        outcome: str = "SUCCESS",
        actor: Actor | None = None,
    ) -> AuditEvent:
        return AuditEvent(
            event_type=event_type,
            actor=actor or self.actor(),
            outcome=outcome,
            reason_code=reason_code,
            refs=self.refs(refs) if refs else [],
            target_type=target_type,
            target_id=target_id,
            detail=detail or {},
            session_id=self.principal.sid if self.principal else None,
            request_id=self.request_id,
            client_ip=self.client_ip(),
        )

    def audit(self, event_type: str, **fields: Any) -> None:
        """Queue an audit row; it is appended just before the commit, so the data never leaves
        without it (W1) and a state change and its row commit together (W2)."""
        self.pending.append(self.event(event_type, **fields))

    def commit(self) -> None:
        for event in self.pending:
            audit.append(self.conn, event)
        self.pending.clear()
        self.conn.commit()

    # refusals -----------------------------------------------------------------------------
    def supplied_id(self, supplied: str) -> str:
        """An id from a path, stored raw only when it is a well-formed uuid (spec section 6)."""
        if well_formed_uuid(supplied):
            return supplied
        return keyed_hash(self.state.settings.hmac_key, supplied)

    def not_found(self, supplied: str, resolved: str | None = None, action: str = "") -> ApiError:
        """404 for an unknown or hidden id, identical for both; the audit row is too."""
        denied = self.event(
            "ACCESS_DENIED",
            outcome="DENIED",
            reason_code="R2_NOT_VISIBLE",
            target_type="UNRESOLVED",
            target_id=self.supplied_id(supplied),
            detail={"action": action or self.action_label(), "http_status": 404},
        )
        denied.resolved_target = resolved
        return ApiError("NOT_FOUND", audits=[denied])

    def forbidden(
        self,
        target_type: str | None,
        target_id: str | None,
        case_ids: Sequence[str] = (),
        reason_code: str = "MATRIX_DENY",
    ) -> ApiError:
        denied = self.event(
            "ACCESS_DENIED",
            outcome="DENIED",
            reason_code=reason_code,
            refs=case_ids,
            target_type=target_type,
            target_id=target_id,
            detail={"action": self.action_label(), "http_status": 403},
        )
        return ApiError("FORBIDDEN", audits=[denied])

    def action_label(self) -> str:
        route = self.request.scope.get("route")
        path = getattr(route, "path", self.request.url.path)
        return f"{self.request.method} {path}"

    # request bodies and cursors -----------------------------------------------------------
    def body[M: BaseModel](self, model: type[M]) -> M:
        """Parse the JSON body after the visibility, role and state checks (R2 order)."""
        raw: bytes = getattr(self.request.state, "body", b"")
        try:
            return model.model_validate(json.loads(raw) if raw else {})
        except ValidationError as exc:
            raise ApiError("VALIDATION_FAILED", pydantic_field_errors(exc)) from exc
        except ValueError as exc:
            raise ApiError("VALIDATION_FAILED", [{"field": "body", "code": "malformed"}]) from exc


def pydantic_field_errors(exc: ValidationError) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for err in exc.errors():
        name = ".".join(str(p) for p in err["loc"]) or "body"
        code = "".join(c if c.islower() else "_" for c in str(err["type"]).lower())
        out.append({"field": name, "code": code.strip("_") or "invalid"})
    return out[:20]


def load_principal(ctx: Ctx, user: Row, sid: str) -> Principal:
    uid = user["id"]
    coverage = many(ctx.conn, "SELECT * FROM user_coverage WHERE user_id = %s", (uid,))
    all_states = any(r["all_states"] for r in coverage)
    states = frozenset(str(r["state_id"]) for r in coverage if r["state_id"])
    districts = frozenset(str(r["district_id"]) for r in coverage if r["district_id"])
    covered: set[str] = set(districts)
    if states:
        for r in many(
            ctx.conn,
            "SELECT id FROM districts WHERE state_id = ANY(%s)",
            ([uuid.UUID(s) for s in states],),
        ):
            covered.add(str(r["id"]))
    assigned = frozenset(
        str(r["case_id"])
        for r in many(
            ctx.conn,
            "SELECT case_id FROM case_assignments WHERE user_id = %s AND active",
            (uid,),
        )
    )
    now = ctx.now()
    grants = {
        str(r["link_id"]): str(r["id"])
        for r in many(
            ctx.conn,
            "SELECT id, link_id FROM access_grants "
            "WHERE holder_id = %s AND state = 'ACTIVE' AND expires_at > %s",
            (uid, now),
        )
    }
    return Principal(
        user_id=str(uid),
        username=user["username"],
        display_name=user["display_name"],
        role=user["role"],
        district_id=str(user["district_id"]) if user["district_id"] else None,
        sid=sid,
        coverage_all=all_states,
        coverage_state_ids=states,
        coverage_district_ids=districts,
        covered_districts=frozenset(covered),
        assigned_cases=assigned,
        active_grants=grants,
    )


def authenticate(ctx: Ctx) -> Principal:
    """Bearer token to principal, checking the session and the user in the database."""
    header = ctx.request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    claimed: str | None = None
    try:
        if scheme.lower() != "bearer" or not token:
            raise TokenError("MISSING")
        claims = decode_token(ctx.state.settings.jwt_key, token, "access", ctx.now())
        claimed = claims.get("sub") if isinstance(claims.get("sub"), str) else None
        sid, sub = str(claims.get("sid")), str(claims.get("sub"))
        if not (well_formed_uuid(sid) and well_formed_uuid(sub)):
            raise TokenError("MALFORMED", claimed)
        session = one(
            ctx.conn,
            "SELECT * FROM sessions WHERE sid = %s AND user_id = %s",
            (uuid.UUID(sid), uuid.UUID(sub)),
        )
        if (
            session is None
            or session["revoked_at"] is not None
            or session["expires_at"] <= ctx.now()
        ):
            raise TokenError("DEAD_SESSION", claimed)
        user = one(ctx.conn, "SELECT * FROM users WHERE id = %s", (uuid.UUID(sub),))
        if user is None or not user["active"]:
            raise TokenError("DEAD_SESSION", claimed)
        if claims.get("ver") != user["authz_version"]:
            raise TokenError("STALE_VERSION", claimed)
    except TokenError as exc:
        detail: dict[str, Any] = {"failure": exc.failure}
        if exc.claimed_sub:
            detail["claimed_sub"] = ctx.supplied_id(exc.claimed_sub)
        rejected = ctx.event(
            "AUTH_TOKEN_REJECTED", outcome="DENIED", detail=detail, actor=audit.ANONYMOUS
        )
        raise ApiError("UNAUTHENTICATED", audits=[rejected]) from exc
    return load_principal(ctx, user, sid)


def expire_stale(ctx: Ctx) -> None:
    """Close grants past `expires_at` and expire pending requests older than 7 days, audited
    with the system actor. Cheap when nothing is due, so it runs on every authenticated request."""
    now = ctx.now()
    due = many(
        ctx.conn,
        "SELECT g.id, g.link_id, l.case_a_id, l.case_b_id FROM access_grants g "
        "JOIN links l USING (link_id) WHERE g.state = 'ACTIVE' AND g.expires_at <= %s",
        (now,),
    )
    for g in due:
        ctx.conn.execute(
            "UPDATE access_grants SET state = 'EXPIRED', closed_at = %s, close_cause = 'TIME' "
            "WHERE id = %s",
            (now, g["id"]),
        )
        ctx.audit(
            "ACCESS_GRANT_EXPIRED",
            actor=audit.SYSTEM,
            refs=[str(g["case_a_id"]), str(g["case_b_id"])],
            target_type="GRANT",
            target_id=str(g["id"]),
            detail={"cause": "TIME"},
        )
    stale = many(
        ctx.conn,
        "SELECT r.id, r.stub_id, l.case_a_id, l.case_b_id FROM access_requests r "
        "JOIN links l USING (link_id) WHERE r.state = 'PENDING' AND r.expires_at <= %s",
        (now,),
    )
    for r in stale:
        ctx.conn.execute("UPDATE access_requests SET state = 'EXPIRED' WHERE id = %s", (r["id"],))
        ctx.audit(
            "ACCESS_REQUEST_EXPIRED",
            actor=audit.SYSTEM,
            refs=[str(r["case_a_id"]), str(r["case_b_id"])],
            target_type="ACCESS_REQUEST",
            target_id=str(r["id"]),
            detail={"stub_id": str(r["stub_id"])},
        )


async def read_body(request: Request) -> None:
    """Keep the raw JSON body for `Ctx.body`, which parses it after the visibility and role
    checks. A multipart upload is parsed by FastAPI itself and has no JSON body."""
    if "multipart/" in request.headers.get("content-type", ""):
        request.state.body = b""
        return
    request.state.body = await request.body()


def _make_ctx(request: Request) -> Iterator[Ctx]:
    state: AppState = request.app.state.tracex
    conn = connect(state.settings.database_url)
    ctx = Ctx(request, state, conn)
    request.state.ctx = ctx
    try:
        yield ctx
    finally:
        conn.close()


def public_ctx(request: Request) -> Iterator[Ctx]:
    yield from _make_ctx(request)


def authed_ctx(request: Request) -> Iterator[Ctx]:
    for ctx in _make_ctx(request):
        ctx.principal = authenticate(ctx)
        expire_stale(ctx)
        ctx.commit()  # expiries stand even if this request is then refused and rolled back
        yield ctx


def endpoint(
    router: APIRouter,
    method: str,
    path: str,
    *,
    policy: Policy,
    audit_event: str,
    status_code: int = 200,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Register a route with its policy and audit event, and wrap the handler (see module doc)."""
    ROUTES.append(RouteSpec(method.upper(), path, policy.name, audit_event))

    def decorate(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        def inner(*args: Any, **kwargs: Any) -> Any:
            return _run(fn, policy, kwargs["ctx"], args, kwargs)

        # FastAPI inspects the wrapped signature; `ctx` is injected through Depends below.
        router.add_api_route(
            path,
            inner,
            methods=[method.upper()],
            status_code=status_code,
            response_model=None,
            dependencies=[Depends(read_body)],
        )
        return inner

    return decorate


def _run(
    fn: Callable[..., Any],
    policy: Policy,
    ctx: Ctx,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> Any:
    """Run the handler and commit; an `ApiError` rolls the transaction back and answers here,
    while the connection is still open, then appends the W3 rows in their own transaction."""
    try:
        principal = ctx.principal
        if principal is not None and principal.role not in policy.allow:
            raise (
                ctx.not_found(ctx.action_label())
                if policy.outside == 404
                else ctx.forbidden(None, None)
            )
        result = fn(*args, **kwargs)
        ctx.commit()
        return result
    except ApiError as exc:
        ctx.pending.clear()
        ctx.conn.rollback()
        if exc.audits:
            _append_independent(ctx.state, exc.audits)
        return JSONResponse(exc.body(), status_code=exc.status, headers=exc.headers)


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    ctx: Ctx | None = getattr(request.state, "ctx", None)
    state: AppState = request.app.state.tracex
    if ctx is not None:
        ctx.pending.clear()
        if not ctx.conn.closed:
            ctx.conn.rollback()
    if exc.audits:
        _append_independent(state, exc.audits)
    return JSONResponse(exc.body(), status_code=exc.status, headers=exc.headers)


def _append_independent(state: AppState, events: Sequence[AuditEvent]) -> None:
    """W3: denials and auth failures are appended in their own transaction."""
    with connect(state.settings.database_url) as conn:
        for event in events:
            audit.append(conn, event)
        conn.commit()


async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {
            "field": ".".join(str(p) for p in e["loc"] if p not in ("query", "path", "body"))
            or "request",
            "code": "".join(c if c.islower() else "_" for c in str(e["type"]).lower()).strip("_")
            or "invalid",
        }
        for e in exc.errors()
    ][:20]
    return JSONResponse(ApiError("VALIDATION_FAILED", errors).body(), status_code=422)


async def http_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = {404: "NOT_FOUND", 405: "NOT_FOUND"}.get(exc.status_code, "INTERNAL")
    error = ApiError(code)
    return JSONResponse(error.body(), status_code=error.status)


async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    ctx: Ctx | None = getattr(request.state, "ctx", None)
    if ctx is not None:
        ctx.pending.clear()
        if not ctx.conn.closed:
            try:
                ctx.conn.rollback()
            except Exception:  # noqa: BLE001 - the connection may already be broken
                logger.debug("rollback failed", exc_info=True)
    logger.error("request failed", exc_info=exc, extra={"path": request.url.path})
    error = ApiError("INTERNAL")
    return JSONResponse(error.body(), status_code=error.status)


def install(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_handler)


def implemented_routes(app: FastAPI) -> set[tuple[str, str]]:
    """Every (method, path) the app serves, read from its OpenAPI document because included
    routers are nested and not listed in `app.routes`."""
    paths: dict[str, dict[str, Any]] = app.openapi()["paths"]
    return {(m.upper(), path) for path, ops in paths.items() for m in ops}


def check_route_inventory(app: FastAPI) -> None:
    """A route without a registered policy and audit event stops the API from starting (R1)."""
    declared = {(r.method, r.path) for r in ROUTES if r.policy and r.audit_event}
    for method, path in sorted(implemented_routes(app)):
        if (method, path) not in declared:
            raise RuntimeError(f"route {method} {path} has no declared policy and audit event")
