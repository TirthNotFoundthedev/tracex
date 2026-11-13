"""Expected links that Tier 1 does not reach yet, pinned per batch (review of PR #28, blocker 1).

`FAILING[batch]` maps each expected link the scorer fails to the tier it waits for and the
exact failure kinds it shows today; `SKIPPED[batch]` lists the expected links the scorer does
not judge, with the reason. The gate compares both with `==`, so a link that starts passing,
fails differently, or a new failure stops CI by name, and this file is updated with the tier
that changed it.

`missed`: no edge on the pair (Low with Tier 1 alone). `STORED`: a SUGGESTED edge with the
Tier 1 part of the evidence (SHARED_* 45 or 50), so state, band, gates, score and evidence kinds
differ from the full expectation, and the expected cited lines of later tiers are missing.
"""

MISSED = frozenset({"missed"})
STORED = frozenset({"band", "evidence_kinds", "gates", "provenance", "score", "state"})


def _without(*kinds: str) -> frozenset[str]:
    return STORED - set(kinds)


_COMMON = {
    "EL-FX01-PER": (3, STORED),  # PER_NAME_SIM (2) and PER_SHARED_NETWORK (3)
    "EL-FX03-PHN": (2, MISSED),  # PHONE_TRANSPOSED and B2 blocking
    "EL-FX08-PER": (3, MISSED),  # REGISTERED_TO 22.5 is Low; needs network k=4 and locality
    "EL-FX10-PER": (2, MISSED),  # 45 - 40 (DOB conflict) is Low; needs name and locality
    "EL-FX11-PER": (3, MISSED),  # every item is Tier 2 or 3
    "EL-FX12-P1P2": (3, STORED),
    "EL-FX12-P2P3": (3, _without("provenance", "state")),  # SUGGESTED as expected
    "EL-FX13-Q2Q3": (3, MISSED),  # Low with Tier 1 alone
    "EL-FX13-Q3Q4": (3, _without("score")),  # band-mode score
    "EL-FX14-R1R2": (3, STORED),
    "EL-FX14-R3R2": (3, _without("provenance", "state")),
    "EL-FX17-PER": (2, frozenset({"evidence_kinds", "gates", "score"})),  # MEDIUM as expected
    "EL-FX21-ORG": (2, frozenset({"band", "evidence_kinds", "gates"})),  # band-mode score
    "EL-FX22-PER": (3, _without("provenance")),
    "EL-SF06-PER": (3, MISSED),  # 45 - 50 (gender conflict) is Low; needs name and network
}

FAILING: dict[str, dict[str, tuple[int, frozenset[str]]]] = {
    "b01": {
        **_COMMON,
        "EL-FX05-PER": (2, MISSED),  # no shared identifier in b01
        "EL-SF07-PER-B01": (2, MISSED),  # name, relative, locality
    },
    "b02": {
        **_COMMON,
        "EL-FX05-PER": (2, frozenset({"evidence_kinds", "gates"})),  # b02 phone: 45.0 SUGGESTED
        "EL-SF07-PER-B02": (2, frozenset({"band", "evidence_kinds", "gates", "state"})),
        "EL-ACC-E1E7": (2, MISSED),  # PHONE_TRANSPOSED
        "EL-ACC-E3E7": (2, MISSED),
        "EL-ACC-E8E7": (2, MISSED),
    },
}

SKIPPED: dict[str, dict[str, str]] = {
    "b01": {
        "EL-ACC-4471-0-3": "batch b02 not loaded",
        "EL-ACC-4471-1-3": "batch b02 not loaded",
        "EL-ACC-4471-2-3": "batch b02 not loaded",
        "EL-ACC-E1E7": "batch b02 not loaded",
        "EL-ACC-E3E7": "batch b02 not loaded",
        "EL-ACC-E8E7": "batch b02 not loaded",
        "EL-FX05-PHN-0-1": "batch b02 not loaded",
        "EL-FX13-Q1Q2": "harness HS-AC13 not applied",
        "EL-SF07-PER-B02": "batch b02 not loaded",
        "EL-SF07-PHN-0-1": "batch b02 not loaded",
    },
    "b02": {
        "EL-FX13-Q1Q2": "harness HS-AC13 not applied",
        "EL-SF07-PER-B01": "superseded by a later batch for the same pair",
    },
}
