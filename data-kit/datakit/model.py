"""In-memory model of the dataset: cases, files, entities and ground truth records."""

from __future__ import annotations

import csv
import io
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from datakit.text import BANNER

CDR_HEADER = [
    "call_id", "start_time", "duration_sec", "calling_no", "called_no",
    "call_type", "cell_id", "tower_place",
]  # fmt: skip
BANK_HEADER = [
    "txn_id", "txn_date", "account_no", "ifsc", "account_holder",
    "direction", "counterparty", "narration", "amount_inr", "balance_inr",
]  # fmt: skip
SDR_HEADER = [
    "msisdn", "subscriber_name", "relative_name", "locality", "district", "activated_on",
]  # fmt: skip

FILE_HEADERS = {"cdr": CDR_HEADER, "bank": BANK_HEADER, "sdr": SDR_HEADER}


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def csv_line(cells: list[str]) -> str:
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="").writerow(cells)
    return buffer.getvalue()


def file_kind(name: str) -> str:
    return name.split("-")[0].split(".")[0]


def file_batch(name: str) -> str:
    return "b02" if "-02" in name else "b01"


@dataclass
class Entity:
    gt_id: str
    type: str
    case_id: str
    raw_text: str
    normalized: str
    attributes: dict[str, Any] = field(default_factory=dict)
    mentions: list[tuple[str, int]] = field(default_factory=list)


@dataclass
class FileDoc:
    """One source file. Planted lines are pinned; the rest is filled with noise."""

    name: str
    header: int
    csv_cells: dict[int, list[str]] = field(default_factory=dict)
    text: dict[int, str] = field(default_factory=dict)
    last: int = 0
    min_total: int = 0

    @property
    def kind(self) -> str:
        return file_kind(self.name)

    @property
    def is_csv(self) -> bool:
        return self.name.endswith(".csv")

    def next_line(self, gap: int) -> int:
        if self.kind == "sdr":
            return self.header + 1 if self.last == 0 else self.last + 1
        if self.last == 0:
            return self.header + (3 if self.is_csv else 1)
        return self.last + gap

    def occupied(self, line: int) -> bool:
        return line in self.text or line in self.csv_cells


@dataclass
class Case:
    case_id: str
    district: str
    state: str
    station: str
    lang: str
    index: int
    planted: bool
    fir_date: str
    occurrence_date: str
    sections: str
    complainant: str = ""
    docs: dict[str, FileDoc] = field(default_factory=dict)
    in_b01: bool = True
    day_base: str = "2025-01-01"

    def batch_of(self, doc: FileDoc) -> str:
        return "b01" if self.in_b01 and file_batch(doc.name) == "b01" else "b02"

    def doc(self, name: str) -> FileDoc:
        if name not in self.docs:
            header = {"fir": 11, "notes": 2}.get(file_kind(name), 1)
            self.docs[name] = FileDoc(name, header)
        return self.docs[name]


@dataclass
class World:
    entities: list[Entity] = field(default_factory=list)
    by_id: dict[str, Entity] = field(default_factory=dict)
    cases: dict[str, Case] = field(default_factory=dict)
    groups: list[dict[str, Any]] = field(default_factory=list)
    attributions: list[dict[str, Any]] = field(default_factory=list)
    links: list[dict[str, Any]] = field(default_factory=list)
    non_links: list[dict[str, Any]] = field(default_factory=list)
    scenarios: list[dict[str, Any]] = field(default_factory=list)

    def entity(
        self,
        gt_id: str,
        type_: str,
        case: Case,
        raw: str,
        normalized: str,
        **attributes: Any,
    ) -> Entity:
        if gt_id in self.by_id:
            raise ValueError(f"duplicate gt_id {gt_id}")
        entity = Entity(gt_id, type_, case.case_id, nfc(raw), nfc(normalized), dict(attributes))
        self.entities.append(entity)
        self.by_id[gt_id] = entity
        return entity

    def _place(self, case: Case, doc: FileDoc, line: int | None, gap: int) -> int:
        number = doc.next_line(gap) if line is None else line
        while line is None and doc.occupied(number):
            number += 1
        if doc.occupied(number):
            raise ValueError(f"{case.case_id}/{doc.name}:{number} already planted")
        doc.last = max(doc.last, number)
        return number

    def _mention(
        self,
        case: Case,
        doc: FileDoc,
        number: int,
        text: str,
        ents: list[Entity],
        attrs: list[tuple[Entity, Entity, str]],
    ) -> None:
        for entity in ents:
            if entity.raw_text not in text:
                raise ValueError(f"{entity.gt_id}: {entity.raw_text!r} not in {text!r}")
            if entity.case_id != case.case_id:
                raise ValueError(f"{entity.gt_id} mentioned in {case.case_id}")
            entity.mentions.append((doc.name, number))
        for person, ident, code in attrs:
            self.attributions.append(
                {
                    "entity": person.gt_id,
                    "identifier": ident.gt_id,
                    "code": code,
                    "source": {"case_id": case.case_id, "file": doc.name, "line": number},
                }
            )

    def put_text(
        self,
        case: Case,
        name: str,
        text: str,
        ents: list[Entity] | None = None,
        attrs: list[tuple[Entity, Entity, str]] | None = None,
        line: int | None = None,
        gap: int = 3,
    ) -> int:
        doc = case.doc(name)
        text = nfc(text)
        number = self._place(case, doc, line, gap)
        doc.text[number] = text
        self._mention(case, doc, number, text, ents or [], attrs or [])
        return number

    def put_row(
        self,
        case: Case,
        name: str,
        cells: list[str],
        ents: list[Entity] | None = None,
        attrs: list[tuple[Entity, Entity, str]] | None = None,
        line: int | None = None,
        gap: int = 2,
    ) -> int:
        doc = case.doc(name)
        cells = [nfc(c) for c in cells]
        number = self._place(case, doc, line, gap)
        doc.csv_cells[number] = cells
        self._mention(case, doc, number, csv_line(cells), ents or [], attrs or [])
        return number

    def group(
        self, group_id: str, scope: str, members: list[Entity], origin: str = "planted"
    ) -> None:
        self.groups.append(
            {
                "group_id": group_id,
                "scope": scope,
                "members": [m.gt_id for m in members],
                "origin": origin,
            }
        )


def banner_lines() -> list[str]:
    return [BANNER]
