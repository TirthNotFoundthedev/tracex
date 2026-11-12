"""The P2.4 gate on the small kit, graded by the data-kit reference scorer (data-kit 8.3).

With only Tier 1 implemented, expected links that need fuzzy (Tier 2) or contextual (Tier 3)
evidence cannot pass yet. The gate is therefore:
  (a) every expected link reachable with Tier 1 passes the scorer's S1 checks;
  (b) the zero-tolerance checks hold over the whole kit, noise included: no forbidden-trap hit,
      no AUTO edge outside a cross_case group, every S4 integrity clause;
  (d) every expected link not reachable yet is listed with the tier it waits for, and what is
      stored for it is not wrong: no AUTO where a SUGGESTED link is expected, no source outside
      its two end cases.
The scorer's `ok` cannot say "expected link not reached yet, nothing wrong stored", so this
test reads its report (see the PR for the request to the kit owner).
"""

import pytest

from tests.engine.e2e.conftest import KitRun

# (a) Expected links Tier 1 reaches: identifier pairs with ID_EXACT only (G5 and G6 included).
TIER1_REACHABLE = {
    "b01": [
        *[f"EL-FX01-{n}-0-1" for n in ("1203", "8816")],
        "EL-ACC-4471-0-1",
        "EL-ACC-4471-0-2",
        "EL-ACC-4471-1-2",
        "EL-ACC-L3-0-1",
        "EL-FX02-0-1",
        *[f"EL-FX-07-R{n}-0-1" for n in (1, 2, 3)],
        "EL-FX07-PHN-0-1",
        *[f"EL-FX-08-R{n}-0-1" for n in (1, 2, 3, 4)],
        "EL-FX08-PHN-0-1",
        *[f"EL-FX-09-R{n}-0-1" for n in (1, 2, 3)],
        *[f"EL-FX09-ACC-{p}" for p in ("0-1", "0-2", "1-2")],
        "EL-FX10-PHN-0-1",
        *[f"EL-FX-11-R{n}-0-1" for n in (1, 2, 3, 4)],
        *[f"EL-FX-12-A-R{n}-0-1" for n in (1, 2, 3)],
        *[f"EL-FX-12-B-R{n}-0-1" for n in (1, 2)],
        "EL-FX12-PA-0-1",
        "EL-FX12-PB-0-1",
        *[f"EL-FX-13-{s}-R{n}-0-1" for s in ("A", "B") for n in (1, 2, 3)],
        *[f"EL-FX-13-C-R{n}-0-1" for n in (1, 2)],
        *[f"EL-FX13-{p}-0-1" for p in ("P12", "P34", "P23")],
        *[f"EL-FX-14-A-R{n}-0-1" for n in (1, 2)],
        *[f"EL-FX-14-B-R{n}-0-1" for n in (1, 2, 3)],
        "EL-FX14-P1-0-1",
        "EL-FX14-P2-0-1",
        "EL-FX17-PHN-0-1",
        "EL-FX19-VEH",
        "EL-FX21-ACC-0-1",
        *[f"EL-FX-22-R{n}-0-1" for n in (1, 2, 3)],
        "EL-FX22-PHN-0-1",
        "EL-FX26-A1A2",
        "EL-FX26-A2A3",
        *[f"EL-SF04-HUB-{p}" for p in ("0-1", "0-2", "1-2")],
        "EL-SF04-X-0-1",
        "EL-SF05-PHN-0-1",
        *[f"EL-SF-06-R{n}-0-1" for n in (1, 2, 3, 4)],
        "EL-SF06-PHN-0-1",
        "EL-SF08-PHN-0-1",
    ],
    "b02": [
        "EL-FX05-PHN-0-1",
        "EL-SF07-PHN-0-1",
        "EL-ACC-4471-0-3",
        "EL-ACC-4471-1-3",
        "EL-ACC-4471-2-3",
    ],
}

# (d) Expected links that wait for a later tier: the highest tier each needs.
WAITING = {
    "EL-FX01-PER": 3,  # PER_NAME_SIM (2) + PER_SHARED_NETWORK (3)
    "EL-FX03-PHN": 2,  # PHONE_TRANSPOSED, B2 blocking
    "EL-FX05-PER": 2,  # name, age, locality; no shared identifier until b02
    "EL-FX08-PER": 3,  # PER_SHARED_NETWORK k=4, PER_LOCALITY
    "EL-FX10-PER": 2,  # PER_NAME_SIM, PER_LOCALITY (DOB conflict already applied)
    "EL-FX11-PER": 3,  # every item is Tier 2 or 3
    "EL-FX12-P1P2": 3,
    "EL-FX12-P2P3": 3,
    "EL-FX13-Q1Q2": 3,  # also needs harness HS-AC13
    "EL-FX13-Q3Q4": 3,
    "EL-FX13-Q2Q3": 3,
    "EL-FX14-R1R2": 3,
    "EL-FX14-R3R2": 3,
    "EL-FX17-PER": 2,  # PER_NAME_SIM 30 on top of SHARED_PHONE 45
    "EL-FX21-ORG": 2,  # ORG_NAME_SIM, PER_LOCALITY
    "EL-FX22-PER": 3,
    "EL-SF06-PER": 3,
    "EL-SF07-PER-B01": 2,
    "EL-SF07-PER-B02": 2,
    "EL-ACC-E1E7": 2,  # PHONE_TRANSPOSED
    "EL-ACC-E3E7": 2,
    "EL-ACC-E8E7": 2,
}

# Failure kinds a waiting link may show: missing or incomplete, never wrong.
NOT_REACHED_YET = {"missed", "state", "band", "gates", "score", "evidence_kinds", "provenance"}

PASS_NOW = {
    "b01": {"AC-02", "AC-04", "AC-06", "AC-07", "AC-09", "AC-19", "AC-26"},
    "b02": {"AC-02", "AC-04", "AC-06", "AC-07", "AC-09", "AC-15", "AC-19", "AC-26"},
}
WAITS = {
    "AC-01": 3, "AC-03": 2, "AC-05": 2, "AC-08": 3, "AC-10": 2, "AC-11": 3, "AC-12": 3,
    "AC-13": 3, "AC-14": 3, "AC-17": 2, "AC-21": 2, "AC-22": 3,
}  # fmt: skip


def reachable(batch: str) -> set[str]:
    return set(TIER1_REACHABLE["b01"]) | (set(TIER1_REACHABLE["b02"]) if batch == "b02" else set())


@pytest.fixture(params=["b01", "b02"])
def kit_run(request: pytest.FixtureRequest) -> tuple[str, KitRun]:
    batch: str = request.param
    return batch, request.getfixturevalue(f"run_{batch}")


def failures(report: dict[str, object]) -> dict[str, set[str]]:
    from tests.engine.e2e.kit import failures_by_link

    return failures_by_link(report)  # type: ignore[arg-type]


def test_every_tier1_reachable_link_passes_s1(kit_run: tuple[str, KitRun]) -> None:
    batch, run = kit_run
    report = run.report
    skipped = {s["id"] for s in report["skipped"]}

    failed = {k: v for k, v in failures(report).items() if k in reachable(batch)}

    assert failed == {}
    assert reachable(batch).isdisjoint(skipped)


def test_zero_tolerance_checks_hold_over_the_whole_kit(kit_run: tuple[str, KitRun]) -> None:
    _, run = kit_run
    report = run.report

    assert report["forbidden_hits"] == []
    assert [w for w in report["wrong_links"] if w["id"] is None] == []
    assert report["checks"]["S3"]["failed"] == 0 and report["checks"]["S4"]["failed"] == 0
    assert report["checks"]["S4"]["passed"] > 1000


def test_every_expected_link_is_either_reachable_or_listed_as_waiting(
    kit_run: tuple[str, KitRun],
) -> None:
    batch, run = kit_run
    report = run.report
    skipped = {s["id"] for s in report["skipped"]}
    judged = set(failures(report)) | reachable(batch)

    assert judged - skipped <= reachable(batch) | set(WAITING)
    assert set(failures(report)) <= set(WAITING)


def test_a_waiting_link_is_incomplete_but_never_wrong(kit_run: tuple[str, KitRun]) -> None:
    _, run = kit_run
    report = run.report

    for link_id, kinds in failures(report).items():
        assert kinds <= NOT_REACHED_YET, (link_id, kinds)
    for item in report["wrong_links"]:
        if item["kind"] == "state":
            assert (item["expected"], item["actual"]) != ("SUGGESTED", "AUTO"), item
        if item["kind"] == "provenance":
            assert item["actual"]["outside_end_cases"] == [], item


def test_acceptance_cases_pass_or_wait_for_their_tier(kit_run: tuple[str, KitRun]) -> None:
    batch, run = kit_run
    per_ac = run.report["per_ac"]

    assert {ac for ac, row in per_ac.items() if row["status"] == "pass"} == PASS_NOW[batch]
    assert {ac for ac, row in per_ac.items() if row["status"] == "fail"} == set(WAITS)


def test_no_suggested_edge_on_a_non_link_pair(kit_run: tuple[str, KitRun]) -> None:
    """S6 is reported, not gating; Tier 1 alone stores nothing on a true non-link."""
    _, run = kit_run

    assert run.report["reported"]["suggested_on_non_link_pairs"] == 0
