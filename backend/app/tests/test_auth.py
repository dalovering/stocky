from __future__ import annotations

import pytest


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
async def test_login_wrong_password(client):
    resp = await client.post("/api/auth/login", json={"password": "nope"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_then_access(admin_client):
    resp = await admin_client.get("/api/admin/users")
    assert resp.status_code == 200
    assert resp.json() == []
