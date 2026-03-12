"""Posts 도메인 — 공통 픽스처."""

import pytest_asyncio
from tests.conftest import create_verified_user, create_test_post


@pytest_asyncio.fixture
async def post_with_author(client, fake):
    """게시글 + 작성자 픽스처."""
    user = await create_verified_user(client, fake)
    post = await create_test_post(client, user["headers"])
    return {"user": user, "post": post}
