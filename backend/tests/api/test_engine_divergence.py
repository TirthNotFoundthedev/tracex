"""Rejected transition records always put the engine edge back (security review PR #30, item 6)."""

import uuid

from tests.api.conftest import World
from tests.api.helpers import ctx_for
from tracex_api.db import one
from tracex_api.engine_bridge import persist_result
from tracex_engine.matching import (
    LinkState,
    RunRecord,
    RunResult,
    RunStatus,
    TransitionRecord,
)

AT = "2026-11-21T10:00:00.000Z"


def run_with(world: World, link_id: str, from_state: LinkState) -> str:
    api = world.api
    run_id = str(uuid.uuid4())
    with api.owner() as conn:
        conn.execute(
            "INSERT INTO match_runs (id, started_at, ruleset_version, thresholds_version, status) "
            "VALUES (%s, now(), 'engine-matching/1.1', 1, 'SUCCEEDED')",
            (uuid.UUID(run_id),),
        )
        conn.commit()
    bad = TransitionRecord(
        link_id, from_state, LinkState.CONFIRMED, "engine", run_id, None, None, AT
    )
    record = RunRecord(
        run_id, AT, None, "u", (), "engine-matching/1.1", 1, {}, {}, 0, RunStatus.SUCCEEDED
    )
    with api.api_role() as conn:
        ctx = ctx_for(api, conn)
        persist_result(ctx, RunResult(record, (bad,)), run_id)
        ctx.commit()
        assert ctx.state.alerts
    return run_id


def test_a_rejected_record_for_a_link_with_no_row_removes_the_edge(world: World) -> None:
    api = world.api
    source = api.engine.links.get(world.links["L-2"])
    assert source is not None
    ghost = str(uuid.uuid4())
    api.engine.links.remove(world.links["L-2"])
    api.engine.links.put(source.with_changes(link_id=ghost, state=LinkState.CONFIRMED))
    run_with(world, ghost, LinkState.SUGGESTED)
    assert api.engine.links.get(ghost) is None
    with api.owner() as conn:
        assert one(conn, "SELECT 1 AS x FROM links WHERE link_id = %s", (ghost,)) is None


def test_a_rejected_record_for_a_withdrawn_row_removes_the_edge_and_audits_it(
    world: World,
) -> None:
    api = world.api
    link_id = world.links["L-2"]
    with api.owner() as conn:
        conn.execute("UPDATE links SET state = 'WITHDRAWN' WHERE link_id = %s", (link_id,))
        conn.commit()
    edge = api.engine.links.get(link_id)
    assert edge is not None
    api.engine.links.put(edge.with_changes(state=LinkState.CONFIRMED))
    before = len(api.audit_rows("ENGINE_DIVERGENCE_REVERTED"))
    run_with(world, link_id, LinkState.AUTO)
    assert api.engine.links.get(link_id) is None
    assert len(api.audit_rows("ENGINE_DIVERGENCE_REVERTED")) == before + 1
    with api.owner() as conn:
        assert one(conn, "SELECT state FROM links WHERE link_id = %s", (link_id,)) == {
            "state": "WITHDRAWN"
        }
