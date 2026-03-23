"""Admin 도메인 -- 공통 픽스처."""

import pytest_asyncio

from tests.conftest import create_admin_user, create_verified_user


@pytest_asyncio.fixture
async def admin(client, fake):
    """인증 완료 + admin 역할이 부여된 사용자."""
    return await create_admin_user(client, fake)


@pytest_asyncio.fixture
async def regular_user(client, fake):
    """인증 완료된 일반 사용자."""
    return await create_verified_user(client, fake)
