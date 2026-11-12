"""G-17: distinct noise persons and organisations in one case have distinct names.

Two noise witnesses written `Rajesh Goyal` in one case, with no stated fact telling them apart,
read as one person; the ground truth must not call them two. Planted look-alikes state a
conflicting fact on purpose and are not noise, so they are outside this rule. Before the fix:
2 collisions (and 1 alias equal to another name) in the small tier, 19 (and 1) in the demo tier.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest

from datakit.generate import DEFAULT_SEED, generate_kit


def name_collisions(gt: dict[str, Any]) -> list[tuple[str, str, str]]:
    """(case, type, normalized name) shared by two noise entities that are not one writing."""
    within = {
        member: group["group_id"]
        for group in gt["groups"]
        if group["scope"] == "within_case"
        for member in group["members"]
    }
    seen: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for entity in gt["entities"]:
        if entity["type"] in ("PERSON", "ORG") and entity["gt_id"].startswith("NZ-"):
            key = (entity["case_id"], entity["type"], entity["normalized"])
            seen[key].add(within.get(entity["gt_id"], entity["gt_id"]))
    return sorted(key for key, owners in seen.items() if len(owners) > 1)


def alias_collisions(gt: dict[str, Any]) -> list[tuple[str, str]]:
    """(case, alias) where a noise person's alias equals another noise entity's name."""
    names: dict[str, set[str]] = defaultdict(set)
    for entity in gt["entities"]:
        if entity["type"] in ("PERSON", "ORG") and entity["gt_id"].startswith("NZ-"):
            names[entity["case_id"]].add(entity["normalized"])
    return sorted(
        (entity["case_id"], alias)
        for entity in gt["entities"]
        if entity["gt_id"].startswith("NZ-")
        for alias in entity.get("attributes", {}).get("aliases", [])
        if alias in names[entity["case_id"]] - {entity["normalized"]}
    )


def test_noise_persons_in_one_case_have_distinct_names_in_the_small_tier(
    gt: dict[str, Any],
) -> None:
    assert name_collisions(gt) == []


def test_a_noise_alias_never_equals_another_name_in_the_case_in_the_small_tier(
    gt: dict[str, Any],
) -> None:
    assert alias_collisions(gt) == []


@pytest.mark.slow
def test_noise_names_are_distinct_in_the_demo_tier(tmp_path: Path) -> None:
    generate_kit("demo", DEFAULT_SEED, tmp_path)
    demo: dict[str, Any] = json.loads((tmp_path / "ground_truth.json").read_text("utf-8"))

    assert name_collisions(demo) == []
    assert alias_collisions(demo) == []
