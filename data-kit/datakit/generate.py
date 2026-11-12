"""Orchestration: build the world, render files, write ground truth and the manifest."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from datakit.alloc import Allocators
from datakit.fill import render_doc
from datakit.model import Case, Entity, World, csv_line
from datakit.noise import TIERS, build_noise, case_sort_key, fill_planted
from datakit.planted import build_planted
from datakit.seed import case_assignments_csv
from datakit.text import BANNER

KIT_VERSION = "data-kit/1.0"
DEFAULT_SEED = 20260401
RULESET_VERSION = "engine-matching/1.1"
SCHEMA_VERSION = "data-kit-gt/1"
BATCH_ORDER = ("b01", "b02")


def prune_orphans(world: World) -> None:
    """Drop noise entities that no line ended up mentioning (unused pool members)."""
    keep = []
    for entity in world.entities:
        if entity.mentions:
            keep.append(entity)
        elif not entity.gt_id.startswith("NZ-"):
            raise ValueError(f"planted entity without a mention: {entity.gt_id}")
    world.entities = keep
    world.by_id = {e.gt_id: e for e in keep}


def build_world(tier: str, seed: int) -> World:
    if tier not in TIERS:
        raise ValueError(f"unknown tier {tier!r}")
    world = World()
    alloc = Allocators(seed)
    build_planted(world)
    fill_planted(world, seed, alloc)
    prune_orphans(world)
    build_noise(world, tier, seed, alloc)
    prune_orphans(world)
    return world


def _dump(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _write(root: Path, rel: str, text: str) -> bytes:
    data = text.encode("utf-8")
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


def _mention_batch(world: World, case_id: str, file: str) -> str:
    case = world.cases[case_id]
    return "b02" if (not case.in_b01 or "-02" in file) else "b01"


def _ref(case_id: str, file: str, line: int) -> dict[str, Any]:
    return {"case_id": case_id, "file": file, "line": line}


def _entity_json(world: World, e: Entity) -> dict[str, Any]:
    mentions = sorted(e.mentions, key=lambda m: (m[0], m[1]))
    batches = {_mention_batch(world, e.case_id, f) for f, _ in mentions}
    out: dict[str, Any] = {
        "gt_id": e.gt_id,
        "type": e.type,
        "case_id": e.case_id,
        "raw_text": e.raw_text,
        "normalized": e.normalized,
        "mentions": [_ref(e.case_id, f, n) for f, n in mentions],
        "batch": min(batches),
    }
    if e.attributes:
        out["attributes"] = e.attributes
    return out


def _cited(world: World, link: dict[str, Any]) -> list[dict[str, Any]]:
    a, b = world.by_id[link["a"]], world.by_id[link["b"]]
    cites: set[tuple[str, str, int]] = set(link["_extra"])
    for e in (a, b):
        cites.update((e.case_id, f, n) for f, n in e.mentions)
    if link["type"] in ("PERSON", "ORG"):
        for att in world.attributions:
            if att["entity"] in (a.gt_id, b.gt_id):
                s = att["source"]
                cites.add((s["case_id"], s["file"], s["line"]))
    if link["batch_min"] == "b01":
        cites = {c for c in cites if _mention_batch(world, c[0], c[1]) == "b01"}
    return [_ref(*c) for c in sorted(cites)]


def ground_truth(world: World, tier: str, seed: int) -> dict[str, Any]:
    links = []
    for link in world.links:
        item = {k: v for k, v in link.items() if k != "_extra"}
        item["cited_lines"] = _cited(world, link)
        links.append(item)
    return {
        "schema_version": SCHEMA_VERSION,
        "kit_version": KIT_VERSION,
        "tier": tier,
        "seed": seed,
        "ruleset_version": RULESET_VERSION,
        "batches": list(BATCH_ORDER),
        "entities": [_entity_json(world, e) for e in world.entities],
        "groups": world.groups,
        "attributions": world.attributions,
        "expected_links": links,
        "expected_non_links": world.non_links,
        "scenarios": world.scenarios,
    }


def _cases_csv(world: World, cases: list[Case]) -> str:
    rows = [csv_line(["case_id", "fir_no", "fir_date", "station", "district", "state"])]
    for c in cases:
        rows.append(
            csv_line(
                [
                    c.case_id,
                    f"SYN-{c.case_id}/{c.fir_date[:4]}",
                    c.fir_date,
                    c.station,
                    c.district,
                    c.state,
                ]
            )  # fmt: skip
        )
    return "\n".join(rows) + "\n"


def generate_kit(
    tier: str,
    seed: int,
    out: Path,
    batches: Sequence[str] = BATCH_ORDER,
) -> Path:
    """Write one tier into `out`. Returns the path of manifest.json."""
    world = build_world(tier, seed)
    out.mkdir(parents=True, exist_ok=True)
    cases = sorted(world.cases.values(), key=lambda c: case_sort_key(c.case_id))
    written: dict[str, bytes] = {}
    for case in cases:
        for name in sorted(case.docs):
            doc = case.docs[name]
            batch = case.batch_of(doc)
            if batch not in batches:
                continue
            rel = f"batches/{batch}/cases/{case.case_id}/{name}"
            written[rel] = _write(out, rel, render_doc(case, doc))
    b01_cases = [c for c in cases if c.in_b01]
    written["cases.csv"] = _write(out, "cases.csv", _cases_csv(world, b01_cases))
    written["ground_truth.json"] = _write(
        out, "ground_truth.json", _dump(ground_truth(world, tier, seed))
    )
    written["SYNTHETIC.txt"] = _write(out, "SYNTHETIC.txt", BANNER + "\n")
    manifest = {
        "kit_version": KIT_VERSION,
        "seed": seed,
        "tier": tier,
        "batches": [b for b in BATCH_ORDER if b in batches],
        "case_languages": {c.case_id: c.lang for c in cases},
        "files": [
            {"path": rel, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
            for rel, data in sorted(written.items())
        ],
    }
    path = out / "manifest.json"
    path.write_bytes(_dump(manifest).encode("utf-8"))
    return path


def seed_assignments(seed: int = DEFAULT_SEED) -> str:
    return case_assignments_csv(seed)
