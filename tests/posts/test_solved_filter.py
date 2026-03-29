"""Posts 도메인 — solved 필터 테스트."""

import pytest
from httpx import AsyncClient

from tests.conftest import create_test_comment, create_test_post, create_verified_user

# ---------------------------------------------------------------------------
# 헬퍼: Q&A 게시글에 답변 채택하여 "해결됨" 상태로 만든다
# ---------------------------------------------------------------------------


async def _create_solved_post(client: AsyncClient, fake, *, title: str = "해결된 질문") -> dict:
    """Q&A 게시글 생성 → 댓글 작성 → 답변 채택까지 완료한 게시글 데이터를 반환한다."""
    author = await create_verified_user(client, fake)
    post = await create_test_post(client, author["headers"], category_id=2, title=title)
    post_id = post["post_id"]

    # 다른 사용자가 답변 작성
    answerer = await create_verified_user(client, fake)
    comment = await create_test_comment(client, answerer["headers"], post_id, content="답변입니다.")

    # 게시글 작성자가 답변 채택
    res = await client.patch(
        f"/v1/posts/{post_id}/accepted-answer",
        json={"comment_id": comment["comment_id"]},
        headers=author["headers"],
    )
    assert res.status_code == 200

    return post


async def _create_unsolved_post(client: AsyncClient, fake, *, title: str = "미해결 질문") -> dict:
    """Q&A 게시글을 답변 채택 없이 생성한다."""
    author = await create_verified_user(client, fake)
    post = await create_test_post(client, author["headers"], category_id=2, title=title)
    return post


# ---------------------------------------------------------------------------
# solved=true 필터
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_filter_solved_posts(client: AsyncClient, fake):
    """solved=true 필터로 해결된 게시글만 조회한다."""
    await _create_solved_post(client, fake, title="해결된 질문")
    await _create_unsolved_post(client, fake, title="미해결 질문")

    res = await client.get("/v1/posts/?solved=true", follow_redirects=True)

    assert res.status_code == 200
    posts = res.json()["data"]["posts"]
    assert len(posts) >= 1
    for post in posts:
        assert post["is_solved"] is True


# ---------------------------------------------------------------------------
# solved=false 필터
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_filter_unsolved_posts(client: AsyncClient, fake):
    """solved=false 필터로 미해결 게시글만 조회한다."""
    await _create_solved_post(client, fake, title="해결된 질문")
    await _create_unsolved_post(client, fake, title="미해결 질문")

    res = await client.get("/v1/posts/?solved=false", follow_redirects=True)

    assert res.status_code == 200
    posts = res.json()["data"]["posts"]
    assert len(posts) >= 1
    for post in posts:
        assert post["is_solved"] is False


# ---------------------------------------------------------------------------
# solved 파라미터 없음 — 전체 반환
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_solved_filter_returns_all(client: AsyncClient, fake):
    """solved 파라미터 없으면 모든 게시글을 반환한다."""
    await _create_solved_post(client, fake, title="해결된 질문")
    await _create_unsolved_post(client, fake, title="미해결 질문")

    res = await client.get("/v1/posts/", follow_redirects=True)

    assert res.status_code == 200
    posts = res.json()["data"]["posts"]
    # 해결/미해결 모두 포함
    solved_flags = {p["is_solved"] for p in posts}
    assert True in solved_flags, "해결된 게시글이 포함되어야 한다"
    assert False in solved_flags, "미해결 게시글이 포함되어야 한다"
