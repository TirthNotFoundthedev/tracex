"""G-16: mapping of engine entities to ground-truth entities (spec section 8.1, as amended)."""

from __future__ import annotations

from typing import Any

import pytest

from datakit.scoremap import GroundTruthIndex


def _gt_entity(
    gt: dict[str, Any], type_: str, case_id: str, file: str, line: int
) -> dict[str, Any]:
    for entity in gt["entities"]:
        if entity["type"] != type_:
            continue
        if any(
            r["case_id"] == case_id and r["file"] == file and r["line"] == line
            for r in entity["mentions"]
        ):
            found: dict[str, Any] = entity
            return found
    raise AssertionError((type_, case_id, file, line))


def _engine(entity: dict[str, Any], **changes: Any) -> dict[str, Any]:
    """An engine entity written as the entity's own mentions; `raw_text` sets every mention's."""
    raw_text = changes.pop("raw_text", entity["raw_text"])
    base: dict[str, Any] = {
        "id": "opaque-1",
        "type": entity["type"],
        "normalized": entity["normalized"],
        "mentions": [{**r, "raw_text": raw_text} for r in entity["mentions"]],
    }
    base.update(changes)
    return base


@pytest.fixture(scope="module")
def index(gt: dict[str, Any]) -> GroundTruthIndex:
    return GroundTruthIndex(gt)


def test_person_maps_on_shared_mention_and_equal_raw_text_whatever_the_normalized_form(
    gt: dict[str, Any], index: GroundTruthIndex
) -> None:
    irfan = _gt_entity(gt, "PERSON", "C-201", "notes.txt", 3)
    engine = _engine(irfan, normalized="a different transliteration entirely")
    assert index.map_engine_entity(engine) == frozenset({irfan["gt_id"]})


def test_person_with_equal_normalized_form_but_other_raw_text_does_not_map(
    gt: dict[str, Any], index: GroundTruthIndex
) -> None:
    irfan = _gt_entity(gt, "PERSON", "C-201", "notes.txt", 3)
    engine = _engine(irfan, raw_text="Irfan bhaiya")
    assert index.map_engine_entity(engine) == frozenset()


def test_org_maps_on_raw_text_like_a_person(gt: dict[str, Any], index: GroundTruthIndex) -> None:
    org = next(e for e in gt["entities"] if e["type"] == "ORG")
    assert index.map_engine_entity(_engine(org, normalized="x")) == frozenset({org["gt_id"]})
    assert index.map_engine_entity(_engine(org, raw_text=org["raw_text"] + " Ltd")) == frozenset()


@pytest.mark.parametrize(
    ("type_", "case_id", "file", "line"),
    [
        ("PHONE", "C-101", "fir.txt", 12),
        ("ACCOUNT", "C-101", "bank.csv", 4),
        ("VEHICLE", "C-103", "fir.txt", 12),
    ],
)
def test_identifier_maps_on_equal_normalized_form_whatever_the_raw_text(
    gt: dict[str, Any],
    index: GroundTruthIndex,
    type_: str,
    case_id: str,
    file: str,
    line: int,
) -> None:
    entity = _gt_entity(gt, type_, case_id, file, line)
    engine = _engine(entity, raw_text="written some other way")
    assert entity["gt_id"] in index.map_engine_entity(engine)


@pytest.mark.parametrize(
    ("type_", "case_id", "file", "line"),
    [
        ("PHONE", "C-101", "fir.txt", 12),
        ("ACCOUNT", "C-101", "bank.csv", 4),
        ("VEHICLE", "C-103", "fir.txt", 12),
    ],
)
def test_identifier_with_another_normalized_form_does_not_map_even_on_the_same_line(
    gt: dict[str, Any],
    index: GroundTruthIndex,
    type_: str,
    case_id: str,
    file: str,
    line: int,
) -> None:
    entity = _gt_entity(gt, type_, case_id, file, line)
    engine = _engine(entity, normalized=entity["normalized"] + "0")
    assert index.map_engine_entity(engine) == frozenset()


def test_entity_on_another_line_does_not_map(gt: dict[str, Any], index: GroundTruthIndex) -> None:
    phone = _gt_entity(gt, "PHONE", "C-101", "fir.txt", 12)
    moved = [{"case_id": "C-101", "file": "fir.txt", "line": 13, "raw_text": phone["raw_text"]}]
    assert index.map_engine_entity(_engine(phone, mentions=moved)) == frozenset()


def test_entity_of_another_type_does_not_map(gt: dict[str, Any], index: GroundTruthIndex) -> None:
    phone = _gt_entity(gt, "PHONE", "C-101", "fir.txt", 12)
    assert index.map_engine_entity(_engine(phone, type="ACCOUNT")) == frozenset()


def test_engine_entity_ids_are_never_used(gt: dict[str, Any], index: GroundTruthIndex) -> None:
    phone = _gt_entity(gt, "PHONE", "C-101", "fir.txt", 12)
    named_like_another = _engine(phone, id="FX-02.VEH.A")
    assert index.map_engine_entity(named_like_another) == index.map_engine_entity(
        _engine(phone, id="x")
    )


def test_engine_entity_with_several_mentions_maps_through_any_of_them(
    gt: dict[str, Any], index: GroundTruthIndex
) -> None:
    phone = _gt_entity(gt, "PHONE", "C-101", "fir.txt", 12)
    far = {"case_id": "C-999", "file": "x.txt", "line": 1, "raw_text": "x"}
    engine = _engine(phone)
    engine["mentions"].insert(0, far)
    assert phone["gt_id"] in index.map_engine_entity(engine)


def test_within_case_group_members_count_for_the_group(
    gt: dict[str, Any], index: GroundTruthIndex
) -> None:
    fir = _gt_entity(gt, "PERSON", "C-101", "fir.txt", 12)
    bank = _gt_entity(gt, "PERSON", "C-101", "bank.csv", 4)
    assert fir["gt_id"] != bank["gt_id"]
    assert index.closure({bank["gt_id"]}) == index.closure({fir["gt_id"]})
    assert {fir["gt_id"], bank["gt_id"]} <= index.closure({bank["gt_id"]})


def test_closure_of_an_ungrouped_entity_is_itself(
    gt: dict[str, Any], index: GroundTruthIndex
) -> None:
    solo = next(e["gt_id"] for e in gt["entities"] if e["gt_id"].startswith("NZ-"))
    in_group = {m for g in gt["groups"] if g["scope"] == "within_case" for m in g["members"]}
    if solo in in_group:
        solo = next(
            e["gt_id"]
            for e in gt["entities"]
            if e["gt_id"].startswith("NZ-") and e["gt_id"] not in in_group
        )
    assert index.closure({solo}) == frozenset({solo})


def test_every_ground_truth_entity_maps_to_itself_and_only_to_its_own_group(
    gt: dict[str, Any], index: GroundTruthIndex
) -> None:
    for entity in gt["entities"]:
        mapped = index.map_engine_entity(_engine(entity))
        assert entity["gt_id"] in mapped, entity["gt_id"]
        assert mapped <= index.closure({entity["gt_id"]}), (entity["gt_id"], sorted(mapped))


def test_person_and_org_mappings_are_unambiguous_on_raw_text(gt: dict[str, Any]) -> None:
    seen: dict[tuple[str, str, int, str, str], str] = {}
    for entity in gt["entities"]:
        if entity["type"] not in ("PERSON", "ORG"):
            continue
        for ref in entity["mentions"]:
            key = (ref["case_id"], ref["file"], ref["line"], entity["type"], entity["raw_text"])
            assert key not in seen, (entity["gt_id"], seen[key])
            seen[key] = entity["gt_id"]


def test_identifier_mappings_are_unambiguous_on_normalized_form(gt: dict[str, Any]) -> None:
    seen: dict[tuple[str, str, int, str, str], str] = {}
    for entity in gt["entities"]:
        if entity["type"] not in ("PHONE", "ACCOUNT", "VEHICLE"):
            continue
        for ref in entity["mentions"]:
            key = (ref["case_id"], ref["file"], ref["line"], entity["type"], entity["normalized"])
            assert key not in seen, (entity["gt_id"], seen[key])
            seen[key] = entity["gt_id"]


def test_every_entity_mention_line_writes_the_raw_text_of_person_and_org_entities(
    gt: dict[str, Any], read_case_file: Any
) -> None:
    for entity in gt["entities"]:
        if entity["type"] not in ("PERSON", "ORG") or entity["gt_id"].startswith("NZ-"):
            continue
        for ref in entity["mentions"]:
            lines: list[str] = []
            for batch in ("b01", "b02"):
                try:
                    lines = read_case_file(ref["case_id"], ref["file"], batch)
                    break
                except FileNotFoundError:
                    continue
            assert entity["raw_text"] in lines[ref["line"] - 1], entity["gt_id"]


def test_each_mention_of_an_engine_entity_maps_on_its_own_raw_text(
    gt: dict[str, Any], index: GroundTruthIndex
) -> None:
    fir = _gt_entity(gt, "PERSON", "C-101", "fir.txt", 12)
    witness = next(
        e for e in gt["entities"] if e["type"] == "PERSON" and e["raw_text"] == "Sunil Pandey"
    )
    merged = _engine(fir)
    merged["mentions"].append({**witness["mentions"][0], "raw_text": witness["raw_text"]})
    per_mention = index.map_mentions(merged)
    assert per_mention == [
        frozenset({fir["gt_id"]}),
        frozenset({witness["gt_id"]}),
    ]
    assert index.closure(per_mention[0]) != index.closure(per_mention[1])


ROLE_WORDS = ("Accused", "Complainant", "Witness", "Abhiyukt", "Shikayatkarta", "Gawah")
ROLE_WORDS_HI = ("अभियुक्त", "शिकायतकर्ता", "गवाह")


def test_person_and_org_raw_text_is_the_bare_name_without_role_prefix_or_alias_clause(
    gt: dict[str, Any],
) -> None:
    for entity in gt["entities"]:
        if entity["type"] not in ("PERSON", "ORG"):
            continue
        raw = entity["raw_text"]
        assert " urf " not in raw and " उर्फ " not in raw and " alias " not in raw, entity["gt_id"]
        assert not raw.startswith("M/s"), entity["gt_id"]
        assert not raw.startswith((*ROLE_WORDS, *ROLE_WORDS_HI)), entity["gt_id"]


def test_names_written_with_an_alias_clause_keep_the_alias_in_attributes(
    gt: dict[str, Any], read_case_file: Any
) -> None:
    named = {e["gt_id"]: e for e in gt["entities"]}
    for gt_id, alias in (("FX-14.PER.R2", "monu"), ("SF-01.PER.A", "kalu")):
        entity = named[gt_id]
        assert " urf " not in entity["raw_text"]
        assert alias in entity["attributes"]["aliases"]
    with_alias = [
        e
        for e in gt["entities"]
        if e["type"] == "PERSON" and e.get("attributes", {}).get("aliases")
    ]
    assert len(with_alias) >= 30
    for entity in with_alias:
        ref = entity["mentions"][0]
        lines = read_case_file(ref["case_id"], ref["file"])
        assert f"{entity['raw_text']} urf " in lines[ref["line"] - 1], entity["gt_id"]


def test_the_org_raw_text_drops_the_m_s_prefix_but_stays_on_the_line(
    gt: dict[str, Any], read_case_file: Any
) -> None:
    orgs = {e["gt_id"]: e for e in gt["entities"] if e["type"] == "ORG"}
    assert orgs["FX-21.ORG.A"]["raw_text"] == "Shree Balaji Traders"
    assert orgs["FX-21.ORG.B"]["raw_text"] == "Shri Balaji Trading Co"
    assert "M/s Shree Balaji Traders" in read_case_file("C-122", "fir.txt")[11]
