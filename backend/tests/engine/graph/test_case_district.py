"""The district of a case, read from the FIR header, in the graph and the corpus."""

from tests.engine.matching.support import from_files, store_of
from tests.engine.support import fir_file, note, notes_file
from tracex_engine.graph import CaseDistrict, EntityType
from tracex_engine.matching.corpus import Corpus


def fir(
    case_id: str, district_line: str | None = "District: Rivergate", narrative: str = ""
) -> str:
    text = fir_file(case_id, {12: narrative or "Accused Ramesh Yadav, mobile 9000022310."})
    lines = text.split("\n")
    if district_line is None:
        lines[5] = "Police Station: PS Rivergate Central"
    else:
        lines[5] = district_line
    return "\n".join(lines)


def test_the_fir_header_district_is_on_the_case_graph_with_its_line() -> None:
    graph = from_files("C-101", {"fir.txt": fir("C-101", "District: Rivergate")})

    assert graph.district == CaseDistrict("rivergate", "Rivergate", "fir.txt", 6)


def test_a_case_without_a_fir_district_has_none() -> None:
    notes = {"notes.txt": notes_file("C-102", {3: note("Number 9000022310 is used by Suresh.")})}

    assert from_files("C-102", notes).district is None
    assert from_files("C-103", {"fir.txt": fir("C-103", None)}).district is None


def test_an_empty_district_value_is_no_district() -> None:
    assert from_files("C-104", {"fir.txt": fir("C-104", "District:")}).district is None


def test_district_survives_the_store_and_reaches_the_corpus() -> None:
    graph = from_files("C-101", {"fir.txt": fir("C-101")})
    store = store_of(graph)

    assert store.read_case("C-101") == graph
    corpus = Corpus.load(store)
    assert corpus.district_of_case("C-101") == "rivergate"
    assert corpus.district_of_case("C-999") is None


def test_effective_district_is_the_stated_one_else_the_case_district() -> None:
    sdr = "msisdn,subscriber_name,relative_name,locality,district,activated_on\n"
    sdr += "9000035562,Kamla Devi,,,Hillcrest,2024-01-05\n"
    stated = from_files("C-101", {"fir.txt": fir("C-101"), "sdr.csv": sdr})
    plain = from_files("C-102", {"fir.txt": fir("C-102", "District: Lakeside")})
    bare = from_files("C-103", {"fir.txt": fir("C-103", None)})
    corpus = Corpus([stated, plain, bare])

    def person(case: str) -> str:
        return next(
            e.entity_id
            for e in corpus.entities.values()
            if e.case_id == case and e.type is EntityType.PERSON
        )

    kamla = next(e.entity_id for e in corpus.entities.values() if e.normalized == "kamla devi")
    assert corpus.effective_districts(kamla) == {"hillcrest"}
    assert corpus.effective_districts(person("C-102")) == {"lakeside"}
    assert corpus.effective_districts(person("C-103")) == frozenset()
