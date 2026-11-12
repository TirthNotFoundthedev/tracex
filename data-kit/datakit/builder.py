"""Helpers for writing planted fixtures: cases, entities, lines, rings and expected links."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from datakit.fill import note_line, officer
from datakit.model import Case, Entity, World
from datakit.pools import KIT_ROOT, load_pools
from datakit.rng import Stream
from datakit.text import (
    PersonText,
    account_extra,
    clause,
    phone_extra,
    phone_format,
    role_sentence,
    vehicle_extra,
)

Gate = str | tuple[str, str]
Attr = tuple[Entity, Entity, str]


def load_jurisdictions() -> dict[str, tuple[str, int, list[str]]]:
    data = json.loads((KIT_ROOT / "seed" / "jurisdictions.json").read_text("utf-8"))
    return {
        d["name"]: (s["name"], d["id_digit"], d["stations"])
        for s in data["states"]
        for d in s["districts"]
    }


def b2_key(number: str) -> str:
    return number[:2] + "".join(sorted(number))


@dataclass
class PlantedPhones:
    """Planted phones from 9000000000..9000099999 without accidental B2 digit-set twins."""

    stream: Stream
    used: dict[str, str] = field(default_factory=dict)

    def reserve(self, *numbers: str) -> None:
        for number in numbers:
            self.used[number] = b2_key(number)

    def alloc(self, count: int = 1) -> list[str]:
        out: list[str] = []
        while len(out) < count:
            number = str(9_000_000_000 + self.stream.between(0, 99_999))
            if number in self.used or b2_key(number) in self.used.values():
                continue
            self.used[number] = b2_key(number)
            out.append(number)
        return out


@dataclass
class RingResult:
    lines: dict[str, list[tuple[str, int]]] = field(default_factory=dict)
    entities: dict[str, list[Entity]] = field(default_factory=dict)


class Builder:
    def __init__(self, world: World, planted_ids: list[str], phones: PlantedPhones) -> None:
        self.w = world
        self.index = {cid: i for i, cid in enumerate(planted_ids)}
        self.phones = phones
        self.jur = load_jurisdictions()
        self.districts = {v[1]: (k, v[0], v[2]) for k, v in self.jur.items()}
        self.keep: dict[str, Entity] = {}

    # cases -----------------------------------------------------------------------
    def case(
        self,
        case_id: str,
        lang: str = "en",
        station: str | None = None,
        fir_date: str | None = None,
        in_b01: bool = True,
    ) -> Case:
        idx = self.index[case_id]
        district, state, stations = self.districts[int(case_id[2])]
        when = date.fromisoformat(fir_date) if fir_date else date(2026, 1, 5) + timedelta(3 * idx)
        case = Case(
            case_id=case_id,
            district=district,
            state=state,
            station=station or stations[idx % 2],
            lang=lang,
            index=idx,
            planted=True,
            fir_date=when.isoformat(),
            occurrence_date=(when - timedelta(2)).isoformat(),
            sections=f"SYN-S{100 + idx}, SYN-S{200 + idx % 7}",
            in_b01=in_b01,
            day_base=(date(2025, 1, 1) + timedelta(3 * idx)).isoformat(),
        )
        self.w.cases[case_id] = case
        return case

    # entities ----------------------------------------------------------------------
    def per(self, c: Case, gt: str, raw: str, norm: str, **attrs: Any) -> Entity:
        return self.w.entity(gt, "PERSON", c, raw, norm, **attrs)

    def org(self, c: Case, gt: str, raw: str, norm: str, **attrs: Any) -> Entity:
        return self.w.entity(gt, "ORG", c, raw, norm, **attrs)

    def phn(self, c: Case, gt: str, number: str, style: int = 0, raw: str | None = None) -> Entity:
        return self.w.entity(gt, "PHONE", c, raw or phone_format(number, style), number)

    def acc(self, c: Case, gt: str, number: str, ifsc: str | None = None) -> Entity:
        attrs = {"bank_ifsc": ifsc} if ifsc else {}
        return self.w.entity(gt, "ACCOUNT", c, number, number, **attrs)

    def veh(self, c: Case, gt: str, raw: str, norm: str | None = None) -> Entity:
        value = norm or raw.replace(" ", "").replace("-", "").upper()
        return self.w.entity(gt, "VEHICLE", c, raw, value)

    # lines -----------------------------------------------------------------------------
    def fir_person(
        self,
        c: Case,
        person: Entity,
        role: str,
        *,
        phone: Entity | None = None,
        acct: Entity | None = None,
        ifsc: str | None = None,
        plate: Entity | None = None,
        line: int | None = None,
        **stated: Any,
    ) -> int:
        """One FIR paragraph about a person; only the stated attributes appear in the text."""
        text = PersonText(
            name=person.raw_text,
            relation=stated.get("relation"),
            relative=stated.get("relative"),
            age=stated.get("age"),
            dob=stated.get("dob_text"),
            gender=stated.get("gender"),
            village=stated.get("village"),
            mohalla=stated.get("mohalla"),
        )
        ents = [person]
        attrs: list[Attr] = []
        if phone:
            text.extras.append(phone_extra(c.lang, phone.raw_text))
            ents.append(phone)
            attrs.append((person, phone, "OWNS"))
        if acct:
            text.extras.append(account_extra(c.lang, acct.raw_text, ifsc))
            ents.append(acct)
            attrs.append((person, acct, "OWNS"))
        if plate:
            text.extras.append(vehicle_extra(c.lang, plate.raw_text))
            ents.append(plate)
        for key in ("age", "gender", "village", "mohalla"):
            if stated.get(key) is not None:
                person.attributes["locality" if key in ("village", "mohalla") else key] = stated[
                    key
                ]
        if stated.get("dob"):
            person.attributes["dob"] = stated["dob"]
        if stated.get("relative"):
            person.attributes["relative"] = {
                "relation": stated["relation"],
                "name": stated["relative"],
            }
        sentence = role_sentence(c.lang, role, clause(c.lang, text))
        return self.w.put_text(c, "fir.txt", sentence, ents, attrs, line=line)

    def fir(self, c: Case, text: str, ents: list[Entity], line: int | None = None) -> int:
        return self.w.put_text(c, "fir.txt", text, ents, line=line)

    def note(
        self,
        c: Case,
        text: str,
        ents: list[Entity],
        attrs: list[Attr] | None = None,
        *,
        line: int | None = None,
        file: str = "notes.txt",
        who: str | None = None,
    ) -> int:
        stream = Stream(0, f"note:{c.case_id}:{file}:{line}:{text}")
        when = date.fromisoformat(c.fir_date) + timedelta(days=line or 3)
        full = note_line(when, who or officer(stream), text)
        return self.w.put_text(c, file, full, ents, attrs, line=line)

    def cdr(
        self,
        c: Case,
        calling: Entity,
        called: Entity,
        *,
        line: int | None = None,
        file: str = "cdr.csv",
        when: str = "",
        tower: str = "",
    ) -> int:
        place = tower or load_pools().towers[c.district][0]
        cells = ["", when, "45", calling.raw_text, called.raw_text, "VOICE", "SYN-CELL-0001", place]
        return self.w.put_row(c, file, cells, [calling, called], line=line)

    def bank(
        self,
        c: Case,
        acct: Entity,
        *,
        ifsc: str = "",
        holder: Entity | None = None,
        direction: str = "DR",
        counterparty: str = "CASH DEPOSIT",
        peer: Entity | None = None,
        line: int | None = None,
        file: str = "bank.csv",
    ) -> int:
        ents = [acct]
        if holder:
            ents.append(holder)
        if peer:
            ents.append(peer)
            counterparty = f"{peer.raw_text}@upi"
        cells = [
            "", "", acct.raw_text, ifsc, holder.raw_text if holder else "",
            direction, counterparty, "UPI transfer", "", "",
        ]  # fmt: skip
        attrs: list[Attr] = [(holder, acct, "OWNS")] if holder else []
        return self.w.put_row(c, file, cells, ents, attrs, line=line)

    def sdr(
        self,
        c: Case,
        phone: Entity,
        subscriber: Entity,
        *,
        relative: str = "",
        locality: str = "",
        district: str = "",
        line: int | None = None,
    ) -> int:
        cells = [phone.raw_text, subscriber.raw_text, relative, locality, district, "2022-04-09"]
        return self.w.put_row(
            c, "sdr.csv", cells, [phone, subscriber], [(subscriber, phone, "REGISTERED_TO")], line
        )

    # rings --------------------------------------------------------------------------
    def ring(
        self,
        tag: str,
        ac: list[str],
        members: Sequence[tuple[Case, Entity | tuple[Entity, str, Entity | None]]],
        numbers: list[str],
        *,
        when: list[str] | None = None,
        towers: list[str] | None = None,
    ) -> RingResult:
        """Each member calls (CDR) or pays (bank, UPI) the same numbers. Returns lines per case.

        A member is (case, owner_phone) for CDR or (case, (account, ifsc, holder)) for bank.
        """
        result = RingResult()
        per_number: list[list[Entity]] = [[] for _ in numbers]
        for case, owner in members:
            result.lines[case.case_id] = []
            result.entities[case.case_id] = []
            for i, number in enumerate(numbers):
                ent = self.phn(case, f"{tag}.PHN.R{i + 1}.{case.case_id}", number)
                per_number[i].append(ent)
                result.entities[case.case_id].append(ent)
                if isinstance(owner, tuple):
                    acct, ifsc, holder = owner
                    line = self.bank(case, acct, ifsc=ifsc, holder=holder, peer=ent)
                    result.lines[case.case_id].append(("bank.csv", line))
                else:
                    stamp = when[i] if when else ""
                    place = towers[i] if towers else ""
                    line = self.cdr(case, owner, ent, when=stamp, tower=place)
                    result.lines[case.case_id].append(("cdr.csv", line))
        for i, ents in enumerate(per_number):
            if len(ents) > 1:
                self.ident_links(f"{tag}-R{i + 1}", ac, ents)
        return result

    # ground truth records ---------------------------------------------------------------
    def ident_links(
        self,
        tag: str,
        ac: list[str],
        ents: list[Entity],
        *,
        batch_min: str = "b01",
        ac_map: dict[tuple[int, int], list[str]] | None = None,
        bmin: dict[tuple[int, int], str] | None = None,
    ) -> None:
        """Same identifier in several cases: one cross-case group, AUTO 100 for every pair."""
        self.w.group(f"G-{tag}", "cross_case", ents)
        for i, first in enumerate(ents):
            for j in range(i + 1, len(ents)):
                self.link(
                    f"EL-{tag}-{i}-{j}",
                    (ac_map or {}).get((i, j), ac if ac_map is None else []),
                    first.type,
                    first,
                    ents[j],
                    "AUTO",
                    "HIGH",
                    100,
                    "exact",
                    [],
                    ["ID_EXACT"],
                    batch_min=(bmin or {}).get((i, j), batch_min),
                )

    def link(
        self,
        link_id: str,
        ac: list[str],
        type_: str,
        a: Entity,
        b: Entity,
        state: str,
        band: str,
        value: float,
        mode: str,
        gates: list[Gate],
        kinds: list[str],
        *,
        extra_cites: list[tuple[str, str, int]] | None = None,
        batch_min: str = "b01",
        harness: str | None = None,
        trap: str | None = None,
    ) -> None:
        first, second = sorted((a, b), key=lambda e: e.gt_id)
        if mode == "exact" and not (ac and set(ac) <= EXACT_ACS):
            mode = "band"
        self.w.links.append(
            {
                "id": link_id,
                "ac": ac,
                "type": type_,
                "a": first.gt_id,
                "b": second.gt_id,
                "batch_min": batch_min,
                "state": state,
                "band": band,
                "score": {"value": value, "mode": mode},
                "gates_failed": [
                    g if isinstance(g, str) else {"gate": g[0], "template_key": g[1]} for g in gates
                ],
                "evidence_kinds": kinds,
                "harness": harness,
                "_extra": extra_cites or [],
                **({"trap": trap} if trap else {}),
            }
        )

    def non_link(self, link_id: str, ac: list[str], trap: str, a: Entity, b: Entity, forbid: str,
                 why: str) -> None:  # fmt: skip
        first, second = sorted((a, b), key=lambda e: e.gt_id)
        self.w.non_links.append(
            {
                "id": link_id,
                "ac": ac,
                "trap": trap,
                "a": first.gt_id,
                "b": second.gt_id,
                "forbid": forbid,
                "why": why,
            }
        )

    def scenario(self, sid: str, ac: list[str], steps: list[tuple[str, str, str, str]]) -> None:
        self.w.scenarios.append(
            {
                "id": sid,
                "ac": ac,
                "steps": [
                    {"actor_role": r, "action": a, "target": t, "expect": e} for r, a, t, e in steps
                ],
            }
        )


EXACT_ACS = {"AC-01", "AC-07", "AC-08", "AC-09", "AC-10", "AC-12", "AC-14", "AC-17", "AC-22"}
