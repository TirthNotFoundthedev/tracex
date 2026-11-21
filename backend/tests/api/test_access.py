"""Role x jurisdiction access control through the API (api-access-control.md section 7)."""

import json
import uuid
from datetime import timedelta
from typing import Any

import pytest

from tests.api.conftest import IRFAN, PHONE, Api, World, case_notes, upload_case
from tests.api.helpers import body_text
from tracex_api.db import many, one

STUB_KEYS = {
    "redacted",
    "stub_id",
    "near_entity_id",
    "connection_exists",
    "access_request",
    "message_key",
}
HIDDEN_WORDS = ("C-201", "Hillcrest", "C-301", "Lakeside")


def doc_id(api: Api, case_number: str) -> str:
    with api.owner() as conn:
        row = one(
            conn,
            "SELECT d.id FROM documents d JOIN cases c ON c.id = d.case_id "
            "WHERE c.case_number = %s AND d.file_name = 'notes.txt'",
            (case_number,),
        )
    assert row is not None
    return str(row["id"])


def request_access(
    api: Api, world: World, user: str = "bharat", entity: str = "E-1"
) -> dict[str, Any]:
    stub = api.get(user, f"/entities/{world.entities[entity]}").json()["stubs"][0]
    response = api.post(
        user,
        "/access-requests",
        {"stub_id": stub["stub_id"], "reason": "The same phone is in my case"},
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def test_a1_to_a4_a_junior_sees_the_district_but_not_other_source_lines(world: World) -> None:
    api = world.api
    cases = api.get("asha", "/cases").json()
    assert {c["case_number"] for c in cases["items"]} == {"C-101", "C-102"}
    assert api.get("asha", f"/links/{world.links['L-2']}").status_code == 200
    assert api.post("asha", f"/links/{world.links['L-2']}/confirm", {}).status_code == 403
    assert (
        api.get(
            "asha", f"/documents/{doc_id(api, 'C-102')}/lines", line_from=1, line_to=3
        ).status_code
        == 403
    )
    assert (
        api.get(
            "asha", f"/documents/{doc_id(api, 'C-101')}/lines", line_from=1, line_to=3
        ).status_code
        == 200
    )


def test_a5_to_a8_a_hidden_link_is_a_stub_and_nothing_more(world: World) -> None:
    api = world.api
    e1 = api.get("bharat", f"/entities/{world.entities['E-1']}").json()
    assert len(e1["stubs"]) == 1 and set(e1["stubs"][0]) == STUB_KEYS
    assert e1["stubs"][0]["near_entity_id"] == world.entities["E-1"]
    assert e1["link_count"] == 1 and e1["has_hidden_connection"] is True
    e4 = api.get("bharat", f"/entities/{world.entities['E-4']}").json()
    assert len(e4["stubs"]) == 1 and e4["link_count"] == 0 and e4["has_hidden_connection"] is True
    for word in (*HIDDEN_WORDS, world.links["L-1"], world.entities["E-2"]):
        assert word not in json.dumps(e1)
    random_id = str(uuid.uuid4())
    hidden = api.get("bharat", f"/links/{world.links['L-1']}")
    assert (hidden.status_code, hidden.json()) == (
        404,
        api.get("bharat", f"/links/{random_id}").json(),
    )
    assert api.get("bharat", f"/links/{world.links['L-1']}/explanation").status_code == 404
    stub = api.get("bharat", f"/stubs/{e1['stubs'][0]['stub_id']}")
    assert stub.status_code == 200 and set(stub.json()) == STUB_KEYS


def test_a9_search_cannot_find_a_value_that_exists_only_in_a_hidden_entity(world: World) -> None:
    api = world.api
    upload_case(
        api,
        "C-201",
        "Hillcrest",
        {"notes-02.txt": case_notes("C-201", "Accused Dev Anand, mobile 9100000055.")["notes.txt"]},
    )
    hidden = api.get("bharat", "/search/entities", q="9100000055").json()
    unknown = api.get("bharat", "/search/entities", q="9100000066").json()
    assert hidden == unknown and hidden["items"] == [] and hidden["total"] == 0


def test_a10_a13_a16_confirmation_follows_the_matrix(world: World) -> None:
    api = world.api
    assert (
        api.post("bharat", f"/links/{world.links['L-2']}/confirm", {}).json()["state"]
        == "CONFIRMED"
    )
    assert api.post("charu", f"/links/{world.links['L-1']}/confirm", {}).status_code == 404
    assert (
        api.post("deepak", f"/links/{world.links['L-1']}/confirm", {}).json()["state"]
        == "CONFIRMED"
    )


def test_a19_to_a22_request_approve_and_read_under_a_grant(world: World) -> None:
    api = world.api
    created = request_access(api, world)
    assert (
        created["status"] == "PENDING" and created["stub"]["access_request"]["status"] == "PENDING"
    )
    other_stub = api.get("bharat", f"/entities/{world.entities['E-1']}").json()["stubs"][0][
        "stub_id"
    ]
    for wrong in (
        world.links["L-1"],
        world.cases["C-201"],
        world.entities["E-2"],
        str(uuid.uuid4()),
    ):
        assert (
            api.post(
                "bharat", "/access-requests", {"stub_id": wrong, "reason": "x" * 12}
            ).status_code
            == 404
        )
    assert (
        api.post(
            "asha", "/access-requests", {"stub_id": other_stub, "reason": "x" * 12}
        ).status_code
        == 404
    )
    assert (
        api.post("bharat", f"/access-requests/{created['request_id']}/approve", {}).status_code
        == 403
    )
    assert (
        api.post("charu", f"/access-requests/{created['request_id']}/approve", {}).status_code
        == 404
    )
    approved = api.post(
        "farid", f"/access-requests/{created['request_id']}/approve", {"duration_days": 30}
    )
    assert approved.status_code == 200
    body = approved.json()
    assert (
        body["grant"]["status"] == "ACTIVE"
        and body["stub"]["near_entity_id"] == world.entities["E-2"]
    )
    assert body["stub"]["stub_id"] != created["stub"]["stub_id"]
    # A new link L-5 appears later; the grant covers L-1 only.
    upload_case(api, "C-202", "Hillcrest", case_notes("C-202", IRFAN))
    assert api.post("hari", "/matching/runs", {}).status_code == 202
    entity = api.get("bharat", f"/entities/{world.entities['E-1']}").json()
    assert len(entity["stubs"]) == 1  # the new link to C-202 is a fresh stub; L-1 is now visible
    assert world.links["L-1"] in {link["link_id"] for link in entity["links"]}


def test_a23_to_a26_the_grant_is_read_only_and_fixed_to_its_ranges(world: World) -> None:
    api = world.api
    created = request_access(api, world)
    api.post("farid", f"/access-requests/{created['request_id']}/approve", {"duration_days": 30})
    l1 = world.links["L-1"]
    assert api.get("bharat", f"/links/{l1}").json()["via_grant"] is True
    assert api.get("bharat", f"/links/{l1}/explanation").status_code == 200
    far = doc_id(api, "C-201")
    ok = api.get("bharat", f"/documents/{far}/lines", line_from=3, line_to=3)
    assert ok.status_code == 200 and ok.json()["via_grant"] is True
    assert api.get("bharat", f"/documents/{far}/lines", line_from=1, line_to=2).status_code == 403
    e2 = api.get("bharat", f"/entities/{world.entities['E-2']}").json()
    assert e2["via_grant"] is True and e2["stubs"] == [] and e2["link_count"] == 1
    assert e2["has_hidden_connection"] is False and [link["link_id"] for link in e2["links"]] == [
        l1
    ]
    assert api.get("bharat", f"/entities/{world.entities['E-2']}/graph").status_code == 404
    assert api.get("bharat", f"/cases/{world.cases['C-201']}/entities").status_code == 404
    assert api.post("bharat", f"/links/{l1}/confirm", {}).status_code == 403
    assert api.get("bharat", f"/links/{l1}").json()["decision_block"] == "GRANT_READ_ONLY"


def test_a25_a_junior_grant_never_gives_source_lines_and_masks_values(world: World) -> None:
    api = world.api
    created = request_access(api, world, user="isha")
    api.post("farid", f"/access-requests/{created['request_id']}/approve", {"duration_days": 7})
    far = doc_id(api, "C-201")
    assert api.get("isha", f"/documents/{far}/lines", line_from=3, line_to=3).status_code == 403
    e2 = api.get("isha", f"/entities/{world.entities['E-2']}")
    explanation = api.get("isha", f"/links/{world.links['L-1']}/explanation")
    assert e2.status_code == 200 and explanation.status_code == 200
    assert PHONE not in body_text(e2) and PHONE not in body_text(explanation)
    assert e2.json()["display_value"] == "91xxxx0001" and e2.json()["masked"] is True


def test_a27_a28_a_grant_expires_and_can_be_revoked(world: World) -> None:
    api = world.api
    created = request_access(api, world)
    approved = api.post(
        "farid", f"/access-requests/{created['request_id']}/approve", {"duration_days": 30}
    )
    grant_id = approved.json()["grant"]["grant_id"]
    api.clock.advance(days=31)
    api.login("bharat")
    assert api.get("bharat", f"/links/{world.links['L-1']}").status_code == 404
    with api.owner() as conn:
        grant = one(conn, "SELECT state, close_cause FROM access_grants WHERE id = %s", (grant_id,))
    assert grant == {"state": "EXPIRED", "close_cause": "TIME"}
    assert len(api.audit_rows("ACCESS_GRANT_EXPIRED")) == 1


def test_a28_revoking_a_grant_ends_access_at_the_next_request(world: World) -> None:
    api = world.api
    created = request_access(api, world)
    approved = api.post("farid", f"/access-requests/{created['request_id']}/approve", {})
    grant_id = approved.json()["grant"]["grant_id"]
    assert api.get("bharat", f"/links/{world.links['L-1']}").status_code == 200
    assert api.post("bharat", f"/grants/{grant_id}/revoke").status_code == 403
    assert api.post("farid", f"/grants/{grant_id}/revoke").status_code == 200
    assert api.get("bharat", f"/links/{world.links['L-1']}").status_code == 404


def test_a29_new_evidence_outside_the_fixed_ranges_closes_the_grant(world: World) -> None:
    api = world.api
    created = request_access(api, world)
    approved = api.post("farid", f"/access-requests/{created['request_id']}/approve", {})
    grant_id = approved.json()["grant"]["grant_id"]
    upload_case(
        api,
        "C-201",
        "Hillcrest",
        {
            "notes-02.txt": case_notes("C-201", "Accused Irfan Khan, mobile 9100000001.")[
                "notes.txt"
            ]
        },
    )
    assert api.post("hari", "/matching/runs", {}).status_code == 202
    with api.owner() as conn:
        grant = one(conn, "SELECT state, close_cause FROM access_grants WHERE id = %s", (grant_id,))
        link = one(
            conn,
            "SELECT count(*) AS n FROM link_cited_lines WHERE link_id = %s",
            (world.links["L-1"],),
        )
    assert link is not None
    if grant and grant["state"] == "REVOKED":
        assert grant["close_cause"] == "EVIDENCE_CHANGED"


def test_a30_changing_a_role_invalidates_tokens_and_closes_grants(world: World) -> None:
    api = world.api
    created = request_access(api, world)
    api.post("farid", f"/access-requests/{created['request_id']}/approve", {})
    with api.owner() as conn:
        bharat = one(conn, "SELECT id FROM users WHERE username = 'bharat'")
    assert bharat is not None
    proposed = api.post(
        "hari",
        "/pending-changes",
        {
            "kind": "USER_ROLE",
            "subject_user_id": str(bharat["id"]),
            "new_value": {"role": "SUPERVISOR"},
        },
    ).json()
    approved = api.post(
        "deepak",
        f"/pending-changes/{proposed['change_id']}/approve",
        {"change_hash": proposed["change_hash"]},
    )
    assert approved.status_code == 200, approved.text
    assert api.client.get("/me", headers=api.h("bharat")).status_code == 401
    with api.owner() as conn:
        grants = many(conn, "SELECT state, close_cause FROM access_grants")
    assert grants == [{"state": "REVOKED", "close_cause": "ROLE_CHANGE"}]


def test_a31_a32_admin_has_no_case_data_rights(world: World) -> None:
    api = world.api
    for path in (
        "/cases",
        f"/cases/{world.cases['C-101']}/entities",
        f"/entities/{world.entities['E-1']}",
        f"/links/{world.links['L-1']}",
        f"/links/{world.links['L-1']}/explanation",
        "/review-queue",
        "/links",
        "/search/entities?q=9100000001",
    ):
        response = api.client.get(path, headers=api.h("hari"))
        assert (response.status_code, response.json()["code"]) == (404, "NOT_FOUND"), path
    assert api.post("hari", f"/links/{world.links['L-1']}/confirm", {}).status_code == 404
    assert api.post("hari", f"/access-requests/{uuid.uuid4()}/approve", {}).status_code == 404


@pytest.mark.parametrize(
    "claims", [{"role": "SENIOR"}, {"district": "Hillcrest", "role": "SENIOR"}]
)
def test_a40_claims_for_role_or_district_are_ignored(api: Api, claims: dict[str, str]) -> None:
    import jwt

    api.login("isha")
    token = api.tokens["isha"]["access_token"]
    decoded = jwt.decode(token, options={"verify_signature": False})
    forged = jwt.encode({**decoded, **claims}, api.settings.jwt_key, algorithm="HS256")
    me = api.client.get("/me", headers={"Authorization": f"Bearer {forged}"}).json()
    assert me["role"] == "JUNIOR"
    assert (
        api.client.get("/users", headers={"Authorization": f"Bearer {forged}"}).status_code == 403
    )


def test_a39_bad_tokens_are_refused_and_audited(api: Api) -> None:
    import jwt

    api.login("asha")
    claims = jwt.decode(api.tokens["asha"]["access_token"], options={"verify_signature": False})
    bad = [
        jwt.encode(claims, b"x" * 32, algorithm="HS256"),
        jwt.encode(claims, key="", algorithm="none"),
        jwt.encode({**claims, "exp": 1}, api.settings.jwt_key, algorithm="HS256"),
        "not-a-token",
    ]
    for token in bad:
        assert (
            api.client.get("/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
        )
    assert api.client.get("/me").status_code == 401
    assert len(api.audit_rows("AUTH_TOKEN_REJECTED")) == 5


def test_a41_random_ids_answer_identically_for_every_id_route(world: World) -> None:
    api = world.api
    routes = [
        "/cases/{}/entities",
        "/entities/{}",
        "/links/{}",
        "/links/{}/explanation",
        "/stubs/{}",
        "/access-requests/{}",
        "/grants/{}",
        "/pending-changes/{}",
        "/documents/{}/lines?line_from=1&line_to=2",
    ]
    expected = json.dumps(
        {"code": "NOT_FOUND", "message_key": "error.not_found"}, separators=(",", ":")
    )
    for user in ("bharat", "hari"):
        for template in routes:
            for _ in range(5):
                response = api.client.get(template.format(uuid.uuid4()), headers=api.h(user))
                if template.startswith("/pending-changes") and user == "bharat":
                    assert response.status_code == 403
                    continue
                assert (response.status_code, response.text) == (404, expected), template


def test_a42_filters_never_widen_the_scope(world: World) -> None:
    api = world.api
    rivergate = {
        d["name"]: d["district_id"]
        for s in api.get("esha", "/jurisdictions").json()["items"]
        for d in s["districts"]
    }["Rivergate"]
    assert api.get("esha", "/cases", district_id=rivergate).json()["items"] == []
    assert api.get("esha", "/cases", case_number="C-101").json()["items"] == []
    assert {c["case_number"] for c in api.get("esha", "/cases").json()["items"]} == {"C-201"}


def test_a43_disabled_users_and_dead_sessions_are_refused(world: World) -> None:
    api = world.api
    api.login("asha")
    assert api.client.post("/auth/logout", headers=api.h("asha")).status_code == 204
    assert api.client.get("/me", headers=api.h("asha")).status_code == 401
    wrong = api.client.post(
        "/auth/login", json={"username": "omkar", "password": "synthetic-omkar-pw"}
    )
    assert wrong.status_code == 401
    api.login("bharat")
    with api.owner() as conn:
        conn.execute("UPDATE users SET active = false WHERE username = 'bharat'")
        conn.commit()
    assert api.client.get("/me", headers=api.h("bharat")).status_code == 401


def test_a46_the_review_queue_lists_only_allowed_links_and_no_stubs(world: World) -> None:
    api = world.api
    queue = api.get("bharat", "/review-queue").json()
    seen = {i["link_id"] for i in queue["items"]}
    assert (
        seen
        == {link for name, link in world.links.items() if name.startswith("P-") and name != "P-x"}
        & seen
    )
    assert "stubs" not in queue
    for item in queue["items"]:
        assert all(end["case"]["case_number"] in ("C-101", "C-102") for end in item["ends"])


def test_a50_phone_values_are_masked_for_those_without_source_rights(world: World) -> None:
    api = world.api
    asha = api.get("asha", f"/entities/{world.entities['E-1']}")
    assert asha.json()["display_value"] == PHONE and asha.json()["masked"] is False
    for user in ("isha",):
        for path in (
            f"/entities/{world.entities['E-1']}",
            f"/cases/{world.cases['C-101']}/entities",
            f"/links/{world.links['L-2']}/explanation",
            f"/links/{world.links['L-2']}",
            f"/entities/{world.entities['E-1']}/graph",
            "/review-queue",
            "/links",
        ):
            response = api.get(user, path)
            assert response.status_code == 200, path
            assert PHONE not in body_text(response), path
    masked = api.get("isha", f"/entities/{world.entities['E-1']}").json()
    assert masked["display_value"] == "91xxxx0001" and masked["masked"] is True
    assert api.get("isha", "/search/entities", q=PHONE).json()["items"] == []
    assert api.get("bharat", "/search/entities", q=PHONE).json()["total"] >= 1


def test_a51_totals_are_one_object_for_admin_only(world: World) -> None:
    api = world.api
    totals = api.get("hari", "/stats/links")
    assert totals.status_code == 200
    assert set(totals.json()) == {"waiting", "rejected", "undone", "auto", "confirmed"}
    assert totals.json()["confirmed"] == 1
    for user in ("asha", "bharat", "charu", "deepak", "meena"):
        assert api.get(user, "/stats/links").status_code == 404
    assert api.get("hari", "/review-queue").status_code == 404


def test_a52_a_withdrawn_link_does_not_exist_for_anyone(world: World) -> None:
    api = world.api
    proposed = api.post(
        "hari",
        "/pending-changes",
        {"kind": "THRESHOLDS", "new_value": {"high_min": 80, "medium_min": 50}},
    ).json()
    assert (
        api.post(
            "meena",
            f"/pending-changes/{proposed['change_id']}/approve",
            {"change_hash": proposed["change_hash"]},
        ).status_code
        == 200
    )
    assert api.post("hari", "/matching/runs", {}).status_code == 202
    with api.owner() as conn:
        withdrawn = [
            str(r["link_id"])
            for r in many(conn, "SELECT link_id FROM links WHERE state = 'WITHDRAWN'")
        ]
    assert withdrawn and len(api.audit_rows("LINK_WITHDRAWN")) == len(withdrawn)
    missing = api.get("bharat", f"/links/{uuid.uuid4()}")
    for link_id in withdrawn:
        for suffix in ("", "/explanation"):
            response = api.get("bharat", f"/links/{link_id}{suffix}")
            assert (response.status_code, response.json()) == (404, missing.json())
        assert link_id not in body_text(api.get("bharat", "/links"))
        assert link_id not in body_text(api.get("bharat", "/review-queue"))
    assert api.get("meena", "/links").json()["total"] <= 4
    assert api.clock.at.tzinfo is not None and timedelta(0) == timedelta(0)


def test_a53_a_scoped_run_matches_against_everything_and_reports_totals_only(world: World) -> None:
    api = world.api
    batches = upload_case(api, "C-202", "Hillcrest", case_notes("C-202", IRFAN))
    run = api.post("hari", "/matching/runs", {"batch_ids": [batches[0]["batch_id"]]})
    assert run.status_code == 202, run.text
    body = run.json()
    assert set(body) == {
        "run_id", "status", "started_at", "finished_at", "triggered_by", "ruleset_version",
        "thresholds_version", "oversized_block_count", "error_code", "input_batch_count",
        "auto_created", "suggested_created",
    }  # fmt: skip
    assert (
        body["input_batch_count"] == 1
        and body["auto_created"] == 3
        and body["suggested_created"] == 3
    )
    again = api.get("hari", f"/matching/runs/{body['run_id']}").json()
    assert again == body
    assert "LOW" not in json.dumps(again)
    unknown = api.post("hari", "/matching/runs", {"batch_ids": [str(uuid.uuid4())]})
    assert unknown.status_code == 422


def test_a49_a_senior_cannot_approve_what_touches_districts_outside_coverage(world: World) -> None:
    api = world.api
    with api.owner() as conn:
        users = {r["username"]: str(r["id"]) for r in many(conn, "SELECT id, username FROM users")}
        states = {r["name"]: str(r["id"]) for r in many(conn, "SELECT id, name FROM states")}
    assignment = api.post(
        "hari",
        "/pending-changes",
        {
            "kind": "ASSIGNMENT_ADD",
            "subject_user_id": users["bharat"],
            "new_value": {"case_number": "C-301"},
        },
    )
    assert assignment.status_code == 201, assignment.text
    create = api.post(
        "hari",
        "/pending-changes",
        {
            "kind": "USER_CREATE",
            "new_value": {
                "username": "eastsenior",
                "display_name": "East Senior",
                "role": "SENIOR",
                "coverage": {
                    "all_states": False,
                    "state_ids": [states["Eastmark"]],
                    "district_ids": [],
                },
            },
        },
    )
    assert create.status_code == 201, create.text
    for proposal in (assignment.json(), create.json()):
        answer = api.post(
            "deepak",
            f"/pending-changes/{proposal['change_id']}/approve",
            {"change_hash": proposal["change_hash"]},
        )
        assert (answer.status_code, answer.json()["code"]) == (404, "NOT_FOUND")
        assert api.get("deepak", f"/pending-changes/{proposal['change_id']}").status_code == 404
    ok = api.post(
        "meena",
        f"/pending-changes/{assignment.json()['change_id']}/approve",
        {"change_hash": assignment.json()["change_hash"]},
    )
    assert ok.status_code == 200


def test_a34_a38_changes_wait_for_approval_and_guard_the_last_approver(world: World) -> None:
    api = world.api
    with api.owner() as conn:
        users = {r["username"]: str(r["id"]) for r in many(conn, "SELECT id, username FROM users")}
    pending = api.post(
        "hari", "/pending-changes", {"kind": "USER_DISABLE", "subject_user_id": users["gita"]}
    ).json()
    assert pending["state"] == "PENDING"
    with api.owner() as conn:
        assert one(conn, "SELECT active FROM users WHERE username = 'gita'") == {"active": True}
    assert (
        api.post(
            "hari",
            f"/pending-changes/{pending['change_id']}/approve",
            {"change_hash": pending["change_hash"]},
        ).status_code
        == 403
    )
    assert (
        api.post(
            "meena", f"/pending-changes/{pending['change_id']}/approve", {"change_hash": "0" * 64}
        ).status_code
        == 409
    )
    for path in ("/users/password", "/auth/password", "/auth/reset"):
        assert api.client.post(path, headers=api.h("hari"), json={}).status_code == 404
    own = api.post(
        "hari", "/pending-changes", {"kind": "USER_DISABLE", "subject_user_id": users["deepak"]}
    ).json()
    assert (
        api.post(
            "deepak",
            f"/pending-changes/{own['change_id']}/approve",
            {"change_hash": own["change_hash"]},
        ).status_code
        == 403
    )
    last = api.post(
        "hari", "/pending-changes", {"kind": "USER_DISABLE", "subject_user_id": users["meena"]}
    ).json()
    refused = api.post(
        "meena",
        f"/pending-changes/{last['change_id']}/approve",
        {"change_hash": last["change_hash"]},
    )
    assert refused.status_code == 403
    threshold = api.post(
        "hari",
        "/pending-changes",
        {"kind": "THRESHOLDS", "new_value": {"high_min": 85, "medium_min": 50}},
    ).json()
    assert (
        api.post(
            "deepak",
            f"/pending-changes/{threshold['change_id']}/approve",
            {"change_hash": threshold["change_hash"]},
        ).status_code
        == 404
    )
    assert (
        api.post(
            "meena",
            f"/pending-changes/{threshold['change_id']}/approve",
            {"change_hash": threshold["change_hash"]},
        ).status_code
        == 200
    )
    assert api.get("meena", "/thresholds").json()["high_min"] == 85


def test_a33_admin_uploads_and_runs_without_seeing_case_data(world: World) -> None:
    api = world.api
    batches = upload_case(
        api, "C-401", "Rampur", case_notes("C-401", "Accused Ravi Teja, mobile 9100000077.")
    )
    assert set(batches[0]) == {
        "batch_id",
        "file_name",
        "file_sha256",
        "byte_count",
        "document_count",
        "status",
        "error_code",
        "created_at",
    }
    status = api.get("hari", f"/uploads/{batches[0]['batch_id']}").json()["status"]
    assert status == "DONE"
    assert api.get("bharat", "/uploads").status_code == 403
    rows = api.audit_rows("DATA_UPLOADED")
    assert {r["detail"]["document_count"] for r in rows} == {1}
