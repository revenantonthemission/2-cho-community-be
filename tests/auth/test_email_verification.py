"""Auth 도메인 — 이메일 인증 테스트."""

import pytest
from httpx import ASGITransport, AsyncClient

from core.database.connection import get_connection
from main import app
from modules.auth.verification_models import create_verification_token
from tests.conftest import _make_user_payload, create_verified_user

# ---------------------------------------------------------------------------
# 헬퍼: 미인증 사용자 생성 + 로그인
# ---------------------------------------------------------------------------


async def _create_unverified_user(client: AsyncClient, fake) -> dict:
    """회원가입 + 로그인은 완료했지만 이메일 미인증 상태인 사용자를 반환한다."""
    payload = _make_user_payload(fake)

    # 회원가입
    signup_res = await client.post("/v1/users/", data=payload)
    assert signup_res.status_code == 201

    # 로그인 (미인증 상태에서도 로그인은 가능)
    login_res = await client.post(
        "/v1/auth/session",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert login_res.status_code == 200

    login_data = login_res.json()["data"]
    access_token = login_data["access_token"]
    user_info = login_data["user"]

    transport = ASGITransport(app=app)
    auth_client = AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {access_token}"},
        cookies=login_res.cookies,
    )

    return {
        "client": auth_client,
        "user_id": user_info["user_id"],
        "email": payload["email"],
        "nickname": user_info["nickname"],
        "token": access_token,
        "headers": {"Authorization": f"Bearer {access_token}"},
        "payload": payload,
    }


# ---------------------------------------------------------------------------
# 이메일 인증 토큰 검증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_email_with_valid_token_succeeds(client: AsyncClient, fake):
    """유효한 인증 토큰으로 이메일 인증이 성공한다."""
    unverified = await _create_unverified_user(client, fake)

    # DB에서 인증 토큰 생성
    raw_token = await create_verification_token(unverified["user_id"])

    # 인증 요청
    res = await client.post(
        "/v1/auth/verify-email",
        json={"token": raw_token},
    )

    assert res.status_code == 200
    assert res.json()["code"] == "EMAIL_VERIFIED"


@pytest.mark.asyncio
async def test_verify_email_with_invalid_token_fails(client: AsyncClient, fake):
    """유효하지 않은 토큰으로 이메일 인증 시 400을 반환한다."""
    res = await client.post(
        "/v1/auth/verify-email",
        json={"token": "completely-invalid-token"},
    )

    assert res.status_code == 400


@pytest.mark.asyncio
async def test_verify_email_with_expired_token_fails(client: AsyncClient, fake):
    """만료된 토큰으로 이메일 인증 시 400을 반환한다."""
    unverified = await _create_unverified_user(client, fake)

    # 인증 토큰 생성 후 만료 시간을 과거로 변경
    raw_token = await create_verification_token(unverified["user_id"])
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE email_verification SET expires_at = '2020-01-01 00:00:00' WHERE user_id = %s",
            (unverified["user_id"],),
        )

    res = await client.post(
        "/v1/auth/verify-email",
        json={"token": raw_token},
    )

    assert res.status_code == 400


@pytest.mark.asyncio
async def test_verify_already_verified_user(client: AsyncClient, fake):
    """이미 인증된 사용자가 재인증 요청 시 적절히 처리된다."""
    user = await create_verified_user(client, fake)

    # 인증 완료된 사용자로 resend-verification 시도 → 400 (이미 인증됨)
    res = await user["client"].post("/v1/auth/resend-verification")

    assert res.status_code == 400
    assert res.json()["detail"]["error"] == "already_verified"


# ---------------------------------------------------------------------------
# 인증 메일 재발송
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resend_verification_email_succeeds(client: AsyncClient, fake):
    """미인증 사용자가 인증 메일 재발송 요청 시 200을 반환한다."""
    unverified = await _create_unverified_user(client, fake)

    res = await unverified["client"].post("/v1/auth/resend-verification")

    assert res.status_code == 200
    assert res.json()["code"] == "VERIFICATION_EMAIL_SENT"


# ---------------------------------------------------------------------------
# 미인증 사용자 쓰기 제한 (require_verified_email 가드)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unverified_user_cannot_create_post(client: AsyncClient, fake):
    """미인증 사용자는 게시글을 생성할 수 없다 (403)."""
    unverified = await _create_unverified_user(client, fake)

    res = await unverified["client"].post(
        "/v1/posts/",
        json={"title": "테스트", "content": "테스트 내용", "category_id": 1},
    )

    assert res.status_code == 403
    assert res.json()["detail"]["error"] == "email_not_verified"


@pytest.mark.asyncio
async def test_unverified_user_cannot_create_comment(client: AsyncClient, fake):
    """미인증 사용자는 댓글을 작성할 수 없다 (403)."""
    # 게시글 작성을 위해 인증된 사용자 필요
    verified = await create_verified_user(client, fake)
    post = await verified["client"].post(
        "/v1/posts/",
        json={"title": "테스트 게시글", "content": "내용", "category_id": 1},
    )
    post_id = post.json()["data"]["post_id"]

    unverified = await _create_unverified_user(client, fake)

    res = await unverified["client"].post(
        f"/v1/posts/{post_id}/comments",
        json={"content": "테스트 댓글"},
    )

    assert res.status_code == 403
    assert res.json()["detail"]["error"] == "email_not_verified"


@pytest.mark.asyncio
async def test_unverified_user_cannot_like_post(client: AsyncClient, fake):
    """미인증 사용자는 게시글에 좋아요를 할 수 없다 (403)."""
    verified = await create_verified_user(client, fake)
    post = await verified["client"].post(
        "/v1/posts/",
        json={"title": "테스트 게시글", "content": "내용", "category_id": 1},
    )
    post_id = post.json()["data"]["post_id"]

    unverified = await _create_unverified_user(client, fake)

    res = await unverified["client"].post(f"/v1/posts/{post_id}/likes")

    assert res.status_code == 403
    assert res.json()["detail"]["error"] == "email_not_verified"


@pytest.mark.asyncio
async def test_unverified_user_cannot_follow(client: AsyncClient, fake):
    """미인증 사용자는 다른 사용자를 팔로우할 수 없다 (403)."""
    verified = await create_verified_user(client, fake)
    unverified = await _create_unverified_user(client, fake)

    res = await unverified["client"].post(f"/v1/users/{verified['user_id']}/follow")

    assert res.status_code == 403
    assert res.json()["detail"]["error"] == "email_not_verified"


@pytest.mark.asyncio
async def test_unverified_user_cannot_send_dm(client: AsyncClient, fake):
    """미인증 사용자는 DM 대화를 시작할 수 없다 (403)."""
    verified = await create_verified_user(client, fake)
    unverified = await _create_unverified_user(client, fake)

    res = await unverified["client"].post(
        "/v1/dms",
        json={"recipient_id": verified["user_id"]},
    )

    assert res.status_code == 403
    assert res.json()["detail"]["error"] == "email_not_verified"
