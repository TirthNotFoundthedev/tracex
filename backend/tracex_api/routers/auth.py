"""Login, refresh, logout, /me and the probes (spec: api-access-control section 6)."""

import uuid
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field

from tracex_api import audit
from tracex_api.audit import Actor
from tracex_api.context import (
    ANY_USER,
    PUBLIC,
    Ctx,
    authed_ctx,
    endpoint,
    iso,
    public_ctx,
)
from tracex_api.db import Row, many, need, one
from tracex_api.errors import ApiError
from tracex_api.security import (
    TokenError,
    decode_token,
    issue_access_token,
    keyed_hash,
    verify_password,
    well_formed_uuid,
)

router = APIRouter()

THROTTLE_FAILURES = 5
THROTTLE_WINDOW = timedelta(minutes=15)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refresh_token: str = Field(min_length=16, max_length=2048)


def user_out(ctx: Ctx, user: Row, with_count: bool = True) -> dict[str, Any]:
    coverage: dict[str, Any] | None = None
    if user["role"] == "SENIOR":
        rows = many(ctx.conn, "SELECT * FROM user_coverage WHERE user_id = %s", (user["id"],))
        coverage = {
            "all_states": any(r["all_states"] for r in rows),
            "state_ids": sorted(str(r["state_id"]) for r in rows if r["state_id"]),
            "district_ids": sorted(str(r["district_id"]) for r in rows if r["district_id"]),
        }
    out: dict[str, Any] = {
        "user_id": str(user["id"]),
        "username": user["username"],
        "display_name": user["display_name"],
        "role": user["role"],
        "district_id": str(user["district_id"]) if user["district_id"] else None,
        "coverage": coverage,
        "active": user["active"],
    }
    if with_count:
        count = one(
            ctx.conn,
            "SELECT count(*) AS n FROM case_assignments WHERE user_id = %s AND active",
            (user["id"],),
        )
        out["assignment_count"] = int(count["n"]) if count else 0
    return out


def _token_pair(
    ctx: Ctx,
    user: Row,
    sid: str,
    session_expires: Any,
    jti: str | None = None,
    insert: bool = True,
) -> dict[str, Any]:
    settings = ctx.state.settings
    now = ctx.now()
    jti = jti or str(uuid.uuid4())
    if insert:
        ctx.conn.execute(
            "INSERT INTO refresh_tokens (jti, sid, issued_at) VALUES (%s, %s, %s)",
            (uuid.UUID(jti), uuid.UUID(sid), now),
        )
    # The refresh token expires with the session (8 h absolute), not 8 h after each rotation.
    refresh = _refresh_until(ctx, sid, jti, session_expires)
    return {
        "access_token": issue_access_token(
            settings.jwt_key,
            str(user["id"]),
            sid,
            user["authz_version"],
            now,
            settings.access_token_minutes,
        ),
        "refresh_token": refresh,
        "token_type": "Bearer",
        "expires_in": settings.access_token_minutes * 60,
        "refresh_expires_in": int((session_expires - now).total_seconds()),
        "user": user_out(ctx, user),
    }


def _refresh_until(ctx: Ctx, sid: str, jti: str, expires: Any) -> str:
    import jwt

    claims = {
        "sid": sid,
        "jti": jti,
        "iat": int(ctx.now().timestamp()),
        "exp": int(expires.timestamp()),
        "typ": "refresh",
    }
    return jwt.encode(claims, ctx.state.settings.jwt_key, algorithm="HS256")


@endpoint(router, "POST", "/auth/login", policy=PUBLIC, audit_event="AUTH_LOGIN_SUCCESS")
def login(ctx: Ctx = Depends(public_ctx)) -> dict[str, Any]:
    body = ctx.body(LoginRequest)
    settings = ctx.state.settings
    now = ctx.now()
    ip = ctx.client_ip() or "unknown"
    username = body.username.strip().lower()
    key = keyed_hash(settings.hmac_key, f"{username}|{ip}")
    failures = one(
        ctx.conn,
        "SELECT count(*) AS n FROM login_attempts WHERE key = %s AND at > %s",
        (key, now - THROTTLE_WINDOW),
    )
    throttled = failures is not None and int(failures["n"]) >= THROTTLE_FAILURES
    user = one(ctx.conn, "SELECT * FROM users WHERE username = %s", (username,))
    ok = verify_password(body.password, user["password_hash"] if user else None)
    if throttled or not ok or user is None or not user["active"]:
        if not throttled:
            ctx.conn.execute("INSERT INTO login_attempts (key, at) VALUES (%s, %s)", (key, now))
            ctx.conn.commit()
        claimed = body.username if user is not None and body.username == user["username"] else None
        detail: dict[str, Any] = {
            "claimed_username": claimed or keyed_hash(settings.hmac_key, body.username),
            "throttled": throttled,
        }
        failed = ctx.event(
            "AUTH_LOGIN_FAILED", outcome="FAILED", detail=detail, actor=audit.ANONYMOUS
        )
        error = ApiError("TOO_MANY_REQUESTS" if throttled else "UNAUTHENTICATED", audits=[failed])
        if throttled:
            error.headers["Retry-After"] = str(int(THROTTLE_WINDOW.total_seconds()))
        raise error
    sid = str(uuid.uuid4())
    expires = now + timedelta(hours=settings.session_hours)
    ctx.conn.execute(
        "INSERT INTO sessions (sid, user_id, created_at, expires_at) VALUES (%s, %s, %s, %s)",
        (uuid.UUID(sid), user["id"], now, expires),
    )
    ctx.principal = None
    ctx.audit(
        "AUTH_LOGIN_SUCCESS",
        actor=Actor(
            "USER",
            str(user["id"]),
            user["role"],
            str(user["district_id"]) if user["district_id"] else None,
        ),
        target_type="USER",
        target_id=str(user["id"]),
    )
    return _token_pair(ctx, user, sid, expires)


@endpoint(router, "POST", "/auth/refresh", policy=PUBLIC, audit_event="AUTH_REFRESHED")
def refresh_token(ctx: Ctx = Depends(public_ctx)) -> dict[str, Any]:
    body = ctx.body(RefreshRequest)
    settings = ctx.state.settings
    try:
        claims = decode_token(settings.jwt_key, body.refresh_token, "refresh", ctx.now())
        sid, jti = str(claims.get("sid")), str(claims.get("jti"))
        if not (well_formed_uuid(sid) and well_formed_uuid(jti)):
            raise TokenError("MALFORMED")
    except TokenError as exc:
        rejected = ctx.event(
            "AUTH_TOKEN_REJECTED",
            outcome="DENIED",
            detail={"failure": exc.failure},
            actor=audit.ANONYMOUS,
        )
        raise ApiError("UNAUTHENTICATED", audits=[rejected]) from exc
    session = one(ctx.conn, "SELECT * FROM sessions WHERE sid = %s", (uuid.UUID(sid),))
    token = one(ctx.conn, "SELECT * FROM refresh_tokens WHERE jti = %s", (uuid.UUID(jti),))
    user = (
        one(ctx.conn, "SELECT * FROM users WHERE id = %s", (session["user_id"],))
        if session
        else None
    )
    actor = (
        Actor(
            "USER",
            str(user["id"]),
            user["role"],
            str(user["district_id"]) if user["district_id"] else None,
        )
        if user
        else audit.ANONYMOUS
    )
    dead = (
        session is None
        or token is None
        or user is None
        or session["revoked_at"] is not None
        or session["expires_at"] <= ctx.now()
        or not user["active"]
    )
    if dead or token["sid"] != session["sid"]:  # type: ignore[index]
        rejected = ctx.event(
            "AUTH_TOKEN_REJECTED",
            outcome="DENIED",
            detail={"failure": "DEAD_SESSION"},
            actor=audit.ANONYMOUS,
        )
        raise ApiError("UNAUTHENTICATED", audits=[rejected])
    session = need(session)
    token = need(token)
    user = need(user)
    new_jti = uuid.uuid4()
    ctx.conn.execute(
        "INSERT INTO refresh_tokens (jti, sid, issued_at) VALUES (%s, %s, %s)",
        (new_jti, session["sid"], ctx.now()),
    )
    won = one(
        ctx.conn,
        "UPDATE refresh_tokens SET used_at = %s, replaced_by = %s "
        "WHERE jti = %s AND used_at IS NULL RETURNING jti",
        (ctx.now(), new_jti, token["jti"]),
    )
    if won is None:
        ctx.conn.rollback()
        ctx.conn.execute(
            "UPDATE sessions SET revoked_at = %s, revoke_reason = 'REFRESH_REUSED' WHERE sid = %s",
            (ctx.now(), session["sid"]),
        )
        ctx.conn.commit()
        reused = ctx.event(
            "AUTH_REFRESH_REUSED",
            outcome="DENIED",
            actor=actor,
            target_type="USER",
            target_id=str(user["id"]),
        )
        raise ApiError("UNAUTHENTICATED", audits=[reused])
    ctx.audit("AUTH_REFRESHED", actor=actor, target_type="USER", target_id=str(user["id"]))
    return _token_pair(ctx, user, sid, session["expires_at"], str(new_jti), insert=False)


@endpoint(
    router, "POST", "/auth/logout", policy=ANY_USER, audit_event="AUTH_LOGOUT", status_code=204
)
def logout(ctx: Ctx = Depends(authed_ctx)) -> Response:
    ctx.conn.execute(
        "UPDATE sessions SET revoked_at = %s, revoke_reason = 'LOGOUT' WHERE sid = %s",
        (ctx.now(), uuid.UUID(ctx.me.sid)),
    )
    ctx.audit("AUTH_LOGOUT", target_type="USER", target_id=ctx.me.user_id)
    return Response(status_code=204)


@endpoint(router, "GET", "/me", policy=ANY_USER, audit_event="NONE")
def get_me(ctx: Ctx = Depends(authed_ctx)) -> dict[str, Any]:
    user = one(ctx.conn, "SELECT * FROM users WHERE id = %s", (uuid.UUID(ctx.me.user_id),))
    user = need(user)
    return user_out(ctx, user)


__all__ = ["iso", "router"]
