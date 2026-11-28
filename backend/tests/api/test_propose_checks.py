"""User changes are checked when proposed, not only when approved (TIR-91)."""

from typing import Any

import pytest

from tests.api.conftest import World
from tests.api.test_change_allowlist import Ids, pending_count
from tracex_api.db import one


def create(ids: Ids, **new: Any) -> dict[str, Any]:
    value = {
        "username": "fresh.user",
        "display_name": "Fresh User",
        "role": "SUPERVISOR",
        "district_id": ids.district,
        **new,
    }
    return {"kind": "USER_CREATE", "new_value": value}


def jurisdiction(ids: Ids, who: str = "deepak") -> dict[str, Any]:
    return {
        "kind": "USER_JURISDICTION",
        "subject_user_id": ids.users[who],
        "new_value": {"coverage": {"state_ids": [ids.state], "district_ids": []}},
    }


def assignment(ids: Ids, case_number: str, kind: str = "ASSIGNMENT_ADD") -> dict[str, Any]:
    return {
        "kind": kind,
        "subject_user_id": ids.users["bharat"],
        "new_value": {"case_number": case_number},
    }


def approve(world: World, change_id: str, who: str = "meena") -> Any:
    shown = world.api.get(who, f"/pending-changes/{change_id}").json()
    return world.api.post(
        who, f"/pending-changes/{change_id}/approve", {"change_hash": shown["change_hash"]}
    )


# Item 1: username and display name are checked at propose time.


@pytest.mark.parametrize(
    "username",
    ["Bad", "has space", "ab", "x" * 65, "semi;colon", "UPPER.case", "unié"],
)
def test_a_bad_username_is_refused_when_proposed(world: World, username: str) -> None:
    ids = Ids(world.api)
    response = world.api.post("hari", "/pending-changes", create(ids, username=username))
    assert response.status_code == 422, response.text
    assert response.json()["field_errors"][0]["field"] == "username"
    assert pending_count(world.api) == 0


@pytest.mark.parametrize("display_name", ["x" * 121, "", "   "])
def test_a_bad_display_name_is_refused_when_proposed(world: World, display_name: str) -> None:
    ids = Ids(world.api)
    response = world.api.post("hari", "/pending-changes", create(ids, display_name=display_name))
    assert response.status_code == 422, response.text
    assert response.json()["field_errors"][0]["field"] == "display_name"
    assert pending_count(world.api) == 0


@pytest.mark.parametrize("username", ["abc", "a.b_c-9", "x" * 64])
def test_the_username_limits_are_inclusive_and_the_approval_applies(
    world: World, username: str
) -> None:
    ids = Ids(world.api)
    body = create(ids, username=username, display_name="y" * 120)
    proposed = world.api.post("hari", "/pending-changes", body)
    assert proposed.status_code == 201, proposed.text
    approved = approve(world, proposed.json()["change_id"])
    assert approved.status_code == 200, approved.text
    with world.api.owner() as conn:
        assert one(conn, "SELECT 1 AS x FROM users WHERE username = %s", (username,)) is not None


# Item 2: a coverage change records the current coverage and goes stale with it.


def test_a_coverage_change_records_the_current_coverage(world: World) -> None:
    api = world.api
    ids = Ids(api)
    proposed = api.post("hari", "/pending-changes", jurisdiction(ids))
    assert proposed.status_code == 201, proposed.text
    old = proposed.json()["old_value"]
    assert old is not None and "coverage" in old
    cover = old["coverage"]
    assert set(cover) == {"all_states", "state_ids", "district_ids"}
    assert cover["state_ids"] == sorted(cover["state_ids"])
    assert cover["district_ids"] == sorted(cover["district_ids"])
    assert cover["state_ids"] or cover["district_ids"] or cover["all_states"]


def test_an_approval_is_refused_when_the_coverage_changed_since(world: World) -> None:
    api = world.api
    ids = Ids(api)
    proposed = api.post("hari", "/pending-changes", jurisdiction(ids))
    assert proposed.status_code == 201, proposed.text
    change = proposed.json()
    with api.superuser() as conn:
        conn.execute("DELETE FROM user_coverage WHERE user_id = %s", (ids.users["deepak"],))
        conn.execute(
            "INSERT INTO user_coverage (user_id, district_id) VALUES (%s, %s)",
            (ids.users["deepak"], ids.other_district),
        )
    response = approve(world, change["change_id"])
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "OLD_VALUE_CHANGED"
    with api.owner() as conn:
        row = one(conn, "SELECT state FROM pending_changes WHERE id = %s", (change["change_id"],))
    assert row is not None and row["state"] == "PENDING"


def test_an_unchanged_coverage_still_approves(world: World) -> None:
    api = world.api
    ids = Ids(api)
    proposed = api.post("hari", "/pending-changes", jurisdiction(ids))
    assert proposed.status_code == 201, proposed.text
    response = approve(world, proposed.json()["change_id"])
    assert response.status_code == 200, response.text


# Item 3: one waiting change of a kind per target.


def test_a_second_waiting_change_of_the_same_kind_is_refused(world: World) -> None:
    api = world.api
    ids = Ids(api)
    body = {"kind": "USER_DISABLE", "subject_user_id": ids.users["bharat"]}
    assert api.post("hari", "/pending-changes", body).status_code == 201
    before = pending_count(api)
    again = api.post("hari", "/pending-changes", body)
    assert again.status_code == 409, again.text
    assert again.json()["code"] == "PENDING_EXISTS"
    assert pending_count(api) == before


def test_a_second_coverage_change_for_the_same_user_is_refused(world: World) -> None:
    api = world.api
    ids = Ids(api)
    assert api.post("hari", "/pending-changes", jurisdiction(ids)).status_code == 201
    again = api.post("hari", "/pending-changes", jurisdiction(ids))
    assert again.status_code == 409, again.text
    assert again.json()["code"] == "PENDING_EXISTS"


def test_the_same_kind_for_another_user_is_accepted(world: World) -> None:
    api = world.api
    ids = Ids(api)
    first = {"kind": "USER_DISABLE", "subject_user_id": ids.users["bharat"]}
    other = {"kind": "USER_DISABLE", "subject_user_id": ids.users["charu"]}
    assert api.post("hari", "/pending-changes", first).status_code == 201
    assert api.post("hari", "/pending-changes", other).status_code == 201


def test_another_kind_for_the_same_user_is_accepted(world: World) -> None:
    api = world.api
    ids = Ids(api)
    disable = {"kind": "USER_DISABLE", "subject_user_id": ids.users["bharat"]}
    role = {
        "kind": "USER_ROLE",
        "subject_user_id": ids.users["bharat"],
        "new_value": {"role": "SUPERVISOR"},
    }
    assert api.post("hari", "/pending-changes", disable).status_code == 201
    assert api.post("hari", "/pending-changes", role).status_code == 201


def test_a_decided_change_no_longer_blocks_a_new_one(world: World) -> None:
    api = world.api
    ids = Ids(api)
    body = jurisdiction(ids)
    first = api.post("hari", "/pending-changes", body)
    assert first.status_code == 201, first.text
    denied = api.post("meena", f"/pending-changes/{first.json()['change_id']}/deny", {})
    assert denied.status_code == 200, denied.text
    assert api.post("hari", "/pending-changes", body).status_code == 201


def test_a_second_waiting_create_of_the_same_username_is_refused(world: World) -> None:
    api = world.api
    ids = Ids(api)
    assert api.post("hari", "/pending-changes", create(ids)).status_code == 201
    again = api.post("hari", "/pending-changes", create(ids, display_name="Other"))
    assert again.status_code == 409, again.text
    assert again.json()["code"] == "PENDING_EXISTS"


def test_assignment_changes_are_limited_per_case(world: World) -> None:
    api = world.api
    ids = Ids(api)
    assert api.post("hari", "/pending-changes", assignment(ids, "C-101")).status_code == 201
    same = api.post("hari", "/pending-changes", assignment(ids, "C-101"))
    assert same.status_code == 409, same.text
    assert same.json()["code"] == "PENDING_EXISTS"
    assert api.post("hari", "/pending-changes", assignment(ids, "C-102")).status_code == 201
