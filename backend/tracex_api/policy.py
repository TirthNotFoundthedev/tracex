"""The access-control policy: who relates how to a case, and what that allows.

Spec: docs/specs/api-access-control.md sections 2 to 4. Everything here is pure: it takes the
principal (loaded from the database on every request, never from token claims) and plain facts
about a case or link, and answers ALLOW, REDACTED or hidden. The routes call it before any data
is serialised.
"""

from dataclasses import dataclass, field
from enum import StrEnum

ROLES = ("JUNIOR", "INVESTIGATOR", "SUPERVISOR", "SENIOR", "ADMIN")
RANK = {role: index for index, role in enumerate(ROLES)}
OFFICER_ROLES = frozenset(ROLES[:4])
VISIBLE_LINK_STATES = frozenset({"AUTO", "SUGGESTED", "CONFIRMED"})
BLOCKING_STATES = frozenset({"REJECTED", "UNDONE"})


class Relation(StrEnum):
    OWN = "OWN"
    JURISDICTION = "JURISDICTION"
    OTHER = "OTHER"


class LinkAccess(StrEnum):
    ALLOW = "ALLOW"
    REDACTED = "REDACTED"
    HIDDEN = "HIDDEN"


@dataclass(frozen=True)
class Principal:
    user_id: str
    username: str
    display_name: str
    role: str
    district_id: str | None
    sid: str
    coverage_all: bool = False
    coverage_state_ids: frozenset[str] = frozenset()
    coverage_district_ids: frozenset[str] = frozenset()
    # Districts a SENIOR covers, states already expanded; empty for other roles.
    covered_districts: frozenset[str] = frozenset()
    assigned_cases: frozenset[str] = frozenset()
    active_grants: dict[str, str] = field(default_factory=dict)  # link_id -> grant_id

    @property
    def rank(self) -> int:
        return RANK[self.role]

    def at_least(self, role: str) -> bool:
        return self.rank >= RANK[role]

    @property
    def is_officer(self) -> bool:
        return self.role in OFFICER_ROLES

    def covers_district(self, district_id: str) -> bool:
        if self.role == "SENIOR":
            return self.coverage_all or district_id in self.covered_districts
        return False

    def in_scope(self, district_id: str) -> bool:
        """The district is inside the user's own district, or a SENIOR's coverage."""
        if self.role == "ADMIN":
            return False
        if self.role == "SENIOR":
            return self.covers_district(district_id)
        return district_id == self.district_id

    def relation(self, case_id: str, district_id: str) -> Relation:
        if self.role == "ADMIN":
            return Relation.OTHER
        if case_id in self.assigned_cases:
            return Relation.OWN
        if self.in_scope(district_id):
            return Relation.JURISDICTION
        return Relation.OTHER

    def can_view_case(self, case_id: str, district_id: str) -> bool:
        return self.relation(case_id, district_id) is not Relation.OTHER

    def can_read_source(self, case_id: str, district_id: str) -> bool:
        """The "View source lines" cell: JUNIOR own case only; INVESTIGATOR and above own case
        and own jurisdiction. A grant is handled by the route, not here."""
        relation = self.relation(case_id, district_id)
        if relation is Relation.OWN:
            return self.is_officer
        if relation is Relation.JURISDICTION:
            return self.at_least("INVESTIGATOR") and self.is_officer
        return False


@dataclass(frozen=True)
class CaseFact:
    case_id: str
    district_id: str


def link_access(
    principal: Principal,
    link_id: str,
    state: str,
    end_a: CaseFact,
    end_b: CaseFact,
) -> LinkAccess:
    """ALLOW when every end is visible or a live grant names the link; REDACTED (a stub) when
    only the caller's own side is visible and the link is a connection; otherwise hidden."""
    if state == "WITHDRAWN" or not principal.is_officer:
        return LinkAccess.HIDDEN
    visible = [principal.can_view_case(e.case_id, e.district_id) for e in (end_a, end_b)]
    if all(visible):
        return LinkAccess.ALLOW
    if link_id in principal.active_grants:
        return LinkAccess.ALLOW
    if any(visible) and state in VISIBLE_LINK_STATES:
        return LinkAccess.REDACTED
    return LinkAccess.HIDDEN


# Decision actions: required role, the states each may start from, and the state it leads to.
DECISIONS: dict[str, tuple[str, frozenset[str], str]] = {
    "CONFIRM": ("INVESTIGATOR", frozenset({"SUGGESTED", "AUTO"}), "CONFIRMED"),
    "REJECT": ("INVESTIGATOR", frozenset({"SUGGESTED"}), "REJECTED"),
    "UNDO": ("SUPERVISOR", frozenset({"AUTO", "CONFIRMED"}), "UNDONE"),
    "REOPEN": ("SUPERVISOR", frozenset({"REJECTED", "UNDONE"}), "SUGGESTED"),
}


def decision_block(
    principal: Principal,
    action: str,
    end_a: CaseFact,
    end_b: CaseFact,
    via_grant_only: bool,
) -> str | None:
    """Why this caller may not decide the link (a `DecisionBlock` value), or None when allowed.
    Visibility (404) and state (409) are judged before and after this, in that order."""
    if via_grant_only:
        return "GRANT_READ_ONLY"
    required = DECISIONS[action][0]
    if not principal.at_least(required) or not principal.is_officer:
        return "ROLE_VIEW_ONLY"
    if end_a.district_id != end_b.district_id:
        if principal.role != "SENIOR":
            return "CROSS_AREA_SENIOR_ONLY"
        if not (
            principal.covers_district(end_a.district_id)
            and principal.covers_district(end_b.district_id)
        ):
            return "COVERAGE_INCOMPLETE"
    return None


def allowed_actions(
    principal: Principal, state: str, end_a: CaseFact, end_b: CaseFact, via_grant_only: bool
) -> list[str]:
    return [
        action
        for action, (_, starts, _) in DECISIONS.items()
        if state in starts
        and decision_block(principal, action, end_a, end_b, via_grant_only) is None
    ]


def can_read_user(principal: Principal, role: str, district_id: str | None) -> bool:
    """`GET /users/{id}` answers 200 for a SENIOR (coverage) or ADMIN (everyone)."""
    if principal.role == "ADMIN":
        return True
    if role in ("SENIOR", "ADMIN"):
        return principal.coverage_all
    return district_id is not None and principal.covers_district(district_id)


def may_name_actor(principal: Principal, actor_id: str, role: str, district_id: str | None) -> bool:
    """Access spec 4.2: a deciding person is named only to the person themselves, to the
    SUPERVISOR of their district (JUNIOR, INVESTIGATOR or SUPERVISOR actors), or to a SENIOR who
    could read them through `GET /users/{id}`. Everyone else, and any ADMIN actor, gets null."""
    if actor_id == principal.user_id:
        return True
    if role == "ADMIN":
        return False
    if principal.role == "SUPERVISOR":
        return (
            role in ("JUNIOR", "INVESTIGATOR", "SUPERVISOR")
            and district_id is not None
            and district_id == principal.district_id
        )
    if principal.role == "SENIOR":
        return can_read_user(principal, role, district_id)
    return False


def final_block(state: str) -> str | None:
    return "STATE_FINAL" if state == "WITHDRAWN" else None


def mask_value(entity_type: str, value: str) -> str:
    """Phone: first 2 and last 4 digits, the rest `x`. Account: 8 `x` then the last 4 digits."""
    if entity_type == "PHONE":
        digits = "".join(c for c in value if c.isdigit())
        if len(digits) <= 6:
            return "x" * len(digits)
        return digits[:2] + "x" * (len(digits) - 6) + digits[-4:]
    if entity_type == "ACCOUNT":
        digits = "".join(c for c in value if c.isdigit())
        return "x" * 8 + digits[-4:]
    return value


MASKED_TYPES = frozenset({"PHONE", "ACCOUNT"})
