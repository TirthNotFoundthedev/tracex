"""The API side of the engine boundary (docs/architecture.md sections 2 and 6).

The engine is a library: it reads and writes Neo4j (or the in-memory stores in tests) and
returns plain records. This module ingests uploaded cases into it, persists what a run returns
(links, history, cited lines, grant closures and one audit row per record), sends human
decisions through the outbox, and reconciles Postgres with the engine's edges.
"""

import copy
import logging
import re
import threading
import uuid
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from psycopg.types.json import Jsonb

from tracex_api import audit
from tracex_api.db import Conn, Row, many, need, one
from tracex_engine.extract import extract_case
from tracex_engine.graph import (
    CaseGraph,
    CaseGraphStore,
    InMemoryCaseGraphStore,
    Neo4jCaseGraphStore,
    build_case_graph,
)
from tracex_engine.matching import (
    DecisionError,
    HistoryEntry,
    InMemoryLinkStore,
    LinkState,
    LinkStore,
    Matcher,
    Neo4jLinkStore,
    RunResult,
    ThresholdsError,
    TransitionRecord,
)
from tracex_engine.scoring import Thresholds

if TYPE_CHECKING:
    from tracex_api.context import AppState, Ctx

logger = logging.getLogger(__name__)

DOC_TYPES = {"fir": "FIR", "notes": "NOTE", "sdr": "SDR", "cdr": "CDR", "bank": "BANK"}
_FILE = re.compile(r"^(?P<kind>fir|notes|sdr|cdr|bank)(?:-\d+)?\.(?:txt|csv)$")
_FACT_KEY = re.compile(r"^[a-z_]+$")


def doc_type_of(file_name: str) -> str | None:
    match = _FILE.match(file_name)
    return DOC_TYPES[match["kind"]] if match else None


def engine_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def engine_iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass
class EngineGateway:
    """The two engine stores plus the per-link locks that serialise decisions."""

    graphs: CaseGraphStore
    links: LinkStore
    clock: Callable[[], str] | None = None
    _locks: dict[str, threading.Lock] = field(default_factory=lambda: defaultdict(threading.Lock))
    _guard: threading.Lock = field(default_factory=threading.Lock)

    @classmethod
    def in_memory(cls) -> "EngineGateway":
        return cls(InMemoryCaseGraphStore(), InMemoryLinkStore())

    @classmethod
    def from_neo4j(cls, uri: str, user: str, password: str) -> "EngineGateway":
        graphs = Neo4jCaseGraphStore.connect(uri, user, password)
        links = Neo4jLinkStore.connect(uri, user, password)
        graphs.ensure_schema()
        links.ensure_schema()
        return cls(graphs, links)

    def copy(self) -> "EngineGateway":
        """An independent gateway over copies of the in-memory stores (tests clone a world)."""
        return EngineGateway(copy.deepcopy(self.graphs), copy.deepcopy(self.links), self.clock)

    def lock_for(self, link_id: str) -> threading.Lock:
        with self._guard:
            return self._locks[link_id]

    def matcher(self, run_id: str | None = None) -> Matcher:
        """A matcher whose first generated id is `run_id` (the run id the API already holds)."""
        pending = [run_id] if run_id else []

        def new_id() -> str:
            return pending.pop() if pending else str(uuid.uuid4())

        if self.clock is not None:
            return Matcher(self.graphs, self.links, clock=self.clock, new_id=new_id)
        return Matcher(self.graphs, self.links, new_id=new_id)


# ----------------------------------------------------------------------------------------------
# ingest


def case_files(conn: Conn, case_id: str) -> dict[str, str]:
    files: dict[str, str] = {}
    for doc in many(
        conn, "SELECT id, file_name FROM documents WHERE case_id = %s", (uuid.UUID(case_id),)
    ):
        lines = many(
            conn,
            "SELECT text FROM document_lines WHERE document_id = %s ORDER BY line_no",
            (doc["id"],),
        )
        files[doc["file_name"]] = "".join(f"{r['text']}\n" for r in lines)
    return files


def ingest_case(conn: Conn, engine: EngineGateway, case: Row) -> CaseGraph:
    """Extract and store the case graph, and mirror new entities and mentions into Postgres."""
    case_id = str(case["id"])
    graph = build_case_graph(extract_case(case["engine_case_id"], case_files(conn, case_id)))
    engine.graphs.write_case(graph)
    documents = {
        r["file_name"]: r["id"]
        for r in many(conn, "SELECT id, file_name FROM documents WHERE case_id = %s", (case["id"],))
    }
    by_entity: dict[str, list[Any]] = defaultdict(list)
    for mention in graph.mentions:
        by_entity[mention.entity_id].append(mention)
    for entity in graph.entities:
        mentions = by_entity[entity.entity_id]
        first = mentions[0] if mentions else None
        facts = _facts(first.attributes) if first else []
        document = documents.get(entity.file)
        if document is None:
            continue
        row = one(
            conn,
            "INSERT INTO entities (case_id, engine_entity_id, type, normalized_value, "
            "display_value, raw_text, extraction_confidence, source_document_id, source_line, "
            "facts) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (engine_entity_id) DO NOTHING RETURNING id",
            (
                case["id"],
                entity.entity_id,
                entity.type.value,
                entity.normalized,
                entity.display_value,
                first.raw_text if first else entity.display_value,
                round(entity.confidence, 3),
                document,
                entity.line,
                Jsonb(facts),
            ),
        )
        entity_uuid = (
            row["id"]
            if row
            else one(
                conn,
                "SELECT id FROM entities WHERE engine_entity_id = %s",
                (entity.entity_id,),
            )["id"]  # type: ignore[index]
        )
        for mention in mentions:
            doc = documents.get(mention.file)
            if doc is not None:
                conn.execute(
                    "INSERT INTO entity_mentions (entity_id, document_id, line) "
                    "VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                    (entity_uuid, doc, mention.line),
                )
    return graph


def _facts(attributes: Sequence[tuple[str, Any]]) -> list[dict[str, str]]:
    facts = []
    for key, value in attributes:
        if not _FACT_KEY.match(key) or key.endswith("_raw"):
            continue
        text = ", ".join(value) if isinstance(value, tuple) else str(value)
        if text:
            facts.append({"key": key, "value": text})
    return facts


# ----------------------------------------------------------------------------------------------
# thresholds and runs


def current_thresholds(conn: Conn) -> Thresholds:
    row = one(conn, "SELECT * FROM threshold_versions ORDER BY thresholds_version DESC LIMIT 1")
    row = need(row)
    return Thresholds.validated(
        int(row["high_min"]), int(row["medium_min"]), int(row["thresholds_version"])
    )


def validate_thresholds(conn: Conn) -> Thresholds:
    """Before a run is marked RUNNING: invalid limits stop here with `ThresholdsError`."""
    return current_thresholds(conn)


def outbox_pending(conn: Conn) -> bool:
    row = one(conn, "SELECT 1 AS x FROM decision_outbox WHERE acked_at IS NULL LIMIT 1")
    return row is not None


def run_in_progress(conn: Conn) -> bool:
    return one(conn, "SELECT 1 AS x FROM match_runs WHERE status = 'RUNNING' LIMIT 1") is not None


@dataclass
class LinkMaps:
    """Engine ids to API ids, loaded once per persist call."""

    entities: dict[str, Row]
    cases: dict[str, Row]
    documents: dict[tuple[str, str], str]

    @classmethod
    def load(cls, conn: Conn, entity_ids: set[str], case_ids: set[str]) -> "LinkMaps":
        entities = {
            r["engine_entity_id"]: r
            for r in many(
                conn,
                "SELECT id, case_id, engine_entity_id FROM entities "
                "WHERE engine_entity_id = ANY(%s)",
                (sorted(entity_ids),),
            )
        }
        cases = {
            r["engine_case_id"]: r
            for r in many(
                conn,
                "SELECT c.id, c.engine_case_id, c.district_id FROM cases c "
                "WHERE c.engine_case_id = ANY(%s)",
                (sorted(case_ids),),
            )
        }
        documents = {
            (r["engine_case_id"], r["file_name"]): str(r["id"])
            for r in many(
                conn,
                "SELECT d.id, d.file_name, c.engine_case_id FROM documents d "
                "JOIN cases c ON c.id = d.case_id WHERE c.engine_case_id = ANY(%s)",
                (sorted(case_ids),),
            )
        }
        return cls(entities, cases, documents)


def cited_ranges(payload: dict[str, Any], maps: LinkMaps) -> list[tuple[str, str, int, int]]:
    """(document id, case id, line_from, line_to) for every line the payload cites, with
    consecutive lines merged. The engine names a document by its file name inside the case."""
    lines: dict[tuple[str, str], set[int]] = defaultdict(set)
    sources: list[dict[str, Any]] = [r["source"] for r in payload.get("records", [])]
    for tier in payload.get("support", []):
        for item in tier.get("items", []):
            sources.extend(item.get("sources", []))
    for item in payload.get("against", []):
        sources.extend(item.get("sources", []))
    for source in sources:
        doc = maps.documents.get((source["case_id"], source["document_id"]))
        if doc is not None:
            lines[(doc, source["case_id"])].add(int(source["line"]))
    ranges = []
    for (doc, engine_case), numbers in lines.items():
        ordered = sorted(numbers)
        start = prev = ordered[0]
        for n in ordered[1:]:
            if n != prev + 1:
                ranges.append((doc, str(maps.cases[engine_case]["id"]), start, prev))
                start = n
            prev = n
        ranges.append((doc, str(maps.cases[engine_case]["id"]), start, prev))
    return ranges


def _dec(value: Any) -> Decimal:
    return Decimal(str(value))


def persist_result(ctx: "Ctx", result: RunResult, run_id: str) -> None:
    """Write what a run returned, in the caller's transaction (architecture section 6).

    The links to refresh are every transition's link plus `updated_link_ids`; an edge is read
    back from the engine for each, so Postgres never lags it. A transition whose `from` state is
    not the Postgres state is rejected: nothing is written, the edge is reverted, the system
    event ENGINE_DIVERGENCE_REVERTED is audited and an alert is raised."""
    engine = ctx.state.engine
    matcher = engine.matcher()
    ids = list(
        dict.fromkeys([t.link_id for t in result.transitions] + list(result.updated_link_ids))
    )
    edges = {i: engine.links.get(i) for i in ids}
    entity_ids = {e for edge in edges.values() if edge for e in edge.pair}
    case_ids = {c for edge in edges.values() if edge for c in (edge.case_a, edge.case_b)}
    maps = LinkMaps.load(ctx.conn, entity_ids, case_ids)
    transitions: dict[str, list[TransitionRecord]] = defaultdict(list)
    for t in result.transitions:
        transitions[t.link_id].append(t)
    for link_id in ids:
        edge = edges[link_id]
        row = one(ctx.conn, "SELECT * FROM links WHERE link_id = %s", (uuid.UUID(link_id),))
        records = transitions.get(link_id, [])
        for record in records:
            if not _from_matches(row, record):
                _reject_record(ctx, row, record)
                break
        else:
            _apply_link(ctx, matcher, edge, row, records, maps, run_id)


def _from_matches(row: Row | None, record: TransitionRecord) -> bool:
    if record.from_state is None:
        return row is None or row["state"] == "WITHDRAWN"
    return row is not None and row["state"] == record.from_state.value


def _reject_record(ctx: "Ctx", row: Row | None, record: TransitionRecord) -> None:
    ctx.state.alert(f"transition record for {record.link_id} does not match the stored state")
    if row is None:
        ctx.state.engine.links.remove(record.link_id)
        return
    revert_edge(ctx, row)
    ctx.audit(
        "ENGINE_DIVERGENCE_REVERTED",
        actor=audit.SYSTEM,
        refs=[str(row["case_a_id"]), str(row["case_b_id"])],
        target_type="LINK",
        target_id=str(row["link_id"]),
        detail={"link_ids": [str(row["link_id"])], "cause": "FROM_STATE_MISMATCH"},
    )


def history_from_rows(rows: Sequence[Row]) -> tuple[HistoryEntry, ...]:
    return tuple(
        HistoryEntry(
            LinkState(r["from_state"]) if r["from_state"] else None,
            LinkState(r["to_state"]) if r["to_state"] else None,
            "engine" if r["actor_kind"] == "ENGINE" else str(r["actor_user_id"]),
            engine_iso(r["at"]),
            r["reason_code"],
            r["reason_text"],
            str(r["decision_id"]) if r["decision_id"] else None,
        )
        for r in rows
    )


def revert_edge(ctx: "Ctx", row: Row) -> None:
    """Put the Neo4j edge back to the Postgres state and history (never only alert). A WITHDRAWN
    row has no edge, so the edge is removed."""
    engine = ctx.state.engine
    edge = engine.links.get(str(row["link_id"]))
    if edge is None:
        return
    if row["state"] == "WITHDRAWN":
        engine.links.remove(edge.link_id)
        return
    history = many(
        ctx.conn, "SELECT * FROM link_history WHERE link_id = %s ORDER BY id", (row["link_id"],)
    )
    engine.links.put(
        edge.with_changes(
            state=LinkState(row["state"]),
            history=history_from_rows(history),
            updated_at=engine_iso(row["updated_at"]),
        )
    )


def _apply_link(
    ctx: "Ctx",
    matcher: Matcher,
    edge: Any,
    row: Row | None,
    records: list[TransitionRecord],
    maps: LinkMaps,
    run_id: str,
) -> None:
    link_id = (records[0].link_id) if records else edge.link_id
    withdrawn = bool(records) and records[-1].to_state is None
    if withdrawn:
        _withdraw(ctx, row, records[-1], run_id)
        return
    if edge is None:
        return
    payload = matcher.explanation(edge.link_id)
    payload = need(payload)
    a, b = maps.entities[edge.entity_a_id], maps.entities[edge.entity_b_id]
    swapped = str(a["id"]) > str(b["id"])
    if swapped:
        a, b = b, a
    case_a, case_b = (str(a["case_id"]), str(b["case_id"]))
    at = engine_time(edge.updated_at)
    previous_version = row["thresholds_version"] if row else None
    values = (
        edge.state.value,
        edge.band.value,
        _dec(edge.score),
        edge.thresholds_version,
        edge.ruleset_version,
        uuid.UUID(edge.match_run_id),
        Jsonb(payload),
        at,
    )
    if row is None:
        ctx.conn.execute(
            "INSERT INTO links (link_id, entity_a_id, entity_b_id, case_a_id, case_b_id, "
            "entity_type, state, band, score, thresholds_version, ruleset_version, match_run_id, "
            "explanation, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
            "%s, %s, %s, %s, %s)",
            (
                uuid.UUID(edge.link_id),
                a["id"],
                b["id"],
                uuid.UUID(case_a),
                uuid.UUID(case_b),
                edge.entity_type.value,
                *values[:7],
                engine_time(edge.created_at),
                at,
            ),
        )
    else:
        ctx.conn.execute(
            "UPDATE links SET state = %s, band = %s, score = %s, thresholds_version = %s, "
            "ruleset_version = %s, match_run_id = %s, explanation = %s, updated_at = %s "
            "WHERE link_id = %s",
            (*values, uuid.UUID(edge.link_id)),
        )
    for record in records:
        ctx.conn.execute(
            "INSERT INTO link_history (link_id, from_state, to_state, actor_kind, at, reason_code, "
            "match_run_id) VALUES (%s, %s, %s, 'ENGINE', %s, %s, %s)",
            (
                uuid.UUID(link_id),
                record.from_state.value if record.from_state else None,
                record.to_state.value if record.to_state else None,
                engine_time(record.at),
                record.reason_code,
                uuid.UUID(run_id),
            ),
        )
        _audit_record(ctx, record, edge, case_a, case_b, a, b, previous_version, run_id)
    refresh_cited_lines(ctx, edge.link_id, payload, maps)
    close_grants_if_needed(ctx, edge.link_id, edge.state.value, case_a, case_b)


def _audit_record(
    ctx: "Ctx",
    record: TransitionRecord,
    edge: Any,
    case_a: str,
    case_b: str,
    a: Row,
    b: Row,
    previous_version: int | None,
    run_id: str,
) -> None:
    to, frm = record.to_state, record.from_state
    base: dict[str, Any] = {
        "actor": audit.SYSTEM,
        "refs": [case_a, case_b],
        "target_type": "LINK",
        "target_id": edge.link_id,
    }
    if frm is None and to in (LinkState.AUTO, LinkState.SUGGESTED):
        event = "LINK_AUTO_CREATED" if to is LinkState.AUTO else "LINK_SUGGESTED"
        ctx.audit(
            event,
            detail={
                "run_id": run_id,
                "band": edge.band.value,
                "score": float(edge.score),
                "entity_ids": [str(a["id"]), str(b["id"])],
            },
            **base,
        )
    elif record.reason_code == "DEMOTED" and frm and to:
        cause = (
            "THRESHOLDS_CHANGED"
            if previous_version is not None and previous_version != edge.thresholds_version
            else "EVIDENCE_LOST"
        )
        ctx.audit(
            "LINK_DEMOTED",
            detail={
                "run_id": run_id,
                "previous_state": frm.value,
                "new_state": to.value,
                "cause": cause,
            },
            **base,
        )
    elif record.reason_code == "PROMOTED" and frm and to:
        ctx.audit(
            "LINK_PROMOTED",
            detail={"run_id": run_id, "previous_state": frm.value, "new_state": to.value},
            **base,
        )


def _withdraw(ctx: "Ctx", row: Row | None, record: TransitionRecord, run_id: str) -> None:
    if row is None or row["state"] == "WITHDRAWN":
        return
    mark_withdrawn(ctx, row, run_id, engine_time(record.at))


def mark_withdrawn(ctx: "Ctx", row: Row, run_id: str | None, at: datetime) -> None:
    ctx.conn.execute(
        "UPDATE links SET state = 'WITHDRAWN', updated_at = %s WHERE link_id = %s",
        (at, row["link_id"]),
    )
    ctx.conn.execute(
        "INSERT INTO link_history (link_id, from_state, to_state, actor_kind, at, reason_code, "
        "match_run_id) VALUES (%s, %s, NULL, 'ENGINE', %s, 'WITHDRAWN', %s)",
        (row["link_id"], row["state"], at, uuid.UUID(run_id) if run_id else None),
    )
    detail: dict[str, Any] = {"previous_state": row["state"]}
    if run_id:
        detail["run_id"] = run_id
    ctx.audit(
        "LINK_WITHDRAWN",
        actor=audit.SYSTEM,
        refs=[str(row["case_a_id"]), str(row["case_b_id"])],
        target_type="LINK",
        target_id=str(row["link_id"]),
        detail=detail,
    )
    close_grants_if_needed(
        ctx, str(row["link_id"]), "WITHDRAWN", str(row["case_a_id"]), str(row["case_b_id"])
    )


def refresh_cited_lines(ctx: "Ctx", link_id: str, payload: dict[str, Any], maps: LinkMaps) -> None:
    ctx.conn.execute("DELETE FROM link_cited_lines WHERE link_id = %s", (uuid.UUID(link_id),))
    for doc, _case, line_from, line_to in cited_ranges(payload, maps):
        ctx.conn.execute(
            "INSERT INTO link_cited_lines (link_id, document_id, line_from, line_to) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
            (uuid.UUID(link_id), uuid.UUID(doc), line_from, line_to),
        )


def close_grants_if_needed(ctx: "Ctx", link_id: str, state: str, case_a: str, case_b: str) -> None:
    """Close live grants when the link is REJECTED, UNDONE or WITHDRAWN (LINK_CLOSED), or its
    evidence now cites a line outside the ranges fixed at approval (EVIDENCE_CHANGED)."""
    grants = many(
        ctx.conn,
        "SELECT id FROM access_grants WHERE link_id = %s AND state = 'ACTIVE'",
        (uuid.UUID(link_id),),
    )
    for grant in grants:
        cause: str | None = None
        if state in ("REJECTED", "UNDONE", "WITHDRAWN"):
            cause = "LINK_CLOSED"
        else:
            outside = one(
                ctx.conn,
                "SELECT 1 AS x FROM link_cited_lines c "
                "JOIN documents d ON d.id = c.document_id "
                "JOIN links l ON l.link_id = c.link_id "
                "JOIN access_grants g ON g.id = %s "
                "WHERE c.link_id = %s AND d.case_id = g.far_case_id "
                "AND NOT EXISTS (SELECT 1 FROM grant_line_ranges r WHERE r.grant_id = g.id "
                "AND r.document_id = c.document_id AND r.line_from <= c.line_from "
                "AND r.line_to >= c.line_to) "
                "AND (SELECT role_at_grant FROM access_grants WHERE id = g.id) <> 'JUNIOR' LIMIT 1",
                (grant["id"], uuid.UUID(link_id)),
            )
            if outside is not None:
                cause = "EVIDENCE_CHANGED"
        if cause:
            close_grant(ctx, grant["id"], cause, link_id, case_a, case_b, "ACCESS_GRANT_CLOSED")


def close_grant(
    ctx: "Ctx",
    grant_id: uuid.UUID,
    cause: str,
    link_id: str,
    case_a: str,
    case_b: str,
    event: str,
) -> None:
    ctx.conn.execute(
        "UPDATE access_grants SET state = %s, closed_at = %s, close_cause = %s WHERE id = %s",
        ("REVOKED" if event == "ACCESS_GRANT_REVOKED" else "REVOKED", ctx.now(), cause, grant_id),
    )
    ctx.audit(
        event,
        actor=audit.SYSTEM if event == "ACCESS_GRANT_CLOSED" else None,
        refs=[case_a, case_b],
        target_type="GRANT",
        target_id=str(grant_id),
        detail={"cause": cause},
    )


# ----------------------------------------------------------------------------------------------
# decisions


@dataclass(frozen=True)
class DecisionOutcome:
    ok: bool
    note: str = ""


def send_decision(state: "AppState", conn: Conn, decision_id: str) -> DecisionOutcome:
    """Call the engine for one outbox row (idempotent on `decision_id`) and acknowledge it.
    Any of the four engine answer codes is divergence: alerted, left unacknowledged."""
    row = one(
        conn, "SELECT * FROM decision_outbox WHERE decision_id = %s", (uuid.UUID(decision_id),)
    )
    if row is None or row["acked_at"] is not None:
        return DecisionOutcome(True)
    engine = state.engine
    link_id = str(row["link_id"])
    with engine.lock_for(link_id):
        answer = engine.matcher().apply_decision(
            link_id,
            LinkState(row["expected_from"]),
            LinkState(row["to_state"]),
            str(row["actor_user_id"]),
            decision_id,
            row["reason_code"],
            row["reason_text"],
        )
    if isinstance(answer, DecisionError):
        state.alert(f"engine answered {answer.value} for decision {decision_id}")
        return DecisionOutcome(False, answer.value)
    conn.execute(
        "UPDATE decision_outbox SET acked_at = %s WHERE decision_id = %s",
        (state.now(), uuid.UUID(decision_id)),
    )
    conn.commit()
    return DecisionOutcome(True)


# ----------------------------------------------------------------------------------------------
# reconcile


def reconcile(ctx: "Ctx") -> dict[str, int]:
    """Startup sweep (architecture section 2, Reconciliation). Returns counts for the log."""
    engine = ctx.state.engine
    conn = ctx.conn
    counts = {"reverted": 0, "withdrawn": 0, "replayed": 0, "imported": 0}
    known_decisions = {
        str(r["decision_id"]) for r in many(conn, "SELECT decision_id FROM decision_outbox")
    }
    seen_ids: set[str] = set()
    for edge in engine.links.edges():
        seen_ids.add(edge.link_id)
        row = one(conn, "SELECT * FROM links WHERE link_id = %s", (uuid.UUID(edge.link_id),))
        forged = [
            h
            for h in edge.history
            if h.decision_id is not None and h.decision_id not in known_decisions
        ]
        if row is None or row["state"] == "WITHDRAWN":
            if forged:
                engine.links.remove(edge.link_id)
                ctx.state.alert(f"edge {edge.link_id} carries a forged decision and no row")
                counts["reverted"] += 1
            else:
                counts["imported"] += import_edge(ctx, edge)
            continue
        if forged:
            revert_edge(ctx, row)
            ctx.audit(
                "ENGINE_DIVERGENCE_REVERTED",
                actor=audit.SYSTEM,
                refs=[str(row["case_a_id"]), str(row["case_b_id"])],
                target_type="LINK",
                target_id=edge.link_id,
                detail={"link_ids": [edge.link_id], "cause": "UNKNOWN_DECISION"},
            )
            ctx.state.alert(f"edge {edge.link_id} carried a decision that is not in the outbox")
            counts["reverted"] += 1
    for row in many(conn, "SELECT * FROM links WHERE state <> 'WITHDRAWN'"):
        if str(row["link_id"]) not in seen_ids:
            mark_withdrawn(ctx, row, None, ctx.now())
            counts["withdrawn"] += 1
    conn.commit()
    for pending in many(conn, "SELECT decision_id FROM decision_outbox WHERE acked_at IS NULL"):
        if send_decision(ctx.state, conn, str(pending["decision_id"])).ok:
            counts["replayed"] += 1
    ctx.commit()
    return counts


def import_edge(ctx: "Ctx", edge: Any) -> int:
    """An edge written by a run whose records never reached Postgres: stub the run row if it is
    missing and write the link, history and audit row from the engine's edge."""
    conn = ctx.conn
    run_id = uuid.UUID(edge.match_run_id)
    if one(conn, "SELECT 1 AS x FROM match_runs WHERE id = %s", (run_id,)) is None:
        conn.execute(
            "INSERT INTO match_runs (id, started_at, finished_at, ruleset_version, "
            "thresholds_version, status, error_code) VALUES (%s, %s, %s, %s, %s, 'FAILED', "
            "'RECONCILED')",
            (
                run_id,
                engine_time(edge.created_at),
                engine_time(edge.updated_at),
                edge.ruleset_version,
                edge.thresholds_version,
            ),
        )
    maps = LinkMaps.load(conn, set(edge.pair), {edge.case_a, edge.case_b})
    if edge.entity_a_id not in maps.entities or edge.entity_b_id not in maps.entities:
        ctx.state.alert(f"edge {edge.link_id} names an entity the API does not know")
        return 0
    created = TransitionRecord(
        edge.link_id, None, edge.state, "engine", edge.match_run_id, None, None, edge.created_at
    )
    result = RunResult(run=None, transitions=(created,))  # type: ignore[arg-type]
    persist_result(ctx, result, edge.match_run_id)
    return 1


def thresholds_error_to_fields(exc: ThresholdsError) -> list[dict[str, str]]:
    del exc
    return [{"field": "thresholds", "code": "invalid"}]


def counts_to_json(created: dict[str, int]) -> dict[str, Any]:
    return {
        "created_by_state": {
            "AUTO": created.get("AUTO", 0),
            "SUGGESTED": created.get("SUGGESTED", 0),
        }
    }
