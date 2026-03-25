"""Notifications 도메인 -- digest_frequency 알림 설정 테스트.

digest_frequency ENUM('daily', 'weekly', 'off') 필드의
기본값 조회, 변경, bool 설정 변경 시 유지 여부를 검증합니다.
"""

import pytest

from tests.conftest import create_verified_user


@pytest.mark.asyncio
async def test_digest_frequency_default(client, fake, db):
    """기본값은 weekly."""
    user = await create_verified_user(client, fake)
    res = await user["client"].get("/v1/notifications/settings", headers=user["headers"])
    assert res.status_code == 200
    assert res.json()["data"]["settings"]["digest_frequency"] == "weekly"


@pytest.mark.asyncio
async def test_digest_frequency_update(client, fake, db):
    """빈도 변경."""
    user = await create_verified_user(client, fake)
    res = await user["client"].patch(
        "/v1/notifications/settings",
        json={"digest_frequency": "daily"},
        headers=user["headers"],
    )
    assert res.status_code == 200
    assert res.json()["data"]["settings"]["digest_frequency"] == "daily"


@pytest.mark.asyncio
async def test_digest_frequency_update_to_off(client, fake, db):
    """off로 변경 가능."""
    user = await create_verified_user(client, fake)
    res = await user["client"].patch(
        "/v1/notifications/settings",
        json={"digest_frequency": "off"},
        headers=user["headers"],
    )
    assert res.status_code == 200
    assert res.json()["data"]["settings"]["digest_frequency"] == "off"


@pytest.mark.asyncio
async def test_digest_frequency_not_reverted_on_bool_update(client, fake, db):
    """bool 설정 변경 시 digest_frequency가 리버트되지 않음."""
    user = await create_verified_user(client, fake)

    # daily로 변경
    await user["client"].patch(
        "/v1/notifications/settings",
        json={"digest_frequency": "daily"},
        headers=user["headers"],
    )

    # bool 설정만 변경
    res = await user["client"].patch(
        "/v1/notifications/settings",
        json={"comment": False},
        headers=user["headers"],
    )
    assert res.status_code == 200
    settings = res.json()["data"]["settings"]
    assert settings["digest_frequency"] == "daily"  # 리버트 안 됨
    assert settings["comment"] is False


@pytest.mark.asyncio
async def test_digest_frequency_persists_after_get(client, fake, db):
    """변경 후 GET 조회에서도 유지됨."""
    user = await create_verified_user(client, fake)

    await user["client"].patch(
        "/v1/notifications/settings",
        json={"digest_frequency": "daily"},
        headers=user["headers"],
    )

    get_res = await user["client"].get("/v1/notifications/settings", headers=user["headers"])
    assert get_res.status_code == 200
    assert get_res.json()["data"]["settings"]["digest_frequency"] == "daily"
