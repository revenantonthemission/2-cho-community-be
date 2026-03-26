import pytest

from tests.conftest import create_verified_user


@pytest.mark.asyncio
async def test_get_user_reputation(client, fake):
    user = await create_verified_user(client, fake)
    res = await client.get(f"/v1/users/{user['user_id']}/reputation/")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["reputation_score"] == 0
    assert data["trust_level"] == 0


@pytest.mark.asyncio
async def test_get_reputation_history(client, fake):
    user = await create_verified_user(client, fake)
    res = await client.get(f"/v1/users/{user['user_id']}/reputation/history/")
    assert res.status_code == 200
    assert "events" in res.json()["data"]
    assert "total" in res.json()["data"]


@pytest.mark.asyncio
async def test_get_user_badges(client, fake):
    user = await create_verified_user(client, fake)
    res = await client.get(f"/v1/users/{user['user_id']}/badges/")
    assert res.status_code == 200
    assert "badges" in res.json()["data"]


@pytest.mark.asyncio
async def test_get_all_badges(client, fake):
    res = await client.get("/v1/badges/")
    assert res.status_code == 200
    assert len(res.json()["data"]["badges"]) == 27


@pytest.mark.asyncio
async def test_get_trust_levels(client, fake):
    res = await client.get("/v1/trust-levels/")
    assert res.status_code == 200
    assert len(res.json()["data"]["levels"]) == 5
