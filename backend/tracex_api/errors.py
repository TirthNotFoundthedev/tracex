"""Errors the API answers with: fixed codes and message keys, never derived from hidden data."""

from dataclasses import dataclass, field

from tracex_api.audit import AuditEvent

MESSAGE_KEYS = {
    "UNAUTHENTICATED": "error.unauthenticated",
    "FORBIDDEN": "error.forbidden",
    "NOT_FOUND": "error.not_found",
    "INVALID_TRANSITION": "error.invalid_transition",
    "STATE_MISMATCH": "error.state_mismatch",
    "REQUEST_COOLDOWN": "error.request_cooldown",
    "REQUEST_LIMIT": "error.request_limit",
    "NOT_PENDING": "error.not_pending",
    "CHANGE_HASH_STALE": "error.change_hash_stale",
    "OLD_VALUE_CHANGED": "error.old_value_changed",
    "PENDING_EXISTS": "error.pending_exists",
    "LAST_APPROVER": "error.last_approver",
    "RUN_IN_PROGRESS": "error.run_in_progress",
    "VALIDATION_FAILED": "error.validation_failed",
    "TOO_MANY_REQUESTS": "error.too_many_requests",
    "NOT_READY": "error.not_ready",
    "INTERNAL": "error.internal",
}

STATUS = {
    "UNAUTHENTICATED": 401,
    "FORBIDDEN": 403,
    "NOT_FOUND": 404,
    "INVALID_TRANSITION": 409,
    "STATE_MISMATCH": 409,
    "REQUEST_COOLDOWN": 409,
    "REQUEST_LIMIT": 409,
    "NOT_PENDING": 409,
    "CHANGE_HASH_STALE": 409,
    "OLD_VALUE_CHANGED": 409,
    "PENDING_EXISTS": 409,
    "LAST_APPROVER": 409,
    "RUN_IN_PROGRESS": 409,
    "VALIDATION_FAILED": 422,
    "TOO_MANY_REQUESTS": 429,
    "NOT_READY": 503,
    "INTERNAL": 500,
}


@dataclass
class ApiError(Exception):
    """Carries the response and, for refusals by policy, the W3 audit rows to append after the
    business transaction has been rolled back."""

    code: str
    field_errors: list[dict[str, str]] = field(default_factory=list)
    audits: list[AuditEvent] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)

    @property
    def status(self) -> int:
        return STATUS[self.code]

    def body(self) -> dict[str, object]:
        body: dict[str, object] = {"code": self.code, "message_key": MESSAGE_KEYS[self.code]}
        if self.field_errors:
            body["field_errors"] = self.field_errors
        return body


def conflict(code: str) -> ApiError:
    return ApiError(code)


def invalid(field_name: str, code: str) -> ApiError:
    return ApiError("VALIDATION_FAILED", [{"field": field_name, "code": code}])
