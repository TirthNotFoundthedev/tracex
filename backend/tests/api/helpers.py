"""Small helpers shared by the API tests."""

import json
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from starlette.requests import Request

from tests.api.conftest import Api, World
from tracex_api.context import AppState, Ctx
from tracex_api.db import Conn, many, one

SEQ_KEYS = re.compile(r"seq|range_")


def person_link(world: World, case_a: str, case_b: str) -> str:
    """The PERSON link between the Irfan entities of two cases."""
    with world.api.owner() as conn:
        row = one(
            conn,
            "SELECT link_id FROM links WHERE entity_type = 'PERSON' "
            "AND case_a_id = ANY(%s) AND case_b_id = ANY(%s)",
            ([world.cases[case_a], world.cases[case_b]],) * 2,
        )
    assert row is not None
    return str(row["link_id"])


def link_state(api: Api, link_id: str) -> str:
    with api.owner() as conn:
        row = one(conn, "SELECT state FROM links WHERE link_id = %s", (link_id,))
    assert row is not None
    return str(row["state"])


def history_count(api: Api, link_id: str) -> int:
    with api.owner() as conn:
        row = one(conn, "SELECT count(*) AS n FROM link_history WHERE link_id = %s", (link_id,))
    assert row is not None
    return int(row["n"])


def audit_count(api: Api, event_type: str) -> int:
    return len(api.audit_rows(event_type))


def ctx_for(api: Api, conn: Conn) -> Ctx:
    """A request-less context for calling the engine bridge the way a route does."""
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [],
            "client": None,
            "query_string": b"",
        }
    )
    state: AppState = api.client.app.state.tracex  # type: ignore[attr-defined]
    return Ctx(request, state, conn)


def keys_of(value: Any) -> set[str]:
    """Every dict key anywhere in a JSON-like value."""
    found: set[str] = set()
    if isinstance(value, dict):
        for k, v in value.items():
            found.add(k)
            found |= keys_of(v)
    elif isinstance(value, list):
        for item in value:
            found |= keys_of(item)
    return found


def body_text(response: Any) -> str:
    return json.dumps(response.json(), sort_keys=True)


def random_uuid() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.now(UTC)


def rows(api: Api, query: str, *params: Any) -> list[dict[str, Any]]:
    with api.owner() as conn:
        return many(conn, query, params)
