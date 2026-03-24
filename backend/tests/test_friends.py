import pytest
from app.models.models import Friendship, UserBan
from tests.conftest import create_user, auth_headers


async def make_friends(db, user_a, user_b):
    a_id, b_id = sorted([user_a.id, user_b.id], key=str)
    db.add(Friendship(user_a_id=a_id, user_b_id=b_id))
    await db.commit()


@pytest.mark.asyncio
async def test_send_friend_request(client, db):
    sender = await create_user(db, "fr_alice", "fr_alice@test.com")
    receiver = await create_user(db, "fr_bob", "fr_bob@test.com")

    r = await client.post("/api/v1/friends/requests",
        headers=auth_headers(sender),
        json={"receiver_username": "fr_bob", "message": "Hi!"}
    )
    assert r.status_code == 201
    assert "id" in r.json()


@pytest.mark.asyncio
async def test_cannot_request_self(client, db):
    user = await create_user(db, "fr_carol", "fr_carol@test.com")
    r = await client.post("/api/v1/friends/requests",
        headers=auth_headers(user),
        json={"receiver_username": "fr_carol"}
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_cannot_request_unknown_user(client, db):
    user = await create_user(db, "fr_dave", "fr_dave@test.com")
    r = await client.post("/api/v1/friends/requests",
        headers=auth_headers(user),
        json={"receiver_username": "nobody_exists"}
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_duplicate_request_blocked(client, db):
    sender = await create_user(db, "fr_eve", "fr_eve@test.com")
    receiver = await create_user(db, "fr_frank", "fr_frank@test.com")

    await client.post("/api/v1/friends/requests",
        headers=auth_headers(sender),
        json={"receiver_username": "fr_frank"}
    )
    r = await client.post("/api/v1/friends/requests",
        headers=auth_headers(sender),
        json={"receiver_username": "fr_frank"}
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_accept_friend_request(client, db):
    sender = await create_user(db, "fr_grace", "fr_grace@test.com")
    receiver = await create_user(db, "fr_henry", "fr_henry@test.com")

    r = await client.post("/api/v1/friends/requests",
        headers=auth_headers(sender),
        json={"receiver_username": "fr_henry"}
    )
    req_id = r.json()["id"]

    r2 = await client.post(f"/api/v1/friends/requests/{req_id}/accept",
        headers=auth_headers(receiver)
    )
    assert r2.status_code == 200

    friends = await client.get("/api/v1/friends", headers=auth_headers(sender))
    usernames = [f["username"] for f in friends.json()]
    assert "fr_henry" in usernames


@pytest.mark.asyncio
async def test_reject_friend_request(client, db):
    sender = await create_user(db, "fr_iris", "fr_iris@test.com")
    receiver = await create_user(db, "fr_jack", "fr_jack@test.com")

    r = await client.post("/api/v1/friends/requests",
        headers=auth_headers(sender),
        json={"receiver_username": "fr_jack"}
    )
    req_id = r.json()["id"]

    r2 = await client.post(f"/api/v1/friends/requests/{req_id}/reject",
        headers=auth_headers(receiver)
    )
    assert r2.status_code == 200

    friends = await client.get("/api/v1/friends", headers=auth_headers(sender))
    usernames = [f["username"] for f in friends.json()]
    assert "fr_jack" not in usernames


@pytest.mark.asyncio
async def test_cannot_accept_others_request(client, db):
    sender = await create_user(db, "fr_kate", "fr_kate@test.com")
    receiver = await create_user(db, "fr_leo", "fr_leo@test.com")
    third = await create_user(db, "fr_mia", "fr_mia@test.com")

    r = await client.post("/api/v1/friends/requests",
        headers=auth_headers(sender),
        json={"receiver_username": "fr_leo"}
    )
    req_id = r.json()["id"]

    r2 = await client.post(f"/api/v1/friends/requests/{req_id}/accept",
        headers=auth_headers(third)
    )
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_remove_friend(client, db):
    user_a = await create_user(db, "fr_noah", "fr_noah@test.com")
    user_b = await create_user(db, "fr_olivia", "fr_olivia@test.com")
    await make_friends(db, user_a, user_b)

    r = await client.delete("/api/v1/friends/fr_olivia", headers=auth_headers(user_a))
    assert r.status_code == 200

    friends = await client.get("/api/v1/friends", headers=auth_headers(user_a))
    usernames = [f["username"] for f in friends.json()]
    assert "fr_olivia" not in usernames


@pytest.mark.asyncio
async def test_ban_user_removes_friendship(client, db):
    user_a = await create_user(db, "fr_pat", "fr_pat@test.com")
    user_b = await create_user(db, "fr_quinn", "fr_quinn@test.com")
    await make_friends(db, user_a, user_b)

    r = await client.post("/api/v1/friends/ban/fr_quinn", headers=auth_headers(user_a))
    assert r.status_code == 200

    friends = await client.get("/api/v1/friends", headers=auth_headers(user_a))
    usernames = [f["username"] for f in friends.json()]
    assert "fr_quinn" not in usernames


@pytest.mark.asyncio
async def test_banned_user_cannot_send_request(client, db):
    user_a = await create_user(db, "fr_rose", "fr_rose@test.com")
    user_b = await create_user(db, "fr_sam", "fr_sam@test.com")

    db.add(UserBan(banner_id=user_a.id, banned_id=user_b.id))
    await db.commit()

    r = await client.post("/api/v1/friends/requests",
        headers=auth_headers(user_b),
        json={"receiver_username": "fr_rose"}
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_pending_requests_visible_to_receiver(client, db):
    sender = await create_user(db, "fr_tom", "fr_tom@test.com")
    receiver = await create_user(db, "fr_uma", "fr_uma@test.com")

    await client.post("/api/v1/friends/requests",
        headers=auth_headers(sender),
        json={"receiver_username": "fr_uma", "message": "Hello"}
    )

    r = await client.get("/api/v1/friends/requests/pending", headers=auth_headers(receiver))
    assert r.status_code == 200
    senders = [req["sender"]["username"] for req in r.json()]
    assert "fr_tom" in senders


@pytest.mark.asyncio
async def test_unban_user(client, db):
    user_a = await create_user(db, "fr_vera", "fr_vera@test.com")
    user_b = await create_user(db, "fr_will", "fr_will@test.com")

    db.add(UserBan(banner_id=user_a.id, banned_id=user_b.id))
    await db.commit()

    r = await client.delete("/api/v1/friends/ban/fr_will", headers=auth_headers(user_a))
    assert r.status_code == 200

    r2 = await client.post("/api/v1/friends/requests",
        headers=auth_headers(user_b),
        json={"receiver_username": "fr_vera"}
    )
    assert r2.status_code == 201
