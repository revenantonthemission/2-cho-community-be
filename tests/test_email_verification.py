"""test_email_verification: 이메일 인증 기능 통합 테스트.

토큰 생성, 검증, 재발송, 만료 토큰 정리를 테스트합니다.
SMTP 미설정 환경에서도 동작하도록 이메일 발송은 mock 처리합니다.
"""

import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from database.connection import get_connection, transactional
from main import app
from models import verification_models


# ==========================================
# 1. 모델 계층 테스트 (DB 직접 조작)
# ==========================================


@pytest.mark.asyncio
async def test_create_verification_token(db):
    """인증 토큰 생성 시 DB에 해시가 저장되는지 확인."""
    # 사용자 생성
    user_id = await _create_test_user()

    raw_token = await verification_models.create_verification_token(user_id)

    # raw_token이 반환되는지 확인
    assert raw_token is not None
    assert len(raw_token) > 0

    # DB에 해시가 저장되었는지 확인
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT user_id, token_hash FROM email_verification WHERE user_id = %s",
                (user_id,),
            )
            row = await cur.fetchone()
            assert row is not None
            assert row[0] == user_id
            assert row[1] == token_hash


@pytest.mark.asyncio
async def test_create_verification_token_replaces_existing(db):
    """같은 user_id로 토큰 재생성 시 기존 토큰이 교체되는지 확인."""
    user_id = await _create_test_user()

    token1 = await verification_models.create_verification_token(user_id)
    token2 = await verification_models.create_verification_token(user_id)

    # 두 토큰이 다른지 확인
    assert token1 != token2

    # DB에 하나의 레코드만 존재하는지 확인 (REPLACE INTO)
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT COUNT(*) FROM email_verification WHERE user_id = %s",
                (user_id,),
            )
            row = await cur.fetchone()
            assert row[0] == 1

    # 최신 토큰이 유효한지 확인
    result = await verification_models.verify_token(token2)
    assert result == user_id


@pytest.mark.asyncio
async def test_verify_token_success(db):
    """유효한 토큰으로 인증 성공 시 user_id 반환 및 email_verified 갱신."""
    user_id = await _create_test_user()

    raw_token = await verification_models.create_verification_token(user_id)
    result = await verification_models.verify_token(raw_token)

    assert result == user_id

    # email_verified가 1로 설정되었는지 확인
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT email_verified FROM user WHERE id = %s",
                (user_id,),
            )
            row = await cur.fetchone()
            assert row[0] == 1

    # 토큰이 삭제되었는지 확인
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT COUNT(*) FROM email_verification WHERE user_id = %s",
                (user_id,),
            )
            row = await cur.fetchone()
            assert row[0] == 0


@pytest.mark.asyncio
async def test_verify_token_invalid(db):
    """존재하지 않는 토큰으로 인증 시 None 반환."""
    result = await verification_models.verify_token("invalid_token_string")
    assert result is None


@pytest.mark.asyncio
async def test_verify_token_expired(db):
    """만료된 토큰으로 인증 시 None 반환 및 토큰 삭제."""
    user_id = await _create_test_user()

    # 토큰 생성 후 만료 시간을 과거로 변경
    raw_token = await verification_models.create_verification_token(user_id)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    expired_time = datetime.now(timezone.utc) - timedelta(hours=1)
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE email_verification SET expires_at = %s WHERE token_hash = %s",
                (expired_time, token_hash),
            )

    result = await verification_models.verify_token(raw_token)
    assert result is None

    # 만료된 토큰이 삭제되었는지 확인
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT COUNT(*) FROM email_verification WHERE token_hash = %s",
                (token_hash,),
            )
            row = await cur.fetchone()
            assert row[0] == 0


@pytest.mark.asyncio
async def test_cleanup_expired_verification_tokens(db):
    """만료된 토큰 일괄 삭제 테스트."""
    user_id1 = await _create_test_user(email="expired1@test.com", nickname="expired1")
    user_id2 = await _create_test_user(email="expired2@test.com", nickname="expired2")
    user_id3 = await _create_test_user(email="valid@test.com", nickname="valid")

    # 3개의 토큰 생성
    await verification_models.create_verification_token(user_id1)
    await verification_models.create_verification_token(user_id2)
    await verification_models.create_verification_token(user_id3)

    # 2개를 만료 처리
    expired_time = datetime.now(timezone.utc) - timedelta(hours=1)
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE email_verification SET expires_at = %s WHERE user_id IN (%s, %s)",
                (expired_time, user_id1, user_id2),
            )

    deleted = await verification_models.cleanup_expired_verification_tokens()
    assert deleted == 2

    # 유효한 토큰은 남아있는지 확인
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT COUNT(*) FROM email_verification WHERE user_id = %s",
                (user_id3,),
            )
            row = await cur.fetchone()
            assert row[0] == 1


# ==========================================
# 2. API 엔드포인트 테스트
# ==========================================


@pytest.mark.asyncio
async def test_verify_email_endpoint_success(client, user_payload):
    """POST /v1/auth/verify-email 성공 테스트."""
    # 회원가입 (이메일 발송 mock 처리)
    with patch("services.user_service.send_email", new_callable=AsyncMock):
        res = await client.post("/v1/users/", data=user_payload)
        assert res.status_code == 201

    # DB에서 user_id 조회
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM user WHERE email = %s",
                (user_payload["email"],),
            )
            row = await cur.fetchone()
            user_id = row[0]

    # 인증 토큰 직접 생성
    raw_token = await verification_models.create_verification_token(user_id)

    # 인증 요청
    res = await client.post("/v1/auth/verify-email", json={"token": raw_token})
    assert res.status_code == 200
    data = res.json()
    assert data["code"] == "EMAIL_VERIFIED"

    # email_verified 확인
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT email_verified FROM user WHERE id = %s",
                (user_id,),
            )
            row = await cur.fetchone()
            assert row[0] == 1


@pytest.mark.asyncio
async def test_verify_email_endpoint_invalid_token(client):
    """POST /v1/auth/verify-email 잘못된 토큰으로 400 반환."""
    res = await client.post(
        "/v1/auth/verify-email", json={"token": "completely_invalid_token"}
    )
    assert res.status_code == 400
    assert res.json()["detail"]["error"] == "invalid_or_expired_token"


@pytest.mark.asyncio
async def test_resend_verification_endpoint_success(client, user_payload):
    """POST /v1/auth/resend-verification 성공 테스트 (미인증 사용자)."""
    # 회원가입
    with patch("services.user_service.send_email", new_callable=AsyncMock):
        res = await client.post("/v1/users/", data=user_payload)
        assert res.status_code == 201

    # 로그인 (이메일 미인증 상태)
    login_res = await client.post(
        "/v1/auth/session",
        json={"email": user_payload["email"], "password": user_payload["password"]},
    )
    assert login_res.status_code == 200
    access_token = login_res.json()["data"]["access_token"]

    # 인증된 클라이언트로 재발송 요청
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {access_token}"},
    ) as auth_client:
        with patch(
            "controllers.auth_controller.send_email", new_callable=AsyncMock
        ):
            res = await auth_client.post("/v1/auth/resend-verification")
            assert res.status_code == 200
            data = res.json()
            assert data["code"] == "VERIFICATION_EMAIL_SENT"


@pytest.mark.asyncio
async def test_resend_verification_endpoint_already_verified(
    client, authorized_user
):
    """POST /v1/auth/resend-verification 이미 인증된 사용자는 400."""
    cli, _, _ = authorized_user
    res = await cli.post("/v1/auth/resend-verification")
    assert res.status_code == 400
    assert res.json()["detail"]["error"] == "already_verified"


@pytest.mark.asyncio
async def test_resend_verification_endpoint_unauthorized(client):
    """POST /v1/auth/resend-verification 미인증 요청은 401."""
    res = await client.post("/v1/auth/resend-verification")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_signup_returns_unverified_user(client, user_payload):
    """회원가입 후 로그인 시 email_verified가 False인지 확인."""
    with patch("services.user_service.send_email", new_callable=AsyncMock):
        res = await client.post("/v1/users/", data=user_payload)
        assert res.status_code == 201

    # 로그인
    login_res = await client.post(
        "/v1/auth/session",
        json={"email": user_payload["email"], "password": user_payload["password"]},
    )
    assert login_res.status_code == 200
    assert login_res.json()["data"]["user"]["email_verified"] is False


@pytest.mark.asyncio
async def test_signup_creates_verification_token(client, user_payload):
    """회원가입 시 인증 토큰이 DB에 생성되는지 확인."""
    with patch("services.user_service.send_email", new_callable=AsyncMock):
        res = await client.post("/v1/users/", data=user_payload)
        assert res.status_code == 201

    # DB에서 인증 토큰 존재 확인
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT ev.user_id
                FROM email_verification ev
                JOIN user u ON ev.user_id = u.id
                WHERE u.email = %s
                """,
                (user_payload["email"],),
            )
            row = await cur.fetchone()
            assert row is not None


@pytest.mark.asyncio
async def test_signup_email_failure_does_not_block(client, user_payload):
    """회원가입 시 이메일 발송 실패해도 회원가입은 성공."""
    with patch(
        "services.user_service.send_email",
        new_callable=AsyncMock,
        side_effect=RuntimeError("SMTP connection failed"),
    ):
        res = await client.post("/v1/users/", data=user_payload)
        assert res.status_code == 201


# ==========================================
# 헬퍼 함수
# ==========================================


async def _create_test_user(
    email: str = "test@example.com",
    nickname: str = "testuser",
    password: str = "hashedpw",
) -> int:
    """테스트용 사용자를 DB에 직접 생성합니다."""
    async with transactional() as cur:
        await cur.execute(
            """
            INSERT INTO user (email, nickname, password)
            VALUES (%s, %s, %s)
            """,
            (email, nickname, password),
        )
        return cur.lastrowid
