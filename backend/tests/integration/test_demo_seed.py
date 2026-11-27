"""The demo seed against a real Postgres and the real API app (in-process, in-memory engine)."""

from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest

from tests.api.conftest import Api, _drop_database, _make_api, password_of
from tracex_api.engine_bridge import EngineGateway
from tracex_api.seed_demo import SeedError, seed_demo

SEED_DIR = Path(__file__).resolve().parents[3] / "data-kit" / "seed"
USERS = ("hari", "meena", "asha", "deepak")
ENV = {"TRACEX_ENV": "development", "TRACEX_ALLOW_DEV_SECRETS": "1"} | {
    f"TRACEX_SEED_PASSWORD_{u.upper()}": password_of(u) for u in USERS
}
COUNTS = (
    "SELECT (SELECT count(*) FROM cases) AS cases, (SELECT count(*) FROM users) AS users, "
    "(SELECT count(*) FROM case_assignments) AS assigned, "
    "(SELECT count(*) FROM match_runs) AS runs, (SELECT count(*) FROM upload_batches) AS batches"
)


class ClientHttp:
    """The seed's `Http` over the FastAPI test client."""

    def __init__(self, api: Api) -> None:
        self.api = api

    def request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        body: Any = None,
        form: Mapping[str, str] | None = None,
        files: list[tuple[str, bytes]] | None = None,
    ) -> tuple[int, Any]:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        if files is not None:
            response = self.api.client.request(
                method,
                path,
                headers=headers,
                data=dict(form or {}),
                files=[("files", (n, d, "text/plain")) for n, d in files],
            )
        else:
            response = self.api.client.request(method, path, headers=headers, json=body)
        return response.status_code, (response.json() if response.content else None)


def seed(api: Api, dataset: Path, env: Mapping[str, str] = ENV) -> tuple[str, list[str]]:
    lines: list[str] = []
    result = seed_demo(ClientHttp(api), env, dataset, SEED_DIR, lines.append)
    return result, lines


@pytest.fixture(scope="module")
def seeded(
    pg_template: str, small_dataset: Path, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[Api]:
    """One seeded world for the read-only checks: the seed takes minutes on the engine."""
    made = _make_api(pg_template, tmp_path_factory.mktemp("seeded"), EngineGateway.in_memory())
    result, _ = seed(made, small_dataset)
    assert result.startswith("seeded")
    yield made
    made.client.close()
    _drop_database(made.dbname)


def test_seed_gives_officers_cases_restricted_links_and_a_queue(seeded: Api) -> None:
    api = seeded
    mine = api.get("asha", "/cases").json()
    assigned = {c["case_number"] for c in mine["items"] if c["is_assigned"]}
    assert "C-101" in assigned

    # C-101 is linked to cases in another police area: shown as stubs, never as case data.
    links = api.get("asha", "/links").json()
    assert links["stubs"], "asha should see at least one restricted link"
    for stub in links["stubs"]:
        assert "case_number" not in stub
        assert "explanation" not in stub

    queue = api.get("meena", "/review-queue", limit=100).json()
    assert queue["total"] > 0
    shown = api.get("meena", "/links", limit=100).json()["items"]
    assert {"AUTO", "SUGGESTED"} <= {item["state"] for item in shown}
    assert {"HIGH", "MEDIUM"} <= {item["band"] for item in shown}


def test_seed_is_idempotent(seeded: Api, small_dataset: Path) -> None:
    api = seeded
    with api.owner() as conn:
        before = conn.execute(COUNTS).fetchone()
    result, lines = seed(api, small_dataset)
    assert result == "already seeded"
    assert lines == ["already seeded"]
    with api.owner() as conn:
        after = conn.execute(COUNTS).fetchone()
    assert before == after


def test_seed_writes_audit_rows_through_the_api(seeded: Api) -> None:
    api = seeded
    uploaded = api.audit_rows("DATA_UPLOADED")
    assert uploaded
    assert {r["actor_kind"] for r in uploaded} == {"USER"}
    assert api.audit_rows("MATCHING_RUN_STARTED")
    assert api.audit_rows("CHANGE_APPROVED")
    chain = api.post("meena", "/audit/verify")
    assert chain.status_code == 200


def test_seed_refuses_an_environment_off_the_allow_list(api: Api, small_dataset: Path) -> None:
    with pytest.raises(SeedError, match="TRACEX_ENV"):
        seed(api, small_dataset, ENV | {"TRACEX_ENV": "production"})
    assert api.get("hari", "/uploads").json()["total"] == 0
