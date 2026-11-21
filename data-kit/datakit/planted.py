"""Planted fixtures FX-01..FX-26 and SF-01..SF-09 (data-kit spec sections 5, 5.1, 6, 7)."""

from __future__ import annotations

from datakit.builder import Builder, PlantedPhones
from datakit.model import Case, Entity, World
from datakit.rng import Stream
from datakit.text import phone_format, vehicle_seen

PLANTED_IDS = (
    [f"C-1{n:02d}" for n in range(1, 37)]
    + [f"C-2{n:02d}" for n in range(1, 19)]
    + [f"C-3{n:02d}" for n in range(1, 7)]
    + ["C-401", "C-402"]
)
B02_CASES = {"C-202"}
PINNED_PHONES = (
    "9000014471", "9000021203", "9000028816", "9000014741", "9000081914", "9000081194",
    "9000091827", "9000097821", "9000022310", "9000035562", "9000046120", "9000051234",
    "9000052210", "9000087000", "9000088120", "9000088555", "9000089015", "9000089990",
    "9000079900", "9000062201",
)  # fmt: skip
IFSC_A, IFSC_B = "SYNB0000123", "FAKE0000456"
SHOP = ("shop number", "PCO")


def build_planted(world: World) -> Builder:
    phones = PlantedPhones(Stream(0, "planted-phones"))
    phones.reserve(*PINNED_PHONES)
    b = Builder(world, PLANTED_IDS, phones)
    langs = {"C-107": "hi-latn", "C-109": "hi-latn", "C-120": "hi", "C-210": "en"}
    stations = {"C-107": "PS Kherapur", "C-108": "PS Kherapur"}
    dates = {"C-136": "2024-03-12", "C-218": "2026-02-10"}
    cs: dict[str, Case] = {}
    for cid in PLANTED_IDS:
        cs[cid] = b.case(
            cid,
            langs.get(cid, "en"),
            stations.get(cid),
            dates.get(cid),
            in_b01=cid not in B02_CASES,
        )
    for fn in (fx01, fx02_to_04, fx05_06, fx07, fx08, fx09, fx10, fx11, fx12, fx13, fx14,
               fx17_19, fx21_22, fx26, sf01_03, sf04, sf05_06, sf07_08, access, scenarios):  # fmt: skip
        fn(b, cs)
    return b


def _within(b: Builder, tag: str, *ents: Entity) -> None:
    b.w.group(f"G-{tag}", "within_case", list(ents))


def _cross(b: Builder, tag: str, *ents: Entity) -> None:
    b.w.group(f"G-{tag}", "cross_case", list(ents))


def fx01(b: Builder, cs: dict[str, Case]) -> None:
    a, c = cs["C-101"], cs["C-201"]
    ac = ["AC-01"]
    irfan_a = b.per(a, "FX-01.PER.IRFAN_A", "Mohd. Irfan", "mohammad irfan")
    ph_a = b.phn(a, "FX-01.PHN.4471.A", "9000014471", style=3)
    acct = b.acc(a, "FX-01.ACC.9082", "5010000019082", IFSC_A)
    b.fir_person(a, irfan_a, "accused", phone=ph_a, acct=acct, ifsc=IFSC_A, line=12)
    holder = b.per(a, "FX-01.PER.IRFAN_A_BANK", "MOHD IRFAN", "mohammad irfan")
    _within(b, "FX01-IRFAN-A", irfan_a, holder)
    p1203_a = b.phn(a, "FX-01.PHN.1203.A", "9000021203")
    p8816_a = b.phn(a, "FX-01.PHN.8816.A", "9000028816")
    b.bank(a, acct, ifsc=IFSC_A, holder=holder, peer=p1203_a, line=4)
    b.bank(a, acct, ifsc=IFSC_A, holder=holder, peer=p8816_a, line=7)
    irfan_b = b.per(c, "FX-01.PER.IRFAN_B", "Irfan bhai", "irfan")
    ph_b = b.phn(c, "FX-01.PHN.4471.B", "9000014471")
    b.note(c, "Number 9000014471 is used by Irfan bhai.", [ph_b, irfan_b],
           [(irfan_b, ph_b, "OWNS")], line=3, who="SI RV")  # fmt: skip
    p1203_b = b.phn(c, "FX-01.PHN.1203.B", "9000021203")
    p8816_b = b.phn(c, "FX-01.PHN.8816.B", "9000028816")
    b.cdr(c, p1203_b, ph_b, line=33)
    b.cdr(c, p8816_b, ph_b, line=41)
    _cross(b, "FX01-PER", irfan_a, irfan_b)
    b.ident_links("FX01-1203", ac, [p1203_a, p1203_b])
    b.ident_links("FX01-8816", ac, [p8816_a, p8816_b])
    b.link(
        "EL-FX01-PER", ["AC-01"], "PERSON", irfan_a, irfan_b,
        "AUTO", "HIGH", 85.5, "exact", [],
        ["SHARED_PHONE", "PER_NAME_SIM", "PER_SHARED_NETWORK"],
        extra_cites=[("C-101", "bank.csv", 4), ("C-101", "bank.csv", 7),
                     ("C-201", "cdr.csv", 33), ("C-201", "cdr.csv", 41)],
    )  # fmt: skip
    # 4471 itself joins the access overlay links in `access`; keep the entities for it.
    b.keep = {"ph_a": ph_a, "ph_b": ph_b, "irfan_a": irfan_a, "irfan_b": irfan_b,
              "p1203_a": p1203_a, "p1203_b": p1203_b}  # fmt: skip
    # TR-10 partner is added in fx17_19


def fx02_to_04(b: Builder, cs: dict[str, Case]) -> None:
    # FX-02 vehicle written two ways
    v1 = b.veh(cs["C-103"], "FX-02.VEH.A", "UP32AB1234")
    b.fir(cs["C-103"], "Accused fled on vehicle UP32AB1234 towards the highway.", [v1])
    v2 = b.veh(cs["C-104"], "FX-02.VEH.B", "up 32 ab 1234")
    b.note(cs["C-104"], "Vehicle up 32 ab 1234 was seen near the shop.", [v2])
    b.ident_links("FX02", ["AC-02"], [v1, v2])
    # FX-03 transposed phone, cross-state
    p1 = b.phn(cs["C-105"], "FX-03.PHN.A", "9000081914")
    b.fir(cs["C-105"], "Threat calls were received from mobile 9000081914.", [p1])
    p2 = b.phn(cs["C-302"], "FX-03.PHN.B", "9000081194")
    b.note(cs["C-302"], "Mobile 9000081194 was noted from the call log.", [p2])
    b.link("EL-FX03-PHN", ["AC-03"], "PHONE", p1, p2, "SUGGESTED", "MEDIUM", 55, "band",
           ["G1"], ["PHONE_TRANSPOSED"])  # fmt: skip
    # FX-04 same account digits, different bank
    a1 = b.acc(cs["C-106"], "FX-04.ACC.A", "5010000077345", IFSC_A)
    b.fir(cs["C-106"], "The money was sent to a/c 5010000077345 (IFSC SYNB0000123).", [a1])
    a2 = b.acc(cs["C-203"], "FX-04.ACC.B", "5010000077345", IFSC_B)
    b.bank(cs["C-203"], a2, ifsc=IFSC_B)
    b.non_link("NL-FX04", ["AC-04"], "TR-17", a1, a2, "ANY_EDGE",
               "Same account digits at different banks: ACCT_BANK_CONFLICT veto, nothing stored")  # fmt: skip


def fx05_06(b: Builder, cs: dict[str, Case]) -> None:
    c7, c8 = cs["C-107"], cs["C-108"]
    j1 = b.per(c7, "FX-05.PER.A", "Jaswinder Bhullar", "jaswinder bhullar")
    j2 = b.per(c8, "FX-05.PER.B", "Jasvinder Bhullar", "jasvinder bhullar")
    b.fir_person(c7, j1, "accused", age=34, village="Kherapur", line=12)
    b.fir_person(c8, j2, "accused", age=35, village="Kherapur", line=12)
    _cross(b, "FX05-PER", j1, j2)
    b.link("EL-FX05-PER", ["AC-05"], "PERSON", j1, j2,
           "SUGGESTED", "MEDIUM", 48.2, "band", ["G1", "G2", "G3"], ["PER_NAME_SIM", "PER_AGE_CLOSE",
                                                                    "PER_LOCALITY"])  # fmt: skip
    # b02: the harness REJECTs the pair before b02 (AC-15) and the engine keeps it REJECTED,
    # with the b01 score, band and gates; the scorer accepts REJECTED here because that step
    # is applied (the pair's human steps are keyed on the pair, not on this id).
    b.link("EL-FX05-PER-B02", ["AC-05", "AC-15"], "PERSON", j1, j2, "REJECTED", "MEDIUM", 48.2, "band",
           ["G1", "G2", "G3"], ["PER_NAME_SIM", "PER_AGE_CLOSE", "PER_LOCALITY"],
           batch_min="b02", harness="SC-AC15-AC25")  # fmt: skip
    # b02: the same number in both cases (AC-15, AC-25)
    n1 = b.phn(c7, "FX-05.PHN.A", "9000079900")
    n2 = b.phn(c8, "FX-05.PHN.B", "9000079900")
    b.note(c7, "Number 9000079900 is used by Jaswinder Bhullar.", [n1, j1], [(j1, n1, "OWNS")],
           line=3, file="notes-02.txt")  # fmt: skip
    b.note(c8, "Number 9000079900 is used by Jasvinder Bhullar.", [n2, j2], [(j2, n2, "OWNS")],
           line=3, file="notes-02.txt")  # fmt: skip
    b.ident_links("FX05-PHN", ["AC-15"], [n1, n2], batch_min="b02")
    # FX-06 common-name trap
    k1 = b.per(cs["C-401"], "FX-06.PER.A", "Mohammed Khan", "mohammad khan")
    k2 = b.per(cs["C-402"], "FX-06.PER.B", "Mohd Khan", "mohammad khan")
    b.fir_person(cs["C-401"], k1, "accused", line=12)
    b.fir_person(cs["C-402"], k2, "accused", line=12)
    b.non_link("NL-FX06", ["AC-06"], "TR-01", k1, k2, "ANY_EDGE",
               "Common name in one district, no village: score 16.0, Low, no edge")  # fmt: skip


def _persons_with_ring(
    b: Builder, tag: str, specs: list[tuple[Case, str, str, str, str, int]]
) -> list[tuple[Entity, Entity]]:
    out = []
    for case, gt, raw, norm, number, style in specs:
        person = b.per(case, f"{tag}.PER.{gt}", raw, norm)
        phone = b.phn(case, f"{tag}.PHN.{gt}", number, style)
        out.append((person, phone))
    return out


def fx07(b: Builder, cs: dict[str, Case]) -> None:
    n, p = cs["C-109"], cs["C-204"]
    num = "9000022310"
    ph_n = b.phn(n, "FX-07.PHN.N", num)
    ph_p = b.phn(p, "FX-07.PHN.P", num)
    ramesh = b.per(n, "FX-07.PER.RAMESH", "Ramesh Yadav", "ramesh yadav")
    sunita = b.per(n, "FX-07.PER.SUNITA", "Sunita Yadav", "sunita yadav")
    suresh = b.per(p, "FX-07.PER.SURESH", "Suresh Yadav", "suresh yadav")
    b.note(n, "Ramesh Yadav ka number 9000022310 hai.", [ph_n, ramesh], [(ramesh, ph_n, "OWNS")])
    b.note(n, "Sunita Yadav ka number 9000022310 hai.", [ph_n, sunita], [(sunita, ph_n, "OWNS")])
    b.fir_person(p, suresh, "accused", phone=ph_p, line=12)
    b.ring("FX-07", ["AC-07"], [(n, ph_n), (p, ph_p)], b.phones.alloc(3))
    b.ident_links("FX07-PHN", ["AC-07"], [ph_n, ph_p])
    b.keep.update({"ph_n": ph_n, "ph_p": ph_p})
    b.non_link("NL-FX07-A", ["AC-07"], "TR-02", ramesh, suresh, "ANY_EDGE",
               "Shared family phone, 33.0 Low, no edge")  # fmt: skip
    b.non_link("NL-FX07-B", ["AC-07"], "TR-02", sunita, suresh, "ANY_EDGE",
               "Shared family phone, 33.0 Low, no edge")  # fmt: skip
    b.non_link("NL-FX07-C", ["AC-07"], "TR-18", ramesh, suresh, "AUTO",
               "Ramesh and Suresh are a transliteration look-alike, different people")  # fmt: skip


def fx08(b: Builder, cs: dict[str, Case]) -> None:
    q, r = cs["C-110"], cs["C-111"]
    num = "9000035562"
    ph_q = b.phn(q, "FX-08.PHN.Q", num)
    ph_r = b.phn(r, "FX-08.PHN.R", num)
    vikram = b.per(q, "FX-08.PER.VIKRAM", "Vikram Chauhan", "vikram chauhan")
    b.fir_person(q, vikram, "accused", phone=ph_q, line=12)
    kamla_sdr = b.per(r, "FX-08.PER.KAMLA_SDR", "Kamla Devi", "kamla devi")
    b.sdr(r, ph_r, kamla_sdr)
    acct = b.acc(r, "FX-08.ACC.KAMLA", "5010000044401", IFSC_A)
    kamla = b.per(r, "FX-08.PER.KAMLA", "KAMLA DEVI", "kamla devi")
    _within(b, "FX08-KAMLA", kamla_sdr, kamla)
    numbers = b.phones.alloc(4)
    b.ring("FX-08", ["AC-08"], [(q, ph_q), (r, (acct, IFSC_A, kamla))], numbers)
    b.ident_links("FX08-PHN", ["AC-08"], [ph_q, ph_r])
    b.link("EL-FX08-PER", ["AC-08"], "PERSON", vikram, kamla, "SUGGESTED", "MEDIUM",
           56.5, "exact", ["G1", "G2"],
           ["SHARED_PHONE", "PER_SHARED_NETWORK", "PER_LOCALITY"])  # fmt: skip
    b.non_link("NL-FX08", ["AC-08"], "TR-03", vikram, kamla_sdr, "AUTO",
               "SIM registered to another person: no anchor, never AUTO")  # fmt: skip


def fx09(b: Builder, cs: dict[str, Case]) -> None:
    number = "5010000055501"
    rows = []
    holders = (("C-112", "AJAY PAL", "ajay pal"), ("C-205", "IMRAN QURESHI", "imran qureshi"),
               ("C-303", "DEEPAK RAWAT", "deepak rawat"))  # fmt: skip
    accts, persons = [], []
    for cid, raw, norm in holders:
        c = cs[cid]
        acct = b.acc(c, f"FX-09.ACC.{cid}", number, IFSC_A)
        person = b.per(c, f"FX-09.PER.{cid}", raw, norm)
        accts.append(acct)
        persons.append(person)
        rows.append((c, (acct, IFSC_A, person)))
    b.ring("FX-09", ["AC-09"], rows[:2], b.phones.alloc(3))
    b.bank(cs["C-303"], accts[2], ifsc=IFSC_A, holder=persons[2])
    b.ident_links("FX09-ACC", ["AC-09"], accts)
    pairs = ((0, 1, "34.0"), (0, 2, "10.0"), (1, 2, "10.0"))
    for i, j, score in pairs:
        b.non_link(f"NL-FX09-{i}{j}", ["AC-09"], "TR-04", persons[i], persons[j], "ANY_EDGE",
                   f"Mule account owned by unrelated people: {score} Low, no edge")  # fmt: skip


def fx10(b: Builder, cs: dict[str, Case]) -> None:
    c1, c2 = cs["C-113"], cs["C-114"]
    num = "9000046120"
    p1, p2 = b.phn(c1, "FX-10.PHN.A", num), b.phn(c2, "FX-10.PHN.B", num)
    a1 = b.per(c1, "FX-10.PER.A", "Arjun Mehra", "arjun mehra", dob="1990-04-12")
    a2 = b.per(c2, "FX-10.PER.B", "Arjun Mehra", "arjun mehra", dob="1978-09-30")
    b.fir_person(c1, a1, "accused", phone=p1, dob="1990-04-12", dob_text="12-04-1990",
                 mohalla="Shivpuri", line=12)  # fmt: skip
    b.fir_person(c2, a2, "accused", phone=p2, dob="1978-09-30", dob_text="30-09-1978",
                 mohalla="Shivpuri", line=12)  # fmt: skip
    b.ident_links("FX10-PHN", ["AC-10"], [p1, p2])
    b.link("EL-FX10-PER", ["AC-10"], "PERSON", a1, a2, "SUGGESTED", "MEDIUM", 45.0, "exact",
           ["G1", "G4"], ["SHARED_PHONE", "PER_NAME_SIM", "PER_LOCALITY", "PER_DOB_CONFLICT"],
           trap="TR-05")  # fmt: skip


def fx11(b: Builder, cs: dict[str, Case]) -> None:
    c1, c2 = cs["C-115"], cs["C-125"]
    own1, own2 = b.phones.alloc(2)
    p1, p2 = b.phn(c1, "FX-11.PHN.A", own1), b.phn(c2, "FX-11.PHN.B", own2)
    a1 = b.per(c1, "FX-11.PER.A", "Parminder Atwal", "parminder atwal", dob="1982-06-18")
    a2 = b.per(c2, "FX-11.PER.B", "Parminder Atwaal", "parminder atwaal", dob="1982-06-18")
    for c, person, phone, rel in ((c1, a1, p1, "Gurmeet Atwal"), (c2, a2, p2, "Gurmeet Atwaal")):
        b.fir_person(c, person, "accused", phone=phone, dob="1982-06-18", dob_text="18-06-1982",
                     mohalla="Lal Darwaza", relation="s/o", relative=rel, line=12)  # fmt: skip
    towers = ["Rivergate Market", "Rivergate Ghat", "Kherapur Chowk", "Rivergate Bus Stand"]
    stamps = [f"2026-03-1{i}T10:15:00+05:30" for i in range(4)]
    ring = b.ring(
        "FX-11", ["AC-11"], [(c1, p1), (c2, p2)], b.phones.alloc(4), when=stamps, towers=towers
    )
    # exactly three shared (tower_place, date) pairs: the fourth row differs in the second case
    _file, line = ring.lines[c2.case_id][3]
    row = c2.doc("cdr.csv").csv_cells[line]
    row[1], row[7] = "2026-03-20T10:15:00+05:30", "Rivergate Civil Lines"
    b.link("EL-FX11-PER", ["AC-11"], "PERSON", a1, a2, "SUGGESTED", "HIGH", 90.0, "band",
           ["G2"], ["PER_NAME_SIM", "PER_RELATIVE_NAME", "PER_DOB_MATCH", "PER_LOCALITY",
                    "PER_SHARED_NETWORK", "PER_CO_LOCATION"], trap="TR-06")  # fmt: skip


def fx12(b: Builder, cs: dict[str, Case]) -> None:
    c1, c2, c3 = cs["C-116"], cs["C-207"], cs["C-304"]
    pa, pb = b.phones.alloc(2)
    p1a = b.phn(c1, "FX-12.PHN.PA.P1", pa)
    p2a, p2b = b.phn(c2, "FX-12.PHN.PA.P2", pa), b.phn(c2, "FX-12.PHN.PB.P2", pb)
    p3b = b.phn(c3, "FX-12.PHN.PB.P3", pb)
    s1 = b.per(c1, "FX-12.PER.P1", "Sohan Rawat", "sohan rawat", dob="1985-02-01")
    s2 = b.per(c2, "FX-12.PER.P2", "Sohan Rawat", "sohan rawat")
    s3 = b.per(c3, "FX-12.PER.P3", "Sohan Rawat", "sohan rawat", dob="1999-07-15")
    b.fir_person(c1, s1, "accused", phone=p1a, dob="1985-02-01", dob_text="01-02-1985", line=12)
    b.fir_person(c2, s2, "accused", phone=p2a, line=12)
    b.note(c2, "Number " + pb + " is used by Sohan Rawat.", [p2b, s2], [(s2, p2b, "OWNS")])
    b.fir_person(c3, s3, "accused", phone=p3b, dob="1999-07-15", dob_text="15-07-1999", line=12)
    b.ring("FX-12-A", ["AC-12"], [(c1, p1a), (c2, p2a)], b.phones.alloc(3))
    b.ring("FX-12-B", ["AC-12"], [(c2, p2b), (c3, p3b)], b.phones.alloc(2))
    b.ident_links("FX12-PA", ["AC-12"], [p1a, p2a])
    b.ident_links("FX12-PB", ["AC-12"], [p2b, p3b])
    _cross(b, "FX12-P1P2", s1, s2)
    kinds = ["SHARED_PHONE", "PER_NAME_SIM", "PER_SHARED_NETWORK"]
    b.link("EL-FX12-P1P2", ["AC-12"], "PERSON", s1, s2, "AUTO", "HIGH", 99.0, "exact", [], kinds)
    b.link("EL-FX12-P2P3", ["AC-12"], "PERSON", s2, s3, "SUGGESTED", "HIGH", 93.0, "exact",
           [("G6", "match.gate.cluster_conflict")], kinds)  # fmt: skip
    b.non_link("NL-FX12", ["AC-12"], "TR-07", s1, s3, "ANY_EDGE",
               "Weak chain across a DOB conflict: no edge between P1 and P3")  # fmt: skip


def fx13(b: Builder, cs: dict[str, Case]) -> None:
    q1, q2, q3, q4 = cs["C-117"], cs["C-208"], cs["C-305"], cs["C-118"]
    names = {
        "Q1": "Harbhajan Sandhawalia", "Q2": "Harbajan Sandhawalia",
        "Q3": "Harbhajan Sandhawaliya", "Q4": "Harbhajan Sandhwalia",
    }  # fmt: skip
    cases = {"Q1": q1, "Q2": q2, "Q3": q3, "Q4": q4}
    p12, p34, p23 = b.phones.alloc(3)
    per = {k: b.per(cases[k], f"FX-13.PER.{k}", names[k], names[k].lower()) for k in names}
    own = {
        ("Q1", "P12"): p12, ("Q2", "P12"): p12, ("Q3", "P34"): p34, ("Q4", "P34"): p34,
        ("Q2", "P23"): p23, ("Q3", "P23"): p23,
    }  # fmt: skip
    ph = {k: b.phn(cases[k[0]], f"FX-13.PHN.{k[1]}.{k[0]}", v) for k, v in own.items()}
    for k in ("Q1", "Q3", "Q4"):
        first = next(x for x in ph if x[0] == k)
        b.fir_person(cases[k], per[k], "accused", phone=ph[first], line=12)
    b.fir_person(q2, per["Q2"], "accused", phone=ph[("Q2", "P12")], line=12)
    b.note(q2, f"Number {p23} is used by {names['Q2']}.", [ph[("Q2", "P23")], per["Q2"]],
           [(per["Q2"], ph[("Q2", "P23")], "OWNS")])  # fmt: skip
    b.note(q3, f"Number {p23} is used by {names['Q3']}.", [ph[("Q3", "P23")], per["Q3"]],
           [(per["Q3"], ph[("Q3", "P23")], "OWNS")])  # fmt: skip
    b.ring(
        "FX-13-A", ["AC-13"], [(q1, ph[("Q1", "P12")]), (q2, ph[("Q2", "P12")])], b.phones.alloc(3)
    )
    b.ring(
        "FX-13-B", ["AC-13"], [(q3, ph[("Q3", "P34")]), (q4, ph[("Q4", "P34")])], b.phones.alloc(3)
    )
    b.ring(
        "FX-13-C", ["AC-13"], [(q2, ph[("Q2", "P23")]), (q3, ph[("Q3", "P23")])], b.phones.alloc(2)
    )
    b.ident_links("FX13-P12", ["AC-13"], [ph[("Q1", "P12")], ph[("Q2", "P12")]])
    b.ident_links("FX13-P34", ["AC-13"], [ph[("Q3", "P34")], ph[("Q4", "P34")]])
    b.ident_links("FX13-P23", ["AC-13"], [ph[("Q2", "P23")], ph[("Q3", "P23")]])
    _cross(b, "FX13-Q1Q2", per["Q1"], per["Q2"])
    _cross(b, "FX13-Q3Q4", per["Q3"], per["Q4"])
    kinds = ["SHARED_PHONE", "PER_NAME_SIM", "PER_SHARED_NETWORK"]
    b.link("EL-FX13-Q1Q2", ["AC-13"], "PERSON", per["Q1"], per["Q2"], "AUTO", "HIGH", 98.0,
           "band", [], kinds, harness="HS-AC13")  # fmt: skip
    b.link("EL-FX13-Q3Q4", ["AC-13"], "PERSON", per["Q3"], per["Q4"], "AUTO", "HIGH", 96.9,
           "band", [], kinds)  # fmt: skip
    b.link("EL-FX13-Q2Q3", ["AC-13"], "PERSON", per["Q2"], per["Q3"], "SUGGESTED", "HIGH", 90.9,
           "band", [("G6", "match.gate.cluster_bridge")], kinds)  # fmt: skip
    for x, y in (("Q1", "Q3"), ("Q1", "Q4"), ("Q2", "Q4")):
        b.non_link(f"NL-FX13-{x}{y}", ["AC-13"], "TR-08", per[x], per[y], "ANY_EDGE",
                   "Non-adjacent members of the chain share nothing: no edge")  # fmt: skip


def fx14(b: Builder, cs: dict[str, Case]) -> None:
    y, z = cs["C-119"], cs["C-209"]
    p1, p2 = b.phones.alloc(2)
    r1 = b.per(y, "FX-14.PER.R1", "Rakesh Dubey", "rakesh dubey")
    r3 = b.per(y, "FX-14.PER.R3", "Monu", "monu")
    r2 = b.per(z, "FX-14.PER.R2", "Rakesh Dubey urf Monu", "rakesh dubey", aliases=["monu"])
    ph1y, ph2y = b.phn(y, "FX-14.PHN.P1.Y", p1), b.phn(y, "FX-14.PHN.P2.Y", p2)
    ph1z, ph2z = b.phn(z, "FX-14.PHN.P1.Z", p1), b.phn(z, "FX-14.PHN.P2.Z", p2)
    b.fir_person(y, r1, "accused", phone=ph1y, line=12)
    b.fir_person(y, r3, "accused", phone=ph2y)
    b.fir_person(z, r2, "accused", phone=ph1z, line=12)
    b.note(z, f"Number {p2} is used by Rakesh Dubey urf Monu.", [ph2z, r2], [(r2, ph2z, "OWNS")])
    b.ring("FX-14-A", ["AC-14"], [(y, ph1y), (z, ph1z)], b.phones.alloc(2))
    b.ring("FX-14-B", ["AC-14"], [(y, ph2y), (z, ph2z)], b.phones.alloc(3))
    b.ident_links("FX14-P1", ["AC-14"], [ph1y, ph1z])
    b.ident_links("FX14-P2", ["AC-14"], [ph2y, ph2z])
    _cross(b, "FX14-R1R2", r1, r2)
    kinds = ["SHARED_PHONE", "PER_NAME_SIM", "PER_SHARED_NETWORK"]
    b.link("EL-FX14-R1R2", ["AC-14"], "PERSON", r1, r2, "AUTO", "HIGH", 93.0, "exact", [], kinds)
    b.link("EL-FX14-R3R2", ["AC-14"], "PERSON", r3, r2, "SUGGESTED", "HIGH", 91.5, "exact",
           [("G6", "match.gate.cluster_same_case")], kinds)  # fmt: skip
    b.non_link("NL-FX14", ["AC-14"], "TR-09", r1, r3, "ANY_EDGE",
               "Two different people of one case, joined only through a third")  # fmt: skip


def fx17_19(b: Builder, cs: dict[str, Case]) -> None:
    aa, ab = cs["C-120"], cs["C-210"]
    p1 = b.phn(aa, "FX-17.PHN.A", "9000051234", style=3)
    p2 = b.phn(ab, "FX-17.PHN.B", "9000051234")
    i1 = b.per(aa, "FX-17.PER.A", "मोहम्मद इरफ़ान", "mohammad irfan")
    i2 = b.per(ab, "FX-17.PER.B", "Mohd Irfan", "mohammad irfan")
    b.fir_person(aa, i1, "accused", phone=p1, line=12)
    b.fir_person(ab, i2, "accused", phone=p2, line=12)
    b.ident_links("FX17-PHN", ["AC-17"], [p1, p2])
    _cross(b, "FX17-PER", i1, i2)
    b.link("EL-FX17-PER", ["AC-17"], "PERSON", i1, i2, "SUGGESTED", "MEDIUM", 75.0, "exact",
           ["G1"], ["SHARED_PHONE", "PER_NAME_SIM"])  # fmt: skip
    k = b.keep
    for tag, x in (("A", i1), ("B", i2)):
        for ctag, y in (("A", k["irfan_a"]), ("B", k["irfan_b"])):
            b.non_link(f"NL-FX17-{tag}{ctag}", ["AC-17"], "TR-10", x, y, "ANY_EDGE",
                       "Different Irfans (AC-17 vs AC-01): rarity and no anchor keep it Low")  # fmt: skip
    # FX-19 hedged plate
    c1, c2 = cs["C-121"], cs["C-211"]
    v1 = b.veh(c1, "FX-19.VEH.A", "UP32CD9021")
    v2 = b.veh(c2, "FX-19.VEH.B", "UP32CD9021")
    b.fir(c1, "The vehicle UP32CD9021 was seen leaving the spot.", [v1])
    b.note(c2, "Plate partly illegible, noted as UP32CD9021 (unverified)", [v2])
    _cross(b, "FX19-VEH", v1, v2)
    b.link("EL-FX19-VEH", ["AC-19"], "VEHICLE", v1, v2, "SUGGESTED", "HIGH", 100, "band",
           ["G5"], ["ID_EXACT"])  # fmt: skip


def fx21_22(b: Builder, cs: dict[str, Case]) -> None:
    c1, c2 = cs["C-122"], cs["C-126"]
    number = "5010000066602"
    a1, a2 = b.acc(c1, "FX-21.ACC.A", number, IFSC_A), b.acc(c2, "FX-21.ACC.B", number, IFSC_A)
    o1 = b.org(c1, "FX-21.ORG.A", "M/s Shree Balaji Traders", "shree balaji")
    o2 = b.org(c2, "FX-21.ORG.B", "M/s Shri Balaji Trading Co", "shri balaji")
    b.fir_person(c1, o1, "complainant", acct=a1, ifsc=IFSC_A, mohalla="Subhash Nagar", line=12)
    b.fir_person(c2, o2, "complainant", acct=a2, ifsc=IFSC_A, mohalla="Subhash Nagar", line=12)
    h1 = b.org(c1, "FX-21.ORG.A_BANK", "SHREE BALAJI TRADERS", "shree balaji")
    h2 = b.org(c2, "FX-21.ORG.B_BANK", "SHRI BALAJI TRADING CO", "shri balaji")
    b.bank(c1, a1, ifsc=IFSC_A, holder=h1)
    b.bank(c2, a2, ifsc=IFSC_A, holder=h2)
    _within(b, "FX21-A", o1, h1)
    _within(b, "FX21-B", o2, h2)
    b.ident_links("FX21-ACC", ["AC-21"], [a1, a2])
    _cross(b, "FX21-ORG", o1, o2)
    b.link("EL-FX21-ORG", ["AC-21"], "ORG", o1, o2, "SUGGESTED", "HIGH", 90.0, "band",
           ["G7"], ["SHARED_ACCOUNT", "ORG_NAME_SIM", "PER_LOCALITY"])  # fmt: skip
    # FX-22 Naveen Tomar
    rg, hc = cs["C-123"], cs["C-213"]
    num = "9000062201"
    ph1, ph2 = b.phn(rg, "FX-22.PHN.RG", num), b.phn(hc, "FX-22.PHN.HC", num)
    n1 = b.per(rg, "FX-22.PER.RG", "Naveen Tomar", "naveen tomar")
    n2 = b.per(hc, "FX-22.PER.HC", "Naveen Tomar", "naveen tomar")
    b.fir_person(rg, n1, "accused", phone=ph1, line=12)
    b.fir_person(hc, n2, "accused", phone=ph2, line=12)
    b.ring("FX-22", ["AC-22"], [(rg, ph1), (hc, ph2)], b.phones.alloc(3))
    b.ident_links("FX22-PHN", ["AC-22"], [ph1, ph2])
    _cross(b, "FX22-PER", n1, n2)
    b.link("EL-FX22-PER", ["AC-22"], "PERSON", n1, n2, "AUTO", "HIGH", 99.0, "exact", [],
           ["SHARED_PHONE", "PER_NAME_SIM", "PER_SHARED_NETWORK"])  # fmt: skip


def fx26(b: Builder, cs: dict[str, Case]) -> None:
    number = "5010000088801"
    ents = []
    for cid, tag, ifsc in (("C-124", "A1", IFSC_A), ("C-214", "A2", ""), ("C-306", "A3", IFSC_B)):
        acct = b.acc(cs[cid], f"FX-26.ACC.{tag}", number, ifsc or None)
        b.bank(cs[cid], acct, ifsc=ifsc)
        ents.append(acct)
    a1, a2, a3 = ents
    _cross(b, "FX26-A1A2", a1, a2)
    b.link("EL-FX26-A1A2", ["AC-26"], "ACCOUNT", a1, a2, "AUTO", "HIGH", 100, "band", [],
           ["ID_EXACT"])  # fmt: skip
    b.link("EL-FX26-A2A3", ["AC-26"], "ACCOUNT", a2, a3, "SUGGESTED", "HIGH", 100, "band",
           [("G6", "match.gate.cluster_conflict")], ["ID_EXACT"])  # fmt: skip
    b.non_link("NL-FX26", ["AC-26", "AC-04"], "TR-17", a1, a3, "ANY_EDGE",
               "Same digits at two different banks: veto, no edge")  # fmt: skip


def sf01_03(b: Builder, cs: dict[str, Case]) -> None:
    c = cs["C-127"]
    forms = ("90000 52210", "+91-9000052210", "09000052210")
    phs = [b.phn(c, f"SF-01.PHN.{i}", "9000052210", raw=raw) for i, raw in enumerate(forms)]
    b.fir(c, f"Accused used mobile {forms[0]} for the calls.", [phs[0]], line=12)
    b.note(c, f"Number {forms[1]} was seen on the second handset.", [phs[1]])
    b.note(c, f"Call details were sought for {forms[2]}.", [phs[2]])
    _within(b, "SF01-PHN", *phs)
    v1, v2 = b.veh(c, "SF-01.VEH.A", "UP32AD4567"), b.veh(c, "SF-01.VEH.B", "up 32 ad 4567")
    b.fir(c, "A vehicle UP32AD4567 was parked near the shop.", [v1])
    b.note(c, "Vehicle up 32 ad 4567 was seen at the checkpoint.", [v2])
    _within(b, "SF01-VEH", v1, v2)
    n1 = b.per(c, "SF-01.PER.A", "Ramesh Kasana urf Kalu", "ramesh kasana", aliases=["kalu"])
    n2 = b.per(c, "SF-01.PER.B", "Kalu", "kalu")
    b.fir_person(c, n1, "accused")
    b.note(c, "Accused Kalu was seen again near the market.", [n2])
    _within(b, "SF01-PER", n1, n2)
    # SF-02, SF-03
    p1 = b.phn(cs["C-128"], "SF-02.PHN.A", "9000091827")
    p2 = b.phn(cs["C-206"], "SF-02.PHN.B", "9000097821")
    b.fir(cs["C-128"], "Calls came from mobile 9000091827 on that night.", [p1])
    b.fir(cs["C-206"], "Calls came from mobile 9000097821 on that night.", [p2])
    b.non_link("NL-SF02", [], "TR-11", p1, p2, "ANY_EDGE", "Non-adjacent digit swap: no edge")
    a1 = b.acc(cs["C-129"], "SF-03.ACC.A", "5010000091001", IFSC_A)
    a2 = b.acc(cs["C-212"], "SF-03.ACC.B", "5010000091002", IFSC_A)
    b.bank(cs["C-129"], a1, ifsc=IFSC_A)
    b.bank(cs["C-212"], a2, ifsc=IFSC_A)
    b.non_link("NL-SF03", [], "TR-12", a1, a2, "ANY_EDGE", "One digit apart: no fuzzy accounts")


def sf04(b: Builder, cs: dict[str, Case]) -> None:
    hub_case, c1, c2 = cs["C-130"], cs["C-131"], cs["C-215"]
    hub = "9000087000"
    callers = b.phones.alloc(30)
    hub_ent = b.phn(hub_case, "SF-04.PHN.HUB.C130", hub)
    for i, number in enumerate(callers):
        caller = b.phn(hub_case, f"SF-04.PHN.CALLER{i + 1}", number)
        b.cdr(hub_case, caller, hub_ent)
    other = b.phones.alloc(1)[0]
    own1, own2 = b.phones.alloc(2)
    ents = [hub_ent]
    g1 = b.per(c1, "SF-04.PER.A", "Gopal Narwal", "gopal narwal")
    g2 = b.per(c2, "SF-04.PER.B", "Gopal Narval", "gopal narval")
    xs = []
    for case, person, own, tag in ((c1, g1, own1, "A"), (c2, g2, own2, "B")):
        phone = b.phn(case, f"SF-04.PHN.OWN.{tag}", own)
        b.fir_person(case, person, "accused", phone=phone, line=12)
        hub_here = b.phn(case, f"SF-04.PHN.HUB.{case.case_id}", hub)
        x = b.phn(case, f"SF-04.PHN.X.{tag}", other)
        b.cdr(case, phone, hub_here)
        b.cdr(case, phone, x)
        ents.append(hub_here)
        xs.append(x)
    b.ident_links("SF04-HUB", [], ents)
    b.ident_links("SF04-X", [], xs)
    b.non_link(
        "NL-SF04", [], "TR-13", g1, g2, "ANY_EDGE", "Hub excluded: k = 1, no PER_SHARED_NETWORK"
    )


def sf05_06(b: Builder, cs: dict[str, Case]) -> None:
    c1, c2 = cs["C-132"], cs["C-216"]
    num = "9000088120"
    p1, p2 = b.phn(c1, "SF-05.PHN.A", num), b.phn(c2, "SF-05.PHN.B", num)
    m = b.per(c1, "SF-05.PER.A", "Mahesh Gupta", "mahesh gupta")
    r = b.per(c2, "SF-05.PER.B", "Rajan Gupta", "rajan gupta")
    b.note(c1, f"Number {num} is used by Mahesh Gupta (shop number, PCO).", [p1, m],
           [(m, p1, "OWNS")], line=3)  # fmt: skip
    b.note(c2, f"Number {num} is used by Rajan Gupta (shop number, PCO).", [p2, r],
           [(r, p2, "OWNS")], line=3)  # fmt: skip
    b.ident_links("SF05-PHN", [], [p1, p2])
    b.non_link("NL-SF05", [], "TR-14", m, r, "ANY_EDGE", "Shop or PCO number: SHARED, factor 0.2")
    d1, d2 = cs["C-133"], cs["C-217"]
    num = "9000088555"
    q1, q2 = b.phn(d1, "SF-06.PHN.A", num), b.phn(d2, "SF-06.PHN.B", num)
    f = b.per(d1, "SF-06.PER.A", "Pooja Verma", "pooja verma", gender="female")
    g = b.per(d2, "SF-06.PER.B", "Pooja Verma", "pooja verma", gender="male")
    b.fir_person(d1, f, "accused", phone=q1, gender="female", line=12)
    b.fir_person(d2, g, "accused", phone=q2, gender="male", line=12)
    b.ring("SF-06", [], [(d1, q1), (d2, q2)], b.phones.alloc(4))
    b.ident_links("SF06-PHN", [], [q1, q2])
    b.link("EL-SF06-PER", [], "PERSON", f, g, "SUGGESTED", "MEDIUM", 55, "band", ["G1", "G4"],
           ["SHARED_PHONE", "PER_NAME_SIM", "PER_SHARED_NETWORK", "PER_GENDER_CONFLICT"], trap="TR-15")  # fmt: skip


def sf07_08(b: Builder, cs: dict[str, Case]) -> None:
    c1, c2 = cs["C-134"], cs["C-135"]
    d1 = b.per(c1, "SF-07.PER.A", "Dinesh Pathania", "dinesh pathania")
    d2 = b.per(c2, "SF-07.PER.B", "Dinesh Pathania", "dinesh pathania")
    for c, person in ((c1, d1), (c2, d2)):
        b.fir_person(c, person, "accused", mohalla="Peepal Wali Gali", relation="s/o",
                     relative="Ganpat Pathania", line=12)  # fmt: skip
    n1, n2 = b.phn(c1, "SF-07.PHN.A", "9000089015"), b.phn(c2, "SF-07.PHN.B", "9000089015")
    for c, person, phone in ((c1, d1, n1), (c2, d2, n2)):
        b.note(c, f"Number 9000089015 is used by {person.raw_text}.", [phone, person],
               [(person, phone, "OWNS")], line=3, file="notes-02.txt")  # fmt: skip
    b.ident_links("SF07-PHN", [], [n1, n2], batch_min="b02")
    _cross(b, "SF07-PER", d1, d2)
    b.link("EL-SF07-PER-B01", [], "PERSON", d1, d2, "SUGGESTED", "MEDIUM", 55.0, "band",
           ["G1", "G2", "G3"], ["PER_NAME_SIM", "PER_RELATIVE_NAME", "PER_LOCALITY"])  # fmt: skip
    b.link(
        "EL-SF07-PER-B02",
        [],
        "PERSON",
        d1,
        d2,
        "AUTO",
        "HIGH",
        100,
        "band",
        [],
        ["SHARED_PHONE", "PER_NAME_SIM", "PER_RELATIVE_NAME", "PER_LOCALITY"],
        batch_min="b02",
    )
    r1, r2 = cs["C-136"], cs["C-218"]
    num = "9000089990"
    p1, p2 = b.phn(r1, "SF-08.PHN.A", num), b.phn(r2, "SF-08.PHN.B", num)
    g = b.per(r1, "SF-08.PER.A", "Girish Bhatt", "girish bhatt")
    t = b.per(r2, "SF-08.PER.B", "Tanvi Oberoi", "tanvi oberoi")
    b.fir_person(r1, g, "accused", phone=p1, line=12)
    b.fir_person(r2, t, "accused", phone=p2, line=12)
    b.ident_links("SF08-PHN", [], [p1, p2])
    b.non_link("NL-SF08", [], "TR-16", g, t, "ANY_EDGE", "Recycled number: different owners")


def access(b: Builder, cs: dict[str, Case]) -> None:
    k = b.keep
    for i, (x, y) in enumerate(
        ((k["p1203_a"], k["ph_n"]), (k["p1203_a"], k["ph_p"]),
         (k["p1203_b"], k["ph_n"]), (k["p1203_b"], k["ph_p"]))
    ):  # fmt: skip
        b.non_link(f"NL-B2-{i + 1}", [], "TR-11", x, y, "ANY_EDGE",
                   "9000021203 and 9000022310 have the same digit set but are not an adjacent swap: "
                   "B2 candidate without evidence, no edge")  # fmt: skip
    a, c, c102, c202 = cs["C-101"], cs["C-201"], cs["C-102"], cs["C-202"]
    caller, peer1, peer2, caller8 = b.phones.alloc(4)
    e3 = b.phn(c102, "ACC.PHN.E3", "9000014471")
    b.cdr(c102, b.phn(c102, "ACC.PHN.E3CALLER", caller), e3)
    e7 = b.phn(c, "ACC.PHN.E7", "9000014741")
    # b02 rows in C-201: the same phone again (cited line) and the swapped number
    b.cdr(c, k["ph_b"], b.phn(c, "ACC.PHN.PEER1", peer1), line=2, file="cdr-02.csv")
    b.cdr(c, e7, b.phn(c, "ACC.PHN.PEER2", peer2), line=4, file="cdr-02.csv")
    e8 = b.phn(c202, "ACC.PHN.E8", "9000014471")
    b.cdr(c202, b.phn(c202, "ACC.PHN.E8CALLER", caller8), e8, line=2)
    ph_a, ph_b = k["ph_a"], k["ph_b"]
    ents = [ph_a, ph_b, e3, e8]
    ac_map = {(0, 1): ["AC-01"]}
    bmin = {(0, 3): "b02", (1, 3): "b02", (2, 3): "b02"}
    b.ident_links("ACC-4471", ["AC-01"], ents, ac_map=ac_map, bmin=bmin)
    for x, y, tag in ((ph_a, e7, "E1E7"), (e3, e7, "E3E7"), (e8, e7, "E8E7")):
        b.link(f"EL-ACC-{tag}", [], "PHONE", x, y, "SUGGESTED", "MEDIUM", 55, "band",
               ["G1", ("G6", "match.gate.cluster_same_case")],
               ["PHONE_TRANSPOSED"], batch_min="b02")  # fmt: skip
    e4 = b.veh(a, "ACC.VEH.E4", "UP32AC5678")
    b.fir(a, vehicle_seen("en", "UP32AC5678"), [e4], line=16)
    e5 = b.veh(cs["C-301"], "ACC.VEH.E5", "UP32AC5678")
    b.note(cs["C-301"], "Vehicle UP32AC5678 was noted near the harbour.", [e5])
    b.ident_links("ACC-L3", [], [e4, e5])


def scenarios(b: Builder, cs: dict[str, Case]) -> None:
    del cs
    fresh = "fresh load of b01"
    b.scenario("SC-AC16", ["AC-16"], [
        ("SUPERVISOR", "UNDO", "EL-FX01-PER", "UNDONE, history 2 entries, phone links unchanged, cluster splits"),
    ])  # fmt: skip
    b.scenario("SC-AC18", ["AC-18"], [
        ("SENIOR", "PUT matching.thresholds high_min 90", "thresholds_version 2", "pending change approved"),
        ("ENGINE", "RUN b01", "EL-FX01-PER", "DEMOTED to SUGGESTED, edge thresholds_version 2, phones AUTO"),
        ("SENIOR", "PUT matching.thresholds high_min 65", "thresholds", "422, rejected by validation"),
    ])  # fmt: skip
    b.scenario("SC-AC15-AC25", ["AC-15", "AC-25"], [
        ("ENGINE", f"RUN b01 ({fresh})", "EL-FX05-PER", "SUGGESTED"),
        ("INVESTIGATOR", "REJECT", "EL-FX05-PER", "REJECTED"),
        ("ENGINE", "RUN b02", "EL-FX05-PER", "still REJECTED, no transition record"),
        ("SUPERVISOR", "REOPEN with reason", "EL-FX05-PER", "SUGGESTED"),
        ("INVESTIGATOR", "CONFIRM", "EL-FX05-PER", "CONFIRMED"),
        ("ENGINE", "RERUN", "EL-FX05-PER", "CONFIRMED, not AUTO, two transition records"),
    ])  # fmt: skip
    b.scenario("SC-AC24", ["AC-24"], [
        ("INVESTIGATOR", "REJECT then CONFIRM", "EL-FX05-PER", "409, state unchanged"),
        ("INVESTIGATOR", "CONFIRM then REJECT", "EL-FX05-PER", "409, state unchanged"),
        ("INVESTIGATOR", "REJECT AUTO link", "EL-FX01-PER", "409 or 403, edge, history, audit unchanged"),
        ("INVESTIGATOR", "UNDO AUTO link", "EL-FX01-PER", "403, edge, history, audit unchanged"),
    ])  # fmt: skip
    b.scenario("SC-AC20", ["AC-20"], [
        ("ENGINE", "RUN every edge on small tier", "all edges", "invariant by decimal equality, sources inside end cases"),
    ])  # fmt: skip
    b.scenario("SC-AC23", ["AC-23"], [
        ("ENGINE", "RUN twice on empty stores, then again on the same store", "FX-01..FX-22",
         "same pairs, states, scores, evidence; rerun makes no edges"),
    ])  # fmt: skip
    b.scenario("SC-AC27", ["AC-27"], [
        ("ADMIN", "LOAD C-101 and C-201 as one batch on an empty store, RUN", "run record",
         "input_case_ids [C-101, C-201], thresholds_version 1, AUTO 4, SUCCEEDED"),
    ])  # fmt: skip
    b.scenario("HS-AC13", ["AC-13"], [
        ("INVESTIGATOR", "CONFIRM", "EL-FX13-Q1Q2", "CONFIRMED"),
        ("ENGINE", "RERUN", "EL-FX13-Q2Q3", "same result: SUGGESTED, cluster_bridge"),
    ])  # fmt: skip
    b.scenario("SF-09", [], [
        ("ENGINE", "RUN b01 (fresh load of C-110, C-111)", "all links", "SUGGESTED edges present"),
        ("SENIOR", "PUT matching.thresholds medium_min 60", "thresholds_version", "approved"),
        ("ENGINE", "RERUN", "SUGGESTED edges below 60",
         "WITHDRAWN: AC-03 55, AC-05 48.2, AC-08 56.5, AC-10 45.0, SF-06 55"),
    ])  # fmt: skip


__all__ = ["B02_CASES", "PLANTED_IDS", "build_planted", "phone_format"]
