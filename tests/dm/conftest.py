"""DM 도메인 테스트용 공통 픽스처."""

import pytest_asyncio

from tests.conftest import create_verified_user


@pytest_asyncio.fixture
async def two_users(client, fake):
    """DM 테스트에 필요한 인증 완료 사용자 2명을 생성한다.

    Returns:
        (user_a, user_b) — 각각 create_verified_user()가 반환하는 dict.
    """
    user_a = await create_verified_user(client, fake)
    user_b = await create_verified_user(client, fake)
    async with user_a["client"], user_b["client"]:
        yield user_a, user_b


@pytest_asyncio.fixture
async def three_users(client, fake):
    """DM 테스트에 필요한 인증 완료 사용자 3명을 생성한다.

    Returns:
        (user_a, user_b, user_c) — 각각 create_verified_user()가 반환하는 dict.
    """
    user_a = await create_verified_user(client, fake)
    user_b = await create_verified_user(client, fake)
    user_c = await create_verified_user(client, fake)
    async with user_a["client"], user_b["client"], user_c["client"]:
        yield user_a, user_b, user_c
