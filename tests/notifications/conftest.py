"""Notifications 도메인 -- 공통 픽스처."""

import pytest_asyncio

from tests.conftest import create_test_post, create_verified_user


@pytest_asyncio.fixture
async def two_users_with_post(client, fake):
    """알림 테스트용 게시글 작성자 + 다른 사용자 픽스처.

    반환 dict:
        author: 게시글 작성자 (알림 수신 대상)
        other: 액션 수행자 (알림 발생자)
        post: 작성된 게시글 데이터
    """
    author = await create_verified_user(client, fake)
    other = await create_verified_user(client, fake)
    post = await create_test_post(client, author["headers"])
    return {"author": author, "other": other, "post": post}
