"""Small hand-built cases for matcher tests, and helpers to run the matcher on them.

Cases are built through the real case-graph builder from hand-written extractor records, or
through the real extractor from hand-written files, so the matcher sees what it sees in
production. Comparator outputs for Tier 2 and Tier 3 items are fixtures (spec section 8).
"""

import itertools
from collections.abc import Iterable, Mapping

from tests.engine.graph.support import (
    account,
    attribute,
    ident,
    org,
    person,
    phone,
    records,
)
from tracex_engine.extract import (
    Attribution,
    AttributionCode,
    IdentifierMention,
    IdKind,
    OrgMention,
    PersonMention,
    extract_case,
)
from tracex_engine.graph import CaseGraph, InMemoryCaseGraphStore, build_case_graph

__all__ = [
    "AttributionCode",
    "IdKind",
    "account",
    "attribute",
    "build",
    "clock",
    "from_files",
    "ident",
    "org",
    "person",
    "owns",
    "phone",
    "store_of",
    "vehicle",
]


def vehicle(
    plate: str, line: int = 12, file: str = "fir.txt", confidence: float = 0.9
) -> IdentifierMention:
    mention = ident(IdKind.VEHICLE, plate, plate, line, file)
    return IdentifierMention(
        mention.kind, mention.raw_text, mention.normalized, mention.source, confidence
    )


def build(
    case_id: str,
    persons: Iterable[PersonMention] = (),
    orgs: Iterable[OrgMention] = (),
    identifiers: Iterable[IdentifierMention] = (),
    attributions: Iterable[Attribution] = (),
) -> CaseGraph:
    """One case graph from hand-written records; identifiers named in attributions are added."""
    idents = list(identifiers)
    for a in attributions:
        if a.identifier not in idents:
            idents.append(a.identifier)
    parties = list(persons)
    organisations = list(orgs)
    for a in attributions:
        if isinstance(a.holder, PersonMention) and a.holder not in parties:
            parties.append(a.holder)
        if isinstance(a.holder, OrgMention) and a.holder not in organisations:
            organisations.append(a.holder)
    return build_case_graph(
        records(
            persons=tuple(parties),
            orgs=tuple(organisations),
            identifiers=tuple(idents),
            attributions=tuple(attributions),
            case_id=case_id,
        )
    )


def from_files(case_id: str, files: Mapping[str, str]) -> CaseGraph:
    return build_case_graph(extract_case(case_id, dict(files)))


def store_of(*graphs: CaseGraph) -> InMemoryCaseGraphStore:
    store = InMemoryCaseGraphStore()
    for graph in graphs:
        store.write_case(graph)
    return store


class clock:  # noqa: N801 - used like a function: clock() gives a fresh fake clock
    """A fake clock: each call returns the next second of 2026-11-20 UTC."""

    def __init__(self) -> None:
        self._tick = itertools.count()

    def __call__(self) -> str:
        n = next(self._tick)
        return f"2026-11-20T10:{n // 60:02d}:{n % 60:02d}Z"


def owns(
    holder: PersonMention | OrgMention,
    identifier: IdentifierMention,
    code: AttributionCode = AttributionCode.OWNS,
    confidence_line: int | None = None,
) -> Attribution:
    return attribute(holder, identifier, code, line=confidence_line)
