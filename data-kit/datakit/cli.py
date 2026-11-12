"""Command line: `python -m datakit generate --tier small`."""

from __future__ import annotations

import argparse
import hashlib
import logging
import sys
from pathlib import Path

from datakit.generate import DEFAULT_SEED, generate_kit
from datakit.noise import TIERS
from datakit.pools import KIT_ROOT
from datakit.seed import case_assignments_csv

log = logging.getLogger("datakit")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="datakit", description="TraceX synthetic data kit")
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate", help="generate one tier")
    gen.add_argument("--tier", choices=sorted(TIERS), default="small")
    gen.add_argument("--seed", type=int, default=DEFAULT_SEED)
    gen.add_argument("--out", type=Path, default=None, help="default: data-kit/out/<tier>")
    sub.add_parser("seed", help="rewrite seed/case_assignments.csv from users.json")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
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
