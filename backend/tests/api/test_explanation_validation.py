"""The explanation payload is validated against contracts/explanation.schema.json before it
leaves the API; an invalid payload fails closed (PR #30 minor, Khan's known gap)."""

import copy
from pathlib import Path
from typing import Any

import pytest

from tests.api.conftest import World
from tracex_api import views
from tracex_api.explanation_check import InvalidExplanation, check_explanation, load_schema


def good(world: World) -> dict[str, Any]:
    response = world.api.get("bharat", f"/links/{world.links['L-2']}/explanation")
    assert response.status_code == 200, response.text
    payload: dict[str, Any] = response.json()
    return payload


def test_a_valid_payload_passes_and_is_returned_unchanged(world: World) -> None:
    payload = good(world)
    check_explanation(payload)
    assert payload["link_id"] == world.links["L-2"]


@pytest.mark.parametrize(
    "damage",
    [
        lambda p: p.pop("score"),
        lambda p: p.update(extra_field="x"),
        lambda p: p.update(state="NOT_A_STATE"),
        lambda p: p.update(link_id="not-a-uuid"),
    ],
    ids=["missing-required", "unknown-field", "bad-enum", "bad-uuid"],
)
def test_an_invalid_payload_is_refused_without_echoing_its_values(
    world: World, damage: Any
) -> None:
    payload = copy.deepcopy(good(world))
    damage(payload)
    with pytest.raises(InvalidExplanation) as info:
        check_explanation(payload)
    assert "NOT_A_STATE" not in str(info.value) and "not-a-uuid" not in str(info.value)


def test_the_route_fails_closed_with_500_and_an_alert_when_the_payload_is_invalid(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    api = world.api
    original = views.explanation_payload

    def broken(*args: Any, **kwargs: Any) -> dict[str, Any]:
        payload = copy.deepcopy(original(*args, **kwargs))
        payload["surprise"] = 1
        return payload

    monkeypatch.setattr("tracex_api.routers.links.explanation_payload", broken)
    response = api.get("bharat", f"/links/{world.links['L-2']}/explanation")
    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL"
    assert "surprise" not in response.text
    assert any("explanation" in a for a in api.client.app.state.tracex.alerts)  # type: ignore[attr-defined]


def test_the_schema_is_read_from_the_environment_directory_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "explanation.schema.json").write_text(
        '{"type": "object", "required": ["only_here"]}', encoding="utf-8"
    )
    monkeypatch.setenv("TRACEX_CONTRACTS_DIR", str(tmp_path))
    load_schema.cache_clear()
    try:
        with pytest.raises(InvalidExplanation):
            check_explanation({})
        check_explanation({"only_here": 1})
    finally:
        monkeypatch.delenv("TRACEX_CONTRACTS_DIR")
        load_schema.cache_clear()
