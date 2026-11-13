"""Identity clusters and the cluster guards C3 and C4 (spec section 6).

A cluster is a connected component of active edges (AUTO, CONFIRMED) of one entity type. It
is derived on demand and never stored. Before an edge becomes AUTO the matcher asks for the
verdict on the cluster the edge would create.
"""

from collections import defaultdict, deque

from tracex_engine.matching.corpus import Corpus
from tracex_engine.matching.evidence import hard_conflict
from tracex_engine.scoring import ClusterVerdict


class ActiveGraph:
    """The active edges known so far in a run, as an adjacency map."""

    def __init__(self) -> None:
        self._adj: dict[str, set[str]] = defaultdict(set)

    def add(self, a: str, b: str) -> None:
        self._adj[a].add(b)
        self._adj[b].add(a)

    def discard(self, a: str, b: str) -> None:
        self._adj[a].discard(b)
        self._adj[b].discard(a)

    def has(self, a: str, b: str) -> bool:
        return b in self._adj.get(a, ())

    def component(self, start: str, without: tuple[str, str] | None = None) -> set[str]:
        """Members of `start`'s cluster, ignoring the edge `without` if given."""
        seen = {start}
        queue = deque([start])
        while queue:
            node = queue.popleft()
            for other in self._adj.get(node, ()):
                if without and {node, other} == set(without):
                    continue
                if other not in seen:
                    seen.add(other)
                    queue.append(other)
        return seen


def cluster_verdict(graph: ActiveGraph, corpus: Corpus, a: str, b: str) -> ClusterVerdict:
    """C3 (no hard or veto item on any cross-case pair of the resulting cluster, other than the
    pair itself) and C4 (no bridge of two clusters of two or more; no two entities of one case)."""
    left = graph.component(a, without=(a, b))
    if b in left:
        joined, bridge = left, False
    else:
        right = graph.component(b, without=(a, b))
        joined, bridge = left | right, len(left) >= 2 and len(right) >= 2
    members = sorted(joined)
    cases = [corpus.entities[m].case_id for m in members]
    same_case = len(set(cases)) < len(cases)
    conflict = False
    for i, x in enumerate(members):
        for y in members[i + 1 :]:
            if {x, y} == {a, b} or corpus.entities[x].case_id == corpus.entities[y].case_id:
                continue
            if hard_conflict(corpus, corpus.entities[x], corpus.entities[y]):
                conflict = True
                break
        if conflict:
            break
    return ClusterVerdict(conflict=conflict, bridge=bridge, same_case=same_case)
