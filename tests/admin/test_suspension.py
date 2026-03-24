"""Admin 도메인 -- 계정 정지(Suspension) 테스트."""

import pytest
from httpx import AsyncClient

from core.database.connection import get_connection
from tests.conftest import create_verified_user

# ---------------------------------------------------------------------------
# DB 직접 조작 헬퍼
# ---------------------------------------------------------------------------


async def _suspend_user_directly(user_id: int, days: int = 7) -> None:
    """DB에서 직접 사용자를 정지한다 (테스트 헬퍼)."""
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE user SET suspended_until = DATE_ADD(NOW(), INTERVAL %s DAY), "
            "suspended_reason = '테스트 정지' WHERE id = %s",
            (days, user_id),
        )


async def _expire_suspension(user_id: int) -> None:
    """정지 기간을 과거로 설정하여 만료시킨다 (테스트 헬퍼)."""
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE user SET suspended_until = DATE_SUB(NOW(), INTERVAL 1 DAY) WHERE id = %s",
            (user_id,),
        )


# ---------------------------------------------------------------------------
# 관리자 정지 / 해제 API
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_suspend_user_returns_200(
    client: AsyncClient,
    admin,
    regular_user,
):
    """관리자가 사용자를 정지하면 200을 반환한다."""
    # Act
    res = await client.post(
        f"/v1/admin/users/{regular_user['user_id']}/suspend",
        json={"duration_days": 7, "reason": "스팸 게시글 반복 작성"},
        headers=admin["headers"],
    )

    # Assert
    assert res.status_code == 200
    data = res.json()
    assert data["code"] == "USER_SUSPENDED"
    assert data["data"]["duration_days"] == 7
    assert data["data"]["user_id"] == regular_user["user_id"]


@pytest.mark.asyncio
async def test_admin_unsuspend_user_returns_200(
    client: AsyncClient,
    admin,
    regular_user,
):
    """관리자가 사용자 정지를 해제하면 200을 반환한다."""
    # Arrange — DB에서 직접 정지
    await _suspend_user_directly(regular_user["user_id"])

    # Act
    res = await client.delete(
        f"/v1/admin/users/{regular_user['user_id']}/suspend",
        headers=admin["headers"],
    )

    # Assert
    assert res.status_code == 200
    assert res.json()["code"] == "USER_UNSUSPENDED"


# ---------------------------------------------------------------------------
# 입력 검증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_suspend_with_empty_reason_returns_422(
    client: AsyncClient,
    admin,
    regular_user,
):
    """정지 사유가 비어있으면 422를 반환한다."""
    # Act
    res = await client.post(
        f"/v1/admin/users/{regular_user['user_id']}/suspend",
        json={"duration_days": 7, "reason": "   "},
        headers=admin["headers"],
    )

    # Assert
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_suspend_with_invalid_duration_returns_422(
    client: AsyncClient,
    admin,
    regular_user,
):
    """정지 기간이 범위(1~365)를 벗어나면 422를 반환한다."""
    # 0일 — 최솟값 미만
    res_zero = await client.post(
        f"/v1/admin/users/{regular_user['user_id']}/suspend",
        json={"duration_days": 0, "reason": "테스트"},
        headers=admin["headers"],
    )
    assert res_zero.status_code == 422

    # 366일 — 최댓값 초과
    res_over = await client.post(
        f"/v1/admin/users/{regular_user['user_id']}/suspend",
        json={"duration_days": 366, "reason": "테스트"},
        headers=admin["headers"],
    )
    assert res_over.status_code == 422


# ---------------------------------------------------------------------------
# 정지된 사용자 차단
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_suspended_user_api_returns_403(
    client: AsyncClient,
    fake,
):
    """정지된 사용자가 기존 토큰으로 API에 접근하면 403을 반환한다."""
    # Arrange — 사용자 생성 후 정지
    user = await create_verified_user(client, fake)
    await _suspend_user_directly(user["user_id"])

    # Act
    res = await client.get("/v1/auth/me", headers=user["headers"])

    # Assert
    assert res.status_code == 403
    assert res.json()["detail"]["error"] == "account_suspended"


@pytest.mark.asyncio
async def test_suspended_user_login_returns_403(
    client: AsyncClient,
    fake,
):
    """정지된 사용자가 로그인하면 403을 반환한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    await _suspend_user_directly(user["user_id"])

    # Act
    res = await client.post(
        "/v1/auth/session",
        json={"email": user["email"], "password": user["payload"]["password"]},
    )

    # Assert
    assert res.status_code == 403
    detail = res.json()["detail"]
    assert detail["error"] == "account_suspended"
    assert "suspended_until" in detail
    assert "suspended_reason" in detail


@pytest.mark.asyncio
async def test_suspended_user_refresh_returns_403(
    client: AsyncClient,
    fake,
):
    """정지된 사용자가 토큰 갱신을 시도하면 403을 반환한다."""
    # Arrange — 로그인으로 refresh 쿠키 확보 후 정지
    user = await create_verified_user(client, fake)

    # 로그인하여 refresh 쿠키 획득
    login_res = await client.post(
        "/v1/auth/session",
        json={"email": user["email"], "password": user["payload"]["password"]},
    )
    assert login_res.status_code == 200

    # 정지 처리
    await _suspend_user_directly(user["user_id"])

    # Act — refresh 시도 (로그인 응답의 쿠키를 클라이언트에 설정)
    client.cookies.update(login_res.cookies)
    res = await client.post("/v1/auth/token/refresh")

    # Assert
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# 정지 기간 만료
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_expired_suspension_allows_login(
    client: AsyncClient,
    fake,
):
    """정지 기간이 만료되면 로그인할 수 있다."""
    # Arrange
    user = await create_verified_user(client, fake)
    await _suspend_user_directly(user["user_id"])
    await _expire_suspension(user["user_id"])

    # Act
    res = await client.post(
        "/v1/auth/session",
        json={"email": user["email"], "password": user["payload"]["password"]},
    )

    # Assert
    assert res.status_code == 200


# ---------------------------------------------------------------------------
# 자기 정지 방지 / 비관리자 차단
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cannot_suspend_self(
    client: AsyncClient,
    admin,
):
    """관리자가 자기 자신을 정지하면 400을 반환한다."""
    # Act
    res = await client.post(
        f"/v1/admin/users/{admin['user_id']}/suspend",
        json={"duration_days": 7, "reason": "자기 정지 테스트"},
        headers=admin["headers"],
    )

    # Assert
    assert res.status_code == 400
    assert res.json()["detail"]["error"] == "cannot_suspend_self"


@pytest.mark.asyncio
async def test_non_admin_suspend_returns_403(
    client: AsyncClient,
    fake,
    regular_user,
):
    """일반 사용자가 정지 API를 호출하면 403을 반환한다."""
    # Arrange
    target = await create_verified_user(client, fake)

    # Act
    res = await client.post(
        f"/v1/admin/users/{target['user_id']}/suspend",
        json={"duration_days": 7, "reason": "테스트"},
        headers=regular_user["headers"],
    )

    # Assert
    assert res.status_code == 403
