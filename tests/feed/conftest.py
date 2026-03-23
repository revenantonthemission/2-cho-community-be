"""Feed 도메인 테스트용 픽스처."""

import pytest_asyncio

from tests.conftest import create_test_post, create_verified_user


@pytest_asyncio.fixture
async def feed_data(client, fake):
    """피드 테스트용: 2명 사용자 + 여러 게시글."""
    user1 = await create_verified_user(client, fake)
    user2 = await create_verified_user(client, fake)

    posts = []
    for i in range(5):
        author = user1 if i % 2 == 0 else user2
        post = await create_test_post(client, author["headers"], title=f"피드 테스트 {i}")
        posts.append(post)

    return {"user1": user1, "user2": user2, "posts": posts}
