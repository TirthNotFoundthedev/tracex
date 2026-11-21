"""API test fixtures: a throwaway Postgres database per test and the seeded synthetic world.

The tests need a Postgres server with a superuser: set `TRACEX_TEST_PG_URL` (CI does; locally
point it at any disposable server). Without it every API test is skipped with that reason. Each
test gets its own database cloned from a migrated, seeded template, so tests never share rows.
The engine runs on its in-memory stores here; the Neo4j path is covered by the engine tests.
"""

import base64
import json
import os
import secrets
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import psycopg
import psycopg.conninfo
import pytest
from fastapi.testclient import TestClient
from psycopg import sql

from tests.engine.support import note, notes_file
from tracex_api import audit
from tracex_api.config import Settings
from tracex_api.db import Conn, bootstrap_roles, connect, many, migrate, one
from tracex_api.engine_bridge import EngineGateway
from tracex_api.main import create_app
from tracex_api.seed import load_seed, seed_jurisdictions, seed_users
from tracex_engine.matching import InMemoryLinkStore

PG_URL = os.environ.get("TRACEX_TEST_PG_URL")
MIGRATOR_PASSWORD = "ci-only-migrator-throwaway"  # noqa: S105 - test database only
API_PASSWORD = "ci-only-api-throwaway"  # noqa: S105 - test database only
SEED_DIR = Path(__file__).resolve().parents[3] / "data-kit" / "seed"
IRFAN = "Accused Irfan Khan, mobile 9100000001."
VEHICLE = "Vehicle MH12AB1234 was seen."
PHONE = "9100000001"


def password_of(username: str) -> str:
    return f"synthetic-{username}-pw"  # noqa: S105 - test users only


def _with_database(
    base: str, name: str, user: str | None = None, password: str | None = None
) -> str:
    parts = psycopg.conninfo.conninfo_to_dict(base)
    parts["dbname"] = name
    if user:
        parts["user"], parts["password"] = user, password
    return psycopg.conninfo.make_conninfo("", **parts)


def _admin(dbname: str | None = None) -> psycopg.Connection[Any]:
    assert PG_URL
    url = _with_database(PG_URL, dbname) if dbname else PG_URL
    return psycopg.connect(url, autocommit=True)


def _create_database(name: str, owner: str | None = None, template: str | None = None) -> None:
    with _admin() as conn:
        query = sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name))
        if owner:
            query += sql.SQL(" OWNER {}").format(sql.Identifier(owner))
        if template:
            query += sql.SQL(" TEMPLATE {}").format(sql.Identifier(template))
        conn.execute(query)


def _drop_database(name: str) -> None:
    with _admin() as conn:
        conn.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
        )


@pytest.fixture(scope="session")
def pg_template() -> Iterator[str]:
    if not PG_URL:
        pytest.skip("TRACEX_TEST_PG_URL is not set: no Postgres server for the API tests")
    try:
        with _admin():
            pass
    except psycopg.OperationalError as exc:
        pytest.skip(f"Postgres at TRACEX_TEST_PG_URL is not reachable: {exc}")
    bootstrap_roles(PG_URL, MIGRATOR_PASSWORD, API_PASSWORD)
    name = f"tracex_tpl_{secrets.token_hex(4)}"
    _create_database(name, owner="tracex_migrator")
    migrator_url = _with_database(PG_URL, name, "tracex_migrator", MIGRATOR_PASSWORD)
    migrate(migrator_url)
    jurisdictions, users, _ = load_seed(SEED_DIR)
    with connect(migrator_url) as conn:
        seed_jurisdictions(conn, jurisdictions)
        seed_users(conn, users, {u["username"]: password_of(u["username"]) for u in users})
        audit.append(
            conn,
            audit.AuditEvent("AUDIT_CHAIN_STARTED", audit.SYSTEM, detail={"schema_version": 1}),
        )
        conn.commit()
    yield name
    _drop_database(name)


class FakeClock:
    """The API's injected clock; tests move it to cross expiry boundaries (A27)."""

    def __init__(self) -> None:
        self.at = datetime.now(UTC)

    def __call__(self) -> datetime:
        return self.at

    def advance(self, **kwargs: float) -> None:
        self.at += timedelta(**kwargs)


def _key() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()


@dataclass
class Api:
    client: TestClient
    settings: Settings
    clock: FakeClock
    engine: EngineGateway
    dbname: str
    migrator_url: str
    admin_url: str
    tokens: dict[str, dict[str, str]] = field(default_factory=dict)

    def login(self, username: str) -> dict[str, str]:
        response = self.client.post(
            "/auth/login", json={"username": username, "password": password_of(username)}
        )
        assert response.status_code == 200, response.text
        self.tokens[username] = response.json()
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    def h(self, username: str) -> dict[str, str]:
        if username not in self.tokens:
            return self.login(username)
        return {"Authorization": f"Bearer {self.tokens[username]['access_token']}"}

    def get(self, username: str, path: str, **params: Any) -> Any:
        return self.client.get(path, headers=self.h(username), params=params)

    def post(self, username: str, path: str, body: Any = None) -> Any:
        return self.client.post(path, headers=self.h(username), json=body)

    def owner(self) -> Conn:
        """A connection as the table owner, for setup and tamper tests only."""
        return connect(self.migrator_url)

    def superuser(self) -> psycopg.Connection[Any]:
        return _admin(self.dbname)

    def api_role(self) -> Conn:
        return connect(self.settings.database_url)

    def audit_rows(self, event_type: str | None = None) -> list[dict[str, Any]]:
        with self.owner() as conn:
            if event_type:
                rows = many(
                    conn,
                    "SELECT * FROM audit_log WHERE event_type = %s ORDER BY seq",
                    (event_type,),
                )
            else:
                rows = many(conn, "SELECT * FROM audit_log ORDER BY seq")
        return rows


@pytest.fixture
def api(pg_template: str, tmp_path: Path) -> Iterator[Api]:
    assert PG_URL
    name = f"tracex_t_{secrets.token_hex(4)}"
    _create_database(name, owner="tracex_migrator", template=pg_template)
    settings = Settings(
        database_url=_with_database(PG_URL, name, "tracex_api", API_PASSWORD),
        database_admin_url=None,
        jwt_key=base64.urlsafe_b64decode(_key()),
        cursor_key=base64.urlsafe_b64decode(_key()),
        row_ref_key=base64.urlsafe_b64decode(_key()),
        hmac_key=base64.urlsafe_b64decode(_key()),
        audit_anchor_path=tmp_path / "anchor.log",
        neo4j_uri=None,
        neo4j_user="",
        neo4j_password="",
    )
    clock = FakeClock()
    engine = EngineGateway.in_memory()
    app = create_app(settings, engine, clock)
    client = TestClient(app, raise_server_exceptions=False)
    yield Api(
        client,
        settings,
        clock,
        engine,
        name,
        _with_database(PG_URL, name, "tracex_migrator", MIGRATOR_PASSWORD),
        _with_database(PG_URL, name),
    )
    client.close()
    _drop_database(name)


def upload_case(
    api: Api, case_number: str, district: str, files: dict[str, str]
) -> list[dict[str, Any]]:
    districts = {
        d["name"]: d["district_id"]
        for s in api.get("hari", "/jurisdictions").json()["items"]
        for d in s["districts"]
    }
    response = api.client.post(
        "/uploads",
        headers=api.h("hari"),
        data={"case_number": case_number, "district_id": districts[district]},
        files=[("files", (name, text.encode(), "text/plain")) for name, text in files.items()],
    )
    assert response.status_code == 202, response.text
    batches: list[dict[str, Any]] = response.json()["batches"]
    return batches


def case_notes(case_number: str, *lines: str) -> dict[str, str]:
    pins = {3 + i: note(line) for i, line in enumerate(lines)}
    return {"notes.txt": notes_file(case_number, pins, last=2 + len(lines))}


@dataclass
class World:
    """The seeded scenario of api-access-control.md section 7, built through the API."""

    api: Api
    cases: dict[str, str]
    entities: dict[str, str]
    links: dict[str, str]


ASSIGNMENTS = [
    ("asha", "C-101"),
    ("bharat", "C-101"),
    ("bharat", "C-102"),
    ("esha", "C-201"),
    ("jatin", "C-201"),
    ("gita", "C-301"),
    ("kiran", "C-301"),
]


@pytest.fixture
def world(api: Api) -> World:
    """Cases C-101, C-102 (Rivergate), C-201 (Hillcrest), C-301 (Lakeside) uploaded by hari and
    matched. E-1 is the phone in C-101, E-2 the same phone in C-201, E-3 in C-102, E-4 the vehicle
    in C-101, E-5 the vehicle in C-301. L-1 joins E-1 and E-2, L-2 E-1 and E-3, L-3 E-4 and E-5
    (confirmed by meena). The person links between the Irfan entities are SUGGESTED."""
    upload_case(api, "C-101", "Rivergate", case_notes("C-101", IRFAN, VEHICLE))
    upload_case(api, "C-102", "Rivergate", case_notes("C-102", IRFAN))
    upload_case(api, "C-201", "Hillcrest", case_notes("C-201", IRFAN))
    upload_case(api, "C-301", "Lakeside", case_notes("C-301", VEHICLE))
    with api.owner() as conn:
        from tracex_api.seed import assign_cases

        assign_cases(conn, ASSIGNMENTS)
        conn.commit()
    response = api.post("hari", "/matching/runs", {})
    assert response.status_code == 202, response.text
    world = snapshot(api)
    confirm = api.post("meena", f"/links/{world.links['L-3']}/confirm", {})
    assert confirm.status_code == 200, confirm.text
    return world


def snapshot(api: Api) -> World:
    with api.owner() as conn:
        cases = {
            r["case_number"]: str(r["id"]) for r in many(conn, "SELECT id, case_number FROM cases")
        }
        by_case = {
            (r["case_number"], r["type"]): str(r["id"])
            for r in many(
                conn,
                "SELECT e.id, e.type, c.case_number FROM entities e "
                "JOIN cases c ON c.id = e.case_id",
            )
        }
        entities = {
            "E-1": by_case[("C-101", "PHONE")],
            "E-2": by_case[("C-201", "PHONE")],
            "E-3": by_case[("C-102", "PHONE")],
            "E-4": by_case[("C-101", "VEHICLE")],
            "E-5": by_case[("C-301", "VEHICLE")],
        }
        links: dict[str, str] = {}
        for name, a, b in (("L-1", "E-1", "E-2"), ("L-2", "E-1", "E-3"), ("L-3", "E-4", "E-5")):
            row = one(
                conn,
                "SELECT link_id FROM links WHERE (entity_a_id = %s AND entity_b_id = %s) "
                "OR (entity_a_id = %s AND entity_b_id = %s)",
                (entities[a], entities[b], entities[b], entities[a]),
            )
            assert row is not None, name
            links[name] = str(row["link_id"])
        persons = many(
            conn,
            "SELECT link_id FROM links WHERE entity_type = 'PERSON' ORDER BY link_id",
        )
        for i, p in enumerate(persons):
            links[f"P-{i + 1}"] = str(p["link_id"])
    return World(api, cases, entities, links)


def new_uuid() -> str:
    return str(uuid.uuid4())


def dump(response: Any) -> str:
    return json.dumps(response.json(), sort_keys=True)


Factory = Callable[..., Any]

__all__ = ["InMemoryLinkStore", "dump"]
