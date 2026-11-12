"""Noise filling: every unpinned line of every file, plus the case-private identifiers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from datakit.alloc import Allocators
from datakit.model import (
    BANK_HEADER,
    CDR_HEADER,
    Case,
    Entity,
    FileDoc,
    World,
    csv_line,
    file_kind,
    nfc,
)
from datakit.pools import NamePair, load_pools
from datakit.rng import Stream
from datakit.text import BANNER, base_lang, phone_format

RANKS = ("SI", "ASI", "HC", "Insp", "SP")
NARRATIONS = ("UPI transfer", "Cash deposit", "ATM withdrawal", "Rent", "Salary", "Shop payment")
FIXED_TODAY = date(2026, 10, 31)
PHONE_STYLE_WEIGHTS = (70, 10, 10, 10)


@dataclass(frozen=True)
class Name:
    display: str
    normalized: str
    given: NamePair
    surname: NamePair
    gender: str

    def upper(self) -> str:
        return f"{self.given.roman} {self.surname.roman}".upper()


def draw_name(stream: Stream, lang: str, gender: str | None = None, native_pct: int = 60) -> Name:
    pools = load_pools()
    sex = gender or ("female" if stream.chance(20) else "male")
    given = stream.zipf(pools.first_f if sex == "female" else pools.first_m)
    surname = stream.choice(pools.surnames)
    native = lang == "hi" and stream.chance(native_pct)
    display = (
        f"{given.devanagari} {surname.devanagari}" if native else f"{given.roman} {surname.roman}"
    )
    return Name(nfc(display), f"{given.roman} {surname.roman}".lower(), given, surname, sex)


def phone_style(stream: Stream) -> int:
    point = stream.below(100)
    for style, weight in enumerate(PHONE_STYLE_WEIGHTS):
        if point < weight:
            return style
        point -= weight
    return 0


def officer(stream: Stream) -> str:
    letters = "ABCDEFGHIJKLMNOPRSTUVWY"
    return f"{stream.choice(RANKS)} {stream.choice(letters)}{stream.choice(letters)}"


def note_line(when: date, who: str, text: str) -> str:
    return f"[{when.isoformat()}] {who}: {text}"


@dataclass
class BankAccount:
    entity: Entity
    ifsc: str
    holder: Entity | None
    holder_text: str


@dataclass
class Filler:
    """Fills one case. `private` cases get identifiers that exist nowhere else."""

    world: World
    case: Case
    stream: Stream
    alloc: Allocators
    region: str
    day_base: date
    seq: int = 0
    phones: dict[str, Entity] = field(default_factory=dict)

    # entities -----------------------------------------------------------------
    def noise_entity(self, type_: str, raw: str, normalized: str, **attrs: object) -> Entity:
        self.seq += 1
        return self.world.entity(
            f"NZ-{self.case.case_id}-{self.seq}", type_, self.case, raw, normalized, **attrs
        )

    def phone_entity(self, number: str, style: int | None = None) -> Entity:
        if number not in self.phones:
            fmt = phone_style(self.stream) if style is None else style
            self.phones[number] = self.noise_entity("PHONE", phone_format(number, fmt), number)
        return self.phones[number]

    def new_phone(self) -> Entity:
        return self.phone_entity(self.alloc.phone(self.region))

    def account_entity(self, number: str | None = None) -> Entity:
        value = number or self.alloc.account(self.region)
        return self.noise_entity("ACCOUNT", value, value)

    # fir / notes ----------------------------------------------------------------
    def fill_fir(
        self,
        units: list[tuple[str, list[Entity], list[tuple[Entity, Entity, str]]]],
        paragraphs: int,
    ) -> None:
        """Pack `units` (sentences with their entities) and filler into FIR paragraph lines."""
        doc = self.case.doc("fir.txt")
        lang = base_lang(self.case.lang)
        filler = load_pools().filler[lang]
        total = max(doc.last + 3, 11 + paragraphs)
        free = [n for n in range(12, total + 1) if not doc.occupied(n)]
        buckets: dict[int, list[tuple[str, list[Entity], list[tuple[Entity, Entity, str]]]]] = {
            n: [] for n in free
        }
        for index, unit in enumerate(units):
            buckets[free[index % len(free)]].append(unit)
        for number in free:
            sentences = [u[0] for u in buckets[number]]
            ents = [e for u in buckets[number] for e in u[1]]
            attrs = [a for u in buckets[number] for a in u[2]]
            sentences.append(self.stream.choice(filler))
            self.world.put_text(self.case, "fir.txt", " ".join(sentences), ents, attrs, line=number)

    def fill_notes(
        self,
        name: str,
        lines: int,
        extra: list[tuple[str, list[Entity], list[tuple[Entity, Entity, str]]]] | None = None,
    ) -> None:
        doc = self.case.doc(name)
        lang = base_lang(self.case.lang)
        filler = load_pools().notes[lang]
        total = max(doc.last + 3, 2 + lines)
        pending = list(extra or [])
        for number in range(3, total + 1):
            if doc.occupied(number):
                continue
            who = officer(self.stream)
            when = date.fromisoformat(self.case.fir_date) + timedelta(days=number)
            if pending:
                text, ents, attrs = pending.pop(0)
                self.world.put_text(
                    self.case, name, note_line(when, who, text), ents, attrs, line=number
                )
            else:
                self.world.put_text(
                    self.case, name, note_line(when, who, self.stream.choice(filler)), line=number
                )

    # csv ------------------------------------------------------------------------
    def fill_cdr(
        self,
        name: str,
        rows: int,
        parties: list[Entity],
        pool: list[Entity],
        hub: bool = False,
    ) -> None:
        doc = self.case.doc(name)
        total = max(doc.last + 3, 1 + rows)
        towers = load_pools().towers[self.case.district]
        clock = datetime.combine(self.day_base, datetime.min.time()) + timedelta(hours=8)
        forced = list(pool) if hub else []
        for number in range(2, total + 1):
            clock += timedelta(minutes=self.stream.between(1, 9))
            stamp = clock.strftime("%Y-%m-%dT%H:%M:%S+05:30")
            if doc.occupied(number):
                cells = doc.csv_cells[number]
                cells[0] = f"SYN-{self.case.case_id}-{number - 1}"
                if not cells[1]:
                    cells[1] = stamp
                continue
            if forced:
                party, other = parties[0], forced.pop(0)
            else:
                party, other = self.stream.choice(parties), self.stream.choice(pool)
            outbound = self.stream.chance(55)
            calling, called = (party, other) if outbound else (other, party)
            sms = self.stream.chance(20)
            cells = [
                f"SYN-{self.case.case_id}-{number - 1}",
                stamp,
                "0" if sms else str(self.stream.between(5, 600)),
                calling.raw_text,
                called.raw_text,
                "SMS" if sms else "VOICE",
                f"SYN-CELL-{self.stream.between(1, 60):04d}",
                self.stream.choice(towers),
            ]
            self.world.put_row(self.case, name, cells, [calling, called], line=number)

    def fill_bank(self, name: str, rows: int, accounts: list[BankAccount]) -> None:
        doc = self.case.doc(name)
        total = max(doc.last + 3, 1 + rows)
        for number in range(2, total + 1):
            if doc.occupied(number):
                cells = doc.csv_cells[number]
                cells[0] = f"SYN-{self.case.case_id}-T{number - 1}"
                if not cells[1]:
                    cells[1] = (self.day_base + timedelta(days=number // 4)).isoformat()
                if not cells[8]:
                    cells[8] = str(self.stream.between(100, 49_999))
                continue
            account = self.stream.choice(accounts)
            kind = self.stream.below(100)
            ents = [account.entity]
            if account.holder is not None:
                ents.append(account.holder)
            if kind < 50:
                peer = self.phone_entity(self.alloc.phone(self.region), 0)
                ents.append(peer)
                counterparty = f"{peer.raw_text}@upi"
            elif kind < 70:
                other = self.account_entity()
                ents.append(other)
                counterparty = other.raw_text
            else:
                counterparty = draw_name(self.stream, "en").upper()
            cells = [
                f"SYN-{self.case.case_id}-T{number - 1}",
                (self.day_base + timedelta(days=number // 4)).isoformat(),
                account.entity.raw_text,
                account.ifsc,
                account.holder_text,
                "DR" if self.stream.chance(50) else "CR",
                counterparty,
                self.stream.choice(NARRATIONS),
                str(self.stream.between(100, 49_999)),
                "",
            ]
            self.world.put_row(self.case, name, cells, ents, line=number)


def finish_balances(doc: FileDoc) -> None:
    """Running integer balance per account, in line order."""
    balances: dict[str, int] = {}
    for number in sorted(doc.csv_cells):
        cells = doc.csv_cells[number]
        account = cells[2]
        balance = balances.get(account, 1_000_000)
        amount = int(cells[8])
        balance = balance - amount if cells[5] == "DR" else balance + amount
        balances[account] = balance
        cells[9] = str(balance)


def render_doc(case: Case, doc: FileDoc) -> str:
    kind = file_kind(doc.name)
    lines: list[str] = []
    if kind == "fir":
        lines = [
            BANNER,
            f"FIR No: SYN-{case.case_id}/{case.fir_date[:4]}",
            f"Date of FIR: {case.fir_date}",
            f"Date of occurrence: {case.occurrence_date}",
            f"Police Station: {case.station}",
            f"District: {case.district}",
            f"State: {case.state}",
            f"Sections: {case.sections}",
            case.complainant,
            "",
            "NARRATIVE:",
        ]
    elif kind == "notes":
        lines = [BANNER, f"# Officer notes, case {case.case_id}"]
    elif kind == "cdr":
        lines = [csv_line(CDR_HEADER)]
    elif kind == "bank":
        finish_balances(doc)
        lines = [csv_line(BANK_HEADER)]
    elif kind == "sdr":
        lines = [csv_line(["msisdn", "subscriber_name", "relative_name", "locality",
                           "district", "activated_on"])]  # fmt: skip
    total = max([doc.last, len(lines)])
    for number in range(len(lines) + 1, total + 1):
        if number in doc.text:
            lines.append(doc.text[number])
        elif number in doc.csv_cells:
            lines.append(csv_line(doc.csv_cells[number]))
        else:
            raise ValueError(f"{case.case_id}/{doc.name}:{number} left unfilled")
    return "\n".join(lines) + "\n"
