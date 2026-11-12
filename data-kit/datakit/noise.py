"""Noise: private filler for planted cases and the noise cases with their own ground truth."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from datakit.alloc import Allocators
from datakit.builder import load_jurisdictions
from datakit.fill import BankAccount, Filler, Name, draw_name, phone_style
from datakit.model import Case, Entity, World, nfc
from datakit.pools import NamePair, load_pools
from datakit.rng import Stream
from datakit.text import (
    PersonText,
    account_extra,
    base_lang,
    clause,
    number_used,
    phone_extra,
    phone_format,
    role_sentence,
    shared_note,
    shared_wording,
    vehicle_extra,
)

Unit = tuple[str, list[Entity], list[tuple[Entity, Entity, str]]]
MONTHS = (
    "January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December",
)  # fmt: skip
TOP_NAMES = ("Rajesh", "Sunil", "Anil", "Vijay")


@dataclass(frozen=True)
class TierParams:
    per_district: int
    cdr_rows: tuple[int, int]
    bank_rows: tuple[int, int]


TIERS = {
    "small": TierParams(15, (40, 80), (15, 40)),
    "demo": TierParams(150, (100, 300), (30, 120)),
}
PLANTED_CDR = (40, 80)
PLANTED_BANK = (15, 40)


# planted cases ---------------------------------------------------------------------------
def fill_planted(world: World, seed: int, alloc: Allocators) -> None:
    """Fill every planted case with case-private noise; independent of the tier."""
    used_names: set[str] = set()
    for case_id in sorted(world.cases, key=case_sort_key):
        case = world.cases[case_id]
        stream = Stream(seed, f"fill:{case_id}")
        f = Filler(world, case, stream, alloc, "planted", date.fromisoformat(case.day_base))
        case.doc("fir.txt")
        complainant, name = _unique_complainant(f, used_names)
        case.complainant = f"Complainant: {name.display}"
        complainant.mentions.append(("fir.txt", 9))
        witness_name = _unique_name(stream, case.lang, used_names)
        witness = f.noise_entity("PERSON", witness_name.display, witness_name.normalized)
        sentence = role_sentence(case.lang, "witness", witness_name.display)
        f.fill_fir([(sentence, [witness], [])], stream.between(3, 8))
        for doc_name in sorted(case.docs):
            doc = case.docs[doc_name]
            kind = doc.kind
            b02 = case.batch_of(doc) == "b02"
            if kind == "notes":
                f.fill_notes(doc_name, 0 if b02 else stream.between(2, 6))
            elif kind == "cdr":
                rows = 0 if doc_name == "cdr-02.csv" else stream.between(*PLANTED_CDR)
                parties = [f.new_phone() for _ in range(2)]
                pool = [f.new_phone() for _ in range(6)]
                f.fill_cdr(doc_name, rows, parties, pool)
            elif kind == "bank":
                holder_name = _unique_name(stream, "en", used_names)
                holder = f.noise_entity("PERSON", holder_name.upper(), holder_name.normalized)
                account = f.account_entity()
                account_row = BankAccount(account, "SYNB0000123", holder, holder_name.upper())
                f.fill_bank(doc_name, stream.between(*PLANTED_BANK), [account_row])


def _unique_name(stream: Stream, lang: str, used: set[str]) -> Name:
    while True:
        name = draw_name(stream, lang)
        if name.normalized not in used:
            used.add(name.normalized)
            return name


def _unique_complainant(f: Filler, used: set[str]) -> tuple[Entity, Name]:
    name = _unique_name(f.stream, f.case.lang, used)
    return f.noise_entity("PERSON", name.display, name.normalized), name


def case_sort_key(case_id: str) -> tuple[int, int]:
    return int(case_id[2]), int(case_id[3:])


# noise cases ------------------------------------------------------------------------------
@dataclass
class Ident:
    idx: int
    given: NamePair
    surname: NamePair
    gender: str
    gender_stated: bool
    age: int | None = None
    dob: str | None = None
    relative: tuple[NamePair, NamePair] | None = None
    relation: str | None = None
    locality: tuple[str, str] | None = None
    alias: NamePair | None = None
    kind: str = "fresh"
    phone: str | None = None
    account: str | None = None
    plate: str | None = None
    cases: list[str] = field(default_factory=list)
    protected: bool = False
    ents: dict[str, Entity] = field(default_factory=dict)

    @property
    def normalized(self) -> str:
        return f"{self.given.roman} {self.surname.roman}".lower()


def _fresh(stream: Stream, idx: int, villages: list[str], mohallas: list[str]) -> Ident:
    pools = load_pools()
    gender = "female" if stream.chance(20) else "male"
    given = stream.zipf(pools.first_f if gender == "female" else pools.first_m)
    ident = Ident(idx, given, stream.choice(pools.surnames), gender, stream.chance(50))
    if stream.chance(50):
        ident.age = stream.between(19, 68)
    if stream.chance(10):
        ident.dob = _dob(stream)
        ident.age = None
    if stream.chance(40):
        rel_given = stream.zipf(pools.first_m if stream.chance(80) else pools.first_f)
        ident.relative = (rel_given, ident.surname)
        ident.relation = "s/o" if gender == "male" else stream.choice(["d/o", "w/o"])
    if stream.chance(40):
        if stream.chance(60):
            ident.locality = ("village", stream.choice(villages))
        else:
            ident.locality = ("mohalla", stream.choice(mohallas))
    if stream.chance(5):
        ident.alias = stream.zipf(pools.first_m)
    return ident


def _dob(stream: Stream) -> str:
    return f"{stream.between(1960, 2005)}-{stream.between(1, 12):02d}-{stream.between(1, 28):02d}"


def _dob_text(stream: Stream, iso: str) -> str:
    year, month, day = iso.split("-")
    style = stream.below(3)
    if style == 0:
        return f"{day}-{month}-{year}"
    if style == 1:
        return f"{day}/{month}/{year}"
    return f"{int(day)} {MONTHS[int(month) - 1]} {year}"


@dataclass
class NoiseCase:
    case: Case
    persons: list[Ident] = field(default_factory=list)
    hub: bool = False
    shared_note: bool = False
    sdr: bool = False
    recurring_phones: list[str] = field(default_factory=list)


def build_noise(world: World, tier: str, seed: int, alloc: Allocators) -> None:
    params = TIERS[tier]
    plan = Stream(seed, "noise:plan")
    jur = load_jurisdictions()
    pools = load_pools()
    districts = {v[1]: (k, v[0], v[2]) for k, v in jur.items()}
    ids = [f"C-{d}{50 + i}" for d in (1, 2, 3, 4) for i in range(params.per_district)]
    total = len(ids)
    langs = _language_quota(plan, total)
    noise = [_make_case(world, cid, langs[i], districts, plan) for i, cid in enumerate(ids)]
    sizes = [plan.between(4, 10) for _ in noise]
    n_persons = sum(sizes)
    counter = [0]

    def new_ident() -> Ident:
        counter[0] += 1
        return _fresh(plan, counter[0], pools.villages, pools.mohallas)

    # recurring identities (12% of person entities)
    target = round(0.12 * n_persons)
    copies = 0
    recurring: list[Ident] = []
    while target - copies >= 2:
        k = min(plan.between(2, 3), target - copies)
        free = [n for n in noise if len(n.persons) < sizes[noise.index(n)] - 1]
        if len(free) < k:
            break
        chosen = plan.sample(free, k)
        ident = new_ident()
        ident.protected = True
        point = plan.below(100)
        if point < 60:
            ident.kind, ident.phone = "phone", alloc.phone("noise")
        elif point < 85:
            ident.kind, ident.account = "account", alloc.account("noise")
        else:
            ident.kind = "none"
            ident.age = ident.age or plan.between(20, 60)
            ident.locality = ident.locality or ("village", plan.choice(pools.villages))
            ident.relative = ident.relative or (plan.zipf(pools.first_m), ident.surname)
            ident.relation = ident.relation or "s/o"
        recurring.append(ident)
        for n in chosen:
            n.persons.append(ident)
            ident.cases.append(n.case.case_id)
        copies += k
    for n, size in zip(noise, sizes, strict=True):
        while len(n.persons) < size:
            ident = new_ident()
            ident.cases.append(n.case.case_id)
            n.persons.append(ident)
        plan.shuffle(n.persons)
        _complainant_first(n, new_ident)

    fresh = [p for n in noise for p in n.persons if not p.protected and len(p.cases) == 1]
    # look-alikes: same name, different DOB, different cases (about 2% of persons)
    look_pairs: list[tuple[Ident, Ident]] = []
    pool = list(fresh)
    plan.shuffle(pool)
    for _ in range(round(0.01 * n_persons)):
        first = pool.pop()
        second = next((p for p in pool if p.cases[0] != first.cases[0]), None)
        if second is None:
            break
        pool.remove(second)
        for p in (first, second):
            p.protected = True
        second.given, second.surname, second.gender = first.given, first.surname, first.gender
        first.dob, second.dob = _dob(plan), _dob(plan)
        first.age = second.age = None
        look_pairs.append((first, second))
    _top_up_common_names(noise, plan)
    _distinct_names_per_case(noise, Stream(seed, "noise:names"))

    # designated material
    en_cases = [n for n in noise if n.case.lang == "en"]
    units = max(1, total // 50)
    for n in plan.sample(en_cases, 2 * units):
        n.shared_note = True
    for n in plan.sample(noise, units):
        n.hub = True
    multi = _multi_user_accounts(noise, plan, alloc, units)
    sdr_cases = plan.sample(noise, round(0.3 * total))
    for n in sdr_cases:
        n.sdr = True
    recur_phones = _recurring_phones(noise, plan, alloc, max(2, total // 7))

    # write every case
    for n in noise:
        _write_case(world, n, params, seed, alloc, multi, recur_phones, pools.villages)
    _groups(world, recurring, recur_phones, multi)
    for first, second in look_pairs:
        a, b = first.ents[first.cases[0]], second.ents[second.cases[0]]
        x, y = sorted((a, b), key=lambda e: e.gt_id)
        world.non_links.append(
            {
                "id": f"NL-NZ-{x.gt_id}-{y.gt_id}",
                "ac": [],
                "trap": "TR-19",
                "a": x.gt_id,
                "b": y.gt_id,
                "forbid": "AUTO",
                "why": "Same common name, different date of birth, different people",
            }
        )


def _distinct_names_per_case(noise: list[NoiseCase], stream: Stream) -> None:
    """No two noise persons of one case share a normalized name, and no alias equals another
    person's name: from the case text they would read as one person. The later colliding
    identity gets another surname, redrawn from its own stream so no other draw moves. A
    protected identity (recurring, or half of a look-alike pair) takes its twins along, so
    true cross-case groups and look-alike pairs keep their shared name; the pass repeats until
    no case collides."""
    pools = load_pools()
    everyone = [p for n in noise for p in n.persons]
    changed = True
    for _ in range(100):
        if not changed:
            break
        changed = False
        for n in noise:
            kept: set[str] = set()
            for ident in sorted(n.persons, key=lambda p: not p.protected):
                if ident.normalized in kept:
                    old = (ident.given.roman, ident.surname.roman)
                    twins = [
                        p
                        for p in everyone
                        if (p is ident)
                        or (
                            ident.protected
                            and p not in n.persons
                            and (p.given.roman, p.surname.roman) == old
                        )
                    ]
                    surname = stream.choice(pools.surnames)
                    for p in twins:
                        p.surname = surname
                    changed = True
                kept.add(ident.normalized)
        names_by_case = {id(n): {p.normalized for p in n.persons} for n in noise}
        for n in noise:
            for ident in n.persons:
                while ident.alias is not None and ident.alias.roman.lower() in names_by_case[
                    id(n)
                ] - {ident.normalized}:
                    ident.alias = stream.zipf(pools.first_m)


def _language_quota(plan: Stream, total: int) -> list[str]:
    quota = {"en": round(0.40 * total), "hi": round(0.25 * total), "hi-latn": round(0.25 * total)}
    langs = [lang for lang, count in quota.items() for _ in range(count)]
    langs += ["mixed"] * (total - len(langs))
    plan.shuffle(langs)
    return langs


def _make_case(
    world: World,
    cid: str,
    lang: str,
    districts: dict[int, tuple[str, str, list[str]]],
    plan: Stream,
) -> NoiseCase:
    district, state, stations = districts[int(cid[2])]
    base = date(2025, 1, 1) + timedelta(days=plan.between(0, 600))
    case = Case(
        case_id=cid,
        district=district,
        state=state,
        station=plan.choice(stations),
        lang=lang,
        index=int(cid[3:]),
        planted=False,
        fir_date=(base + timedelta(5)).isoformat(),
        occurrence_date=base.isoformat(),
        sections=f"SYN-S{plan.between(100, 399)}, SYN-S{plan.between(400, 499)}",
        day_base=base.isoformat(),
    )
    world.cases[cid] = case
    return NoiseCase(case)


def _complainant_first(n: NoiseCase, new_ident: Any) -> None:
    """Put an identity without identifiers first: it becomes the header complainant."""
    for i, p in enumerate(n.persons):
        if p.kind in ("fresh", "none") and not p.protected:
            n.persons.insert(0, n.persons.pop(i))
            return


def _top_up_common_names(noise: list[NoiseCase], plan: Stream) -> None:
    pools = load_pools()
    top = {p.roman: p for p in pools.first_m if p.roman in TOP_NAMES}
    people = [p for n in noise for p in n.persons]

    def count(name: str) -> int:
        return sum(1 for p in people if p.given.roman == name)

    movable = [p for p in people if not p.protected and p.gender == "male" and len(p.cases) == 1]
    plan.shuffle(movable)
    for name in TOP_NAMES:
        while count(name) < 24 and movable:
            movable.pop().given = top[name]


def _multi_user_accounts(
    noise: list[NoiseCase], plan: Stream, alloc: Allocators, units: int
) -> list[tuple[str, list[tuple[str, Ident]]]]:
    out = []
    for _ in range(units):
        number = alloc.account("noise")
        picks: list[tuple[str, Ident]] = []
        for n in plan.sample(noise, 6):
            candidates = [p for p in n.persons[1:] if not p.protected and p.account is None]
            if not candidates:
                continue
            ident = plan.choice(candidates)
            if any(
                ident.given.roman == o.given.roman or ident.surname.roman == o.surname.roman
                for _, o in picks
            ):
                continue
            ident.account = number
            ident.protected = True
            picks.append((n.case.case_id, ident))
            if len(picks) == 2:
                break
        out.append((number, picks))
    return out


def _recurring_phones(
    noise: list[NoiseCase], plan: Stream, alloc: Allocators, count: int
) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for _ in range(count):
        number = alloc.phone("noise")
        cases = plan.sample(noise, 2)
        out[number] = [n.case.case_id for n in cases]
        for n in cases:
            n.recurring_phones.append(number)
    return out


def _person_text(n: NoiseCase, ident: Ident, stream: Stream) -> tuple[Name, PersonText]:
    lang = n.case.lang
    native = lang == "hi" and stream.chance(60)
    shown = (
        f"{ident.given.devanagari} {ident.surname.devanagari}"
        if native
        else f"{ident.given.roman} {ident.surname.roman}"
    )
    name = Name(nfc(shown), ident.normalized, ident.given, ident.surname, ident.gender)
    text = PersonText(name=name.display)
    if ident.alias:
        text.name = f"{name.display} urf {ident.alias.devanagari if native else ident.alias.roman}"
    if ident.relative and ident.relation:
        rel_given, rel_surname = ident.relative
        text.relation = ident.relation
        text.relative = nfc(
            f"{rel_given.devanagari} {rel_surname.devanagari}"
            if native
            else f"{rel_given.roman} {rel_surname.roman}"
        )
    if ident.dob:
        text.dob = _dob_text(stream, ident.dob)
    elif ident.age is not None:
        text.age = ident.age
    if ident.gender_stated:
        text.gender = ident.gender
    if ident.locality:
        setattr(text, ident.locality[0], ident.locality[1])
    return name, text


def _write_case(
    world: World,
    n: NoiseCase,
    params: TierParams,
    seed: int,
    alloc: Allocators,
    multi: list[tuple[str, list[tuple[str, Ident]]]],
    recur: dict[str, list[str]],
    villages: list[str],
) -> None:
    case = n.case
    stream = Stream(seed, f"noise:{case.case_id}")
    f = Filler(world, case, stream, alloc, "noise", date.fromisoformat(case.day_base))
    lang = case.lang
    units: list[Unit] = []
    case_phones: list[Entity] = []
    case_accounts: dict[str, Entity] = {}
    for position, ident in enumerate(n.persons):
        name, text = _person_text(n, ident, stream)
        attrs = _attributes(ident, text)
        entity = f.noise_entity("PERSON", text.name, ident.normalized, **attrs)
        ident.ents[case.case_id] = entity
        ents = [entity]
        links: list[tuple[Entity, Entity, str]] = []
        extras: list[str] = []
        phone_value = ident.phone
        if phone_value is None and position > 0 and not ident.protected and stream.chance(35):
            phone_value = alloc.phone("noise")
        if phone_value:
            phone = f.phone_entity(phone_value)
            case_phones.append(phone)
            ents.append(phone)
            links.append((entity, phone, "OWNS"))
            extras.append(phone_extra(lang, phone.raw_text))
        if ident.account:
            account = _account_for(f, case_accounts, ident.account)
            ifsc = stream.choice(["SYNB0000123", "FAKE0000456", None])
            ents.append(account)
            links.append((entity, account, "OWNS"))
            extras.append(account_extra(lang, account.raw_text, ifsc))
        elif position > 0 and not ident.protected and stream.chance(10) and len(case_accounts) < 2:
            value = alloc.account("noise")
            ident.account = value
            account = _account_for(f, case_accounts, value)
            ents.append(account)
            links.append((entity, account, "OWNS"))
            extras.append(account_extra(lang, account.raw_text, None))
        if position > 0 and not ident.protected and stream.chance(10) and not n.shared_note:
            plate_value = alloc.plate("noise")
            plate = f.noise_entity("VEHICLE", _plate_text(plate_value, stream), plate_value)
            ents.append(plate)
            extras.append(vehicle_extra(lang, plate.raw_text))
        if position == 0:
            case.complainant = "Complainant: " + clause(lang, text)
            entity.mentions.append(("fir.txt", 9))
            if len(ents) > 1:
                body = ", ".join([text.name, *extras])
                units.append((role_sentence(lang, "complainant", body), ents, links))
            continue
        text.extras = extras
        role = "accused" if stream.chance(40) else "witness"
        units.append((role_sentence(lang, role, clause(lang, text)), ents, links))
    if not case_phones:
        phone = f.new_phone()
        case_phones.append(phone)
    notes_extra: list[Unit] = []
    shared_pair = list(n.persons[1:3])
    if n.shared_note and len(shared_pair) == 2 and len(case_phones) >= 1:
        shared = f.new_phone()
        a, b = (p.ents[case.case_id] for p in shared_pair)
        text_note = shared_note(lang, shared.raw_text, shared_wording(lang), a.raw_text, b.raw_text)
        notes_extra.append((text_note, [shared, a, b], [(a, shared, "OWNS"), (b, shared, "OWNS")]))
    if stream.chance(60):
        for _sentence, _ents, owned in units:
            phone_links = [link for link in owned if link[1].type == "PHONE"]
            if phone_links:
                person, phone_ent, _code = phone_links[0]
                notes_extra.append(
                    (number_used(lang, phone_ent.raw_text, person.raw_text), [phone_ent, person],
                     [(person, phone_ent, "OWNS")])
                )  # fmt: skip
                break
    paragraphs = stream.between(3, 8)
    stream.shuffle(units)
    f.fill_fir(units, paragraphs)
    f.fill_notes("notes.txt", stream.between(2, 6), notes_extra)
    # CDR
    parties = case_phones[:3]
    pool_size = 34 if n.hub else stream.between(12, 18)
    pool = [f.new_phone() for _ in range(pool_size)]
    for number in n.recurring_phones:
        pool[stream.below(len(pool))] = f.phone_entity(number, 0)
    f.fill_cdr("cdr.csv", stream.between(*params.cdr_rows), parties, pool, hub=n.hub)
    # bank
    holder_ident = n.persons[min(1, len(n.persons) - 1)]
    accounts = []
    owners = [p for p in n.persons if p.account]
    statement = owners[0] if owners else holder_ident
    value = statement.account or alloc.account("noise")
    account = _account_for(f, case_accounts, value)
    holder_entity = statement.ents[case.case_id]
    holder_row = f.noise_entity("PERSON", _upper_name(statement), statement.normalized)
    world.group(f"G-NZ-W{case.case_id}-{holder_row.gt_id}", "within_case",
                [holder_entity, holder_row], "noise")  # fmt: skip
    ifsc = stream.choice(["SYNB0000123", "FAKE0000456", ""])
    accounts.append(BankAccount(account, ifsc, holder_row, holder_row.raw_text))
    f.fill_bank("bank.csv", stream.between(*params.bank_rows), accounts)
    if n.sdr:
        _write_sdr(world, f, case_phones, stream, {p.normalized for p in n.persons})


def _account_for(f: Filler, cache: dict[str, Entity], value: str) -> Entity:
    if value not in cache:
        cache[value] = f.account_entity(value)
    return cache[value]


def _upper_name(ident: Ident) -> str:
    return f"{ident.given.roman} {ident.surname.roman}".upper()


def _plate_text(plate: str, stream: Stream) -> str:
    style = stream.below(3)
    if style == 1:
        return f"{plate[:2]}-{plate[2:4]}-{plate[4:6]}-{plate[6:]}"
    if style == 2:
        return f"{plate[:2]} {plate[2:4]} {plate[4:6]} {plate[6:]}".lower()
    return plate


def _attributes(ident: Ident, text: PersonText) -> dict[str, Any]:
    attrs: dict[str, Any] = {}
    if ident.age is not None and text.age is not None:
        attrs["age"] = ident.age
    if ident.dob:
        attrs["dob"] = ident.dob
    if text.gender:
        attrs["gender"] = ident.gender
    if text.relative and ident.relation:
        attrs["relative"] = {"relation": ident.relation, "name": text.relative}
    if ident.locality:
        attrs["locality"] = ident.locality[1]
    if ident.alias:
        attrs["aliases"] = [ident.alias.roman.lower()]
    return attrs


def _write_sdr(
    world: World, f: Filler, case_phones: list[Entity], stream: Stream, used: set[str]
) -> None:
    case = f.case
    rows = stream.between(1, 3)
    for i in range(rows):
        phone = case_phones[i] if i < len(case_phones) else f.new_phone()
        name = _unique_name(stream, "en", used)
        subscriber = f.noise_entity("PERSON", name.display, name.normalized)
        cells = [phone.raw_text, name.display, "", "", case.district, "2023-05-17"]
        world.put_row(case, "sdr.csv", cells, [phone, subscriber],
                      [(subscriber, phone, "REGISTERED_TO")])  # fmt: skip


def _groups(
    world: World,
    recurring: list[Ident],
    recur_phones: dict[str, list[str]],
    multi: list[tuple[str, list[tuple[str, Ident]]]],
) -> None:
    for ident in recurring:
        ents = [ident.ents[c] for c in ident.cases if c in ident.ents]
        if len(ents) > 1:
            world.group(f"G-NZ-P{ident.idx}", "cross_case", ents, "noise")
        if ident.phone or ident.account:
            kind = "PHONE" if ident.phone else "ACCOUNT"
            value = ident.phone or ident.account
            found = [e for e in world.entities if e.type == kind and e.normalized == value]
            if len(found) > 1:
                world.group(f"G-NZ-I{ident.idx}", "cross_case", found, "noise")
    for number in recur_phones:
        found = [e for e in world.entities if e.type == "PHONE" and e.normalized == number]
        if len(found) > 1:
            world.group(f"G-NZ-R{number}", "cross_case", found, "noise")
    for number, _picks in multi:
        found = [e for e in world.entities if e.type == "ACCOUNT" and e.normalized == number]
        if len(found) > 1:
            world.group(f"G-NZ-M{number}", "cross_case", found, "noise")


__all__ = ["TIERS", "build_noise", "fill_planted", "phone_format", "phone_style", "base_lang"]
