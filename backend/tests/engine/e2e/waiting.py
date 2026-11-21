"""Expected links that Tier 1 and Tier 3 do not reach yet, pinned per batch (PR #28 review).

`FAILING[batch]` maps each expected link the scorer fails to the tier it waits for and the
exact failure kinds it shows today; `SKIPPED[batch]` lists the expected links the scorer does
not judge, with the reason. The gate compares both with `==`, so a link that starts passing,
fails differently, or a new failure stops CI by name, and this file is updated with the tier
that changed it.

`missed`: no edge on the pair (Low without the Tier 2 items). `STORED`: a SUGGESTED edge with the
Tier 1 and Tier 3 part of the evidence, so state, band, gates, score and evidence kinds differ
from the full expectation, and the cited lines of the Tier 2 items are missing. With Tier 3 in,
every entry waits only for Tier 2.
"""

MISSED = frozenset({"missed"})
STORED = frozenset({"band", "evidence_kinds", "gates", "provenance", "score", "state"})


def _without(*kinds: str) -> frozenset[str]:
    return STORED - set(kinds)


_COMMON = {
    "EL-FX01-PER": (2, _without("provenance")),  # needs PER_NAME_SIM; Tier 3 gives 63.0
    "EL-FX03-PHN": (2, MISSED),  # PHONE_TRANSPOSED and B2 blocking
    "EL-FX08-PER": (2, frozenset({"evidence_kinds", "score"})),  # needs PER_LOCALITY; 52.5
    "EL-FX10-PER": (2, MISSED),  # 45 - 40 (DOB conflict) is Low; needs name and locality
    "EL-FX11-PER": (2, MISSED),  # Tier 3 gives 35 (Low); needs the Tier 2 items
    "EL-FX12-P1P2": (2, STORED),  # needs PER_NAME_SIM, which cites the missing notes line
    "EL-FX12-P2P3": (2, _without("provenance", "state")),  # SUGGESTED as expected
    "EL-FX13-Q2Q3": (2, MISSED),  # Low until PER_NAME_SIM
    "EL-FX13-Q3Q4": (2, _without("score")),  # band-mode score
    "EL-FX14-R1R2": (2, STORED),
    "EL-FX14-R3R2": (2, _without("provenance", "state")),
    "EL-FX17-PER": (2, frozenset({"evidence_kinds", "gates", "score"})),  # MEDIUM as expected
    "EL-FX21-ORG": (2, frozenset({"band", "evidence_kinds", "gates"})),  # band-mode score
    "EL-FX22-PER": (2, _without("provenance")),  # needs PER_NAME_SIM; Tier 3 gives 69.0
    "EL-SF06-PER": (2, MISSED),  # 45 - 50 (gender conflict) is Low; needs name
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
