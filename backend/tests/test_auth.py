import pytest
from tests.conftest import create_user, auth_headers


@pytest.mark.asyncio
async def test_register_success(client):
    r = await client.post("/api/v1/auth/register", json={
        "username": "alice", "email": "alice@test.com", "password": "password123"
    })
    assert r.status_code == 201
    data = r.json()
    assert data["username"] == "alice"
    assert "password_hash" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client, db):
    await create_user(db, "bob", "bob@test.com")
    r = await client.post("/api/v1/auth/register", json={
        "username": "bob2", "email": "bob@test.com", "password": "password123"
    })
    assert r.status_code == 400
    assert "Email" in r.json()["detail"]


@pytest.mark.asyncio
async def test_register_duplicate_username(client, db):
    await create_user(db, "carol", "carol@test.com")
    r = await client.post("/api/v1/auth/register", json={
        "username": "carol", "email": "carol2@test.com", "password": "password123"
    })
    assert r.status_code == 400
    assert "Username" in r.json()["detail"] or "username" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_register_weak_password(client):
    r = await client.post("/api/v1/auth/register", json={
        "username": "dave", "email": "dave@test.com", "password": "short"
    })
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client, db):
    await create_user(db, "eve", "eve@test.com", "mypassword")
    r = await client.post("/api/v1/auth/login", json={
        "email": "eve@test.com", "password": "mypassword"
    })
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client, db):
    await create_user(db, "frank", "frank@test.com", "correct")
    r = await client.post("/api/v1/auth/login", json={
        "email": "frank@test.com", "password": "wrong"
    })
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_email(client):
    r = await client.post("/api/v1/auth/login", json={
        "email": "nobody@test.com", "password": "whatever"
    })
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_get_me(client, db):
    user = await create_user(db, "grace", "grace@test.com")
    r = await client.get("/api/v1/auth/me", headers=auth_headers(user))
    assert r.status_code == 200
    assert r.json()["username"] == "grace"


@pytest.mark.asyncio
async def test_get_me_no_token(client):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_change_password(client, db):
    user = await create_user(db, "henry", "henry@test.com", "oldpassword")
    r = await client.post("/api/v1/auth/password/change",
        headers=auth_headers(user),
        json={"current_password": "oldpassword", "new_password": "newpassword123"}
    )
    assert r.status_code == 200

    r2 = await client.post("/api/v1/auth/login", json={
        "email": "henry@test.com", "password": "newpassword123"
    })
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_change_password_wrong_current(client, db):
    user = await create_user(db, "iris", "iris@test.com", "realpassword")
    r = await client.post("/api/v1/auth/password/change",
        headers=auth_headers(user),
        json={"current_password": "wrongpassword", "new_password": "newpassword123"}
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_delete_account(client, db):
    user = await create_user(db, "jack", "jack@test.com")
    r = await client.delete("/api/v1/auth/account", headers=auth_headers(user))
    assert r.status_code == 200

    r2 = await client.get("/api/v1/auth/me", headers=auth_headers(user))
    assert r2.status_code == 401
