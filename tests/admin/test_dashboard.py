"""Admin 도메인 -- 대시보드(Dashboard) 테스트."""

import pytest
from httpx import AsyncClient

# ---------------------------------------------------------------------------
# 대시보드 통계
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_dashboard_stats(client: AsyncClient, admin):
    """관리자가 대시보드 통계를 조회할 수 있다."""
    # Act
    res = await client.get("/v1/admin/dashboard", headers=admin["headers"])

    # Assert
    assert res.status_code == 200
    data = res.json()["data"]
    assert "summary" in data
    assert "total_users" in data["summary"]
    assert "total_posts" in data["summary"]
    assert "total_comments" in data["summary"]
    assert "today_signups" in data["summary"]
    assert "daily_stats" in data


# ---------------------------------------------------------------------------
# 사용자 목록 / 검색
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_user_list(client: AsyncClient, admin):
    """관리자가 사용자 목록을 조회할 수 있다."""
    # Act
    res = await client.get("/v1/admin/users", headers=admin["headers"])

    # Assert
    assert res.status_code == 200
    data = res.json()["data"]
    assert "users" in data
    assert "pagination" in data
    assert len(data["users"]) >= 1


@pytest.mark.asyncio
async def test_admin_user_search(client: AsyncClient, admin):
    """관리자가 닉네임으로 사용자를 검색할 수 있다."""
    # Act
    res = await client.get(
        f"/v1/admin/users?search={admin['nickname']}",
        headers=admin["headers"],
    )

    # Assert
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data["users"]) >= 1


# ---------------------------------------------------------------------------
# 권한 검증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_admin_dashboard_returns_403(
    client: AsyncClient,
    regular_user,
):
    """일반 사용자가 대시보드에 접근하면 403을 반환한다."""
    # Act
    res = await client.get(
        "/v1/admin/dashboard",
        headers=regular_user["headers"],
    )

    # Assert
    assert res.status_code == 403
    assert res.json()["detail"]["error"] == "admin_required"


@pytest.mark.asyncio
async def test_unauthenticated_dashboard_returns_401(client: AsyncClient):
    """미인증 사용자가 대시보드에 접근하면 401을 반환한다."""
    # Act
    res = await client.get("/v1/admin/dashboard")

    # Assert
    assert res.status_code == 401
