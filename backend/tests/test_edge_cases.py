import pytest
import io
from app.models.models import Friendship, RoomMember
from tests.conftest import create_user, auth_headers


async def make_room(client, user, name, visibility="public"):
    r = await client.post("/api/v1/rooms",
        headers=auth_headers(user),
        json={"name": name, "visibility": visibility}
    )
    assert r.status_code == 201
    return r.json()["id"]


async def make_friends(db, user_a, user_b):
    a_id, b_id = sorted([user_a.id, user_b.id], key=str)
    db.add(Friendship(user_a_id=a_id, user_b_id=b_id))
    await db.commit()


@pytest.mark.asyncio
async def test_room_invite_and_accept(client, db):
    """Full invite flow: invite -> pending -> accept -> member."""
    owner = await create_user(db, "inv_alice", "inv_alice@test.com")
    invitee = await create_user(db, "inv_bob", "inv_bob@test.com")

    room_id = await make_room(client, owner, "inv-private-room", "private")

    r = await client.post(f"/api/v1/rooms/{room_id}/invite",
        headers=auth_headers(owner),
        json={"username": "inv_bob"}
    )
    assert r.status_code == 200

    pending = await client.get("/api/v1/rooms/invitations/pending",
        headers=auth_headers(invitee)
    )
    assert r.status_code == 200
    inv_room_ids = [i["room_id"] for i in pending.json()]
    assert room_id in inv_room_ids

    r2 = await client.post(f"/api/v1/rooms/{room_id}/accept-invite",
        headers=auth_headers(invitee)
    )
    assert r2.status_code == 200

    members = await client.get(f"/api/v1/rooms/{room_id}/members",
        headers=auth_headers(invitee)
    )
    user_ids = [m["user_id"] for m in members.json()]
    assert str(invitee.id) in user_ids


@pytest.mark.asyncio
async def test_cannot_invite_banned_user(client, db):
    owner = await create_user(db, "inv_carol", "inv_carol@test.com")
    target = await create_user(db, "inv_dave", "inv_dave@test.com")

    room_id = await make_room(client, owner, "inv-room-2", "private")
    await client.post(f"/api/v1/rooms/{room_id}/join", headers=auth_headers(target))
    await client.post(f"/api/v1/rooms/{room_id}/members/{target.id}/ban",
        headers=auth_headers(owner))

    r = await client.post(f"/api/v1/rooms/{room_id}/invite",
        headers=auth_headers(owner),
        json={"username": "inv_dave"}
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_non_member_cannot_invite(client, db):
    owner = await create_user(db, "inv_eve", "inv_eve@test.com")
    outsider = await create_user(db, "inv_frank", "inv_frank@test.com")
    target = await create_user(db, "inv_grace", "inv_grace@test.com")

    room_id = await make_room(client, owner, "inv-room-3", "private")

    r = await client.post(f"/api/v1/rooms/{room_id}/invite",
        headers=auth_headers(outsider),
        json={"username": "inv_grace"}
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_accept_invite_nonexistent(client, db):
    user = await create_user(db, "inv_henry", "inv_henry@test.com")
    room_id = await make_room(client, user, "inv-room-4", "private")

    other = await create_user(db, "inv_iris", "inv_iris@test.com")
    r = await client.post(f"/api/v1/rooms/{room_id}/accept-invite",
        headers=auth_headers(other)
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_message_content_size_limit(client, db):
    """Messages exceeding 3KB must be rejected."""
    user = await create_user(db, "sz_alice", "sz_alice@test.com")
    room_id = await make_room(client, user, "sz-room-1")

    content_ok = "x" * 3000
    r = await client.post(f"/api/v1/rooms/{room_id}/messages",
        headers=auth_headers(user),
        json={"content": content_ok}
    )
    assert r.status_code == 200

    content_too_big = "x" * 4000
    r2 = await client.post(f"/api/v1/rooms/{room_id}/messages",
        headers=auth_headers(user),
        json={"content": content_too_big}
    )
    assert r2.status_code == 422


@pytest.mark.asyncio
async def test_room_search(client, db):
    user = await create_user(db, "srch_alice", "srch_alice@test.com")
    await make_room(client, user, "searchable-alpha")
    await make_room(client, user, "searchable-beta")
    await make_room(client, user, "unrelated-room")

    r = await client.get("/api/v1/rooms?search=searchable",
        headers=auth_headers(user)
    )
    assert r.status_code == 200
    names = [x["name"] for x in r.json()]
    assert "searchable-alpha" in names
    assert "searchable-beta" in names
    assert "unrelated-room" not in names


@pytest.mark.asyncio
async def test_room_search_case_insensitive(client, db):
    user = await create_user(db, "srch_bob", "srch_bob@test.com")
    await make_room(client, user, "CaseSensitiveRoom")

    r = await client.get("/api/v1/rooms?search=casesensitive",
        headers=auth_headers(user)
    )
    names = [x["name"] for x in r.json()]
    assert "CaseSensitiveRoom" in names


@pytest.mark.asyncio
async def test_non_admin_cannot_grant_admin(client, db):
    owner = await create_user(db, "adm_alice", "adm_alice@test.com")
    member_a = await create_user(db, "adm_bob", "adm_bob@test.com")
    member_b = await create_user(db, "adm_carol", "adm_carol@test.com")

    room_id = await make_room(client, owner, "adm-room-1")
    await client.post(f"/api/v1/rooms/{room_id}/join", headers=auth_headers(member_a))
    await client.post(f"/api/v1/rooms/{room_id}/join", headers=auth_headers(member_b))

    r = await client.post(
        f"/api/v1/rooms/{room_id}/members/{member_b.id}/admin",
        headers=auth_headers(member_a)
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_cannot_revoke_owner_admin(client, db):
    owner = await create_user(db, "adm_dave", "adm_dave@test.com")
    admin = await create_user(db, "adm_eve", "adm_eve@test.com")

    room_id = await make_room(client, owner, "adm-room-2")
    await client.post(f"/api/v1/rooms/{room_id}/join", headers=auth_headers(admin))
    await client.post(
        f"/api/v1/rooms/{room_id}/members/{admin.id}/admin",
        headers=auth_headers(owner)
    )

    r = await client.delete(
        f"/api/v1/rooms/{room_id}/members/{owner.id}/admin",
        headers=auth_headers(admin)
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_admin_can_delete_others_messages(client, db):
    owner = await create_user(db, "adm_frank", "adm_frank@test.com")
    member = await create_user(db, "adm_grace", "adm_grace@test.com")
    admin = await create_user(db, "adm_henry", "adm_henry@test.com")

    room_id = await make_room(client, owner, "adm-room-3")
    await client.post(f"/api/v1/rooms/{room_id}/join", headers=auth_headers(member))
    await client.post(f"/api/v1/rooms/{room_id}/join", headers=auth_headers(admin))
    await client.post(
        f"/api/v1/rooms/{room_id}/members/{admin.id}/admin",
        headers=auth_headers(owner)
    )

    r = await client.post(f"/api/v1/rooms/{room_id}/messages",
        headers=auth_headers(member),
        json={"content": "Delete this"}
    )
    msg_id = r.json()["id"]

    r2 = await client.delete(f"/api/v1/messages/{msg_id}", headers=auth_headers(admin))
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_file_access_denied_after_ban(client, db):
    """After being banned from a room, file access must be revoked."""
    owner = await create_user(db, "file_alice", "file_alice@test.com")
    member = await create_user(db, "file_bob", "file_bob@test.com")

    room_id = await make_room(client, owner, "file-room-1")
    await client.post(f"/api/v1/rooms/{room_id}/join", headers=auth_headers(member))

    msg_r = await client.post(f"/api/v1/rooms/{room_id}/messages",
        headers=auth_headers(member),
        json={"content": "with file"}
    )
    msg_id = msg_r.json()["id"]

    file_data = io.BytesIO(b"hello world")
    upload_r = await client.post(
        "/api/v1/upload",
        headers=auth_headers(member),
        data={"message_id": msg_id},
        files={"file": ("test.txt", file_data, "text/plain")}
    )
    assert upload_r.status_code == 200
    att_id = upload_r.json()["id"]

    r_before = await client.get(f"/api/v1/files/{att_id}", headers=auth_headers(member))
    assert r_before.status_code == 200

    await client.post(
        f"/api/v1/rooms/{room_id}/members/{member.id}/ban",
        headers=auth_headers(owner)
    )

    r_after = await client.get(f"/api/v1/files/{att_id}", headers=auth_headers(member))
    assert r_after.status_code == 403


@pytest.mark.asyncio
async def test_file_access_only_for_members(client, db):
    owner = await create_user(db, "file_carol", "file_carol@test.com")
    outsider = await create_user(db, "file_dave", "file_dave@test.com")

    room_id = await make_room(client, owner, "file-room-2")

    msg_r = await client.post(f"/api/v1/rooms/{room_id}/messages",
        headers=auth_headers(owner),
        json={"content": "secret file"}
    )
    msg_id = msg_r.json()["id"]

    file_data = io.BytesIO(b"secret content")
    upload_r = await client.post(
        "/api/v1/upload",
        headers=auth_headers(owner),
        data={"message_id": msg_id},
        files={"file": ("secret.txt", file_data, "text/plain")}
    )
    att_id = upload_r.json()["id"]

    r = await client.get(f"/api/v1/files/{att_id}", headers=auth_headers(outsider))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_room_update_by_owner_only(client, db):
    owner = await create_user(db, "upd_alice", "upd_alice@test.com")
    member = await create_user(db, "upd_bob", "upd_bob@test.com")

    room_id = await make_room(client, owner, "upd-room-1")
    await client.post(f"/api/v1/rooms/{room_id}/join", headers=auth_headers(member))

    r = await client.patch(f"/api/v1/rooms/{room_id}",
        headers=auth_headers(member),
        json={"description": "hacked"}
    )
    assert r.status_code == 403

    r2 = await client.patch(f"/api/v1/rooms/{room_id}",
        headers=auth_headers(owner),
        json={"description": "updated by owner"}
    )
    assert r2.status_code == 200
    assert r2.json()["description"] == "updated by owner"


@pytest.mark.asyncio
async def test_ban_list_visible_to_admins_only(client, db):
    owner = await create_user(db, "ban_alice", "ban_alice@test.com")
    member = await create_user(db, "ban_bob", "ban_bob@test.com")

    room_id = await make_room(client, owner, "ban-room-1")
    await client.post(f"/api/v1/rooms/{room_id}/join", headers=auth_headers(member))

    r = await client.get(f"/api/v1/rooms/{room_id}/bans",
        headers=auth_headers(member)
    )
    assert r.status_code == 403

    r2 = await client.get(f"/api/v1/rooms/{room_id}/bans",
        headers=auth_headers(owner)
    )
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_unban_allows_rejoin(client, db):
    owner = await create_user(db, "ubn_alice", "ubn_alice@test.com")
    target = await create_user(db, "ubn_bob", "ubn_bob@test.com")

    room_id = await make_room(client, owner, "ubn-room-1")
    await client.post(f"/api/v1/rooms/{room_id}/join", headers=auth_headers(target))
    await client.post(
        f"/api/v1/rooms/{room_id}/members/{target.id}/ban",
        headers=auth_headers(owner)
    )

    r_blocked = await client.post(f"/api/v1/rooms/{room_id}/join",
        headers=auth_headers(target)
    )
    assert r_blocked.status_code == 403

    await client.delete(
        f"/api/v1/rooms/{room_id}/members/{target.id}/ban",
        headers=auth_headers(owner)
    )

    r_allowed = await client.post(f"/api/v1/rooms/{room_id}/join",
        headers=auth_headers(target)
    )
    assert r_allowed.status_code == 200


@pytest.mark.asyncio
async def test_my_rooms_returns_only_joined(client, db):
    user = await create_user(db, "my_alice", "my_alice@test.com")
    other = await create_user(db, "my_bob", "my_bob@test.com")

    await make_room(client, user, "my-room-joined")
    await make_room(client, other, "my-room-not-joined")

    r = await client.get("/api/v1/rooms/my", headers=auth_headers(user))
    assert r.status_code == 200
    names = [x["name"] for x in r.json()]
    assert "my-room-joined" in names
    assert "my-room-not-joined" not in names


@pytest.mark.asyncio
async def test_leave_room_removes_from_my_rooms(client, db):
    owner = await create_user(db, "lv_alice", "lv_alice@test.com")
    member = await create_user(db, "lv_bob", "lv_bob@test.com")

    room_id = await make_room(client, owner, "lv-room-1")
    await client.post(f"/api/v1/rooms/{room_id}/join", headers=auth_headers(member))

    r_before = await client.get("/api/v1/rooms/my", headers=auth_headers(member))
    assert any(x["id"] == room_id for x in r_before.json())

    await client.post(f"/api/v1/rooms/{room_id}/leave", headers=auth_headers(member))

    r_after = await client.get("/api/v1/rooms/my", headers=auth_headers(member))
    assert not any(x["id"] == room_id for x in r_after.json())
