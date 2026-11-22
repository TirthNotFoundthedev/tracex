"""The audit event registry: every event type and the `detail` keys it may carry.

Spec: docs/specs/api-audit-log.md section 3. Key classes (section 2): A actor and event (no case
involved), S side (tied to one case in `refs`), J joint (tied to the link or request as a whole,
owned by every end case), P private (stored, never returned: sequence numbers and chain
positions). The registry is mirrored in the table `audit_detail_key_owner` by migration 0003
and a test keeps both equal.
"""

from typing import Final

A, S, J, P = "A", "S", "J", "P"

# Keys whose values are ids of cases or of things that belong to cases, by what they reveal.
CASE_KEYS: Final = frozenset({"case_ids", "case_id"})
ENTITY_KEYS: Final = frozenset({"entity_ids", "near_entity_ids"})
LINK_KEYS: Final = frozenset({"link_ids", "link_ids_shown"})
STUB_KEYS: Final = frozenset({"stub_ids", "stub_ids_shown", "stub_id"})
REQUEST_KEYS: Final = frozenset({"request_ids"})
GRANT_KEYS: Final = frozenset({"grant_ids", "grant_id"})

_VIEW = {"via_grant": A}

EVENTS: Final[dict[str, dict[str, str]]] = {
    "AUDIT_CHAIN_STARTED": {"schema_version": A},
    "AUTH_LOGIN_SUCCESS": {},
    "AUTH_LOGIN_FAILED": {"claimed_username": A, "throttled": A},
    "AUTH_LOGOUT": {},
    "AUTH_REFRESHED": {},
    "AUTH_TOKEN_REJECTED": {"failure": A, "claimed_sub": A},
    "AUTH_REFRESH_REUSED": {},
    "CASE_LISTED": {"case_ids": S},
    "CASE_ENTITIES_VIEWED": {"entity_ids": S, **_VIEW},
    "ENTITY_VIEWED": {"link_ids_shown": J, "stub_ids_shown": J, **_VIEW},
    "LINK_VIEWED": {**_VIEW},
    "STUB_VIEWED": {"stub_ids": J, "near_entity_ids": S, **_VIEW},
    "ACCESS_REQUEST_VIEWED": {"request_ids": J, "stub_ids": J, "near_entity_ids": S},
    "GRANT_VIEWED": {"grant_ids": J, "link_ids": J},
    "CHANGE_VIEWED": {"change_ids": A, "case_ids": S},
    "GRAPH_VIEWED": {"entity_ids": S, "link_ids": J, "stub_ids": J, **_VIEW},
    "REVIEW_QUEUE_VIEWED": {"link_ids": J},
    "EXPLANATION_VIEWED": {**_VIEW},
    "SOURCE_LINES_VIEWED": {"line_from": S, "line_to": S, **_VIEW},
    "SEARCH_RUN": {"entity_ids": S, "entity_type_filter": A},
    "ACCESS_DENIED": {"action": A, "http_status": A},
    "LINKS_LISTED": {"link_ids": J, "stub_ids": J},
    "LINK_AUTO_CREATED": {"run_id": J, "band": J, "score": J, "entity_ids": J},
    "LINK_SUGGESTED": {"run_id": J, "band": J, "score": J, "entity_ids": J},
    "LINK_DEMOTED": {"run_id": J, "previous_state": J, "new_state": J, "cause": A},
    "LINK_PROMOTED": {"run_id": J, "previous_state": J, "new_state": J},
    "ENGINE_DIVERGENCE_REVERTED": {"link_ids": J, "cause": A},
    "LINK_WITHDRAWN": {"run_id": J, "previous_state": J},
    "LINK_CONFIRMED": {"previous_state": J, "new_state": J},
    "LINK_REJECTED": {"previous_state": J, "new_state": J},
    "LINK_UNDONE": {"previous_state": J, "new_state": J},
    "LINK_REOPENED": {"previous_state": J, "new_state": J},
    "ACCESS_REQUEST_CREATED": {"stub_id": J},
    "ACCESS_REQUEST_WITHDRAWN": {"stub_id": J},
    "ACCESS_REQUEST_EXPIRED": {"stub_id": J},
    "ACCESS_REQUEST_APPROVED": {"grant_id": J, "expires_at": A},
    "ACCESS_REQUEST_REJECTED": {"grant_id": J},
    "ACCESS_GRANT_REVOKED": {"cause": A},
    "ACCESS_GRANT_EXPIRED": {"cause": A},
    "ACCESS_GRANT_CLOSED": {"cause": A},
    "DATA_UPLOADED": {"file_sha256": A, "byte_count": A, "document_count": A},
    "MATCHING_RUN_STARTED": {"thresholds_version": A},
    "MATCHING_RUN_COMPLETED": {
        "thresholds_version": A,
        "auto_count": A,
        "suggested_count": A,
    },
    "CHANGE_PROPOSED": {
        "kind": A,
        "subject_id": A,
        "change_hash": A,
        "old_value": A,
        "new_value": A,
    },
    "CHANGE_APPROVED": {
        "kind": A,
        "subject_id": A,
        "change_hash": A,
        "old_value": A,
        "new_value": A,
    },
    "CHANGE_DENIED": {
        "kind": A,
        "subject_id": A,
        "change_hash": A,
        "old_value": A,
        "new_value": A,
    },
    "ASSIGNMENT_CHANGED": {"case_id": S, "added": A},
    "USER_CREATED": {"role": A, "district_id": A},
    "USER_ENABLED": {"role": A, "district_id": A},
    "USER_DISABLED": {"role": A, "district_id": A},
    "AUDIT_VIEWED": {
        "filter_keys": A,
        "seq_from": P,
        "seq_to": P,
        "result_count": A,
        "redacted": A,
    },
    "AUDIT_VERIFY_RUN": {
        "range_from": P,
        "range_to": P,
        "result": A,
        "first_bad_seq": P,
        "head_seq": P,
        "anchor_seq": P,
    },
}

# Events that belong to the system rather than to a case, for the reader rule (d).
SYSTEM_EVENT_PREFIXES: Final = (
    "AUTH_",
    "DATA_UPLOADED",
    "MATCHING_RUN_",
    "CHANGE_",
    "USER_",
    "AUDIT_",
)


def owner_of(klass: str) -> str:
    """The `owner_ref` stored in `audit_detail_key_owner` for a key class."""
    return {A: "NONE", S: "ONE_CASE", J: "ALL_LINK_ENDS", P: "PRIVATE"}[klass]


def registry_rows() -> list[tuple[str, str, str]]:
    return sorted(
        (event, key, owner_of(klass))
        for event, keys in EVENTS.items()
        for key, klass in keys.items()
    )
