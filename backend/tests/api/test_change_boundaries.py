"""Pending changes: strict coverage types, the SENIOR role boundary, canonical ids (PR #60)."""

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest

from tests.api.conftest import World
from tests.api.test_change_allowlist import Ids, coverage_rows_of, pending_count
from tracex_api.db import one

FIELD = "coverage"


def create_senior(ids: Ids, coverage: Any) -> dict[str, Any]:
    return {
        "kind": "USER_CREATE",
        "new_value": {
            "username": "strict.sen",
            "display_name": "Strict Sen",
            "role": "SENIOR",
            "coverage": coverage,
        },
    }


def jurisdiction_senior(ids: Ids, coverage: Any) -> dict[str, Any]:
    return {
        "kind": "USER_JURISDICTION",
        "subject_user_id": ids.users["deepak"],
        "new_value": {"coverage": coverage},
    }


def role_change(ids: Ids, who: str, role: str, **extra: Any) -> dict[str, Any]:
    return {
        "kind": "USER_ROLE",
        "subject_user_id": ids.users[who],
        "new_value": {"role": role, **extra},
    }


def bad_coverages(ids: Ids) -> list[Any]:
    some = "00000000-0000-0000-0000-00000000000a"
    return [
        {"all_states": "false", "state_ids": [], "district_ids": []},
        {"all_states": 1, "state_ids": [], "district_ids": []},
        {"all_states": "true"},
        {"all_states": None, "state_ids": [ids.state], "district_ids": []},
        {"state_ids": ids.state, "district_ids": []},
        {"state_ids": [ids.state, ids.state], "district_ids": []},
        {"state_ids": [], "district_ids": [ids.district, ids.district]},
        {"state_ids": [ids.state.upper(), ids.state], "district_ids": []},
        {"state_ids": [1], "district_ids": []},
        {"state_ids": [None], "district_ids": []},
        {"state_ids": ["not-a-uuid"], "district_ids": []},
        {"state_ids": [], "district_ids": {"x": ids.district}},
        {"state_ids": [], "district_ids": [[ids.district]]},
        {"state_ids": None, "district_ids": []},
        {"state_ids": [], "district_ids": None},
        {"state_ids": [some], "district_ids": []},
    ]


@pytest.mark.parametrize("build", [create_senior, jurisdiction_senior])
def test_coverage_types_are_strict(world: World, build: Any) -> None:
    api = world.api
    ids = Ids(api)
    for coverage in bad_coverages(ids):
        response = api.post("hari", "/pending-changes", build(ids, coverage))
        assert response.status_code == 422, (coverage, response.text)
    assert pending_count(api) == 0


def test_a_real_boolean_all_states_is_still_accepted(world: World) -> None:
    api = world.api
    ids = Ids(api)
    ok = {"all_states": True, "state_ids": [], "district_ids": []}
    response = api.post("hari", "/pending-changes", create_senior(ids, ok))
    assert response.status_code == 201, response.text
    assert response.json()["new_value"]["coverage"]["all_states"] is True
    off = {"all_states": False, "state_ids": [ids.state], "district_ids": []}
    response = api.post("hari", "/pending-changes", jurisdiction_senior(ids, off))
    assert response.status_code == 201, response.text


def approve(world: World, change: dict[str, Any], who: str = "meena") -> Any:
    shown = world.api.get(who, f"/pending-changes/{change['change_id']}").json()
    assert shown["new_value"] == change["new_value"]
    return world.api.post(
        who,
        f"/pending-changes/{change['change_id']}/approve",
        {"change_hash": shown["change_hash"]},
    )


def test_a_role_change_to_senior_needs_coverage(world: World) -> None:
    api = world.api
    ids = Ids(api)
    extras: list[dict[str, Any]] = [
        {},
        {"district_id": ids.district},
        {"coverage": "x"},
        {"coverage": []},
    ]
    for extra in extras:
        body = role_change(ids, "charu", "SENIOR", **extra)
        assert api.post("hari", "/pending-changes", body).status_code == 422, extra
    assert pending_count(api) == 0


def test_a_role_change_to_senior_applies_the_coverage_the_approver_saw(world: World) -> None:
    api = world.api
    ids = Ids(api)
    coverage = {"state_ids": [ids.state], "district_ids": []}
    proposed = api.post(
        "hari", "/pending-changes", role_change(ids, "charu", "SENIOR", coverage=coverage)
    )
    assert proposed.status_code == 201, proposed.text
    change = proposed.json()
    assert change["new_value"]["coverage"] == coverage
    assert "coverage_rows" not in change["new_value"]
    approved = approve(world, change)
    assert approved.status_code == 200, approved.text
    with api.owner() as conn:
        user = one(conn, "SELECT role, district_id FROM users WHERE username = 'charu'")
    assert user is not None and user["role"] == "SENIOR" and user["district_id"] is None
    rows = coverage_rows_of(api, "charu")
    assert [(str(r["state_id"]), r["district_id"], r["all_states"]) for r in rows] == [
        (ids.state, None, False)
    ]


def test_a_role_change_from_senior_needs_a_district(world: World) -> None:
    api = world.api
    ids = Ids(api)
    extras: list[dict[str, Any]] = [
        {},
        {"coverage": {"all_states": True}},
        {"district_id": "nope"},
    ]
    for extra in extras:
        body = role_change(ids, "deepak", "SUPERVISOR", **extra)
        assert api.post("hari", "/pending-changes", body).status_code == 422, extra
    assert pending_count(api) == 0
    proposed = api.post(
        "hari",
        "/pending-changes",
        role_change(ids, "deepak", "SUPERVISOR", district_id=ids.district.upper()),
    )
    assert proposed.status_code == 201, proposed.text
    change = proposed.json()
    assert change["new_value"] == {"role": "SUPERVISOR", "district_id": ids.district}
    approved = approve(world, change)
    assert approved.status_code == 200, approved.text
    with api.owner() as conn:
        user = one(conn, "SELECT role, district_id FROM users WHERE username = 'deepak'")
    assert user is not None and user["role"] == "SUPERVISOR"
    assert str(user["district_id"]) == ids.district
    assert coverage_rows_of(api, "deepak") == []


def test_the_boundary_keys_are_refused_inside_one_side(world: World) -> None:
    api = world.api
    ids = Ids(api)
    cover = {"all_states": True, "state_ids": [], "district_ids": []}
    for who, role in (("bharat", "SUPERVISOR"), ("charu", "INVESTIGATOR")):
        extras: list[dict[str, Any]] = [{"coverage": cover}, {"district_id": ids.other_district}]
        for extra in extras:
            body = role_change(ids, who, role, **extra)
            assert api.post("hari", "/pending-changes", body).status_code == 422, (who, extra)
    assert pending_count(api) == 0


def test_a_district_user_made_admin_loses_the_district(world: World) -> None:
    api = world.api
    ids = Ids(api)
    proposed = api.post("hari", "/pending-changes", role_change(ids, "bharat", "ADMIN"))
    assert proposed.status_code == 201, proposed.text
    approved = approve(world, proposed.json())
    assert approved.status_code == 200, approved.text
    with api.owner() as conn:
        user = one(conn, "SELECT role, district_id FROM users WHERE username = 'bharat'")
    assert user is not None and user["role"] == "ADMIN" and user["district_id"] is None


def test_a_failing_apply_does_not_block_the_next_request(world: World) -> None:
    """An approval that cannot apply answers at once and leaves no lock behind."""
    api = world.api
    ids = Ids(api)
    with api.owner() as conn:
        conn.execute(
            "INSERT INTO pending_changes (kind, subject_user_id, old_value, new_value, proposer_id,"
            " change_hash, state, proposed_at, subject_district_ids, needs_all_states) "
            'SELECT \'USER_ROLE\', u.id, \'{"role": "SUPERVISOR"}\', \'{"role": "BOGUS"}\', '
            "p.id, decode(repeat('ab', 32), 'hex'), 'PENDING', now(), '{}', true "
            "FROM users u, users p WHERE u.username = 'charu' AND p.username = 'hari'"
        )
        pid = str(one(conn, "SELECT id FROM pending_changes")["id"])  # type: ignore[index]
    response = api.post("meena", f"/pending-changes/{pid}/approve", {"change_hash": "ab" * 32})
    assert response.status_code == 500
    assert api.get("meena", "/pending-changes").status_code == 200
    assert (
        api.post("hari", "/pending-changes", role_change(ids, "bharat", "ADMIN")).status_code == 201
    )
    assert api.get("meena", "/pending-changes", state="PENDING").status_code == 200


def test_user_create_stores_the_district_id_in_canonical_form(world: World) -> None:
    api = world.api
    ids = Ids(api)
    body = {
        "kind": "USER_CREATE",
        "new_value": {
            "username": "canon.sup",
            "display_name": "Canon Sup",
            "role": "SUPERVISOR",
            "district_id": "{" + ids.district.upper() + "}",
        },
    }
    response = api.post("hari", "/pending-changes", body)
    assert response.status_code == 201, response.text
    assert response.json()["new_value"]["district_id"] == ids.district
    with api.owner() as conn:
        stored = one(conn, "SELECT new_value FROM pending_changes")
    assert stored is not None and stored["new_value"]["district_id"] == ids.district


def test_a_decision_never_waits_long_on_a_held_lock(world: World) -> None:
    """A request gives up on a row lock after a bounded wait instead of blocking for good."""
    api = world.api
    ids = Ids(api)
    proposed = api.post("hari", "/pending-changes", role_change(ids, "bharat", "ADMIN"))
    assert proposed.status_code == 201, proposed.text
    change = proposed.json()
    shown = api.get("meena", f"/pending-changes/{change['change_id']}").json()
    body = {"change_hash": shown["change_hash"]}
    path = f"/pending-changes/{change['change_id']}/approve"
    holder = api.owner()
    pool = ThreadPoolExecutor(1)
    try:
        holder.execute(
            "SELECT 1 FROM pending_changes WHERE id = %s FOR UPDATE", (change["change_id"],)
        )
        started = time.monotonic()
        blocked = pool.submit(api.post, "meena", path, body)
        response = blocked.result(timeout=30)
        waited = time.monotonic() - started
    finally:
        holder.rollback()
        holder.close()
        pool.shutdown(wait=True)
    assert response.status_code == 500, response.text
    assert waited < 15, waited
    retried = api.post("meena", path, body)
    assert retried.status_code == 200, retried.text
