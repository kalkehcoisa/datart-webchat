import pytest
from app.models.models import RoomVisibility
from tests.conftest import create_user, auth_headers


@pytest.mark.asyncio
async def test_create_room(client, db):
    user = await create_user(db, "room_alice", "room_alice@test.com")
    r = await client.post("/api/v1/rooms",
        headers=auth_headers(user),
        json={"name": "general", "visibility": "public"}
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "general"
    assert data["owner_id"] == str(user.id)
    assert data["member_count"] == 1


@pytest.mark.asyncio
async def test_create_room_duplicate_name(client, db):
    user = await create_user(db, "room_bob", "room_bob@test.com")
    await client.post("/api/v1/rooms",
        headers=auth_headers(user),
        json={"name": "unique-room", "visibility": "public"}
    )
    r = await client.post("/api/v1/rooms",
        headers=auth_headers(user),
        json={"name": "unique-room", "visibility": "public"}
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_list_public_rooms(client, db):
    user = await create_user(db, "room_carol", "room_carol@test.com")
    await client.post("/api/v1/rooms",
        headers=auth_headers(user),
        json={"name": "public-room-1", "visibility": "public"}
    )
    r = await client.get("/api/v1/rooms", headers=auth_headers(user))
    assert r.status_code == 200
    names = [x["name"] for x in r.json()]
    assert "public-room-1" in names


@pytest.mark.asyncio
async def test_private_room_not_in_catalog(client, db):
    user = await create_user(db, "room_dave", "room_dave@test.com")
    await client.post("/api/v1/rooms",
        headers=auth_headers(user),
        json={"name": "secret-room", "visibility": "private"}
    )
    r = await client.get("/api/v1/rooms", headers=auth_headers(user))
    assert r.status_code == 200
    names = [x["name"] for x in r.json()]
    assert "secret-room" not in names


@pytest.mark.asyncio
async def test_join_public_room(client, db):
    owner = await create_user(db, "room_eve", "room_eve@test.com")
    joiner = await create_user(db, "room_frank", "room_frank@test.com")

    r = await client.post("/api/v1/rooms",
        headers=auth_headers(owner),
        json={"name": "joinable-room", "visibility": "public"}
    )
    room_id = r.json()["id"]

    r2 = await client.post(f"/api/v1/rooms/{room_id}/join", headers=auth_headers(joiner))
    assert r2.status_code == 200

    r3 = await client.get(f"/api/v1/rooms/{room_id}/members", headers=auth_headers(joiner))
    user_ids = [m["user_id"] for m in r3.json()]
    assert str(joiner.id) in user_ids


@pytest.mark.asyncio
async def test_cannot_join_private_room_directly(client, db):
    owner = await create_user(db, "room_grace", "room_grace@test.com")
    other = await create_user(db, "room_henry", "room_henry@test.com")

    r = await client.post("/api/v1/rooms",
        headers=auth_headers(owner),
        json={"name": "private-only", "visibility": "private"}
    )
    room_id = r.json()["id"]

    r2 = await client.post(f"/api/v1/rooms/{room_id}/join", headers=auth_headers(other))
    assert r2.status_code == 403


@pytest.mark.asyncio
async def test_owner_cannot_leave(client, db):
    owner = await create_user(db, "room_iris", "room_iris@test.com")
    r = await client.post("/api/v1/rooms",
        headers=auth_headers(owner),
        json={"name": "no-leave-room", "visibility": "public"}
    )
    room_id = r.json()["id"]

    r2 = await client.post(f"/api/v1/rooms/{room_id}/leave", headers=auth_headers(owner))
    assert r2.status_code == 400


@pytest.mark.asyncio
async def test_ban_and_rejoin_blocked(client, db):
    owner = await create_user(db, "room_jack", "room_jack@test.com")
    target = await create_user(db, "room_kate", "room_kate@test.com")

    r = await client.post("/api/v1/rooms",
        headers=auth_headers(owner),
        json={"name": "ban-test-room", "visibility": "public"}
    )
    room_id = r.json()["id"]

    await client.post(f"/api/v1/rooms/{room_id}/join", headers=auth_headers(target))
    await client.post(f"/api/v1/rooms/{room_id}/members/{target.id}/ban",
        headers=auth_headers(owner)
    )

    r2 = await client.post(f"/api/v1/rooms/{room_id}/join", headers=auth_headers(target))
    assert r2.status_code == 403


@pytest.mark.asyncio
async def test_delete_room_owner_only(client, db):
    owner = await create_user(db, "room_leo", "room_leo@test.com")
    other = await create_user(db, "room_mia", "room_mia@test.com")

    r = await client.post("/api/v1/rooms",
        headers=auth_headers(owner),
        json={"name": "delete-test", "visibility": "public"}
    )
    room_id = r.json()["id"]

    await client.post(f"/api/v1/rooms/{room_id}/join", headers=auth_headers(other))

    r2 = await client.delete(f"/api/v1/rooms/{room_id}", headers=auth_headers(other))
    assert r2.status_code == 403

    r3 = await client.delete(f"/api/v1/rooms/{room_id}", headers=auth_headers(owner))
    assert r3.status_code == 200


@pytest.mark.asyncio
async def test_admin_grant_revoke(client, db):
    owner = await create_user(db, "room_noah", "room_noah@test.com")
    member = await create_user(db, "room_olivia", "room_olivia@test.com")

    r = await client.post("/api/v1/rooms",
        headers=auth_headers(owner),
        json={"name": "admin-test", "visibility": "public"}
    )
    room_id = r.json()["id"]
    await client.post(f"/api/v1/rooms/{room_id}/join", headers=auth_headers(member))

    r2 = await client.post(f"/api/v1/rooms/{room_id}/members/{member.id}/admin",
        headers=auth_headers(owner)
    )
    assert r2.status_code == 200

    members = await client.get(f"/api/v1/rooms/{room_id}/members", headers=auth_headers(owner))
    member_data = next(m for m in members.json() if m["user_id"] == str(member.id))
    assert member_data["is_admin"] is True

    r3 = await client.delete(f"/api/v1/rooms/{room_id}/members/{member.id}/admin",
        headers=auth_headers(owner)
    )
    assert r3.status_code == 200


@pytest.mark.asyncio
async def test_invitations_pending_route_reachable(client, db):
    user = await create_user(db, "room_pat", "room_pat@test.com")
    r = await client.get("/api/v1/rooms/invitations/pending", headers=auth_headers(user))
    assert r.status_code == 200
    assert isinstance(r.json(), list)
