"""Mapping of engine entities to ground-truth entities (spec section 8.1).

An engine entity maps to a ground-truth entity when they share at least one
`(case_id, file, line, type)` mention and, for PHONE, ACCOUNT and VEHICLE, their normalized
forms are equal, or, for PERSON and ORG, their `raw_text` is equal. Engine ids are never used.
Writings of one real entity in one case are joined by a `within_case` group; matching any member
counts for the whole group (`closure`).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any

IDENTIFIER_TYPES = frozenset({"PHONE", "ACCOUNT", "VEHICLE"})
NAME_TYPES = frozenset({"PERSON", "ORG"})

MentionKey = tuple[str, str, int, str]


def mention_key(ref: dict[str, Any], type_: str) -> MentionKey:
    return (str(ref["case_id"]), str(ref["file"]), int(ref["line"]), type_)


def _value_of(entity: dict[str, Any], type_: str) -> str:
    """The field the mapping compares: normalized form for identifiers, raw text for names."""
    return str(entity["normalized"] if type_ in IDENTIFIER_TYPES else entity["raw_text"])


class GroundTruthIndex:
    def __init__(self, gt: dict[str, Any]) -> None:
        self._by_mention: dict[MentionKey, list[tuple[str, str]]] = defaultdict(list)
        self._type: dict[str, str] = {}
        for entity in gt["entities"]:
            type_ = str(entity["type"])
            self._type[entity["gt_id"]] = type_
            value = _value_of(entity, type_)
            for ref in entity["mentions"]:
                self._by_mention[mention_key(ref, type_)].append((entity["gt_id"], value))
        self._within: dict[str, frozenset[str]] = {}
        for group in gt["groups"]:
            if group["scope"] != "within_case":
                continue
            members = frozenset(group["members"])
            for member in members:
                self._within[member] = self._within.get(member, frozenset()) | members

    def map_engine_entity(self, entity: dict[str, Any]) -> frozenset[str]:
        """Ground-truth ids the engine entity maps to directly; empty when it maps to none."""
        type_ = str(entity["type"])
        value = _value_of(entity, type_)
        found: set[str] = set()
        for ref in entity["mentions"]:
            for gt_id, expected in self._by_mention.get(mention_key(ref, type_), ()):
                if expected == value:
                    found.add(gt_id)
        return frozenset(found)

    def closure(self, gt_ids: Iterable[str]) -> frozenset[str]:
        """The ids plus every member of their within-case groups."""
        out: set[str] = set()
        for gt_id in gt_ids:
            out.add(gt_id)
            out |= self._within.get(gt_id, frozenset())
        return frozenset(out)

    def type_of(self, gt_id: str) -> str:
        return self._type[gt_id]
