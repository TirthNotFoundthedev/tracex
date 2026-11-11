"""Contract checks added after the PR #11 reviews (security gate and engine review)."""

import json
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from tests.test_contracts import (
    AC01,
    ARCHITECTURE,
    AUDIT_EVENTS,
    CONTRACTS,
    REPO,
    _load_example,
    _load_openapi,
    _operations,
    _validator,
)

SEQ_KEYS = {
    "seq",
    "seq_from",
    "seq_to",
    "range_from",
    "range_to",
    "head_seq",
    "anchor_seq",
    "first_bad_seq",
}


def _schemas() -> dict[str, Any]:
    schemas: dict[str, Any] = _load_openapi()["components"]["schemas"]
    return schemas


def _op(path: str, method: str) -> dict[str, Any]:
    return next(o for m, p, o in _operations() if p == path and m == method)


def test_finding_1_audit_detail_never_returns_a_sequence_number() -> None:
    detail = _schemas()["AuditDetail"]
    assert detail["additionalProperties"] is False
    assert not SEQ_KEYS & set(detail["properties"])
    mapping = detail["x-detail-keys"]
    assert set(mapping) <= AUDIT_EVENTS
    for event, keys in mapping.items():
        assert set(keys) <= set(detail["properties"]), event
        assert not SEQ_KEYS & set(keys), event
    assert _schemas()["AuditRow"]["properties"]["detail"] == {
        "$ref": "#/components/schemas/AuditDetail"
    }


def test_finding_2_rule_d_for_a_senior_needs_every_named_subject_in_coverage() -> None:
    description = _op("/audit", "get")["description"]
    assert "lies inside their coverage" in description
    assert "never admits a row that references a case" in description


def test_finding_3_cursor_is_encrypted_and_expires() -> None:
    cursor = _load_openapi()["components"]["parameters"]["Cursor"]["description"]
    assert "Encrypted" in cursor and "expires" in cursor
    assert "sequence number" in _schemas()["Cursor"]["description"]


def _entity(**overrides: Any) -> dict[str, Any]:
    entity: dict[str, Any] = {
        "entity_id": "E-2",
        "case_id": "C-201",
        "type": "PHONE",
        "display_value": "98xxxx4471",
        "masked": True,
        "link_count": 1,
        "has_hidden_connection": False,
        "needs_review": False,
        "via_grant": True,
    }
    entity.update(overrides)
    return entity


@pytest.mark.parametrize(
    "overrides",
    [{"link_count": 4}, {"has_hidden_connection": True}, {"needs_review": True}],
    ids=["link_count", "hidden_connection", "needs_review"],
)
def test_finding_4_entity_under_a_grant_shows_no_counts(overrides: dict[str, Any]) -> None:
    validator = Draft202012Validator(
        {"$ref": "#/components/schemas/EntitySummary", "components": {"schemas": _schemas()}}
    )
    validator.validate(_entity())
    with pytest.raises(ValidationError):
        validator.validate(_entity(**overrides))
    validator.validate(_entity(via_grant=False, **overrides))


def test_finding_5_history_under_a_grant_has_no_actor_or_free_text() -> None:
    schemas = _schemas()
    assert set(schemas["HistoryEntryGranted"]["properties"]) == {"from", "to", "at", "reason_code"}
    assert schemas["HistoryEntryGranted"]["additionalProperties"] is False
    assert (
        "never under a grant" in schemas["HistoryEntry"]["properties"]["reason_text"]["description"]
    )


def test_finding_6_requests_and_grants_have_one_shape_per_view() -> None:
    schemas = _schemas()
    for name in ("AccessRequestMine", "AccessRequestToDecide", "GrantHeld", "GrantAuthority"):
        assert schemas[name]["additionalProperties"] is False, name
    mine = schemas["AccessRequestMine"]["properties"]
    decide = schemas["AccessRequestToDecide"]["properties"]
    assert not {"far_case_id", "requester", "reason"} & set(mine)
    assert "decision_note" not in decide
    held, authority = schemas["GrantHeld"]["properties"], schemas["GrantAuthority"]["properties"]
    assert not {"far_case_id", "holder"} & set(held)
    assert not {"link_id", "far_entity_id"} & set(authority)
    assert "approver" in schemas["AccessRequestToDecide"]["description"]


def test_finding_7_stub_set_does_not_depend_on_the_state_filter() -> None:
    assert "never depends on `state`" in _op("/links", "get")["description"]


def test_finding_8_pending_change_approval_covers_every_touched_jurisdiction() -> None:
    for _, path, op in _operations():
        if path.startswith("/pending-changes/{change_id}/"):
            assert "every jurisdiction the change touches" in op["x-jurisdiction"], path
            assert "all-state" in op["x-jurisdiction"], path
    architecture = ARCHITECTURE.read_text(encoding="utf-8")
    assert "needs_all_states" in architecture and "district of the case" in architecture


def test_finding_9_postgres_and_audit_are_the_record_and_the_engine_follows() -> None:
    architecture = ARCHITECTURE.read_text(encoding="utf-8")
    assert "decision_outbox" in architecture
    assert "Postgres plus the audit log" in architecture
    assert "commit in Postgres **first**" in architecture


def test_n1_reads_that_name_cases_links_or_decisions_are_audited() -> None:
    events = {p: o["x-audit-event"] for m, p, o in _operations() if m == "get"}
    assert events["/grants"] == events["/grants/{grant_id}"] == "GRANT_VIEWED"
    assert events["/pending-changes"] == events["/pending-changes/{change_id}"] == "CHANGE_VIEWED"
    assert (
        events["/access-requests"]
        == events["/access-requests/{request_id}"]
        == "ACCESS_REQUEST_VIEWED"
    )
    for path in (
        "/users",
        "/thresholds",
        "/uploads",
        "/matching/runs",
        "/jurisdictions",
        "/roles",
        "/me",
    ):
        assert events[path] == "NONE", path


def test_n2_admin_totals_route_is_admin_only_and_takes_no_parameters() -> None:
    op = _op("/stats/links", "get")
    assert op["x-required-role"] == "ADMIN"
    assert "parameters" not in op
    assert set(_schemas()["LinkTotals"]["properties"]) == {
        "waiting",
        "rejected",
        "undone",
        "auto",
        "confirmed",
    }
    queue = _op("/review-queue", "get")
    state = next(p for p in queue["parameters"] if p.get("name") == "state")
    assert state["schema"]["enum"] == ["SUGGESTED", "REJECTED", "UNDONE"]


def test_n3_upload_response_is_identical_for_new_and_existing_cases() -> None:
    op = _op("/uploads", "post")
    assert "identical for a new and an existing case" in op["description"]
    assert "case_id" not in json.dumps(_schemas()["UploadBatch"])
    assert "refs" in op["x-audit-note"]


def test_n4_masking_rule_is_in_the_access_spec_and_the_contract() -> None:
    spec = (REPO / "docs" / "specs" / "api-access-control.md").read_text(encoding="utf-8")
    assert "4.1 Masking of identifier values" in spec and "98xxxx1234" in spec
    assert "masked" in _load_openapi()["info"]["description"]
    assert _validator().is_valid({**_load_example(AC01), "masked": True})
    assert not _validator().is_valid({**_load_example(AC01), "masked": "yes"})


def test_n8_only_verify_returns_a_sequence_number_and_only_when_broken() -> None:
    description = _schemas()["AuditVerifyResult"]["properties"]["first_bad_seq"]["description"]
    assert "only with BROKEN" in description
    spec = (REPO / "docs" / "specs" / "api-audit-log.md").read_text(encoding="utf-8")
    assert "`seq_from^`" in spec and "W8" in spec


def test_d49_run_is_scoped_by_upload_batch_never_by_named_cases() -> None:
    op = _op("/matching/runs", "post")
    assert op["requestBody"]["required"] is False
    props = _schemas()["StartRunRequest"]["properties"]
    assert set(props) == {"batch_ids"}
    assert "always matched against all loaded cases" in props["batch_ids"]["description"] or (
        "matched against all loaded cases" in props["batch_ids"]["description"]
    )
    assert "input_case_ids" in ARCHITECTURE.read_text(encoding="utf-8")


def test_d49_run_result_exposes_only_auto_and_suggested_totals() -> None:
    run = _schemas()["MatchRun"]
    assert not {"counts_by_band", "counts_by_state", "input_case_count"} & set(run["properties"])
    assert {"auto_created", "suggested_created"} <= set(run["properties"])
    assert "LOW" not in json.dumps(run)


def test_d49_run_and_decisions_guard_each_other() -> None:
    assert "no unacknowledged row" in _op("/matching/runs", "post")["description"]
    for action in ("confirm", "reject", "undo", "reopen"):
        op = _op("/links/{link_id}/" + action, "post")
        assert "RUN_IN_PROGRESS" in op["description"], action
        assert "409" in op["responses"], action
    architecture = ARCHITECTURE.read_text(encoding="utf-8")
    assert "Reconcile never imports a `decision_id`" in architecture
    assert "match_run_id, decision_id, reason_code, at" in architecture
    assert "ENGINE_DIVERGENCE_REVERTED" in _schemas()["AuditEventType"]["enum"]


def test_m1_rule_d_names_the_actor_district_and_claimed_identifiers() -> None:
    description = _op("/audit", "get")["description"]
    assert "claimed_username" in description and "actor's district" in description


def test_m2_pending_change_list_description_matches_its_jurisdiction_rule() -> None:
    assert "every touched jurisdiction" in _op("/pending-changes", "get")["description"]


def test_iyer_promoted_and_withdrawn_transitions_are_audited() -> None:
    assert {"LINK_PROMOTED", "LINK_WITHDRAWN"} <= set(_schemas()["AuditEventType"]["enum"])
    assert "WITHDRAWN link keeps its row" in _op("/matching/runs", "post")["description"]
    assert "state <> 'WITHDRAWN'" in ARCHITECTURE.read_text(encoding="utf-8")


def test_iyer_reopened_link_is_ended_only_by_a_human() -> None:
    assert "CONFIRMED, or REJECTED again" in _op("/links/{link_id}/reopen", "post")["description"]


def test_iyer_ac11_example_uses_two_spellings_for_a_similarity_below_one() -> None:
    payload = _load_example(CONTRACTS / "examples" / "explanation-ac11-person-caps.json")
    params = payload["support"][0]["items"][0]["params"]
    assert params["name_a"] != params["name_b"] and params["sim"] < 1


def test_spec_amendments_are_in_both_specs() -> None:
    access = (REPO / "docs" / "specs" / "api-access-control.md").read_text(encoding="utf-8")
    audit = (REPO / "docs" / "specs" / "api-audit-log.md").read_text(encoding="utf-8")
    assert "district of the case" in access and "C-202" in access and "Rampur" in access
    for event in (
        "LINK_PROMOTED",
        "LINK_WITHDRAWN",
        "GRANT_VIEWED",
        "CHANGE_VIEWED",
        "ACCESS_REQUEST_VIEWED",
    ):
        assert event in audit
    assert "an actor with no jurisdiction" in audit
