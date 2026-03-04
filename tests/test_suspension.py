"""test_suspension: 계정 정지 시스템 테스트.

테스트 범위:
- 관리자 정지/해제 API
- 정지된 사용자 로그인 차단
- 정지된 사용자 API 접근 차단
- 정지 기간 만료 시 자동 해제
- 자기 자신/다른 관리자 정지 방지
- 신고 처리 시 정지 연동
"""

import pytest
from httpx import AsyncClient

from database.connection import get_connection


# ==========================================
# 헬퍼 함수
# ==========================================


async def _create_verified_user(client: AsyncClient, fake) -> tuple[str, dict, dict]:
    """인증된 사용자를 생성하고 (access_token, user_info, payload)를 반환합니다."""
    payload = {
        "email": fake.email(),
        "password": "Password123!",
        "nickname": fake.lexify(text="?????") + str(fake.random_int(10, 99)),
    }
    res = await client.post("/v1/users/", data=payload)
    assert res.status_code == 201

    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE user SET email_verified = 1 WHERE email = %s",
                (payload["email"],),
            )

    login_res = await client.post(
        "/v1/auth/session",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert login_res.status_code == 200
    data = login_res.json()["data"]
    return data["access_token"], data["user"], payload


async def _make_admin(user_id: int) -> None:
    """사용자를 관리자로 설정합니다."""
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE user SET role = 'admin' WHERE id = %s", (user_id,),
            )


async def _suspend_user_directly(user_id: int, days: int = 7) -> None:
    """DB에서 직접 사용자를 정지합니다 (테스트 헬퍼)."""
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE user SET suspended_until = DATE_ADD(NOW(), INTERVAL %s DAY), "
                "suspended_reason = '테스트 정지' WHERE id = %s",
                (days, user_id),
            )


async def _expire_suspension(user_id: int) -> None:
    """정지 기간을 과거로 설정하여 만료시킵니다 (테스트 헬퍼)."""
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE user SET suspended_until = DATE_SUB(NOW(), INTERVAL 1 DAY) WHERE id = %s",
                (user_id,),
            )


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ==========================================
# 1. 관리자 정지 API
# ==========================================


@pytest.mark.asyncio
async def test_admin_suspend_user(client: AsyncClient, authorized_user, fake):
    """SUSPEND-01: 관리자가 사용자를 정지할 수 있다."""
    admin_cli, admin_info, _ = authorized_user
    await _make_admin(admin_info["user_id"])

    user_token, user_info, _ = await _create_verified_user(client, fake)

    res = await admin_cli.post(
        f"/v1/admin/users/{user_info['user_id']}/suspend",
        json={"duration_days": 7, "reason": "스팸 게시글 반복 작성"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["code"] == "USER_SUSPENDED"
    assert data["data"]["duration_days"] == 7


@pytest.mark.asyncio
async def test_admin_unsuspend_user(client: AsyncClient, authorized_user, fake):
    """SUSPEND-02: 관리자가 사용자 정지를 해제할 수 있다."""
    admin_cli, admin_info, _ = authorized_user
    await _make_admin(admin_info["user_id"])

    _, user_info, _ = await _create_verified_user(client, fake)
    await _suspend_user_directly(user_info["user_id"])

    res = await admin_cli.delete(
        f"/v1/admin/users/{user_info['user_id']}/suspend",
    )
    assert res.status_code == 200
    assert res.json()["code"] == "USER_UNSUSPENDED"


@pytest.mark.asyncio
async def test_cannot_suspend_self(client: AsyncClient, authorized_user, fake):
    """SUSPEND-03: 관리자가 자기 자신을 정지할 수 없다."""
    admin_cli, admin_info, _ = authorized_user
    await _make_admin(admin_info["user_id"])

    res = await admin_cli.post(
        f"/v1/admin/users/{admin_info['user_id']}/suspend",
        json={"duration_days": 7, "reason": "테스트"},
    )
    assert res.status_code == 400
    assert res.json()["detail"]["error"] == "cannot_suspend_self"


@pytest.mark.asyncio
async def test_cannot_suspend_admin(client: AsyncClient, authorized_user, fake):
    """SUSPEND-04: 관리자가 다른 관리자를 정지할 수 없다."""
    admin_cli, admin_info, _ = authorized_user
    await _make_admin(admin_info["user_id"])

    _, other_admin_info, _ = await _create_verified_user(client, fake)
    await _make_admin(other_admin_info["user_id"])

    res = await admin_cli.post(
        f"/v1/admin/users/{other_admin_info['user_id']}/suspend",
        json={"duration_days": 7, "reason": "테스트"},
    )
    assert res.status_code == 400
    assert res.json()["detail"]["error"] == "cannot_suspend_admin"


@pytest.mark.asyncio
async def test_non_admin_cannot_suspend(client: AsyncClient, authorized_user, fake):
    """SUSPEND-05: 일반 사용자는 정지 API에 접근할 수 없다."""
    user_cli, _, _ = authorized_user

    _, target_info, _ = await _create_verified_user(client, fake)

    res = await user_cli.post(
        f"/v1/admin/users/{target_info['user_id']}/suspend",
        json={"duration_days": 7, "reason": "테스트"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_suspend_nonexistent_user(client: AsyncClient, authorized_user, fake):
    """SUSPEND-06: 존재하지 않는 사용자를 정지할 수 없다."""
    admin_cli, admin_info, _ = authorized_user
    await _make_admin(admin_info["user_id"])

    res = await admin_cli.post(
        "/v1/admin/users/99999/suspend",
        json={"duration_days": 7, "reason": "테스트"},
    )
    assert res.status_code == 404


# ==========================================
# 2. 정지된 사용자 로그인/API 차단
# ==========================================


@pytest.mark.asyncio
async def test_suspended_user_cannot_login(client: AsyncClient, fake):
    """SUSPEND-07: 정지된 사용자는 로그인할 수 없다."""
    _, user_info, payload = await _create_verified_user(client, fake)
    await _suspend_user_directly(user_info["user_id"])

    res = await client.post(
        "/v1/auth/session",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert res.status_code == 403
    detail = res.json()["detail"]
    assert detail["error"] == "account_suspended"
    assert "suspended_until" in detail
    assert "suspended_reason" in detail


@pytest.mark.asyncio
async def test_suspended_user_cannot_access_api(client: AsyncClient, fake):
    """SUSPEND-08: 정지된 사용자는 기존 토큰으로 API에 접근할 수 없다."""
    token, user_info, _ = await _create_verified_user(client, fake)

    # 토큰 발급 후 정지
    await _suspend_user_directly(user_info["user_id"])

    res = await client.get("/v1/auth/me", headers=_auth(token))
    assert res.status_code == 403
    assert res.json()["detail"]["error"] == "account_suspended"


@pytest.mark.asyncio
async def test_suspended_user_cannot_create_post(client: AsyncClient, fake):
    """SUSPEND-09: 정지된 사용자는 게시글을 작성할 수 없다."""
    token, user_info, _ = await _create_verified_user(client, fake)
    await _suspend_user_directly(user_info["user_id"])

    res = await client.post(
        "/v1/posts/",
        json={"title": "Test", "content": "Content", "category_id": 1},
        headers=_auth(token),
    )
    assert res.status_code == 403


# ==========================================
# 3. 정지 기간 만료
# ==========================================


@pytest.mark.asyncio
async def test_expired_suspension_allows_login(client: AsyncClient, fake):
    """SUSPEND-10: 정지 기간이 만료되면 로그인할 수 있다."""
    _, user_info, payload = await _create_verified_user(client, fake)
    await _suspend_user_directly(user_info["user_id"])

    # 정지 만료 처리
    await _expire_suspension(user_info["user_id"])

    res = await client.post(
        "/v1/auth/session",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_expired_suspension_allows_api_access(client: AsyncClient, fake):
    """SUSPEND-11: 정지 기간이 만료되면 API에 접근할 수 있다."""
    token, user_info, _ = await _create_verified_user(client, fake)
    await _suspend_user_directly(user_info["user_id"])
    await _expire_suspension(user_info["user_id"])

    res = await client.get("/v1/auth/me", headers=_auth(token))
    assert res.status_code == 200


# ==========================================
# 4. 신고 -> 정지 연동
# ==========================================


@pytest.mark.asyncio
async def test_report_resolve_with_suspension(client: AsyncClient, authorized_user, fake):
    """SUSPEND-12: 신고 resolved 시 작성자를 정지할 수 있다."""
    admin_cli, admin_info, _ = authorized_user
    await _make_admin(admin_info["user_id"])

    # 일반 사용자 게시글 작성
    user_token, user_info, _ = await _create_verified_user(client, fake)
    post_res = await client.post(
        "/v1/posts/",
        json={"title": "Bad Post", "content": "Spam content", "category_id": 1},
        headers=_auth(user_token),
    )
    post_id = post_res.json()["data"]["post_id"]

    # 별도 사용자가 신고
    reporter_token, _, _ = await _create_verified_user(client, fake)
    report_res = await client.post(
        "/v1/reports",
        json={"target_type": "post", "target_id": post_id, "reason": "spam"},
        headers=_auth(reporter_token),
    )
    assert report_res.status_code == 201
    report_id = report_res.json()["data"]["report_id"]

    # 신고 처리 + 정지
    resolve_res = await admin_cli.patch(
        f"/v1/admin/reports/{report_id}",
        json={"status": "resolved", "suspend_days": 30},
    )
    assert resolve_res.status_code == 200

    # DB에서 정지 상태 확인
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT suspended_until, suspended_reason FROM user WHERE id = %s",
                (user_info["user_id"],),
            )
            row = await cur.fetchone()
            assert row[0] is not None  # suspended_until이 설정됨
            assert "신고 처리" in row[1]  # 사유에 신고 처리 문구 포함


@pytest.mark.asyncio
async def test_report_resolve_without_suspension(client: AsyncClient, authorized_user, fake):
    """SUSPEND-13: 신고 resolved 시 정지 없이 콘텐츠만 삭제할 수 있다."""
    admin_cli, admin_info, _ = authorized_user
    await _make_admin(admin_info["user_id"])

    user_token, user_info, _ = await _create_verified_user(client, fake)
    post_res = await client.post(
        "/v1/posts/",
        json={"title": "Bad Post", "content": "Content", "category_id": 1},
        headers=_auth(user_token),
    )
    post_id = post_res.json()["data"]["post_id"]

    reporter_token, _, _ = await _create_verified_user(client, fake)
    report_res = await client.post(
        "/v1/reports",
        json={"target_type": "post", "target_id": post_id, "reason": "spam"},
        headers=_auth(reporter_token),
    )
    report_id = report_res.json()["data"]["report_id"]

    # suspend_days 없이 처리
    resolve_res = await admin_cli.patch(
        f"/v1/admin/reports/{report_id}",
        json={"status": "resolved"},
    )
    assert resolve_res.status_code == 200

    # 사용자 정지되지 않음
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT suspended_until FROM user WHERE id = %s",
                (user_info["user_id"],),
            )
            row = await cur.fetchone()
            assert row[0] is None


# ==========================================
# 5. 입력 검증
# ==========================================


@pytest.mark.asyncio
async def test_suspend_invalid_duration(client: AsyncClient, authorized_user, fake):
    """SUSPEND-14: duration_days가 범위를 벗어나면 422를 반환한다."""
    admin_cli, admin_info, _ = authorized_user
    await _make_admin(admin_info["user_id"])

    _, user_info, _ = await _create_verified_user(client, fake)

    # 0일
    res = await admin_cli.post(
        f"/v1/admin/users/{user_info['user_id']}/suspend",
        json={"duration_days": 0, "reason": "테스트"},
    )
    assert res.status_code == 422

    # 366일
    res = await admin_cli.post(
        f"/v1/admin/users/{user_info['user_id']}/suspend",
        json={"duration_days": 366, "reason": "테스트"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_suspend_empty_reason(client: AsyncClient, authorized_user, fake):
    """SUSPEND-15: reason이 비어있으면 422를 반환한다."""
    admin_cli, admin_info, _ = authorized_user
    await _make_admin(admin_info["user_id"])

    _, user_info, _ = await _create_verified_user(client, fake)

    res = await admin_cli.post(
        f"/v1/admin/users/{user_info['user_id']}/suspend",
        json={"duration_days": 7, "reason": "   "},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_unsuspend_not_suspended_user(client: AsyncClient, authorized_user, fake):
    """SUSPEND-16: 정지 상태가 아닌 사용자를 해제하면 400을 반환한다."""
    admin_cli, admin_info, _ = authorized_user
    await _make_admin(admin_info["user_id"])

    _, user_info, _ = await _create_verified_user(client, fake)

    res = await admin_cli.delete(
        f"/v1/admin/users/{user_info['user_id']}/suspend",
    )
    assert res.status_code == 400
    assert res.json()["detail"]["error"] == "user_not_suspended"


@pytest.mark.asyncio
async def test_report_dismiss_with_suspend_days_rejected(
    client: AsyncClient, authorized_user, fake,
):
    """SUSPEND-17: dismissed 상태에서 suspend_days를 보내면 422를 반환한다."""
    admin_cli, admin_info, _ = authorized_user
    await _make_admin(admin_info["user_id"])

    user_token, _, _ = await _create_verified_user(client, fake)
    post_res = await client.post(
        "/v1/posts/",
        json={"title": "Post", "content": "Content", "category_id": 1},
        headers=_auth(user_token),
    )
    post_id = post_res.json()["data"]["post_id"]

    reporter_token, _, _ = await _create_verified_user(client, fake)
    report_res = await client.post(
        "/v1/reports",
        json={"target_type": "post", "target_id": post_id, "reason": "spam"},
        headers=_auth(reporter_token),
    )
    report_id = report_res.json()["data"]["report_id"]

    # dismissed + suspend_days → 422
    res = await admin_cli.patch(
        f"/v1/admin/reports/{report_id}",
        json={"status": "dismissed", "suspend_days": 7},
    )
    assert res.status_code == 422
