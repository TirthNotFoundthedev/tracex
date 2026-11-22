"""C3 cluster conflict sees the hard opposing items of Tier 2 as well (review of PR #31)."""

from tests.engine.matching.support import build, person
from tracex_engine.graph import CaseGraph, EntityType
from tracex_engine.matching.clusters import ActiveGraph, cluster_verdict
from tracex_engine.matching.corpus import Corpus


def _person_id(graph: CaseGraph) -> str:
    return next(e.entity_id for e in graph.entities if e.type is EntityType.PERSON)


def _verdict_joining_z(age_x: str) -> bool:
    """X ~ Y is active; is joining Z (age 52) to Y a C3 conflict, given X's age?"""
    x = build("C-101", persons=[person("Ravi Verma", age=age_x)])
    y = build("C-102", persons=[person("Ravi Verma")])
    z = build("C-103", persons=[person("Ravi Verma", age="52")])
    corpus = Corpus((x, y, z))
    graph = ActiveGraph()
    graph.add(_person_id(x), _person_id(y))
    return cluster_verdict(graph, corpus, _person_id(y), _person_id(z)).conflict


def test_ages_more_than_ten_years_apart_inside_the_cluster_are_a_conflict() -> None:
    assert _verdict_joining_z("30") is True


def test_ages_ten_years_apart_are_not_a_cluster_conflict() -> None:
    assert _verdict_joining_z("42") is False
