"""Checks that contracts/ is valid and keeps the access, audit and engine promises.

Covers the OpenAPI document, the explanation JSON Schema and its example payloads.
"""

import copy
import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError
from openapi_spec_validator import validate

REPO = Path(__file__).resolve().parents[2]
CONTRACTS = REPO / "contracts"
OPENAPI_PATH = CONTRACTS / "openapi.yaml"
SCHEMA_PATH = CONTRACTS / "explanation.schema.json"
EXAMPLES = sorted((CONTRACTS / "examples").glob("*.json"))
ARCHITECTURE = REPO / "docs" / "architecture.md"

HTTP_METHODS = ("get", "post", "put", "patch", "delete")
PUBLIC_OPERATIONS = {"getHealth", "getReady", "login", "refreshToken"}
NO_STORED_FIELDS = {
    "seq",
    "event_id",
    "row_hash",
    "prev_hash",
    "row_nonce",
    "session_id",
    "request_id",
    "client_ip",
}
STUB_FIELDS = {
    "redacted",
    "stub_id",
    "near_entity_id",
    "connection_exists",
    "access_request",
    "message_key",
}

# Event names from docs/specs/api-audit-log.md section 3.
AUDIT_EVENTS = {
    "AUDIT_CHAIN_STARTED",
    "AUTH_LOGIN_SUCCESS",
    "AUTH_LOGIN_FAILED",
    "AUTH_LOGOUT",
    "AUTH_REFRESHED",
    "AUTH_TOKEN_REJECTED",
    "AUTH_REFRESH_REUSED",
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
    "ACCESS_DENIED",
    "LINKS_LISTED",
    "LINK_AUTO_CREATED",
    "LINK_SUGGESTED",
    "LINK_DEMOTED",
    "LINK_CONFIRMED",
    "LINK_REJECTED",
    "LINK_UNDONE",
    "LINK_REOPENED",
    "ACCESS_REQUEST_CREATED",
    "ACCESS_REQUEST_WITHDRAWN",
    "ACCESS_REQUEST_EXPIRED",
    "ACCESS_REQUEST_APPROVED",
    "ACCESS_REQUEST_REJECTED",
    "ACCESS_GRANT_REVOKED",
    "ACCESS_GRANT_EXPIRED",
    "ACCESS_GRANT_CLOSED",
    "DATA_UPLOADED",
    "MATCHING_RUN_STARTED",
    "MATCHING_RUN_COMPLETED",
    "CHANGE_PROPOSED",
    "CHANGE_APPROVED",
    "CHANGE_DENIED",
    "ASSIGNMENT_CHANGED",
    "USER_CREATED",
    "USER_ENABLED",
    "USER_DISABLED",
    "AUDIT_VIEWED",
    "AUDIT_VERIFY_RUN",
}

# Every evidence kind and gate in docs/specs/engine-matching.md sections 3 and 5.
SUPPORT_KINDS = {
    "ID_EXACT",
    "PHONE_TRANSPOSED",
    "SHARED_PHONE",
    "SHARED_ACCOUNT",
    "SHARED_VEHICLE",
    "PER_NAME_SIM",
    "PER_RELATIVE_NAME",
    "PER_DOB_MATCH",
    "PER_AGE_CLOSE",
    "PER_LOCALITY",
    "PER_NEAR_PHONE",
    "PER_SHARED_NETWORK",
    "PER_CO_LOCATION",
    "ORG_NAME_SIM",
}
AGAINST_KINDS = {
    "ACCT_BANK_CONFLICT",
    "PER_DOB_CONFLICT",
    "PER_DOB_MISMATCH",
    "PER_AGE_CONFLICT",
    "PER_GENDER_CONFLICT",
    "PER_RELATIVE_CONFLICT",
}
GATES = {
    "G1": "match.gate.below_high",
    "G2": "match.gate.no_anchor",
    "G3": "match.gate.single_tier",
    "G4": "match.gate.hard_conflict",
    "G5": "match.gate.low_extraction",
    "G6": "match.gate.cluster_conflict",
    "G7": "match.gate.org_review_only",
}


def _load_openapi() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    return loaded


def _load_schema() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return loaded


def _load_example(path: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def _load_example_decimal(path: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)
    return loaded


def _validator() -> Draft202012Validator:
    return Draft202012Validator(_load_schema(), format_checker=FormatChecker())


def _operations() -> list[tuple[str, str, dict[str, Any]]]:
    spec = _load_openapi()
    found: list[tuple[str, str, dict[str, Any]]] = []
    for path, item in spec["paths"].items():
        for method in HTTP_METHODS:
            if method in item:
                found.append((method, path, item[method]))
    return found


def invariant_holds(payload: dict[str, Any]) -> bool:
    """Engine spec section 7: exact decimal equality, tiers consistent, items rounded once."""
    total = Decimal(0)
    for tier in payload["support"]:
        item_sum = Decimal(0)
        for item in tier["items"]:
            expected = (Decimal(item["weight"]) * Decimal(item["strength"])).quantize(
                Decimal("0.1"), rounding=ROUND_HALF_UP
            )
            if Decimal(item["contribution"]) != expected:
                return False
            item_sum += Decimal(item["contribution"])
        raw = Decimal(tier["raw"])
        adjustment = Decimal(tier["cap_adjustment"]["value"])
        if raw != item_sum or adjustment != min(Decimal(0), Decimal(tier["cap"]) - raw):
            return False
        if Decimal(tier["subtotal"]) != raw + adjustment:
            return False
        total += Decimal(tier["subtotal"])
    total += sum((Decimal(item["contribution"]) for item in payload["against"]), Decimal(0))
    total += Decimal(payload["clamp_adjustment"]["value"])
    return total == Decimal(payload["score"])


def sources_stay_in_end_cases(payload: dict[str, Any]) -> bool:
    """Every source belongs to one of the link's two end cases; no item cites a third case."""
    end_cases = {record["case_id"] for record in payload["records"]}
    items = [i for tier in payload["support"] for i in tier["items"]] + payload["against"]
    cited = [source["case_id"] for item in items for source in item["sources"]]
    return set(cited) <= end_cases


# ---------------------------------------------------------------- explanation schema


def test_explanation_schema_is_a_valid_2020_12_schema() -> None:
    Draft202012Validator.check_schema(_load_schema())


def test_there_are_at_least_two_explanation_examples() -> None:
    assert len(EXAMPLES) >= 2


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_example_validates_against_the_schema(path: Path) -> None:
    _validator().validate(_load_example(path))


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_example_score_equals_subtotals_plus_against_plus_clamp(path: Path) -> None:
    assert invariant_holds(_load_example_decimal(path))


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_example_sources_stay_inside_the_two_end_cases(path: Path) -> None:
    assert sources_stay_in_end_cases(_load_example(path))


def test_examples_cover_a_cap_adjustment_and_an_opposing_item() -> None:
    payloads = [_load_example(path) for path in EXAMPLES]
    assert any(t["cap_adjustment"]["value"] < 0 for p in payloads for t in p["support"])
    assert any(p["against"] for p in payloads)


def test_schema_defines_every_evidence_kind_and_gate_in_the_matching_spec() -> None:
    schema = _load_schema()
    kinds = {
        d["properties"]["kind"]["const"]
        for name, d in schema["$defs"].items()
        if name.startswith(("i_", "a_"))
    }
    assert kinds == SUPPORT_KINDS | AGAINST_KINDS
    gate_keys: set[str] = set()
    for name, d in schema["$defs"].items():
        if name.startswith("gate_g"):
            key = d["properties"]["template_key"]
            gate_keys.update([key["const"]] if "const" in key else key["enum"])
    assert set(GATES.values()) <= gate_keys
    assert {"match.gate.cluster_bridge", "match.gate.cluster_same_case"} <= gate_keys


def _mutate(path: Path, change: Any) -> dict[str, Any]:
    payload = copy.deepcopy(_load_example(path))
    change(payload)
    return payload


AC01 = CONTRACTS / "examples" / "explanation-ac01-person-auto.json"
AC10 = CONTRACTS / "examples" / "explanation-ac10-person-conflict.json"
AC02 = CONTRACTS / "examples" / "explanation-ac02-vehicle-auto.json"

BAD_PAYLOADS = {
    "unknown_root_property": lambda p: p.update(actor="u1"),
    "english_text_field_is_rejected": lambda p: p["support"][0]["items"][0].update(
        text="Same phone"
    ),
    "missing_template_key": lambda p: p["support"][0]["items"][0].pop("template_key"),
    "template_key_not_matching_kind": lambda p: p["support"][0]["items"][0].update(
        template_key="match.evidence.shared_account"
    ),
    "unknown_kind": lambda p: p["support"][0]["items"][0].update(kind="PER_VIBES"),
    "attribution_must_be_a_code": lambda p: p["support"][0]["items"][0]["params"].update(
        how_a="stated user"
    ),
    "item_without_sources": lambda p: p["support"][0]["items"][0].update(sources=[]),
    "three_records": lambda p: p["records"].append(copy.deepcopy(p["records"][0])),
    "gates_passed_with_failures": lambda p: p["gates"].update(
        failed=[{"gate": "G2", "template_key": "match.gate.no_anchor"}]
    ),
    "gate_with_wrong_key": lambda p: p["gates"].update(
        passed=False, failed=[{"gate": "G2", "template_key": "match.gate.single_tier"}]
    ),
    "gates_failed_without_failures": lambda p: p["gates"].update(passed=False),
    "history_actor_must_not_leak": lambda p: p["history"][0].update(actor="u-77"),
    "history_reason_text_must_not_leak": lambda p: p["history"][0].update(reason_text="because"),
    "state_not_in_enum": lambda p: p.update(state="CLOSED"),
    "extraction_confidence_above_one": lambda p: p["records"][0].update(extraction_confidence=1.5),
    "cap_adjustment_positive": lambda p: p["support"][0]["cap_adjustment"].update(value=1.0),
    "modifier_factor_other_than_point_two": lambda p: p["support"][0]["items"][0].update(
        modifiers=[
            {"code": "SHARED", "factor": 0.5, "template_key": "match.modifier.trap_identifier"}
        ]
    ),
}


@pytest.mark.parametrize("name", sorted(BAD_PAYLOADS))
def test_schema_rejects(name: str) -> None:
    payload = _mutate(AC01, BAD_PAYLOADS[name])
    with pytest.raises(ValidationError):
        _validator().validate(payload)


def test_against_item_needs_a_severity() -> None:
    payload = _mutate(AC10, lambda p: p["against"][0].pop("severity"))
    with pytest.raises(ValidationError):
        _validator().validate(payload)


def test_identifier_pair_cannot_carry_a_tier_three() -> None:
    def add_tier_three(p: dict[str, Any]) -> None:
        p["support"].append(
            {
                "tier": 3,
                "cap": 35,
                "raw": 0.0,
                "cap_adjustment": {"value": 0.0, "template_key": "match.adjust.cap"},
                "subtotal": 0.0,
                "items": [],
            }
        )

    with pytest.raises(ValidationError):
        _validator().validate(_mutate(AC02, add_tier_three))


def test_trap_modifier_with_the_defined_shape_is_accepted() -> None:
    modifier = {
        "code": "MULTI_USER",
        "factor": 0.2,
        "template_key": "match.modifier.trap_identifier",
    }
    payload = _mutate(AC01, lambda p: p["support"][0]["items"][0].update(modifiers=[modifier]))
    _validator().validate(payload)


def test_invariant_detects_a_score_that_does_not_add_up() -> None:
    payload = _load_example_decimal(AC01)
    payload["score"] = Decimal("85.6")
    assert not invariant_holds(payload)


def test_source_check_detects_a_third_case() -> None:
    payload = _mutate(
        AC01,
        lambda p: p["support"][0]["items"][0]["sources"].append(
            {"case_id": "CASE-Z", "document_id": "doc_z", "line": 1}
        ),
    )
    assert not sources_stay_in_end_cases(payload)


# ---------------------------------------------------------------- OpenAPI


def test_openapi_document_is_valid_openapi_3_1() -> None:
    spec = _load_openapi()
    assert spec["openapi"].startswith("3.1")
    validate(spec, base_uri=OPENAPI_PATH.as_uri())


def test_every_operation_has_a_unique_id_a_role_a_jurisdiction_rule_and_an_audit_event() -> None:
    seen: set[str] = set()
    for method, path, op in _operations():
        where = f"{method.upper()} {path}"
        assert op.get("operationId"), where
        assert op["operationId"] not in seen, where
        seen.add(op["operationId"])
        assert str(op.get("x-required-role", "")).strip(), where
        assert str(op.get("x-jurisdiction", "")).strip(), where
        event = op.get("x-audit-event")
        assert event == "NONE" or event in AUDIT_EVENTS, where
        if event == "NONE":
            assert str(op.get("x-audit-note", "")).strip(), f"{where}: NONE needs a justification"


def test_audit_event_enum_matches_the_audit_spec() -> None:
    enum = set(_load_openapi()["components"]["schemas"]["AuditEventType"]["enum"])
    assert enum == AUDIT_EVENTS


def test_only_health_ready_login_and_refresh_are_unauthenticated() -> None:
    public = {op["operationId"] for _, _, op in _operations() if op.get("security") == []}
    assert public == PUBLIC_OPERATIONS


def test_authenticated_operations_answer_401_and_every_operation_but_probes_answers_500() -> None:
    for method, path, op in _operations():
        where = f"{method.upper()} {path}"
        if op["operationId"] not in PUBLIC_OPERATIONS:
            assert "401" in op["responses"], where
        if op["operationId"] not in {"getHealth", "getReady"}:
            assert "500" in op["responses"], where


def test_every_operation_with_an_id_in_the_path_answers_the_shared_404() -> None:
    for method, path, op in _operations():
        where = f"{method.upper()} {path}"
        if "{" in path:
            assert op["responses"].get("404") == {"$ref": "#/components/responses/NotFound"}, where


def test_case_data_reads_by_id_never_declare_403() -> None:
    """Access spec R2: hidden case, entity, link and stub are 404; only source lines may be 403."""
    for method, path, op in _operations():
        if (
            method == "get"
            and "{" in path
            and path.startswith(("/cases", "/entities", "/links", "/stubs"))
        ):
            assert "403" not in op["responses"], path


def test_the_404_response_carries_no_per_request_headers() -> None:
    responses = _load_openapi()["components"]["responses"]
    assert "headers" not in responses["NotFound"]
    assert "headers" not in responses["Forbidden"]


def test_error_examples_use_declared_codes_and_message_keys() -> None:
    schemas = _load_openapi()["components"]["schemas"]
    codes = set(schemas["ErrorCode"]["enum"])
    for response in _load_openapi()["components"]["responses"].values():
        example = response["content"]["application/json"]["example"]
        assert example["code"] in codes
        assert example["message_key"].startswith("error.")


def test_no_route_sets_or_resets_a_password() -> None:
    for _, path, _ in _operations():
        assert "password" not in path and "reset" not in path, path
    schemas = _load_openapi()["components"]["schemas"]
    for name, schema in schemas.items():
        if name != "LoginRequest":
            assert "password" not in json.dumps(schema), name


def test_stub_has_exactly_the_allowed_fields_and_no_far_side_data() -> None:
    stub = _load_openapi()["components"]["schemas"]["Stub"]
    assert set(stub["properties"]) == STUB_FIELDS
    assert stub["additionalProperties"] is False


def test_audit_row_exposes_no_private_columns() -> None:
    row = _load_openapi()["components"]["schemas"]["AuditRow"]
    assert not NO_STORED_FIELDS & set(row["properties"])
    assert "seq" not in json.dumps(_load_openapi()["components"]["schemas"]["AuditPage"])


def test_review_queue_filters_include_rejected_for_reopen() -> None:
    op = next(o for m, p, o in _operations() if p == "/review-queue" and m == "get")
    state = next(p for p in op["parameters"] if p.get("name") == "state")
    assert {"SUGGESTED", "REJECTED"} <= set(state["schema"]["enum"])


def test_link_decision_routes_exist_with_the_roles_from_the_access_spec() -> None:
    roles = {
        p: o["x-required-role"]
        for m, p, o in _operations()
        if m == "post" and p.startswith("/links/{link_id}/")
    }
    assert roles == {
        "/links/{link_id}/confirm": "INVESTIGATOR",
        "/links/{link_id}/reject": "INVESTIGATOR",
        "/links/{link_id}/undo": "SUPERVISOR",
        "/links/{link_id}/reopen": "SUPERVISOR",
    }


def test_explanation_is_referenced_from_the_schema_file() -> None:
    schemas = _load_openapi()["components"]["schemas"]
    assert schemas["Explanation"] == {"$ref": "explanation.schema.json"}


def test_every_list_operation_takes_a_signed_cursor() -> None:
    spec = _load_openapi()
    cursor = spec["components"]["parameters"]["Cursor"]
    assert "Signed and bound to the reader and filters" in cursor["description"]
    for method, path, op in _operations():
        names = [
            spec["components"]["parameters"][p["$ref"].rsplit("/", 1)[1]].get("name")
            if "$ref" in p
            else p.get("name")
            for p in op.get("parameters", [])
        ]
        bounded = path in {"/entities/{entity_id}/graph", "/entities/{entity_id}/paths"}
        if method == "get" and "limit" in names and "cursor" not in names and not bounded:
            pytest.fail(f"{path} pages without a cursor")


# ---------------------------------------------------------------- D40 minors


def test_minor_a_audit_read_rule_d_applies_only_to_rows_without_case_references() -> None:
    op = next(o for m, p, o in _operations() if p == "/audit" and m == "get")
    assert "(d) the row **references no cases** (`refs` empty)" in op["description"]


def test_minor_b_cursor_is_signed_and_bound_to_reader_and_filters() -> None:
    spec = _load_openapi()
    assert "signed" in spec["info"]["description"] and "bound" in spec["info"]["description"]
    audit_next = spec["components"]["schemas"]["AuditPage"]["properties"]["next_cursor"]
    assert "bound to the reader and the filters" in audit_next["description"]


def test_minor_c_rule_c_uses_case_level_access_and_every_detail_key_has_an_owner() -> None:
    op = next(o for m, p, o in _operations() if p == "/audit" and m == "get")
    assert "case-level access" in op["description"]
    assert "a grant never counts" in op["description"]
    assert "audit_detail_key_owner" in op["description"]
    architecture = ARCHITECTURE.read_text(encoding="utf-8")
    assert "audit_detail_key_owner" in architecture
    assert "audit_log_refs_cover_detail" in architecture


def test_minor_d_denied_lookup_of_a_hidden_id_is_stored_without_a_case_reference() -> None:
    architecture = ARCHITECTURE.read_text(encoding="utf-8")
    assert "audit_log_unresolved_has_no_refs" in architecture
    assert "resolved_target" in architecture
    not_found = _load_openapi()["components"]["responses"]["NotFound"]["description"]
    assert "UNRESOLVED" in not_found and "no case reference" in not_found
