"""Admin 도메인 -- 내부 API(Internal) 인증 테스트."""

import pytest
from httpx import AsyncClient

INTERNAL_KEY = "test-internal-key-12345"


# ---------------------------------------------------------------------------
# 내부 API 키 인증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_internal_key_auth_succeeds(client: AsyncClient, monkeypatch):
    """유효한 내부 API 키로 토큰 정리 엔드포인트를 호출할 수 있다."""
    # Arrange
    from core.config import settings

    monkeypatch.setattr(settings, "INTERNAL_API_KEY", INTERNAL_KEY)

    # Act
    res = await client.post(
        "/v1/admin/cleanup/tokens",
        headers={"X-Internal-Key": INTERNAL_KEY},
    )

    # Assert
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "refresh_tokens_deleted" in data["data"]
    assert "verification_tokens_deleted" in data["data"]


@pytest.mark.asyncio
async def test_feed_recompute_with_internal_key(
    client: AsyncClient,
    monkeypatch,
):
    """유효한 내부 API 키로 피드 재계산을 호출할 수 있다."""
    # Arrange
    from core.config import settings

    monkeypatch.setattr(settings, "INTERNAL_API_KEY", INTERNAL_KEY)

    # Act
    res = await client.post(
        "/v1/admin/feed/recompute",
        headers={"X-Internal-Key": INTERNAL_KEY},
    )

    # Assert
    assert res.status_code == 200
    assert res.json()["status"] == "success"


@pytest.mark.asyncio
async def test_token_cleanup_with_internal_key(
    client: AsyncClient,
    monkeypatch,
):
    """유효한 내부 API 키로 토큰 정리를 호출할 수 있다."""
    # Arrange
    from core.config import settings

    monkeypatch.setattr(settings, "INTERNAL_API_KEY", INTERNAL_KEY)

    # Act
    res = await client.post(
        "/v1/admin/cleanup/tokens",
        headers={"X-Internal-Key": INTERNAL_KEY},
    )

    # Assert
    assert res.status_code == 200
    data = res.json()["data"]
    assert "refresh_tokens_deleted" in data
    assert "verification_tokens_deleted" in data


# ---------------------------------------------------------------------------
# 잘못된 키 / 미인증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_internal_key_returns_403(
    client: AsyncClient,
    monkeypatch,
):
    """잘못된 내부 API 키로 호출하면 403을 반환한다."""
    # Arrange
    from core.config import settings

    monkeypatch.setattr(settings, "INTERNAL_API_KEY", "correct-key")

    # Act
    res = await client.post(
        "/v1/admin/cleanup/tokens",
        headers={"X-Internal-Key": "wrong-key"},
    )

    # Assert
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# 관리자 JWT 폴백
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_jwt_admin_fallback_for_internal_api(
    client: AsyncClient,
    admin,
    monkeypatch,
):
    """내부 API 키 없이도 관리자 JWT로 내부 API를 호출할 수 있다."""
    # Arrange — 내부 키 비활성화
    from core.config import settings

    monkeypatch.setattr(settings, "INTERNAL_API_KEY", "")

    # Act
    res = await client.post(
        "/v1/admin/cleanup/tokens",
        headers=admin["headers"],
    )

    # Assert
    assert res.status_code == 200
    assert res.json()["status"] == "success"
