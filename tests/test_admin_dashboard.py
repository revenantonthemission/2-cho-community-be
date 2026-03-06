"""test_admin_dashboard: 관리자 대시보드 테스트."""

import pytest
from database.connection import get_connection


async def _make_admin(user_id: int) -> None:
    """사용자를 관리자로 변경합니다."""
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("UPDATE user SET role = 'admin' WHERE id = %s", (user_id,))
            await conn.commit()


@pytest.mark.asyncio
async def test_dashboard_01_get_stats(client, authorized_user):
    """관리자 대시보드 통계 조회 (200)."""
    cli, user_info, _ = authorized_user
    await _make_admin(user_info["user_id"])
    res = await cli.get("/v1/admin/dashboard")
    assert res.status_code == 200
    data = res.json()["data"]
    assert "summary" in data
    assert "total_users" in data["summary"]
    assert "total_posts" in data["summary"]
    assert "total_comments" in data["summary"]
    assert "today_signups" in data["summary"]
    assert "daily_stats" in data


@pytest.mark.asyncio
async def test_dashboard_02_non_admin_forbidden(client, authorized_user):
    """비관리자 대시보드 접근 (403)."""
    cli, _, _ = authorized_user
    res = await cli.get("/v1/admin/dashboard")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_dashboard_03_user_list(client, authorized_user):
    """관리자 사용자 목록 조회 (200)."""
    cli, user_info, _ = authorized_user
    await _make_admin(user_info["user_id"])
    res = await cli.get("/v1/admin/users")
    assert res.status_code == 200
    data = res.json()["data"]
    assert "users" in data
    assert "pagination" in data
    assert len(data["users"]) >= 1


@pytest.mark.asyncio
async def test_dashboard_04_user_search(client, authorized_user):
    """관리자 사용자 검색."""
    cli, user_info, _ = authorized_user
    await _make_admin(user_info["user_id"])
    res = await cli.get(f"/v1/admin/users?search={user_info['nickname']}")
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data["users"]) >= 1


@pytest.mark.asyncio
async def test_dashboard_05_unauthorized(client):
    """비로그인 대시보드 접근 (401)."""
    res = await client.get("/v1/admin/dashboard")
    assert res.status_code == 401
