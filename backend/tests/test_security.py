import pytest
from tests.conftest import create_user, auth_headers
from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password


@pytest.mark.asyncio
async def test_invalid_token_rejected(client, db):
    r = await client.get("/api/v1/auth/me",
        headers={"Authorization": "Bearer not.a.valid.token"}
    )
    assert r.status_code == 401 or r.status_code == 403


@pytest.mark.asyncio
async def test_expired_token_rejected(client):
    from datetime import datetime, timedelta, timezone
    from jose import jwt
    from app.core.config import settings
    payload = {
        "sub": "00000000-0000-0000-0000-000000000000",
        "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
        "type": "access",
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    r = await client.get("/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_refresh_token_as_access_rejected(client, db):
    user = await create_user(db, "sec_alice", "sec_alice@test.com")
    refresh = create_refresh_token(str(user.id))
    r = await client.get("/api/v1/auth/me",
        headers={"Authorization": f"Bearer {refresh}"}
    )
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_access_token_as_refresh_rejected(client, db):
    user = await create_user(db, "sec_bob", "sec_bob@test.com")
    access = create_access_token(str(user.id))
    r = await client.post("/api/v1/auth/refresh",
        json={"refresh_token": access}
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_room_access_requires_membership(client, db):
    owner = await create_user(db, "sec_carol", "sec_carol@test.com")
    outsider = await create_user(db, "sec_dave", "sec_dave@test.com")

    r = await client.post("/api/v1/rooms",
        headers=auth_headers(owner),
        json={"name": "sec-room-1", "visibility": "public"}
    )
    room_id = r.json()["id"]

    r2 = await client.get(f"/api/v1/rooms/{room_id}/members",
        headers=auth_headers(outsider)
    )
    assert r2.status_code == 403


@pytest.mark.asyncio
async def test_private_room_not_accessible_by_non_member(client, db):
    owner = await create_user(db, "sec_eve", "sec_eve@test.com")
    outsider = await create_user(db, "sec_frank", "sec_frank@test.com")

    r = await client.post("/api/v1/rooms",
        headers=auth_headers(owner),
        json={"name": "sec-private", "visibility": "private"}
    )
    room_id = r.json()["id"]

    r2 = await client.get(f"/api/v1/rooms/{room_id}", headers=auth_headers(outsider))
    assert r2.status_code == 403


@pytest.mark.asyncio
async def test_non_admin_cannot_ban(client, db):
    owner = await create_user(db, "sec_grace", "sec_grace@test.com")
    member = await create_user(db, "sec_henry", "sec_henry@test.com")
    target = await create_user(db, "sec_iris", "sec_iris@test.com")

    r = await client.post("/api/v1/rooms",
        headers=auth_headers(owner),
        json={"name": "sec-room-2", "visibility": "public"}
    )
    room_id = r.json()["id"]
    await client.post(f"/api/v1/rooms/{room_id}/join", headers=auth_headers(member))
    await client.post(f"/api/v1/rooms/{room_id}/join", headers=auth_headers(target))

    r2 = await client.post(
        f"/api/v1/rooms/{room_id}/members/{target.id}/ban",
        headers=auth_headers(member)
    )
    assert r2.status_code == 403


@pytest.mark.asyncio
async def test_cannot_ban_room_owner(client, db):
    owner = await create_user(db, "sec_jack", "sec_jack@test.com")
    admin = await create_user(db, "sec_kate", "sec_kate@test.com")

    r = await client.post("/api/v1/rooms",
        headers=auth_headers(owner),
        json={"name": "sec-room-3", "visibility": "public"}
    )
    room_id = r.json()["id"]
    await client.post(f"/api/v1/rooms/{room_id}/join", headers=auth_headers(admin))
    await client.post(f"/api/v1/rooms/{room_id}/members/{admin.id}/admin",
        headers=auth_headers(owner))

    r2 = await client.post(
        f"/api/v1/rooms/{room_id}/members/{owner.id}/ban",
        headers=auth_headers(admin)
    )
    assert r2.status_code == 400


@pytest.mark.asyncio
async def test_password_hashing():
    pw = "mysecretpassword"
    hashed = hash_password(pw)
    assert hashed != pw
    assert verify_password(pw, hashed)
    assert not verify_password("wrongpassword", hashed)


@pytest.mark.asyncio
async def test_token_decode_roundtrip(db):
    user = await create_user(db, "sec_leo", "sec_leo@test.com")
    token = create_access_token(str(user.id))
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == str(user.id)
    assert payload["type"] == "access"


@pytest.mark.asyncio
async def test_message_non_author_cannot_delete(client, db):
    owner = await create_user(db, "sec_mia", "sec_mia@test.com")
    member = await create_user(db, "sec_noah", "sec_noah@test.com")

    r = await client.post("/api/v1/rooms",
        headers=auth_headers(owner),
        json={"name": "sec-room-4", "visibility": "public"}
    )
    room_id = r.json()["id"]
    await client.post(f"/api/v1/rooms/{room_id}/join", headers=auth_headers(member))

    r2 = await client.post(f"/api/v1/rooms/{room_id}/messages",
        headers=auth_headers(member),
        json={"content": "Member message"}
    )
    msg_id = r2.json()["id"]

    non_admin_other = await create_user(db, "sec_olivia", "sec_olivia@test.com")
    await client.post(f"/api/v1/rooms/{room_id}/join", headers=auth_headers(non_admin_other))

    r3 = await client.delete(f"/api/v1/messages/{msg_id}",
        headers=auth_headers(non_admin_other)
    )
    assert r3.status_code == 403


@pytest.mark.asyncio
async def test_account_deletion_does_not_delete_room_messages(client, db):
    """Spec 2.1.5: deleting account must not delete messages in other people's rooms."""
    owner = await create_user(db, "sec_pat", "sec_pat@test.com")
    member = await create_user(db, "sec_quinn", "sec_quinn@test.com")

    r = await client.post("/api/v1/rooms",
        headers=auth_headers(owner),
        json={"name": "sec-room-5", "visibility": "public"}
    )
    room_id = r.json()["id"]
    await client.post(f"/api/v1/rooms/{room_id}/join", headers=auth_headers(member))

    await client.post(f"/api/v1/rooms/{room_id}/messages",
        headers=auth_headers(member),
        json={"content": "Message before deletion"}
    )

    await client.delete("/api/v1/auth/account", headers=auth_headers(member))

    msgs = await client.get(f"/api/v1/rooms/{room_id}/messages",
        headers=auth_headers(owner)
    )
    assert msgs.status_code == 200
    contents = [m["content"] for m in msgs.json() if not m["is_deleted"]]
    assert "Message before deletion" in contents


@pytest.mark.asyncio
async def test_search_users(client, db):
    user = await create_user(db, "sec_rose", "sec_rose@test.com")
    await create_user(db, "sec_rosemary", "sec_rosemary@test.com")

    r = await client.get("/api/v1/users/search?q=sec_rose", headers=auth_headers(user))
    assert r.status_code == 200
    usernames = [u["username"] for u in r.json()]
    assert "sec_rose" in usernames
    assert "sec_rosemary" in usernames


@pytest.mark.asyncio
async def test_search_users_too_short_query(client, db):
    user = await create_user(db, "sec_sam", "sec_sam@test.com")
    r = await client.get("/api/v1/users/search?q=a", headers=auth_headers(user))
    assert r.status_code == 422
