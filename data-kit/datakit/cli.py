"""Command line: `python -m datakit generate --tier small`."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from pathlib import Path

from datakit.generate import DEFAULT_SEED, generate_kit
from datakit.noise import TIERS
from datakit.pools import KIT_ROOT
from datakit.scorer import ScoreInputError, format_report, score
from datakit.seed import case_assignments_csv

log = logging.getLogger("datakit")


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScoreInputError(f"{path}: {exc}") from exc


def _defer_ids(defer: list[str], defer_file: Path | None) -> list[str]:
    """Link ids from `--defer` (comma separated, repeatable) and `--defer-file` (a JSON array of
    ids, or a JSON object whose keys are ids)."""
    ids = [i.strip() for group in defer for i in group.split(",") if i.strip()]
    if defer_file is not None:
        listed = _load_json(defer_file)
        if isinstance(listed, dict):
            listed = list(listed)
        if not isinstance(listed, list) or not all(isinstance(i, str) for i in listed):
            raise ScoreInputError(f"{defer_file}: expected a JSON array of link ids")
        ids.extend(listed)
    return ids


def _score_command(
    ground_truth: Path,
    result: Path,
    as_json: bool,
    defer: list[str] | None = None,
    defer_file: Path | None = None,
) -> int:
    """Exit 0 when every gating check passes, 1 when one fails, 2 on unreadable input."""
    try:
        gt = _load_json(ground_truth)
        document = _load_json(result)
        if not isinstance(gt, dict) or not isinstance(document, dict):
            raise ScoreInputError("ground truth and engine result must be JSON objects")
        report = score(gt, document, _defer_ids(defer or [], defer_file))
    except ScoreInputError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2
    if as_json:
        sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(format_report(report))
    return 0 if report["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="datakit", description="TraceX synthetic data kit")
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate", help="generate one tier")
    gen.add_argument("--tier", choices=sorted(TIERS), default="small")
    gen.add_argument("--seed", type=int, default=DEFAULT_SEED)
    gen.add_argument("--out", type=Path, default=None, help="default: data-kit/out/<tier>")
    sco = sub.add_parser("score", help="score an engine result against ground_truth.json")
    sco.add_argument("--ground-truth", type=Path, required=True, help="ground_truth.json")
    sco.add_argument("--result", type=Path, required=True, help="engine result (engine-result/1)")
    sco.add_argument("--json", action="store_true", help="print the report as JSON")
    sco.add_argument(
        "--defer",
        action="append",
        default=[],
        metavar="ID[,ID...]",
        help="expected links that wait for a later tier (reported as deferred, never as passed)",
    )
    sco.add_argument(
        "--defer-file", type=Path, default=None, help="JSON array of link ids to defer"
    )
    sub.add_parser("seed", help="rewrite seed/case_assignments.csv from users.json")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if args.command == "score":
        return _score_command(
            args.ground_truth, args.result, args.json, args.defer, args.defer_file
        )
    if args.command == "seed":
        (KIT_ROOT / "seed" / "case_assignments.csv").write_bytes(
            case_assignments_csv(DEFAULT_SEED).encode("utf-8")
        )
        return 0
    out: Path = args.out or KIT_ROOT / "out" / args.tier
    manifest = generate_kit(args.tier, args.seed, out)
    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    log.info("generated tier=%s seed=%d out=%s", args.tier, args.seed, out)
    log.info("manifest sha256 %s", digest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
