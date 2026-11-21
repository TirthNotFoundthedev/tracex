"""Human decisions through the API: engine-matching AC-15, AC-16, AC-24, AC-25 and the D49 guard."""

import uuid

from tests.api.conftest import IRFAN, World, case_notes, upload_case
from tests.api.helpers import audit_count, history_count, link_state, person_link
from tracex_api.db import many, one

REASON = {"reason": "Checked against the case file"}


def test_ac24_illegal_transitions_answer_409_or_403_and_change_nothing(world: World) -> None:
    api = world.api
    pair = person_link(world, "C-101", "C-102")
    l2 = world.links["L-2"]
    before = {i: history_count(api, i) for i in (pair, l2)}
    decided = sum(audit_count(api, e) for e in ("LINK_CONFIRMED", "LINK_REJECTED", "LINK_UNDONE"))
    # AUTO -> REJECTED is refused: an AUTO link can only be undone.
    assert api.post("bharat", f"/links/{l2}/reject", REASON).status_code == 409
    # An INVESTIGATOR may not undo (403, the role case).
    assert api.post("bharat", f"/links/{l2}/undo", REASON).status_code == 403
    # REJECTED -> CONFIRMED.
    assert api.post("bharat", f"/links/{pair}/reject", REASON).status_code == 200
    confirm = api.post("bharat", f"/links/{pair}/confirm", {})
    assert (confirm.status_code, confirm.json()["code"]) == (409, "INVALID_TRANSITION")
    # CONFIRMED -> REJECTED.
    assert api.post("bharat", f"/links/{l2}/confirm", {}).status_code == 200
    reject = api.post("bharat", f"/links/{l2}/reject", REASON)
    assert (reject.status_code, reject.json()["code"]) == (409, "INVALID_TRANSITION")
    assert link_state(api, l2) == "CONFIRMED"
    assert link_state(api, pair) == "REJECTED"
    assert history_count(api, l2) == before[l2] + 1
    assert history_count(api, pair) == before[pair] + 1
    after = sum(audit_count(api, e) for e in ("LINK_CONFIRMED", "LINK_REJECTED", "LINK_UNDONE"))
    assert after == decided + 2


def test_stale_expected_state_is_a_conflict(world: World) -> None:
    response = world.api.post(
        "bharat", f"/links/{world.links['L-2']}/confirm", {"expected_state": "SUGGESTED"}
    )
    assert (response.status_code, response.json()["code"]) == (409, "STATE_MISMATCH")


def test_ac16_undo_splits_the_cluster_and_keeps_the_payload(world: World) -> None:
    api = world.api
    l2 = world.links["L-2"]
    cluster = api.get("bharat", f"/entities/{world.entities['E-1']}/cluster").json()
    assert {m["entity_id"] for m in cluster["members"]} == {
        world.entities["E-1"],
        world.entities["E-3"],
    }
    assert api.post("charu", f"/links/{l2}/undo", {}).status_code == 422
    undone = api.post("charu", f"/links/{l2}/undo", REASON)
    assert undone.status_code == 200
    assert undone.json()["state"] == "UNDONE"
    assert [h["to"] for h in undone.json()["history"]] == ["AUTO", "UNDONE"]
    split = api.get("bharat", f"/entities/{world.entities['E-1']}/cluster").json()
    assert {m["entity_id"] for m in split["members"]} == {world.entities["E-1"]}
    assert api.get("charu", f"/links/{l2}/explanation").status_code == 200
    with api.owner() as conn:
        outbox = many(conn, "SELECT acked_at FROM decision_outbox WHERE link_id = %s", (l2,))
    assert len(outbox) == 1 and outbox[0]["acked_at"] is not None
    edge = api.engine.links.get(l2)
    assert edge is not None and edge.state.value == "UNDONE"


def test_ac15_and_ac25_rejected_pair_stays_blocked_then_reopens_to_confirmed(
    world: World,
) -> None:
    api = world.api
    pair = person_link(world, "C-101", "C-102")
    assert api.post("bharat", f"/links/{pair}/reject", REASON).status_code == 200
    transitions = history_count(api, pair)
    # New evidence in both cases: a second owned phone. No new edge for the rejected pair.
    more = "Accused Irfan Khan, mobile 9100000099."
    for case, district in (("C-101", "Rivergate"), ("C-102", "Rivergate")):
        text = case_notes(case, more)["notes.txt"]
        upload_case(api, case, district, {"notes-02.txt": text})
    run = api.post("hari", "/matching/runs", {})
    assert run.status_code == 202, run.text
    assert link_state(api, pair) == "REJECTED"
    assert history_count(api, pair) == transitions
    with api.owner() as conn:
        count = one(
            conn,
            "SELECT count(*) AS n FROM links WHERE entity_type = 'PERSON' AND state <> 'WITHDRAWN' "
            "AND case_a_id = ANY(%s) AND case_b_id = ANY(%s)",
            ([world.cases["C-101"], world.cases["C-102"]],) * 2,
        )
    assert count is not None and count["n"] == 1
    # AC-25: reopen by a SUPERVISOR, confirm by an INVESTIGATOR, rerun never makes it AUTO.
    assert api.post("bharat", f"/links/{pair}/reopen", REASON).status_code == 403
    assert api.post("charu", f"/links/{pair}/reopen", REASON).json()["state"] == "SUGGESTED"
    assert api.post("bharat", f"/links/{pair}/confirm", {}).json()["state"] == "CONFIRMED"
    assert api.post("hari", "/matching/runs", {}).status_code == 202
    assert link_state(api, pair) == "CONFIRMED"
    with api.owner() as conn:
        steps = many(
            conn,
            "SELECT from_state, to_state FROM link_history WHERE link_id = %s ORDER BY id",
            (pair,),
        )
    assert [(s["from_state"], s["to_state"]) for s in steps] == [
        (None, "SUGGESTED"),
        ("SUGGESTED", "REJECTED"),
        ("REJECTED", "SUGGESTED"),
        ("SUGGESTED", "CONFIRMED"),
    ]


def test_u53_run_and_decisions_refuse_each_other(world: World) -> None:
    """D49: a run is refused while an outbox row is unacknowledged, and a decision while a run is
    RUNNING; both answer 409 RUN_IN_PROGRESS and change nothing."""
    api = world.api
    pair = person_link(world, "C-101", "C-102")
    with api.owner() as conn:
        user = one(conn, "SELECT id FROM users WHERE username = 'bharat'")
        assert user is not None
        conn.execute(
            "INSERT INTO decision_outbox (decision_id, link_id, expected_from, to_state, "
            "actor_user_id) VALUES (%s, %s, 'SUGGESTED', 'CONFIRMED', %s)",
            (uuid.uuid4(), pair, user["id"]),
        )
        conn.commit()
    run = api.post("hari", "/matching/runs", {})
    assert (run.status_code, run.json()["code"]) == (409, "RUN_IN_PROGRESS")
    with api.owner() as conn:
        conn.execute("UPDATE decision_outbox SET acked_at = now()")
        conn.execute(
            "INSERT INTO match_runs (id, started_at, ruleset_version, thresholds_version, status) "
            "VALUES (%s, now(), 'engine-matching/1.1', 1, 'RUNNING')",
            (uuid.uuid4(),),
        )
        conn.commit()
    for action in ("confirm", "reject"):
        response = api.post(
            "bharat", f"/links/{pair}/{action}", {} if action == "confirm" else REASON
        )
        assert (response.status_code, response.json()["code"]) == (409, "RUN_IN_PROGRESS")
    assert link_state(api, pair) == "SUGGESTED"
    assert history_count(api, pair) == 1
    again = api.post("hari", "/matching/runs", {})
    assert again.status_code == 409


def test_a12_a14_undo_needs_a_supervisor_and_a_reason(world: World) -> None:
    api = world.api
    l2 = world.links["L-2"]
    assert api.post("bharat", f"/links/{l2}/confirm", {}).status_code == 200
    assert api.post("bharat", f"/links/{l2}/undo", REASON).status_code == 403
    assert api.post("charu", f"/links/{l2}/undo", {}).status_code == 422
    assert api.post("charu", f"/links/{l2}/undo", REASON).json()["state"] == "UNDONE"
    assert api.post("bharat", f"/links/{l2}/reopen", REASON).status_code == 403
    assert api.post("charu", f"/links/{l2}/reopen", REASON).json()["state"] == "SUGGESTED"


def test_cross_district_links_are_decided_by_a_covering_senior(world: World) -> None:
    api = world.api
    l1, l3 = world.links["L-1"], world.links["L-3"]
    assert api.post("charu", f"/links/{l1}/confirm", {}).status_code == 404
    assert api.post("deepak", f"/links/{l1}/confirm", {}).json()["state"] == "CONFIRMED"
    assert api.get("deepak", f"/links/{l3}").status_code == 404
    assert api.post("deepak", f"/links/{l3}/undo", REASON).status_code == 404
    assert api.post("meena", f"/links/{l3}/undo", REASON).json()["state"] == "UNDONE"


def test_uploaded_irfan_lines_are_what_the_decisions_run_on(world: World) -> None:
    assert IRFAN.startswith("Accused Irfan")
    assert len(world.links) == 6
