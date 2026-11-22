"""Responses of the running API validate against the contract, and the route table matches it."""

from typing import Any

from tests.api.conftest import Api, World
from tests.api.contract import explanation_valid, spec_audit_events, spec_routes, validate
from tracex_api import context
from tracex_api.main import create_app


def test_every_contract_route_exists_with_its_audit_event(api: Api) -> None:
    """A47: every route has a declared policy and audit event, and the table equals the contract."""
    app = create_app(api.settings, api.engine, api.clock)
    implemented = context.implemented_routes(app)
    assert implemented == spec_routes()
    declared = {(r.method, r.path): r.audit_event for r in context.ROUTES}
    for key, event in spec_audit_events().items():
        assert declared[key] == event, key
    assert all(r.policy and r.audit_event for r in context.ROUTES)


def _ok(response: Any, schema: str) -> Any:
    assert response.status_code in (200, 201, 202), response.text
    validate(schema, response.json())
    return response.json()


def test_officer_reads_match_the_contract(world: World) -> None:
    api = world.api
    _ok(api.get("bharat", "/me"), "User")
    cases = _ok(api.get("bharat", "/cases"), "CasePage")
    assert {c["case_number"] for c in cases["items"]} == {"C-101", "C-102"}
    _ok(api.get("bharat", f"/cases/{world.cases['C-101']}/entities"), "CaseEntitiesPage")
    entity = _ok(api.get("bharat", f"/entities/{world.entities['E-1']}"), "EntityDetail")
    assert len(entity["stubs"]) == 1
    _ok(api.get("bharat", "/search/entities", q="9100000001"), "EntityPage")
    _ok(api.get("bharat", "/links"), "LinkPage")
    detail = _ok(api.get("bharat", f"/links/{world.links['L-2']}"), "LinkDetail")
    assert detail["allowed_actions"] == ["CONFIRM"]
    payload = api.get("bharat", f"/links/{world.links['L-2']}/explanation").json()
    explanation_valid(payload)
    _ok(api.get("bharat", "/review-queue"), "ReviewQueuePage")
    _ok(api.get("bharat", f"/entities/{world.entities['E-1']}/graph"), "GraphResponse")
    _ok(api.get("bharat", f"/entities/{world.entities['E-1']}/cluster"), "ClusterResponse")
    _ok(api.get("bharat", f"/entities/{world.entities['E-1']}/paths"), "PathsResponse")
    stub = entity["stubs"][0]
    _ok(api.get("bharat", f"/stubs/{stub['stub_id']}"), "Stub")
    _ok(api.get("bharat", "/jurisdictions"), "JurisdictionList")
    _ok(api.get("bharat", "/roles"), "RoleList")
    document = api.get("bharat", f"/entities/{world.entities['E-1']}").json()["provenance"][0]
    lines = api.get("bharat", f"/documents/{document['document_id']}/lines", line_from=1, line_to=5)
    _ok(lines, "SourceLines")


def test_access_request_and_grant_views_match_the_contract(world: World) -> None:
    api = world.api
    stub = api.get("bharat", f"/entities/{world.entities['E-1']}").json()["stubs"][0]
    created = _ok(
        api.post(
            "bharat",
            "/access-requests",
            {"stub_id": stub["stub_id"], "reason": "Same phone in my case"},
        ),
        "AccessRequestMine",
    )
    _ok(api.get("bharat", "/access-requests"), "AccessRequestPage")
    to_decide = _ok(api.get("farid", "/access-requests", scope="to_decide"), "AccessRequestPage")
    assert len(to_decide["items"]) == 1
    _ok(api.get("farid", f"/access-requests/{created['request_id']}"), "AccessRequest")
    approved = _ok(
        api.post(
            "farid", f"/access-requests/{created['request_id']}/approve", {"duration_days": 30}
        ),
        "AccessRequestToDecide",
    )
    grant_id = approved["grant"]["grant_id"]
    _ok(api.get("bharat", "/grants"), "GrantPage")
    _ok(api.get("farid", "/grants", scope="authority"), "GrantPage")
    _ok(api.get("bharat", f"/grants/{grant_id}"), "Grant")
    _ok(api.post("farid", f"/grants/{grant_id}/revoke"), "GrantAuthority")


def test_admin_and_senior_views_match_the_contract(world: World) -> None:
    api = world.api
    _ok(api.get("hari", "/uploads"), "UploadBatchPage")
    runs = _ok(api.get("hari", "/matching/runs"), "MatchRunPage")
    _ok(api.get("hari", f"/matching/runs/{runs['items'][0]['run_id']}"), "MatchRun")
    _ok(api.get("hari", "/stats/links"), "LinkTotals")
    _ok(api.get("hari", "/users"), "UserPage")
    _ok(api.get("meena", "/thresholds"), "Thresholds")
    proposed = _ok(
        api.post(
            "hari",
            "/pending-changes",
            {"kind": "THRESHOLDS", "new_value": {"high_min": 85, "medium_min": 50}},
        ),
        "PendingChange",
    )
    _ok(api.get("meena", "/pending-changes"), "PendingChangePage")
    _ok(api.get("meena", f"/pending-changes/{proposed['change_id']}"), "PendingChange")
    approved = _ok(
        api.post(
            "meena",
            f"/pending-changes/{proposed['change_id']}/approve",
            {"change_hash": proposed["change_hash"]},
        ),
        "PendingChange",
    )
    assert approved["state"] == "APPROVED"
    _ok(api.get("meena", "/audit"), "AuditPage")
    verified = _ok(api.post("meena", "/audit/verify"), "AuditVerifyResult")
    assert verified == {"result": "OK"}


def test_audit_rows_with_every_kind_of_detail_match_the_contract(world: World) -> None:
    api = world.api
    api.get("bharat", f"/entities/{world.entities['E-1']}")
    api.get("bharat", f"/links/{world.links['L-1']}")
    api.get("bharat", "/search/entities", q="9100000001")
    api.get("bharat", "/review-queue")
    api.post("bharat", f"/links/{world.links['L-2']}/confirm", {})
    api.post(
        "hari",
        "/pending-changes",
        {"kind": "THRESHOLDS", "new_value": {"high_min": 85, "medium_min": 50}},
    )
    api.client.post("/auth/login", json={"username": "asha", "password": "wrong"})
    cursor = None
    seen = 0
    while True:
        params: dict[str, Any] = {"limit": 20}
        if cursor:
            params["cursor"] = cursor
        page = _ok(api.get("meena", "/audit", **params), "AuditPage")
        seen += len(page["items"])
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert seen > 20
    _ok(api.get("hari", "/audit"), "AuditPage")
