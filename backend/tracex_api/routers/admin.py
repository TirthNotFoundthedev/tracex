"""ADMIN routes: uploads, matching runs, totals; and the reference data every user may read."""

import hashlib
import logging
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile

from tracex_api import audit
from tracex_api.context import (
    ADMIN_HIDDEN,
    ADMIN_ONLY,
    ANY_USER,
    SENIOR_OR_ADMIN,
    AppState,
    Ctx,
    authed_ctx,
    endpoint,
    iso,
)
from tracex_api.db import Row, connect, many, need, one
from tracex_api.engine_bridge import (
    DOC_TYPES,
    current_thresholds,
    doc_type_of,
    ingest_case,
    outbox_pending,
    persist_result,
    replay_outbox,
    run_in_progress,
    validate_thresholds,
)
from tracex_api.errors import ApiError, invalid
from tracex_api.policy import ROLES, can_read_user
from tracex_api.routers.auth import user_out
from tracex_api.views import as_uuid, page_slice
from tracex_engine.matching import ThresholdsError

router = APIRouter()
logger = logging.getLogger(__name__)
MAX_FILES_PER_UPLOAD = 20
ENGINE_SCOPE_LIMIT = 10_000


# ---------------------------------------------------------------------------------------------
# uploads


def batch_out(b: Row, shown_status: str | None = None) -> dict[str, Any]:
    return {
        "batch_id": str(b["id"]),
        "file_name": b["file_name"],
        "file_sha256": b["file_sha256"],
        "byte_count": b["byte_count"],
        "document_count": b["document_count"],
        "status": shown_status or b["status"],
        "error_code": None if shown_status else b["error_code"],
        "created_at": iso(b["created_at"]),
    }


def _engine_case_id(code: int, serial: int) -> str:
    return f"C-{code}{serial:02d}"


def _process_batches(state: AppState, case_id: str, payloads: list[tuple[str, str, bytes]]) -> None:
    """After the response: read each file into documents and lines, then ingest the case."""
    with connect(state.settings.database_url) as conn:
        done = 0
        for batch_id, file_name, data in payloads:
            key = uuid.UUID(batch_id)
            conn.execute("UPDATE upload_batches SET status = 'READING' WHERE id = %s", (key,))
            conn.commit()
            code = _store_document(state, conn, case_id, key, file_name, data)
            if code is None:
                conn.execute(
                    "UPDATE upload_batches SET status = 'DONE', document_count = 1 WHERE id = %s",
                    (key,),
                )
                done += 1
            else:
                conn.execute(
                    "UPDATE upload_batches SET status = 'FAILED', error_code = %s WHERE id = %s",
                    (code, key),
                )
            conn.commit()
        if done:
            case = one(conn, "SELECT * FROM cases WHERE id = %s", (uuid.UUID(case_id),))
            case = need(case)
            try:
                ingest_case(conn, state.engine, case)
                conn.commit()
            except Exception:
                conn.rollback()
                logger.exception("case ingest failed")
                conn.execute(
                    "UPDATE upload_batches SET status = 'FAILED', error_code = 'INGEST_ERROR' "
                    "WHERE case_id = %s AND status = 'DONE'",
                    (uuid.UUID(case_id),),
                )
                conn.commit()


def _store_document(
    state: AppState, conn: Any, case_id: str, batch: uuid.UUID, file_name: str, data: bytes
) -> str | None:
    if doc_type_of(file_name) is None:
        return "UNKNOWN_FILE_NAME"
    if len(data) > state.settings.max_upload_bytes:
        return "TOO_LARGE"
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return "NOT_UTF8"
    existing = one(
        conn,
        "SELECT 1 AS x FROM documents WHERE case_id = %s AND file_name = %s",
        (uuid.UUID(case_id), file_name),
    )
    if existing:
        return "DUPLICATE_FILE"
    doc = one(
        conn,
        "INSERT INTO documents (case_id, doc_type, batch_id, file_name) VALUES (%s, %s, %s, %s) "
        "RETURNING id",
        (uuid.UUID(case_id), doc_type_of(file_name), batch, file_name),
    )
    doc = need(doc)
    for number, line in enumerate(text.splitlines(), start=1):
        conn.execute(
            "INSERT INTO document_lines (document_id, line_no, text) VALUES (%s, %s, %s)",
            (doc["id"], number, line),
        )
    return None


@endpoint(
    router, "POST", "/uploads", policy=ADMIN_ONLY, audit_event="DATA_UPLOADED", status_code=202
)
def upload_files(
    background: BackgroundTasks,
    ctx: Ctx = Depends(authed_ctx),
    case_number: str = Form(..., min_length=1, max_length=64),
    district_id: str = Form(...),
    files: list[UploadFile] = File(...),
) -> dict[str, Any]:
    district = (
        one(ctx.conn, "SELECT * FROM districts WHERE id = %s", (as_uuid(district_id),))
        if as_uuid(district_id)
        else None
    )
    if district is None:
        raise invalid("district_id", "unknown_district")
    if not files:
        raise invalid("files", "required")
    case = one(
        ctx.conn,
        "SELECT * FROM cases WHERE district_id = %s AND case_number = %s",
        (district["id"], case_number),
    )
    if case is None:
        serial = one(ctx.conn, "SELECT nextval(pg_get_serial_sequence('cases', 'serial')) AS n")
        serial = need(serial)
        n = int(serial["n"])
        case = one(
            ctx.conn,
            "INSERT INTO cases (case_number, district_id, serial, engine_case_id) "
            "VALUES (%s, %s, %s, %s) RETURNING *",
            (case_number, district["id"], n, _engine_case_id(int(district["code"]), n)),
        )
    case = need(case)
    case_id = str(case["id"])
    if len(files) > MAX_FILES_PER_UPLOAD:
        raise invalid("files", "too_many")
    limit = ctx.state.settings.max_upload_bytes
    contents = [upload.file.read(limit + 1) for upload in files]
    if any(len(data) > limit for data in contents):
        raise invalid("files", "too_large")
    payloads: list[tuple[str, str, bytes]] = []
    out = []
    for upload, data in zip(files, contents, strict=True):
        name = (upload.filename or "").rsplit("/", 1)[-1]
        batch = one(
            ctx.conn,
            "INSERT INTO upload_batches (uploaded_by, file_name, file_sha256, byte_count, status, "
            "case_id) VALUES (%s, %s, %s, %s, 'WAITING', %s) RETURNING *",
            (
                uuid.UUID(ctx.me.user_id),
                name,
                hashlib.sha256(data).hexdigest(),
                len(data),
                case["id"],
            ),
        )
        batch = need(batch)
        payloads.append((str(batch["id"]), name, data))
        out.append(batch_out(batch, shown_status="WAITING"))
        ctx.audit(
            "DATA_UPLOADED",
            refs=[case_id],
            target_type="BATCH",
            target_id=str(batch["id"]),
            detail={
                "file_sha256": batch["file_sha256"],
                "byte_count": batch["byte_count"],
                "document_count": 1,
            },
        )
    background.add_task(_process_batches, ctx.state, case_id, payloads)
    return {"batches": out}


@endpoint(router, "GET", "/uploads", policy=ADMIN_ONLY, audit_event="NONE")
def list_uploads(
    ctx: Ctx = Depends(authed_ctx),
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = Query(None),
) -> dict[str, Any]:
    rows = many(ctx.conn, "SELECT * FROM upload_batches ORDER BY created_at DESC, id")
    chunk, token = page_slice(ctx, rows, limit, cursor, {}, "uploads")
    return {"items": [batch_out(b) for b in chunk], "next_cursor": token, "total": len(rows)}


@endpoint(router, "GET", "/uploads/{batch_id}", policy=ADMIN_ONLY, audit_event="NONE")
def get_upload(batch_id: str, ctx: Ctx = Depends(authed_ctx)) -> dict[str, Any]:
    key = as_uuid(batch_id)
    row = one(ctx.conn, "SELECT * FROM upload_batches WHERE id = %s", (key,)) if key else None
    if row is None:
        raise ctx.not_found(batch_id)
    return batch_out(row)


# ---------------------------------------------------------------------------------------------
# matching runs


def run_out(ctx: Ctx, r: Row) -> dict[str, Any]:
    created = (r["counts"] or {}).get("created_by_state", {})
    return {
        "run_id": str(r["id"]),
        "status": r["status"],
        "started_at": iso(r["started_at"]),
        "finished_at": iso(r["finished_at"]),
        "triggered_by": str(r["triggered_by"]) if r["triggered_by"] else str(ctx.me.user_id),
        "ruleset_version": r["ruleset_version"],
        "thresholds_version": r["thresholds_version"],
        "oversized_block_count": r["oversized_block_count"],
        "error_code": r["error_code"],
        "input_batch_count": len(r["input_batch_ids"]),
        "auto_created": int(created.get("AUTO", 0)),
        "suggested_created": int(created.get("SUGGESTED", 0)),
    }


@endpoint(
    router,
    "POST",
    "/matching/runs",
    policy=ADMIN_ONLY,
    audit_event="MATCHING_RUN_STARTED",
    status_code=202,
)
def start_run(ctx: Ctx = Depends(authed_ctx)) -> dict[str, Any]:
    import json

    try:
        raw = json.loads(getattr(ctx.request.state, "body", b"") or b"{}")
    except ValueError:
        raise invalid("body", "malformed") from None
    batch_ids: list[str] | None = None
    if isinstance(raw, dict) and raw.get("batch_ids") is not None:
        ids = raw["batch_ids"]
        if not isinstance(ids, list) or not all(isinstance(i, str) and as_uuid(i) for i in ids):
            raise invalid("batch_ids", "invalid_uuid")
        batch_ids = ids
    if run_in_progress(ctx.conn):
        raise ApiError("RUN_IN_PROGRESS")
    if outbox_pending(ctx.conn):
        replay_outbox(ctx.state, ctx.conn)
        if outbox_pending(ctx.conn):
            raise ApiError("RUN_IN_PROGRESS")
    try:
        limits = validate_thresholds(ctx.conn)
    except ThresholdsError:
        raise invalid("thresholds", "invalid") from None
    if batch_ids is not None:
        rows = many(
            ctx.conn,
            "SELECT * FROM upload_batches WHERE id = ANY(%s)",
            ([uuid.UUID(i) for i in batch_ids],),
        )
        if len(rows) != len(set(batch_ids)):
            raise invalid("batch_ids", "unknown_batch")
    else:
        rows = many(
            ctx.conn,
            "SELECT * FROM upload_batches WHERE status = 'DONE' AND matched_run_id IS NULL",
        )
    case_ids = sorted({str(b["case_id"]) for b in rows if b["case_id"]})
    engine_ids = [
        c["engine_case_id"]
        for c in many(
            ctx.conn,
            "SELECT engine_case_id FROM cases WHERE id = ANY(%s)",
            ([uuid.UUID(c) for c in case_ids],),
        )
    ]
    run_id = str(uuid.uuid4())
    now = ctx.now()
    ctx.conn.execute(
        "INSERT INTO match_runs (id, started_at, triggered_by, input_case_ids, input_batch_ids, "
        "ruleset_version, thresholds_version, status) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, 'RUNNING')",
        (
            uuid.UUID(run_id), now, uuid.UUID(ctx.me.user_id),
            [uuid.UUID(c) for c in case_ids], [b["id"] for b in rows],
            "engine-matching/1.1", limits.version,
        ),
    )  # fmt: skip
    ctx.audit(
        "MATCHING_RUN_STARTED",
        target_type="RUN",
        target_id=run_id,
        detail={"thresholds_version": limits.version},
    )
    ctx.commit()
    try:
        result = ctx.state.engine.matcher(run_id).run_matching(
            engine_ids,
            ctx.me.user_id,
            limits.version,
            {"high_min": int(limits.high_min), "medium_min": int(limits.medium_min)},
        )
    except Exception:
        _fail_run(ctx, run_id, "ENGINE_ERROR")
        raise
    try:
        persist_result(ctx, result, run_id)
    except Exception:
        _fail_run(ctx, run_id, "PERSIST_ERROR")
        raise
    record = result.run
    created = {k: int(v) for k, v in record.created_by_state.items()}
    ctx.conn.execute(
        "UPDATE match_runs SET status = %s, finished_at = %s, counts = %s, "
        "oversized_block_count = %s, "
        "error_code = %s WHERE id = %s",
        (
            record.status.value, ctx.now(),
            _jsonb(
                {
                    "created_by_state": {
                        "AUTO": created.get("AUTO", 0),
                        "SUGGESTED": created.get("SUGGESTED", 0),
                    }
                }
            ),
            record.oversized_block, record.error_code, uuid.UUID(run_id),
        ),
    )  # fmt: skip
    if record.status.value == "SUCCEEDED":
        ctx.conn.execute(
            "UPDATE upload_batches SET matched_run_id = %s WHERE id = ANY(%s)",
            (uuid.UUID(run_id), [b["id"] for b in rows]),
        )
    ctx.audit(
        "MATCHING_RUN_COMPLETED",
        actor=audit.SYSTEM,
        target_type="RUN",
        target_id=run_id,
        outcome="SUCCESS" if record.status.value == "SUCCEEDED" else "FAILED",
        detail={
            "thresholds_version": limits.version,
            "auto_count": created.get("AUTO", 0),
            "suggested_count": created.get("SUGGESTED", 0),
        },
    )
    done = one(ctx.conn, "SELECT * FROM match_runs WHERE id = %s", (uuid.UUID(run_id),))
    done = need(done)
    return run_out(ctx, done)


def _fail_run(ctx: Ctx, run_id: str, error_code: str) -> None:
    """Close a run that threw, so it cannot stay RUNNING and block every later run."""
    ctx.conn.rollback()
    ctx.conn.execute(
        "UPDATE match_runs SET status = 'FAILED', error_code = %s, finished_at = %s WHERE id = %s",
        (error_code, ctx.now(), uuid.UUID(run_id)),
    )
    ctx.conn.commit()


def _jsonb(value: dict[str, Any]) -> Any:
    from psycopg.types.json import Jsonb

    return Jsonb(value)


@endpoint(router, "GET", "/matching/runs", policy=ADMIN_ONLY, audit_event="NONE")
def list_runs(
    ctx: Ctx = Depends(authed_ctx),
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = Query(None),
) -> dict[str, Any]:
    rows = many(ctx.conn, "SELECT * FROM match_runs ORDER BY started_at DESC, id")
    chunk, token = page_slice(ctx, rows, limit, cursor, {}, "runs")
    return {"items": [run_out(ctx, r) for r in chunk], "next_cursor": token, "total": len(rows)}


@endpoint(router, "GET", "/matching/runs/{run_id}", policy=ADMIN_ONLY, audit_event="NONE")
def get_run(run_id: str, ctx: Ctx = Depends(authed_ctx)) -> dict[str, Any]:
    key = as_uuid(run_id)
    row = one(ctx.conn, "SELECT * FROM match_runs WHERE id = %s", (key,)) if key else None
    if row is None:
        raise ctx.not_found(run_id)
    return run_out(ctx, row)


@endpoint(router, "GET", "/stats/links", policy=ADMIN_HIDDEN, audit_event="NONE")
def get_link_totals(ctx: Ctx = Depends(authed_ctx)) -> dict[str, int]:
    counts = {
        r["state"]: int(r["n"])
        for r in many(ctx.conn, "SELECT state, count(*) AS n FROM links GROUP BY state")
    }
    return {
        "waiting": counts.get("SUGGESTED", 0),
        "rejected": counts.get("REJECTED", 0),
        "undone": counts.get("UNDONE", 0),
        "auto": counts.get("AUTO", 0),
        "confirmed": counts.get("CONFIRMED", 0),
    }


# ---------------------------------------------------------------------------------------------
# reference data, users, thresholds


@endpoint(router, "GET", "/jurisdictions", policy=ANY_USER, audit_event="NONE")
def list_jurisdictions(ctx: Ctx = Depends(authed_ctx)) -> dict[str, Any]:
    states = many(ctx.conn, "SELECT * FROM states ORDER BY name")
    districts = many(ctx.conn, "SELECT * FROM districts ORDER BY name")
    return {
        "items": [
            {
                "state_id": str(s["id"]),
                "name": s["name"],
                "districts": [
                    {"district_id": str(d["id"]), "name": d["name"]}
                    for d in districts
                    if d["state_id"] == s["id"]
                ],
            }
            for s in states
        ]
    }


@endpoint(router, "GET", "/roles", policy=ANY_USER, audit_event="NONE")
def list_roles(ctx: Ctx = Depends(authed_ctx)) -> dict[str, Any]:
    scope = {"SENIOR": "COVERAGE", "ADMIN": "NONE"}
    return {
        "items": [
            {
                "role": r,
                "name_key": f"role.{r.lower()}.name",
                "description_key": f"role.{r.lower()}.description",
                "scope": scope.get(r, "DISTRICT"),
            }
            for r in ROLES
        ]
    }


def user_visible(ctx: Ctx, u: Row) -> bool:
    district = str(u["district_id"]) if u["district_id"] else None
    return can_read_user(ctx.me, u["role"], district)


@endpoint(router, "GET", "/users", policy=SENIOR_OR_ADMIN, audit_event="NONE")
def list_users(
    ctx: Ctx = Depends(authed_ctx),
    role: str | None = Query(None),
    active: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = Query(None),
) -> dict[str, Any]:
    if role is not None and role not in ROLES:
        raise invalid("role", "invalid_enum")
    rows = [
        u for u in many(ctx.conn, "SELECT * FROM users ORDER BY username") if user_visible(ctx, u)
    ]
    if role:
        rows = [u for u in rows if u["role"] == role]
    if active is not None:
        rows = [u for u in rows if u["active"] is active]
    chunk, token = page_slice(ctx, rows, limit, cursor, {"role": role, "active": active}, "users")
    return {"items": [user_out(ctx, u) for u in chunk], "next_cursor": token, "total": len(rows)}


@endpoint(router, "GET", "/users/{user_id}", policy=SENIOR_OR_ADMIN, audit_event="NONE")
def get_user(user_id: str, ctx: Ctx = Depends(authed_ctx)) -> dict[str, Any]:
    key = as_uuid(user_id)
    row = one(ctx.conn, "SELECT * FROM users WHERE id = %s", (key,)) if key else None
    if row is None or not user_visible(ctx, row):
        raise ctx.not_found(user_id, resolved=user_id if row else None)
    return user_out(ctx, row)


@endpoint(router, "GET", "/thresholds", policy=SENIOR_OR_ADMIN, audit_event="NONE")
def get_thresholds(ctx: Ctx = Depends(authed_ctx)) -> dict[str, Any]:
    row = one(ctx.conn, "SELECT * FROM threshold_versions ORDER BY thresholds_version DESC LIMIT 1")
    row = need(row)
    limits = current_thresholds(ctx.conn)
    return {
        "high_min": float(limits.high_min),
        "medium_min": float(limits.medium_min),
        "thresholds_version": limits.version,
        "effective_at": iso(row["effective_at"]),
    }


__all__ = ["DOC_TYPES", "router"]
