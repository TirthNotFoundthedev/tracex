from tests.api.conftest import Api, World


def test_login_and_me(api: Api) -> None:
    response = api.get("asha", "/me")
    assert response.status_code == 200
    assert response.json()["role"] == "JUNIOR"


def test_world_is_built(world: World) -> None:
    assert set(world.links) >= {"L-1", "L-2", "L-3"}
