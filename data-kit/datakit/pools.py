"""Committed synthetic pools (data-kit spec sections 2 and 10)."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from functools import cache
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parent.parent
POOL_DIR = KIT_ROOT / "pools"


@dataclass(frozen=True)
class NamePair:
    roman: str
    devanagari: str


def _lines(name: str) -> list[str]:
    text = unicodedata.normalize("NFC", (POOL_DIR / name).read_text("utf-8"))
    return [line.strip() for line in text.splitlines() if line.strip()]


def _pairs(name: str) -> list[NamePair]:
    result = []
    for line in _lines(name):
        roman, devanagari = line.split("|")
        result.append(NamePair(roman, devanagari))
    return result


@dataclass(frozen=True)
class Pools:
    first_m: list[NamePair]
    first_f: list[NamePair]
    surnames: list[NamePair]
    villages: list[str]
    mohallas: list[str]
    towers: dict[str, list[str]]
    filler: dict[str, list[str]]
    notes: dict[str, list[str]]
    excluded: frozenset[str]


@cache
def load_pools() -> Pools:
    towers: dict[str, list[str]] = {}
    for line in _lines("towers.txt"):
        district, place = line.split("|")
        towers.setdefault(district, []).append(place)
    pools = Pools(
        first_m=_pairs("first_names_m.txt"),
        first_f=_pairs("first_names_f.txt"),
        surnames=_pairs("surnames.txt"),
        villages=_lines("villages.txt"),
        mohallas=_lines("mohallas.txt"),
        towers=towers,
        filler={lang: _lines(f"filler_{lang}.txt") for lang in ("en", "hi", "hi-latn")},
        notes={lang: _lines(f"notes_{lang}.txt") for lang in ("en", "hi", "hi-latn")},
        excluded=frozenset(_lines("excluded_tokens.txt")),
    )
    pooled = {p.roman.lower() for p in [*pools.first_m, *pools.first_f, *pools.surnames]}
    clash = pooled & pools.excluded
    if clash:
        raise ValueError(f"pool names collide with planted tokens: {sorted(clash)}")
    return pools
