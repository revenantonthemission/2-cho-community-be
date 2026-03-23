"""인증 가드 통합 테스트.

get_current_user, require_verified_email, require_admin, get_optional_user의
접근 제어 동작을 검증한다.
"""

import pytest

from tests.conftest import create_verified_user

# ---------------------------------------------------------------------------
# 미인증 요청
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unauthenticated_write_returns_401(client, fake):
    """토큰 없이 게시글 작성 시 401을 반환해야 한다."""
    # Act
    res = await client.post(
        "/v1/posts/",
        json={"title": "제목", "content": "내용", "category_id": 1},
    )

    # Assert
    assert res.status_code == 401
    assert res.json()["detail"]["error"] == "unauthorized"


# ---------------------------------------------------------------------------
# 이메일 미인증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unverified_email_write_returns_403(client, fake):
    """이메일 미인증 사용자가 게시글 작성 시 403을 반환해야 한다."""
    # Arrange — 이메일 인증 없이 회원가입 + 로그인
    from tests.conftest import _make_user_payload

    payload = _make_user_payload(fake)
    signup_res = await client.post("/v1/users/", data=payload)
    assert signup_res.status_code == 201

    login_res = await client.post(
        "/v1/auth/session",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert login_res.status_code == 200
    token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Act — 미인증 사용자가 게시글 작성 시도
    res = await client.post(
        "/v1/posts/",
        json={"title": "제목", "content": "내용", "category_id": 1},
        headers=headers,
    )

    # Assert
    assert res.status_code == 403
    assert res.json()["detail"]["error"] == "email_not_verified"


# ---------------------------------------------------------------------------
# 관리자 전용 API
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_only_api_returns_403_for_regular_user(client, fake):
    """일반 사용자가 관리자 전용 API 접근 시 403을 반환해야 한다."""
    # Arrange
    user = await create_verified_user(client, fake)

    # Act — 관리자 전용 신고 목록 조회
    res = await user["client"].get("/v1/admin/reports")

    # Assert
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# 선택적 인증 (get_optional_user)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_optional_user_returns_none_for_unauthenticated(client, fake):
    """토큰 없이 게시글 목록 조회는 정상 동작해야 한다 (공개 API)."""
    # Act — 인증 없이 게시글 목록 조회
    res = await client.get("/v1/posts/")

    # Assert — 200 OK (get_optional_user가 None 반환, 에러 없음)
    assert res.status_code == 200
    assert "data" in res.json()
