"""TIR-85: the deciding person and the last decision on queue items and link history.

Spec: api-access-control.md section 4.2 (actor names, reason on queue items), api-audit-log.md
section 3 (REVIEW_QUEUE_VIEWED and LINK_VIEWED cover it, ids only in the log).
"""

from typing import Any

import pytest

from tests.api.conftest import World
from tests.api.contract import validate
from tests.api.helpers import body_text, person_link
from tracex_api.db import one

REASON = "Checked against the case file, different people"


def _user(world: World, username: str) -> dict[str, Any]:
    with world.api.owner() as conn:
        row = one(conn, "SELECT id, display_name, role FROM users WHERE username = %s", (username,))
    assert row is not None
    return {"user_id": str(row["id"]), "display_name": row["display_name"], "role": row["role"]}


def _decide_pair(world: World, decider: str, action: str = "reject") -> str:
    pair = person_link(world, "C-101", "C-102")
    response = world.api.post(decider, f"/links/{pair}/{action}", {"reason": REASON})
    assert response.status_code == 200, response.text
    return pair


def _queue_item(world: World, viewer: str, link_id: str, state: str) -> dict[str, Any]:
    response = world.api.get(viewer, "/review-queue", state=state)
    assert response.status_code == 200, response.text
    validate("ReviewQueuePage", response.json())
    items = [i for i in response.json()["items"] if i["link_id"] == link_id]
    assert len(items) == 1, f"{viewer} should see {link_id} in {state}"
    item: dict[str, Any] = items[0]
    return item


def _last_history(world: World, viewer: str, link_id: str) -> dict[str, Any]:
    response = world.api.get(viewer, f"/links/{link_id}")
    assert response.status_code == 200, response.text
    validate("LinkDetail", response.json())
    last: dict[str, Any] = response.json()["history"][-1]
    return last


# (decider, viewer, viewer may know the decider). Pair C-101 ~ C-102 is Rivergate only.
ACTOR_RULE = [
    ("bharat", "bharat", True),  # the viewer is the decider
    ("bharat", "charu", True),  # a SUPERVISOR sees an INVESTIGATOR of the same district
    ("charu", "charu", True),  # the viewer is the decider
    ("charu", "bharat", False),  # an INVESTIGATOR does not see a SUPERVISOR
    ("bharat", "asha", False),  # a JUNIOR sees nobody else
    ("deepak", "charu", False),  # a SUPERVISOR does not see a SENIOR
    ("deepak", "bharat", False),
    ("bharat", "deepak", True),  # a SENIOR sees an actor inside coverage
    ("charu", "deepak", True),
    ("meena", "deepak", False),  # a SENIOR does not see an actor outside coverage
    ("meena", "meena", True),
    ("bharat", "meena", True),
]


@pytest.mark.parametrize(("decider", "viewer", "named"), ACTOR_RULE)
def test_actor_is_filled_only_when_the_viewer_may_know_the_person(
    world: World, decider: str, viewer: str, named: bool
) -> None:
    pair = _decide_pair(world, decider)
    who = _user(world, decider)
    expected = who if named else None
    decision = _queue_item(world, viewer, pair, "REJECTED")["last_decision"]
    assert decision["to"] == "REJECTED"
    assert decision["actor"] == expected
    assert decision["reason_text"] == REASON
    entry = _last_history(world, viewer, pair)
    assert entry["actor"] == expected
    assert entry["actor_user_id"] == who["user_id"]
    if not named:
        assert who["display_name"] not in body_text(world.api.get(viewer, "/review-queue"))


def test_a_null_actor_carries_no_role_district_or_name(world: World) -> None:
    pair = _decide_pair(world, "deepak")
    decision = _queue_item(world, "charu", pair, "REJECTED")["last_decision"]
    assert decision["actor"] is None
    assert set(decision) == {"to", "at", "actor", "reason_text"}
    assert "Deepak" not in body_text(world.api.get("charu", f"/links/{pair}"))


def test_a_junior_sees_a_supervisors_undo_without_a_name_and_their_own_decision_with_one(
    world: World,
) -> None:
    api = world.api
    l2 = world.links["L-2"]
    assert api.post("charu", f"/links/{l2}/undo", {"reason": REASON}).status_code == 200
    decision = _queue_item(world, "asha", l2, "UNDONE")["last_decision"]
    assert (decision["to"], decision["actor"], decision["reason_text"]) == ("UNDONE", None, REASON)
    assert _last_history(world, "asha", l2)["actor"] is None
    # A JUNIOR cannot decide today. A person who was an INVESTIGATOR then and is a JUNIOR now
    # is still the decider of the stored entry and sees their own name.
    pair = _decide_pair(world, "bharat")
    asha = _user(world, "asha")
    with api.owner() as conn:
        conn.execute(
            "UPDATE link_history SET actor_user_id = %s "
            "WHERE link_id = %s AND to_state = 'REJECTED'",
            (asha["user_id"], pair),
        )
        conn.commit()
    assert _queue_item(world, "asha", pair, "REJECTED")["last_decision"]["actor"] == asha
    assert _last_history(world, "asha", pair)["actor"] == asha


def test_engine_entries_and_suggested_items_have_no_actor_and_no_last_decision(
    world: World,
) -> None:
    pair = person_link(world, "C-101", "C-102")
    assert _queue_item(world, "charu", pair, "SUGGESTED")["last_decision"] is None
    assert _last_history(world, "charu", pair)["actor"] is None


def test_a_reopened_item_has_no_last_decision_while_it_is_suggested(world: World) -> None:
    pair = _decide_pair(world, "bharat")
    assert world.api.post("charu", f"/links/{pair}/reopen", {"reason": REASON}).status_code == 200
    assert _queue_item(world, "charu", pair, "SUGGESTED")["last_decision"] is None


def test_a_queue_page_writes_one_queue_row_and_no_link_user_or_denied_row(world: World) -> None:
    api = world.api
    _decide_pair(world, "deepak")
    api.h("charu")
    before = len(api.audit_rows())
    response = api.get("charu", "/review-queue", state="REJECTED")
    assert response.status_code == 200
    assert response.json()["items"][0]["last_decision"] is not None
    rows = api.audit_rows()[before:]
    assert [r["event_type"] for r in rows] == ["REVIEW_QUEUE_VIEWED"]
    assert set(rows[0]["detail"]) == {"link_ids"}
    logged = str([(r["detail"], r["refs"]) for r in rows])
    assert REASON not in logged
    assert "Deepak" not in logged and "Charu" not in logged


def _all_pages(world: World, viewer: str, **params: Any) -> tuple[int, set[int]]:
    """The number of items over all pages of size 1, and every `total` seen on the way."""
    count, totals = 0, set()
    cursor: str | None = None
    while True:
        extra = {"cursor": cursor} if cursor else {}
        page = world.api.get(viewer, "/review-queue", limit=1, **params, **extra)
        assert page.status_code == 200, page.text
        body = page.json()
        totals.add(body["total"])
        count += len(body["items"])
        cursor = body["next_cursor"]
        if not cursor:
            return count, totals


@pytest.mark.parametrize("viewer", ["bharat", "charu", "deepak", "meena"])
@pytest.mark.parametrize(
    "params",
    [{}, {"entity_type": "PERSON"}, {"entity_type": "PHONE"}, {"waiting_days_min": 7}],
)
def test_queue_total_equals_the_items_the_viewer_may_see_with_the_filters(
    world: World, viewer: str, params: dict[str, Any]
) -> None:
    count, totals = _all_pages(world, viewer, **params)
    assert totals == {count}


def test_queue_total_leaves_out_hidden_links(world: World) -> None:
    # Three SUGGESTED person links join C-101, C-102 and C-201; bharat may see only one.
    assert _all_pages(world, "bharat") == (1, {1})
    assert _all_pages(world, "deepak") == (3, {3})
    assert _all_pages(world, "meena") == (3, {3})


def test_a_grant_holder_gets_no_actor_no_actor_id_no_reason_and_no_queue_item(world: World) -> None:
    api = world.api
    l1 = world.links["L-1"]  # Rivergate to Hillcrest: only a SENIOR with both in coverage decides
    assert api.post("deepak", f"/links/{l1}/undo", {"reason": REASON}).status_code == 200
    assert api.post("deepak", f"/links/{l1}/reopen", {"reason": REASON}).status_code == 200
    stub = api.get("bharat", f"/entities/{world.entities['E-1']}").json()["stubs"][0]
    created = api.post(
        "bharat", "/access-requests", {"stub_id": stub["stub_id"], "reason": "Same phone"}
    )
    assert created.status_code == 201, created.text
    approve = api.post(
        "farid", f"/access-requests/{created.json()['request_id']}/approve", {"duration_days": 30}
    )
    assert approve.status_code == 200, approve.text
    response = api.get("bharat", f"/links/{l1}")
    assert response.status_code == 200 and response.json()["via_grant"] is True
    history = response.json()["history"]
    assert len(history) >= 3
    for entry in history:
        assert not {"actor", "actor_user_id", "reason_text", "actor_kind"} & set(entry)
    text = body_text(response)
    assert REASON not in text and "Deepak" not in text
    for state in ("SUGGESTED", "REJECTED", "UNDONE"):
        queue = api.get("bharat", "/review-queue", state=state)
        assert l1 not in body_text(queue)
