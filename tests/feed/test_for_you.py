"""추천(for_you) 피드 API 테스트.

GET /v1/posts/?sort=for_you 로 추천 피드를 조회하는 기능을 검증합니다.
user_post_score가 없으면 latest로 폴백하는 동작이 주요 테스트 대상입니다.
"""

import pytest

from core.database.connection import get_connection
from tests.conftest import create_test_post, create_verified_user


@pytest.mark.asyncio
async def test_for_you_feed_returns_posts(client, fake, feed_data):
    """sort=for_you로 조회 시 200과 게시글 목록을 반환한다."""
    user1 = feed_data["user1"]

    res = await client.get(
        "/v1/posts/",
        params={"sort": "for_you"},
        headers=user1["headers"],
    )
    assert res.status_code == 200

    data = res.json()["data"]
    assert "posts" in data
    assert len(data["posts"]) > 0
    assert "pagination" in data


@pytest.mark.asyncio
async def test_for_you_without_scores_falls_back_to_latest(client, fake, feed_data):
    """user_post_score가 없으면 latest와 동일한 결과를 반환한다."""
    user1 = feed_data["user1"]

    # for_you 정렬 조회
    res_for_you = await client.get(
        "/v1/posts/",
        params={"sort": "for_you"},
        headers=user1["headers"],
    )
    assert res_for_you.status_code == 200

    # latest 정렬 조회
    res_latest = await client.get(
        "/v1/posts/",
        params={"sort": "latest"},
        headers=user1["headers"],
    )
    assert res_latest.status_code == 200

    # 점수 미존재 시 for_you는 latest로 폴백하므로 동일한 게시글 ID 순서
    for_you_ids = [p["post_id"] for p in res_for_you.json()["data"]["posts"]]
    latest_ids = [p["post_id"] for p in res_latest.json()["data"]["posts"]]
    assert for_you_ids == latest_ids


@pytest.mark.asyncio
async def test_for_you_unauthenticated_falls_back_to_latest(client, fake, feed_data):
    """비로그인 시 sort=for_you는 latest로 폴백한다."""
    # 인증 없이 for_you 조회
    res_for_you = await client.get("/v1/posts/", params={"sort": "for_you"})
    assert res_for_you.status_code == 200

    # 인증 없이 latest 조회
    res_latest = await client.get("/v1/posts/", params={"sort": "latest"})
    assert res_latest.status_code == 200

    for_you_ids = [p["post_id"] for p in res_for_you.json()["data"]["posts"]]
    latest_ids = [p["post_id"] for p in res_latest.json()["data"]["posts"]]
    assert for_you_ids == latest_ids


@pytest.mark.asyncio
async def test_for_you_with_scores_uses_score_ordering(client, fake):
    """user_post_score에 점수가 있으면 점수 기반 정렬을 사용한다."""
    user = await create_verified_user(client, fake)

    # 게시글 2개 생성
    post_low = await create_test_post(client, user["headers"], title="낮은 점수 게시글")
    post_high = await create_test_post(client, user["headers"], title="높은 점수 게시글")

    # user_post_score에 직접 점수 삽입
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO user_post_score (user_id, post_id, combined_score) VALUES (%s, %s, %s), (%s, %s, %s)",
            (
                user["user_id"],
                post_low["post_id"],
                10.0,
                user["user_id"],
                post_high["post_id"],
                90.0,
            ),
        )

    res = await client.get(
        "/v1/posts/",
        params={"sort": "for_you"},
        headers=user["headers"],
    )
    assert res.status_code == 200

    posts = res.json()["data"]["posts"]
    post_ids = [p["post_id"] for p in posts]

    # 높은 점수 게시글이 먼저 나와야 한다
    idx_high = post_ids.index(post_high["post_id"])
    idx_low = post_ids.index(post_low["post_id"])
    assert idx_high < idx_low
