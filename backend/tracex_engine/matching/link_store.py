"""Where SAME_AS edges live: the interface the matcher writes through, and an in-memory adapter.

At most one edge per canonical pair at any time. Edges are replaced whole, keyed by `link_id`;
`remove` exists only for WITHDRAWN (spec section 6: apart from withdrawal the engine never
deletes an edge). Case graphs are never touched, so a case rewrite keeps every edge.

`put_if_unchanged` is the compare-and-set human decisions use: it writes only when the stored
edge still has the `updated_at` the caller read. Pair uniqueness in `put` is a read-then-write
check; it relies on the API's guard that at most one matching run is RUNNING and no decision
is accepted meanwhile (spec section 6), so two writers never race on one pair.
"""

from typing import Protocol

from tracex_engine.graph import entity_sort_key
from tracex_engine.matching.model import SameAsEdge


class LinkStore(Protocol):
    def ensure_schema(self) -> None:
        """Create the constraints the edges need; safe to call again."""
        ...

    def edges(self) -> tuple[SameAsEdge, ...]:
        """Every stored SAME_AS edge, in canonical pair order."""
        ...

    def get(self, link_id: str) -> SameAsEdge | None: ...

    def put(self, edge: SameAsEdge) -> None:
        """Create the edge, or replace the edge with the same `link_id` (same pair)."""
        ...

    def put_if_unchanged(self, edge: SameAsEdge, expected_updated_at: str) -> bool:
        """Replace the stored edge only if its `updated_at` is still `expected_updated_at`."""
        ...

    def remove(self, link_id: str) -> None:
        """Delete a withdrawn edge."""
        ...


class LinkConflictError(ValueError):
    """A second edge for a pair that already has one, or a link id moved to another pair."""


class InMemoryLinkStore:
    """`LinkStore` over a dict; same behaviour as the Neo4j adapter."""

    def __init__(self) -> None:
        self._by_id: dict[str, SameAsEdge] = {}
        self._by_pair: dict[tuple[str, str], str] = {}

    def ensure_schema(self) -> None:
        return None

    def edges(self) -> tuple[SameAsEdge, ...]:
        pairs = sorted(self._by_pair, key=lambda p: (entity_sort_key(p[0]), entity_sort_key(p[1])))
        return tuple(self._by_id[self._by_pair[p]] for p in pairs)

    def get(self, link_id: str) -> SameAsEdge | None:
        return self._by_id.get(link_id)

    def put(self, edge: SameAsEdge) -> None:
        holder = self._by_pair.get(edge.pair)
        if holder is not None and holder != edge.link_id:
            raise LinkConflictError(f"pair already linked by {holder}")
        old = self._by_id.get(edge.link_id)
        if old is not None and old.pair != edge.pair:
            raise LinkConflictError("a link id never moves to another pair")
        self._by_id[edge.link_id] = edge
        self._by_pair[edge.pair] = edge.link_id

    def put_if_unchanged(self, edge: SameAsEdge, expected_updated_at: str) -> bool:
        current = self._by_id.get(edge.link_id)
        if current is None or current.updated_at != expected_updated_at:
            return False
        self.put(edge)
        return True

    def remove(self, link_id: str) -> None:
        edge = self._by_id.pop(link_id, None)
        if edge is not None:
            del self._by_pair[edge.pair]
