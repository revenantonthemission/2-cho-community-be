"""test_internal_auth: 내부 API 인증 및 배치 엔드포인트 테스트."""

import pytest
from database.connection import get_connection


async def _make_admin(user_id: int) -> None:
    """사용자를 관리자로 변경합니다."""
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("UPDATE user SET role = 'admin' WHERE id = %s", (user_id,))
            await conn.commit()


# ============ 내부 API 키 인증 ============


@pytest.mark.asyncio
async def test_internal_key_cleanup_tokens(client, monkeypatch):
    """유효한 내부 API 키로 토큰 정리 엔드포인트 호출 (200)."""
    monkeypatch.setenv("INTERNAL_API_KEY", "test-internal-key-12345")

    # settings 캐시를 우회하기 위해 직접 패치
    from core.config import settings
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", "test-internal-key-12345")

    res = await client.post(
        "/v1/admin/cleanup/tokens",
        headers={"X-Internal-Key": "test-internal-key-12345"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "refresh_tokens_deleted" in data["data"]
    assert "verification_tokens_deleted" in data["data"]


@pytest.mark.asyncio
async def test_internal_key_invalid(client, monkeypatch):
    """잘못된 내부 API 키로 호출 (403)."""
    from core.config import settings
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", "correct-key")

    res = await client.post(
        "/v1/admin/cleanup/tokens",
        headers={"X-Internal-Key": "wrong-key"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_internal_key_missing(client, monkeypatch):
    """내부 API 키 헤더 없이 호출 (403, 비인증)."""
    from core.config import settings
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", "some-key")

    res = await client.post("/v1/admin/cleanup/tokens")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_internal_key_empty_config(client, monkeypatch):
    """INTERNAL_API_KEY 미설정 시 내부 키 인증 불가 (403)."""
    from core.config import settings
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", "")

    res = await client.post(
        "/v1/admin/cleanup/tokens",
        headers={"X-Internal-Key": "any-key"},
    )
    assert res.status_code == 403


# ============ 관리자 JWT + 내부 키 이중 인증 ============


@pytest.mark.asyncio
async def test_admin_jwt_cleanup_tokens(client, authorized_user, monkeypatch):
    """관리자 JWT로 토큰 정리 엔드포인트 호출 (200)."""
    from core.config import settings
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", "")

    cli, user_info, _ = authorized_user
    await _make_admin(user_info["user_id"])

    res = await cli.post("/v1/admin/cleanup/tokens")
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_non_admin_jwt_cleanup_tokens(client, authorized_user, monkeypatch):
    """비관리자 JWT로 토큰 정리 엔드포인트 호출 (403)."""
    from core.config import settings
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", "")

    cli, _, _ = authorized_user
    res = await cli.post("/v1/admin/cleanup/tokens")
    assert res.status_code == 403


# ============ 피드 재계산 내부 인증 ============


@pytest.mark.asyncio
async def test_internal_key_feed_recompute(client, monkeypatch):
    """유효한 내부 API 키로 피드 재계산 호출 (200)."""
    from core.config import settings
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", "test-key")

    res = await client.post(
        "/v1/admin/feed/recompute",
        headers={"X-Internal-Key": "test-key"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "success"


@pytest.mark.asyncio
async def test_admin_jwt_feed_recompute(client, authorized_user, monkeypatch):
    """관리자 JWT로 피드 재계산 호출 (200)."""
    from core.config import settings
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", "")

    cli, user_info, _ = authorized_user
    await _make_admin(user_info["user_id"])

    res = await cli.post("/v1/admin/feed/recompute")
    assert res.status_code == 200
