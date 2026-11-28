"""Audit event groups and the case number on refs (TIR-92)."""

import json
import uuid
from typing import Any

import pytest

from tests.api.conftest import World
from tests.api.test_audit_read import gita_activity, read_all

GROUPS = {
    "VIEWED": {
        "CASE_LISTED",
        "CASE_ENTITIES_VIEWED",
        "ENTITY_VIEWED",
        "LINK_VIEWED",
        "STUB_VIEWED",
        "GRAPH_VIEWED",
        "REVIEW_QUEUE_VIEWED",
        "EXPLANATION_VIEWED",
        "SOURCE_LINES_VIEWED",
        "SEARCH_RUN",
        "LINKS_LISTED",
        "ACCESS_REQUEST_VIEWED",
        "GRANT_VIEWED",
        "CHANGE_VIEWED",
        "AUDIT_VIEWED",
    },
    "CONFIRMED": {"LINK_CONFIRMED"},
    "REJECTED": {"LINK_REJECTED"},
    "REQUESTED": {"ACCESS_REQUEST_CREATED"},
    "APPROVED": {"ACCESS_REQUEST_APPROVED"},
    "UPLOADED": {"DATA_UPLOADED"},
}


def activity(world: World) -> None:
    api = world.api
    api.get("bharat", f"/entities/{world.entities['E-1']}")
    api.get("bharat", f"/links/{world.links['L-1']}")
    api.get("bharat", "/cases")
    api.get("hari", "/pending-changes")


@pytest.mark.parametrize("group", sorted(GROUPS))
def test_a_group_returns_only_its_events(world: World, group: str) -> None:
    activity(world)
    full = read_all(world.api, "deepak")
    rows = read_all(world.api, "deepak", event_group=group)
    assert {r["event_type"] for r in rows} <= GROUPS[group]
    # Reading adds AUDIT_VIEWED rows, so compare the other events only.
    mine = [r for r in rows if r["event_type"] != "AUDIT_VIEWED"]
    want = [r for r in full if r["event_type"] in GROUPS[group] - {"AUDIT_VIEWED"}]
    assert len(mine) == len(want)
    assert group != "VIEWED" or mine


def test_the_viewed_group_has_rows_and_pages_on_the_server(world: World) -> None:
    activity(world)
    page = world.api.get("deepak", "/audit", event_group="VIEWED", limit=1)
    assert page.status_code == 200, page.text
    body = page.json()
    assert len(body["items"]) == 1 and body["next_cursor"]
    assert body["items"][0]["event_type"] in GROUPS["VIEWED"]
    nxt = world.api.get(
        "deepak", "/audit", event_group="VIEWED", limit=1, cursor=body["next_cursor"]
    )
    assert nxt.status_code == 200, nxt.text
    other = world.api.get(
        "deepak", "/audit", event_group="CONFIRMED", limit=1, cursor=body["next_cursor"]
    )
    assert other.status_code == 422


@pytest.mark.parametrize("value", ["viewed", "LOOKED_AT", "", "LINK_CONFIRMED"])
def test_an_unknown_group_is_a_422(world: World, value: str) -> None:
    response = world.api.get("deepak", "/audit", event_group=value)
    assert response.status_code == 422, response.text
    assert response.json()["field_errors"][0]["field"] == "event_group"


def test_a_group_and_an_event_type_must_both_match(world: World) -> None:
    activity(world)
    both = read_all(world.api, "deepak", event_group="VIEWED", event_type="LINK_VIEWED")
    assert both and all(r["event_type"] == "LINK_VIEWED" for r in both)
    clash = read_all(world.api, "deepak", event_group="CONFIRMED", event_type="LINK_VIEWED")
    assert clash == []


def test_a_group_of_hidden_rows_looks_like_an_empty_group(world: World) -> None:
    api = world.api
    gita_activity(api, world)
    for user in ("charu", "deepak"):
        hidden = api.get(user, "/audit", event_group="REQUESTED")
        none = api.get(user, "/audit", event_group="APPROVED")
        assert hidden.status_code == 200 and none.status_code == 200
        assert hidden.json()["items"] == [] and hidden.json()["next_cursor"] is None
        assert hidden.json()["result_count"] == none.json()["result_count"] == 0


def test_the_group_name_is_logged_as_a_filter_key(world: World) -> None:
    api = world.api
    api.get("deepak", "/audit", event_group="VIEWED")
    rows = read_all(api, "deepak", event_type="AUDIT_VIEWED")
    keys = [k for r in rows for k in r["detail"].get("filter_keys", [])]
    assert "event_group" in keys


def case_numbers(rows: list[dict[str, Any]]) -> set[str]:
    return {ref["case_number"] for r in rows for ref in r["refs"]}


def test_every_visible_ref_has_its_case_number(world: World) -> None:
    activity(world)
    rows = read_all(world.api, "charu")
    refs = [ref for r in rows for ref in r["refs"]]
    assert refs
    by_id = {v: k for k, v in world.cases.items()}
    for ref in refs:
        assert ref["case_number"] == by_id[ref["case_id"]]
        assert set(ref) == {"case_id", "district_id", "case_number"}


def test_a_hidden_case_number_never_appears(world: World) -> None:
    api = world.api
    gita_activity(api, world)
    api.get("bharat", f"/entities/{world.entities['E-1']}")
    api.get("bharat", f"/links/{world.links['L-1']}")
    api.get("gita", f"/entities/{world.entities['E-5']}")
    for user, hidden in (("charu", ["C-301", "C-201"]), ("deepak", ["C-301"])):
        rows = read_all(api, user)
        text = json.dumps(rows)
        for number in hidden:
            assert number not in text, (user, number)
            assert world.cases[number] not in text, (user, number)
    stub_rows = read_all(api, "charu", event_type="STUB_VIEWED")
    assert stub_rows
    assert case_numbers(stub_rows) <= {"C-101", "C-102"}


def test_a_filter_on_a_hidden_case_gets_nothing(world: World) -> None:
    api = world.api
    gita_activity(api, world)
    for value in ("C-301", "C-999", str(uuid.uuid4())):
        page = api.get("charu", "/audit", case_id=value)
        assert page.status_code == 200
        assert page.json()["items"] == [] and page.json()["next_cursor"] is None
