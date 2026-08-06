from __future__ import annotations

import pytest

from app.tests.conftest import TEST_ADMIN_PASSWORD


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_admin_routes_require_auth(client):
    resp = await client.get("/api/admin/users")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_status_needs_setup_before_configured(client):
    resp = await client.get("/api/auth/status")
    assert resp.status_code == 200
    assert resp.json() == {"authenticated": False, "needs_setup": True}


@pytest.mark.asyncio
async def test_login_before_setup_rejected(client):
    resp = await client.post("/api/auth/login", json={"password": "whatever123"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_setup_then_status_reflects_it(admin_client):
    resp = await admin_client.get("/api/auth/status")
    assert resp.json() == {"authenticated": True, "needs_setup": False}


@pytest.mark.asyncio
async def test_setup_twice_rejected(admin_client):
    resp = await admin_client.post("/api/auth/setup", json={"password": "another-password"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_setup_rejects_short_password(client):
    resp = await client.post("/api/auth/setup", json={"password": "short"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_wrong_password(admin_client):
    await admin_client.post("/api/auth/logout")
    resp = await admin_client.post("/api/auth/login", json={"password": "nope"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_then_access(admin_client):
    resp = await admin_client.get("/api/admin/users")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_change_password(admin_client):
    resp = await admin_client.post(
        "/api/auth/change-password",
        json={"current_password": TEST_ADMIN_PASSWORD, "new_password": "a-new-strong-password"},
    )
    assert resp.status_code == 200

    await admin_client.post("/api/auth/logout")
    resp = await admin_client.post("/api/auth/login", json={"password": TEST_ADMIN_PASSWORD})
    assert resp.status_code == 401
    resp = await admin_client.post("/api/auth/login", json={"password": "a-new-strong-password"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_change_password_wrong_current_rejected(admin_client):
    resp = await admin_client.post(
        "/api/auth/change-password",
        json={"current_password": "wrong-password", "new_password": "a-new-strong-password"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_change_password_requires_auth(client):
    resp = await client.post(
        "/api/auth/change-password",
        json={"current_password": "whatever", "new_password": "a-new-strong-password"},
    )
    assert resp.status_code == 401
