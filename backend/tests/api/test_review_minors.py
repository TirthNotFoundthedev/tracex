"""Security review PR #30, minors 7 to 11: upload caps, masking, grant scope, approval re-check."""

import uuid

import pytest

from tests.api.conftest import World
from tests.api.helpers import body_text
from tests.api.test_access import doc_id, request_access
from tracex_api.db import need, one
from tracex_api.views import mask_text


@pytest.mark.parametrize(
    "text",
    [
        "Mobile 9876543210 seen",
        "Mobile +91 98765 43210 seen",
        "Mobile 98765-43210 seen",
        "Mobile 98765 43210 seen",
        "Mobile +919876543210 seen",
    ],
)
def test_formatted_phone_numbers_are_masked_in_free_text(text: str) -> None:
    masked = mask_text(text)
    assert "43210" not in masked and "98765" not in masked
    assert masked.startswith("Mobile ") and masked.endswith(" seen")


def test_upload_over_the_size_cap_or_file_count_is_refused(world: World) -> None:
    api = world.api
    with api.owner() as conn:
        district = need(one(conn, "SELECT id FROM districts LIMIT 1"))["id"]
    big = b"x" * (api.settings.max_upload_bytes + 1)
    too_big = api.client.post(
        "/uploads",
        headers=api.h("hari"),
        data={"case_number": "C-900", "district_id": str(district)},
        files=[("files", ("big.txt", big, "text/plain"))],
    )
    assert too_big.status_code == 422
    many_files = api.client.post(
        "/uploads",
        headers=api.h("hari"),
        data={"case_number": "C-900", "district_id": str(district)},
        files=[("files", (f"f{i}.txt", b"a", "text/plain")) for i in range(21)],
    )
    assert many_files.status_code == 422
    with api.owner() as conn:
        assert one(conn, "SELECT 1 AS x FROM cases WHERE case_number = 'C-900'") is None


def test_a_grant_holder_does_not_get_the_far_case_title(world: World) -> None:
    api = world.api
    created = request_access(api, world)
    assert (
        api.post("farid", f"/access-requests/{created['request_id']}/approve", {}).status_code
        == 200
    )
    with api.owner() as conn:
        conn.execute("UPDATE cases SET title = 'Far case secret title'")
        conn.commit()
    granted = api.get("bharat", f"/entities/{world.entities['E-2']}")
    assert granted.status_code == 200 and granted.json()["via_grant"] is True
    assert "title" not in granted.json()["case"]
    assert "Far case secret title" not in body_text(granted)


def test_approval_is_refused_when_the_requester_no_longer_sees_a_stub(world: World) -> None:
    api = world.api
    created = request_access(api, world)
    with api.owner() as conn:
        conn.execute("UPDATE users SET active = false WHERE username = 'bharat'")
        conn.commit()
    response = api.post("farid", f"/access-requests/{created['request_id']}/approve", {})
    assert response.status_code == 409
    with api.owner() as conn:
        assert one(conn, "SELECT 1 AS x FROM access_grants") is None


def test_a_holder_with_several_grants_on_a_document_reads_the_range_one_of_them_covers(
    world: World,
) -> None:
    api = world.api
    created = request_access(api, world)
    assert (
        api.post("farid", f"/access-requests/{created['request_id']}/approve", {}).status_code
        == 200
    )
    document = doc_id(api, "C-201")
    with api.owner() as conn:
        first = need(one(conn, "SELECT * FROM access_grants"))
        request = need(
            one(conn, "SELECT * FROM access_requests WHERE id = %s", (first["request_id"],))
        )
        for i in range(4):
            copy = need(
                one(
                    conn,
                    "INSERT INTO access_requests (requester_id, stub_id, link_id, near_case_id, "
                    "far_case_id, reason, state, requested_at, expires_at, decided_by, decided_at) "
                    "SELECT requester_id, stub_id, link_id, near_case_id, far_case_id, reason, "
                    "'APPROVED', requested_at, expires_at, decided_by, decided_at "
                    "FROM access_requests WHERE id = %s RETURNING id",
                    (request["id"],),
                )
            )
            decoy = need(
                one(
                    conn,
                    "INSERT INTO access_grants (request_id, holder_id, link_id, far_entity_id, "
                    "far_case_id, state, starts_at, expires_at, role_at_grant) "
                    "SELECT %s, holder_id, link_id, far_entity_id, far_case_id, state, starts_at, "
                    "expires_at, role_at_grant FROM access_grants WHERE id = %s RETURNING id",
                    (copy["id"], first["id"]),
                )
            )
            conn.execute(
                "INSERT INTO grant_line_ranges (grant_id, document_id, line_from, line_to) "
                "VALUES (%s, %s, %s, %s)",
                (decoy["id"], uuid.UUID(document), 90 + i, 90 + i),
            )
        conn.commit()
        cited = need(
            one(
                conn,
                "SELECT line_from, line_to FROM grant_line_ranges WHERE grant_id = %s",
                (first["id"],),
            )
        )
    for _ in range(3):
        response = api.get(
            "bharat",
            f"/documents/{document}/lines",
            line_from=cited["line_from"],
            line_to=cited["line_to"],
        )
        assert response.status_code == 200, response.text
