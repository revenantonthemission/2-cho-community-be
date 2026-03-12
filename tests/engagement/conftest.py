"""Engagement 도메인 -- 공통 픽스처."""

import pytest_asyncio
from tests.conftest import create_verified_user, create_test_post


@pytest_asyncio.fixture
async def post_for_engagement(client, fake):
    """좋아요/북마크/투표 테스트용 게시글 + 작성자 + 다른 사용자 픽스처."""
    author = await create_verified_user(client, fake)
    other = await create_verified_user(client, fake)
    post = await create_test_post(client, author["headers"])
    return {"author": author, "other": other, "post": post}
