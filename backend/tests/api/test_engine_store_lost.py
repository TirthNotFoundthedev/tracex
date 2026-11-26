"""N3: an empty engine store on restart must not mark every link WITHDRAWN (PR #30 re-review)."""

import time

from fastapi.testclient import TestClient

from tests.api.conftest import Api, World
from tests.api.test_startup import wait_ready
from tracex_api.engine_bridge import EngineGateway
from tracex_api.main import create_app


def link_states(api: Api) -> dict[str, str]:
    with api.owner() as conn:
        rows = conn.execute("SELECT link_id, state FROM links").fetchall()
    return {str(r["link_id"]): str(r["state"]) for r in rows}


def test_an_empty_engine_store_does_not_withdraw_every_link(world: World) -> None:
    api = world.api
    before = link_states(api)
    assert before and "WITHDRAWN" not in before.values()
    restarted = create_app(api.settings, EngineGateway.in_memory(), api.clock)
    with TestClient(restarted) as client:
        time.sleep(2)
        assert client.get("/ready").status_code == 503
        assert client.get("/health").status_code == 200
    state = restarted.state.tracex
    assert not state.reconciled.is_set()
    assert any("engine store" in a for a in state.alerts)
    assert link_states(api) == before


def test_links_really_gone_from_a_non_empty_store_are_still_withdrawn(world: World) -> None:
    api = world.api
    victim = world.links["L-3"]
    api.engine.links.remove(victim)
    assert list(api.engine.links.edges())
    restarted = create_app(api.settings, api.engine, api.clock)
    with TestClient(restarted) as client:
        assert wait_ready(client) == 200
    states = link_states(api)
    assert states[victim] == "WITHDRAWN"
    assert [s for k, s in states.items() if k != victim and s == "WITHDRAWN"] == []


def test_the_sweep_recovers_when_the_store_comes_back(world: World) -> None:
    api = world.api
    before = link_states(api)
    empty = EngineGateway.in_memory()
    restarted = create_app(api.settings, empty, api.clock)
    with TestClient(restarted) as client:
        time.sleep(1)
        assert client.get("/ready").status_code == 503
        empty.graphs = api.engine.graphs
        empty.links = api.engine.links
        assert wait_ready(client, seconds=30) == 200
    assert link_states(api) == before
