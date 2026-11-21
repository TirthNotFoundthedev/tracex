"""Login throttle keys and atomic refresh rotation (security review PR #30, items 1 and 2)."""

import threading
from typing import Any

import pytest

from tests.api.conftest import Api, password_of


@pytest.mark.parametrize("variant", ["ASHA", "Asha", "  asha  ", "aSHa"])
def test_throttle_key_ignores_case_and_surrounding_spaces(api: Api, variant: str) -> None:
    for attempt in range(5):
        bad = api.client.post("/auth/login", json={"username": "asha", "password": f"bad{attempt}"})
        assert bad.status_code == 401
    right = api.client.post(
        "/auth/login", json={"username": variant, "password": password_of("asha")}
    )
    assert right.status_code == 429
    again = api.client.post("/auth/login", json={"username": "asha", "password": "x"})
    assert again.status_code == 429


def test_login_accepts_a_differently_cased_username_when_not_throttled(api: Api) -> None:
    ok = api.client.post("/auth/login", json={"username": "ASHA", "password": password_of("asha")})
    assert ok.status_code == 200


def test_parallel_refresh_with_one_token_lets_one_win_and_revokes_the_session(api: Api) -> None:
    api.login("asha")
    refresh = api.tokens["asha"]["refresh_token"]
    racers = 8
    barrier = threading.Barrier(racers)
    codes: list[int] = []
    bodies: list[dict[str, Any]] = []

    def go() -> None:
        barrier.wait()
        response = api.client.post("/auth/refresh", json={"refresh_token": refresh})
        codes.append(response.status_code)
        if response.status_code == 200:
            bodies.append(response.json())

    threads = [threading.Thread(target=go) for _ in range(racers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert sorted(codes) == [200] + [401] * (racers - 1)
    # A loser that arrives after the session was revoked is refused as a dead session instead.
    dead = [
        r for r in api.audit_rows("AUTH_TOKEN_REJECTED") if r["detail"]["failure"] == "DEAD_SESSION"
    ]
    assert len(api.audit_rows("AUTH_REFRESH_REUSED")) >= 1
    assert len(api.audit_rows("AUTH_REFRESH_REUSED")) + len(dead) == racers - 1
    winner = {"Authorization": f"Bearer {bodies[0]['access_token']}"}
    assert api.client.get("/me", headers=winner).status_code == 401
    with api.owner() as conn:
        row = conn.execute(
            "SELECT count(*) AS n FROM refresh_tokens WHERE used_at IS NOT NULL"
        ).fetchone()
    assert row is not None and row["n"] == 1
