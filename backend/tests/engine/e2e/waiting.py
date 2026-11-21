"""Expected links the engine does not reach yet, pinned per batch (review of PR #28).

`FAILING[batch]` maps each expected link the scorer fails to the tier it waits for and the
exact failure kinds it shows today; `SKIPPED[batch]` lists the expected links the scorer does
not judge, with the reason. The gate compares both with `==`, so a link that starts passing,
fails differently, or a new failure stops CI by name, and this file is updated with the work
that changed it. A tier of 1 or more is engine work and the link may be deferred in the scorer
(`--defer`); 0 would mean a kit error, which is fixed in the kit and never deferred.
"""

MISSED = frozenset({"missed"})  # no edge on the pair

# Both entries wait for engine work, not for a tier of evidence: tier 3 here means P3.x.
FAILING: dict[str, dict[str, tuple[int, frozenset[str]]]] = {
    "b01": {
        # PER_LOCALITY at district-only 0.4 needs the case district in the graph: 52.5 vs 56.5.
        "EL-FX08-PER": (3, frozenset({"evidence_kinds", "score"})),
        # MULTI_USER uses whole-token similarity, so the shared phone P23 counts 0.2 (no anchor,
        # G2): 55.5 MEDIUM vs 90.9. flags.py moves to `name_sim` in P3.3.
        "EL-FX13-Q2Q3": (3, frozenset({"band", "gates"})),
    },
    "b02": {
        "EL-FX08-PER": (3, frozenset({"evidence_kinds", "score"})),
        "EL-FX13-Q2Q3": (3, frozenset({"band", "gates"})),
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
        "EL-FX05-PER-B02": "batch b02 not loaded",
        "EL-FX05-PHN-0-1": "batch b02 not loaded",
        "EL-FX13-Q1Q2": "harness HS-AC13 not applied",
        "EL-SF07-PER-B02": "batch b02 not loaded",
        "EL-SF07-PHN-0-1": "batch b02 not loaded",
    },
    "b02": {
        "EL-FX05-PER": "superseded by a later batch for the same pair",
        "EL-FX13-Q1Q2": "harness HS-AC13 not applied",
        "EL-SF07-PER-B01": "superseded by a later batch for the same pair",
    },
}
