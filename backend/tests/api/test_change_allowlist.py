"""Pending changes keep only allow-listed keys, so the approver sees what is applied (D35, D51)."""

from typing import Any

import pytest

from tests.api.conftest import Api, World
from tracex_api.db import many, one


class Ids:
    def __init__(self, api: Api) -> None:
        with api.owner() as conn:
            self.users = {
                r["username"]: str(r["id"]) for r in many(conn, "SELECT id, username FROM users")
            }
            districts = many(conn, "SELECT id, state_id FROM districts ORDER BY id")
        self.district = str(districts[0]["id"])
        self.other_district = str(districts[1]["id"])
        self.state = str(districts[0]["state_id"])


def proposals(ids: Ids) -> dict[str, dict[str, Any]]:
    """One valid proposal per change type (keys: the type, plus a variant where one is needed)."""
    return {
        "USER_CREATE/district": {
            "kind": "USER_CREATE",
            "new_value": {
                "username": "new.sup",
                "display_name": "New Sup",
                "role": "SUPERVISOR",
                "district_id": ids.district,
            },
        },
        "USER_CREATE/senior": {
            "kind": "USER_CREATE",
            "new_value": {
                "username": "new.sen",
                "display_name": "New Sen",
                "role": "SENIOR",
                "coverage": {"state_ids": [ids.state], "district_ids": []},
            },
        },
        "USER_ENABLE": {"kind": "USER_ENABLE", "subject_user_id": ids.users["bharat"]},
        "USER_DISABLE": {"kind": "USER_DISABLE", "subject_user_id": ids.users["bharat"]},
        "USER_ROLE": {
            "kind": "USER_ROLE",
            "subject_user_id": ids.users["bharat"],
            "new_value": {"role": "SUPERVISOR"},
        },
        "USER_JURISDICTION/district": {
            "kind": "USER_JURISDICTION",
            "subject_user_id": ids.users["bharat"],
            "new_value": {"district_id": ids.other_district},
        },
        "USER_JURISDICTION/senior": {
            "kind": "USER_JURISDICTION",
            "subject_user_id": ids.users["deepak"],
            "new_value": {"coverage": {"state_ids": [ids.state], "district_ids": []}},
        },
        "ASSIGNMENT_ADD": {
            "kind": "ASSIGNMENT_ADD",
            "subject_user_id": ids.users["bharat"],
            "new_value": {"case_number": "C-101"},
        },
        "ASSIGNMENT_REMOVE": {
            "kind": "ASSIGNMENT_REMOVE",
            "subject_user_id": ids.users["bharat"],
            "new_value": {"case_number": "C-101"},
        },
        "THRESHOLDS": {"kind": "THRESHOLDS", "new_value": {"high_min": 85, "medium_min": 60}},
    }


NAMES = [
    "USER_CREATE/district",
    "USER_CREATE/senior",
    "USER_ENABLE",
    "USER_DISABLE",
    "USER_ROLE",
    "USER_JURISDICTION/district",
    "USER_JURISDICTION/senior",
    "ASSIGNMENT_ADD",
    "ASSIGNMENT_REMOVE",
    "THRESHOLDS",
]
HIDDEN = {
    "coverage_rows": [{"all_states": True}],
    "case_id": "00000000-0000-0000-0000-000000000001",
}


def pending_count(api: Api) -> int:
    with api.owner() as conn:
        row = one(conn, "SELECT count(*) AS n FROM pending_changes")
    assert row is not None
    return int(row["n"])


def coverage_rows_of(api: Api, username: str) -> list[Any]:
    with api.owner() as conn:
        return many(
            conn,
            "SELECT c.* FROM user_coverage c JOIN users u ON u.id = c.user_id "
            "WHERE u.username = %s",
            (username,),
        )


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("extra", ["coverage_rows", "case_id", "role_override"])
def test_an_unknown_key_in_new_value_is_a_422_and_nothing_is_stored(
    world: World, name: str, extra: str
) -> None:
    api = world.api
    body = proposals(Ids(api))[name]
    body = {**body, "new_value": {**body.get("new_value", {}), extra: HIDDEN.get(extra, "x")}}
    before = pending_count(api)
    response = api.post("hari", "/pending-changes", body)
    assert response.status_code == 422, (name, extra, response.text)
    # Enable and disable take no new_value at all, so the object itself is refused.
    field = "new_value" if name in ("USER_ENABLE", "USER_DISABLE") else extra
    assert response.json()["field_errors"] == [{"field": field, "code": "unknown_field"}]
    assert pending_count(api) == before


@pytest.mark.parametrize("name", NAMES)
def test_an_unknown_top_level_key_is_a_422_and_nothing_is_stored(world: World, name: str) -> None:
    api = world.api
    body = {**proposals(Ids(api))[name], "case_id": HIDDEN["case_id"]}
    before = pending_count(api)
    response = api.post("hari", "/pending-changes", body)
    assert response.status_code == 422, (name, response.text)
    assert response.json()["field_errors"] == [{"field": "case_id", "code": "unknown_field"}]
    assert pending_count(api) == before


@pytest.mark.parametrize("name", NAMES)
def test_a_clean_proposal_is_stored_with_only_allowed_keys(world: World, name: str) -> None:
    api = world.api
    ids = Ids(api)
    if name == "USER_ENABLE":
        with api.owner() as conn:
            conn.execute("UPDATE users SET active = false WHERE username = 'bharat'")
    response = api.post("hari", "/pending-changes", proposals(ids)[name])
    assert response.status_code == 201, (name, response.text)
    kind = name.split("/")[0]
    allowed = {
        "USER_CREATE": {"username", "display_name", "role", "district_id", "coverage"},
        "USER_ROLE": {"role"},
        "USER_JURISDICTION": {"district_id", "coverage"},
        "ASSIGNMENT_ADD": {"case_number"},
        "ASSIGNMENT_REMOVE": {"case_number"},
        "THRESHOLDS": {"high_min", "medium_min"},
    }.get(kind, set())
    assert set(response.json()["new_value"]) <= allowed
    with api.owner() as conn:
        stored = one(conn, "SELECT new_value FROM pending_changes")
    assert stored is not None
    assert set(stored["new_value"]) <= allowed | {"coverage_rows", "case_id"}


def test_dutta_probe_hidden_coverage_on_create_is_refused(world: World) -> None:
    api = world.api
    ids = Ids(api)
    body = {
        "kind": "USER_CREATE",
        "new_value": {
            "username": "plant.one",
            "display_name": "Plant One",
            "role": "SUPERVISOR",
            "district_id": ids.district,
            "coverage_rows": [{"all_states": True}],
        },
    }
    assert api.post("hari", "/pending-changes", body).status_code == 422
    assert pending_count(api) == 0


def test_dutta_probe_hidden_coverage_on_jurisdiction_change_is_refused(world: World) -> None:
    api = world.api
    ids = Ids(api)
    body = {
        "kind": "USER_JURISDICTION",
        "subject_user_id": ids.users["bharat"],
        "new_value": {"district_id": ids.other_district, "coverage_rows": [{"all_states": True}]},
    }
    assert api.post("hari", "/pending-changes", body).status_code == 422
    assert pending_count(api) == 0
    assert coverage_rows_of(api, "bharat") == []


def test_coverage_with_an_unknown_key_is_a_422(world: World) -> None:
    api = world.api
    ids = Ids(api)
    body = proposals(ids)["USER_JURISDICTION/senior"]
    body["new_value"]["coverage"]["all_states_hidden"] = True
    response = api.post("hari", "/pending-changes", body)
    assert response.status_code == 422
    assert "all_states_hidden" in response.text


def test_a_district_role_change_cannot_carry_coverage_or_a_senior_a_district(
    world: World,
) -> None:
    api = world.api
    ids = Ids(api)
    district_change = proposals(ids)["USER_JURISDICTION/district"]
    district_change["new_value"]["coverage"] = {"all_states": True}
    assert api.post("hari", "/pending-changes", district_change).status_code == 422
    senior_change = proposals(ids)["USER_JURISDICTION/senior"]
    senior_change["new_value"]["district_id"] = ids.district
    assert api.post("hari", "/pending-changes", senior_change).status_code == 422
    assert pending_count(api) == 0


def test_the_approver_sees_what_is_applied_for_a_new_senior(world: World) -> None:
    api = world.api
    ids = Ids(api)
    created = api.post("hari", "/pending-changes", proposals(ids)["USER_CREATE/senior"])
    assert created.status_code == 201, created.text
    change = created.json()
    shown = api.get("meena", f"/pending-changes/{change['change_id']}").json()
    assert shown["new_value"] == change["new_value"]
    assert shown["new_value"]["coverage"] == {"state_ids": [ids.state], "district_ids": []}
    approved = api.post(
        "meena",
        f"/pending-changes/{change['change_id']}/approve",
        {"change_hash": shown["change_hash"]},
    )
    assert approved.status_code == 200, approved.text
    rows = coverage_rows_of(api, "new.sen")
    assert [(str(r["state_id"]), r["district_id"], r["all_states"]) for r in rows] == [
        (ids.state, None, False)
    ]


def test_an_approved_district_change_leaves_no_coverage_row(world: World) -> None:
    api = world.api
    ids = Ids(api)
    created = api.post("hari", "/pending-changes", proposals(ids)["USER_JURISDICTION/district"])
    assert created.status_code == 201, created.text
    change = created.json()
    assert change["new_value"] == {"district_id": ids.other_district}
    approved = api.post(
        "meena",
        f"/pending-changes/{change['change_id']}/approve",
        {"change_hash": change["change_hash"]},
    )
    assert approved.status_code == 200, approved.text
    assert coverage_rows_of(api, "bharat") == []
    with api.owner() as conn:
        row = one(conn, "SELECT district_id FROM users WHERE username = 'bharat'")
    assert row is not None and str(row["district_id"]) == ids.other_district
