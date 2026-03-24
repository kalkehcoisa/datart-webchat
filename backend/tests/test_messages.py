import pytest
from app.models.models import Friendship, PersonalChat, UserBan
from tests.conftest import create_user, auth_headers


async def make_room(client, user, name, visibility="public"):
    r = await client.post("/api/v1/rooms",
        headers=auth_headers(user),
        json={"name": name, "visibility": visibility}
    )
    assert r.status_code == 201
    return r.json()["id"]


async def make_friends(db, user_a, user_b):
    import uuid
    a_id, b_id = sorted([user_a.id, user_b.id], key=str)
    db.add(Friendship(user_a_id=a_id, user_b_id=b_id))
    await db.commit()


async def make_personal_chat(db, user_a, user_b):
    a_id, b_id = sorted([user_a.id, user_b.id], key=str)
    chat = PersonalChat(user_a_id=a_id, user_b_id=b_id)
    db.add(chat)
    await db.commit()
    await db.refresh(chat)
    return chat


@pytest.mark.asyncio
async def test_send_room_message(client, db):
    user = await create_user(db, "msg_alice", "msg_alice@test.com")
    room_id = await make_room(client, user, "msg-room-1")

    r = await client.post(f"/api/v1/rooms/{room_id}/messages",
        headers=auth_headers(user),
        json={"content": "Hello world"}
    )
    assert r.status_code == 200
    data = r.json()
    assert data["content"] == "Hello world"
    assert data["author"]["username"] == "msg_alice"
    assert data["is_deleted"] is False


@pytest.mark.asyncio
async def test_send_message_attachment_only(client, db):
    """Attachment-only messages (null content) must be allowed."""
    user = await create_user(db, "msg_attach", "msg_attach@test.com")
    room_id = await make_room(client, user, "attach-room")

    r = await client.post(f"/api/v1/rooms/{room_id}/messages",
        headers=auth_headers(user),
        json={"content": None}
    )
    assert r.status_code == 200
    assert r.json()["content"] is None


@pytest.mark.asyncio
async def test_send_message_non_member_blocked(client, db):
    owner = await create_user(db, "msg_bob", "msg_bob@test.com")
    outsider = await create_user(db, "msg_carol", "msg_carol@test.com")
    room_id = await make_room(client, owner, "msg-room-2")

    r = await client.post(f"/api/v1/rooms/{room_id}/messages",
        headers=auth_headers(outsider),
        json={"content": "Sneaky"}
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_get_room_messages_pagination(client, db):
    user = await create_user(db, "msg_dave", "msg_dave@test.com")
    room_id = await make_room(client, user, "msg-room-3")

    for i in range(5):
        await client.post(f"/api/v1/rooms/{room_id}/messages",
            headers=auth_headers(user),
            json={"content": f"Message {i}"}
        )

    r = await client.get(f"/api/v1/rooms/{room_id}/messages?limit=3",
        headers=auth_headers(user)
    )
    assert r.status_code == 200
    assert len(r.json()) == 3


@pytest.mark.asyncio
async def test_edit_message(client, db):
    user = await create_user(db, "msg_eve", "msg_eve@test.com")
    room_id = await make_room(client, user, "msg-room-4")

    r = await client.post(f"/api/v1/rooms/{room_id}/messages",
        headers=auth_headers(user),
        json={"content": "Original"}
    )
    msg_id = r.json()["id"]

    r2 = await client.patch(f"/api/v1/messages/{msg_id}",
        headers=auth_headers(user),
        json={"content": "Edited"}
    )
    assert r2.status_code == 200
    data = r2.json()
    assert data["content"] == "Edited"
    assert data["edited_at"] is not None


@pytest.mark.asyncio
async def test_edit_others_message_blocked(client, db):
    owner = await create_user(db, "msg_frank", "msg_frank@test.com")
    other = await create_user(db, "msg_grace", "msg_grace@test.com")
    room_id = await make_room(client, owner, "msg-room-5")
    await client.post(f"/api/v1/rooms/{room_id}/join", headers=auth_headers(other))

    r = await client.post(f"/api/v1/rooms/{room_id}/messages",
        headers=auth_headers(owner),
        json={"content": "Owner's message"}
    )
    msg_id = r.json()["id"]

    r2 = await client.patch(f"/api/v1/messages/{msg_id}",
        headers=auth_headers(other),
        json={"content": "Hacked"}
    )
    assert r2.status_code == 403


@pytest.mark.asyncio
async def test_edit_deleted_message_blocked(client, db):
    """Editing a deleted message must return 400."""
    user = await create_user(db, "msg_henry", "msg_henry@test.com")
    room_id = await make_room(client, user, "msg-room-6")

    r = await client.post(f"/api/v1/rooms/{room_id}/messages",
        headers=auth_headers(user),
        json={"content": "Will be deleted"}
    )
    msg_id = r.json()["id"]

    await client.delete(f"/api/v1/messages/{msg_id}", headers=auth_headers(user))

    r2 = await client.patch(f"/api/v1/messages/{msg_id}",
        headers=auth_headers(user),
        json={"content": "Try to revive"}
    )
    assert r2.status_code == 400


@pytest.mark.asyncio
async def test_delete_message_author(client, db):
    user = await create_user(db, "msg_iris", "msg_iris@test.com")
    room_id = await make_room(client, user, "msg-room-7")

    r = await client.post(f"/api/v1/rooms/{room_id}/messages",
        headers=auth_headers(user),
        json={"content": "Delete me"}
    )
    msg_id = r.json()["id"]

    r2 = await client.delete(f"/api/v1/messages/{msg_id}", headers=auth_headers(user))
    assert r2.status_code == 200

    msgs = await client.get(f"/api/v1/rooms/{room_id}/messages", headers=auth_headers(user))
    deleted = next((m for m in msgs.json() if m["id"] == msg_id), None)
    assert deleted is not None
    assert deleted["is_deleted"] is True
    assert deleted["content"] is None


@pytest.mark.asyncio
async def test_delete_message_admin_can(client, db):
    owner = await create_user(db, "msg_jack", "msg_jack@test.com")
    member = await create_user(db, "msg_kate", "msg_kate@test.com")
    room_id = await make_room(client, owner, "msg-room-8")
    await client.post(f"/api/v1/rooms/{room_id}/join", headers=auth_headers(member))

    r = await client.post(f"/api/v1/rooms/{room_id}/messages",
        headers=auth_headers(member),
        json={"content": "Member's post"}
    )
    msg_id = r.json()["id"]

    r2 = await client.delete(f"/api/v1/messages/{msg_id}", headers=auth_headers(owner))
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_reply_to_message(client, db):
    user = await create_user(db, "msg_leo", "msg_leo@test.com")
    room_id = await make_room(client, user, "msg-room-9")

    r1 = await client.post(f"/api/v1/rooms/{room_id}/messages",
        headers=auth_headers(user),
        json={"content": "Original"}
    )
    original_id = r1.json()["id"]

    r2 = await client.post(f"/api/v1/rooms/{room_id}/messages",
        headers=auth_headers(user),
        json={"content": "Reply", "reply_to_id": original_id}
    )
    assert r2.status_code == 200
    assert r2.json()["reply_to"]["id"] == original_id


@pytest.mark.asyncio
async def test_personal_chat_requires_friendship(client, db):
    user_a = await create_user(db, "msg_mia", "msg_mia@test.com")
    user_b = await create_user(db, "msg_noah", "msg_noah@test.com")

    r = await client.post(f"/api/v1/chats/{user_b.username}",
        headers=auth_headers(user_a)
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_personal_chat_friends_can_message(client, db):
    user_a = await create_user(db, "msg_olivia", "msg_olivia@test.com")
    user_b = await create_user(db, "msg_pat", "msg_pat@test.com")
    await make_friends(db, user_a, user_b)

    r = await client.post(f"/api/v1/chats/{user_b.username}",
        headers=auth_headers(user_a)
    )
    assert r.status_code == 200
    chat_id = r.json()["id"]
    assert r.json()["frozen"] is False

    r2 = await client.post(f"/api/v1/chats/{chat_id}/messages",
        headers=auth_headers(user_a),
        json={"content": "Hey!"}
    )
    assert r2.status_code == 200
    assert r2.json()["content"] == "Hey!"


@pytest.mark.asyncio
async def test_personal_chat_frozen_after_ban(client, db):
    """After a ban the chat must be accessible (frozen=True) but sending blocked."""
    user_a = await create_user(db, "msg_quinn", "msg_quinn@test.com")
    user_b = await create_user(db, "msg_rose", "msg_rose@test.com")
    await make_friends(db, user_a, user_b)

    r = await client.post(f"/api/v1/chats/{user_b.username}",
        headers=auth_headers(user_a)
    )
    chat_id = r.json()["id"]

    await client.post(f"/api/v1/chats/{chat_id}/messages",
        headers=auth_headers(user_a),
        json={"content": "Before ban"}
    )

    db.add(UserBan(banner_id=user_a.id, banned_id=user_b.id))
    await db.commit()

    chats = await client.get("/api/v1/chats", headers=auth_headers(user_a))
    chat_entry = next((c for c in chats.json() if c["id"] == chat_id), None)
    assert chat_entry is not None
    assert chat_entry["frozen"] is True

    msgs = await client.get(f"/api/v1/chats/{chat_id}/messages", headers=auth_headers(user_a))
    assert msgs.status_code == 200
    assert len(msgs.json()) >= 1

    r2 = await client.post(f"/api/v1/chats/{chat_id}/messages",
        headers=auth_headers(user_a),
        json={"content": "After ban"}
    )
    assert r2.status_code == 403


@pytest.mark.asyncio
async def test_message_pagination_tiebreaker(client, db):
    """Multiple messages at same timestamp must not cause cursor skips."""
    user = await create_user(db, "msg_sam", "msg_sam@test.com")
    room_id = await make_room(client, user, "msg-room-page")

    for i in range(10):
        await client.post(f"/api/v1/rooms/{room_id}/messages",
            headers=auth_headers(user),
            json={"content": f"Msg {i}"}
        )

    page1 = await client.get(
        f"/api/v1/rooms/{room_id}/messages?limit=5",
        headers=auth_headers(user)
    )
    assert len(page1.json()) == 5
    cursor_id = page1.json()[0]["id"]

    page2 = await client.get(
        f"/api/v1/rooms/{room_id}/messages?limit=5&before={cursor_id}",
        headers=auth_headers(user)
    )
    page1_ids = {m["id"] for m in page1.json()}
    page2_ids = {m["id"] for m in page2.json()}
    assert page1_ids.isdisjoint(page2_ids), "Pagination returned duplicate messages"


@pytest.mark.asyncio
async def test_non_member_cannot_read_messages(client, db):
    owner = await create_user(db, "msg_tom", "msg_tom@test.com")
    outsider = await create_user(db, "msg_uma", "msg_uma@test.com")
    room_id = await make_room(client, owner, "msg-private-read")

    await client.post(f"/api/v1/rooms/{room_id}/messages",
        headers=auth_headers(owner),
        json={"content": "Secret"}
    )

    r = await client.get(f"/api/v1/rooms/{room_id}/messages", headers=auth_headers(outsider))
    assert r.status_code == 403
