"""Posts 도메인 — Q&A 답변 채택/해제 테스트."""

import pytest
from httpx import AsyncClient

from tests.conftest import create_test_comment, create_test_post, create_verified_user

# ---------------------------------------------------------------------------
# 답변 채택 성공
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_accept_answer(client: AsyncClient, fake):
    """게시글 작성자가 Q&A 게시글의 루트 댓글을 채택하면 200을 반환한다."""
    author = await create_verified_user(client, fake)
    post = await create_test_post(client, author["headers"], category_id=2)
    post_id = post["post_id"]

    # 다른 사용자가 댓글 작성
    answerer = await create_verified_user(client, fake)
    comment = await create_test_comment(client, answerer["headers"], post_id, content="답변입니다.")
    comment_id = comment["comment_id"]

    res = await client.patch(
        f"/v1/posts/{post_id}/accepted-answer",
        json={"comment_id": comment_id},
        headers=author["headers"],
    )

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["accepted_answer_id"] == comment_id


# ---------------------------------------------------------------------------
# 답변 채택 해제
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unmark_accepted_answer(client: AsyncClient, fake):
    """게시글 작성자가 채택된 답변을 해제하면 200을 반환한다."""
    author = await create_verified_user(client, fake)
    post = await create_test_post(client, author["headers"], category_id=2)
    post_id = post["post_id"]

    answerer = await create_verified_user(client, fake)
    comment = await create_test_comment(client, answerer["headers"], post_id, content="답변입니다.")
    comment_id = comment["comment_id"]

    # 채택
    accept_res = await client.patch(
        f"/v1/posts/{post_id}/accepted-answer",
        json={"comment_id": comment_id},
        headers=author["headers"],
    )
    assert accept_res.status_code == 200

    # 채택 해제
    res = await client.delete(
        f"/v1/posts/{post_id}/accepted-answer",
        headers=author["headers"],
    )

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["accepted_answer_id"] is None


# ---------------------------------------------------------------------------
# 권한 검증: 게시글 작성자만 채택 가능
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_only_post_author_can_accept(client: AsyncClient, fake):
    """게시글 작성자가 아닌 사용자가 채택을 시도하면 403을 반환한다."""
    author = await create_verified_user(client, fake)
    post = await create_test_post(client, author["headers"], category_id=2)
    post_id = post["post_id"]

    other_user = await create_verified_user(client, fake)
    comment = await create_test_comment(client, other_user["headers"], post_id, content="답변입니다.")
    comment_id = comment["comment_id"]

    # 다른 사용자가 채택 시도
    res = await client.patch(
        f"/v1/posts/{post_id}/accepted-answer",
        json={"comment_id": comment_id},
        headers=other_user["headers"],
    )

    assert res.status_code == 403


# ---------------------------------------------------------------------------
# Q&A 카테고리 검증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_only_qa_category(client: AsyncClient, fake):
    """Q&A가 아닌 카테고리 게시글에서 채택을 시도하면 400을 반환한다."""
    author = await create_verified_user(client, fake)
    # category_id=1 은 '배포판' 카테고리
    post = await create_test_post(client, author["headers"], category_id=1)
    post_id = post["post_id"]

    answerer = await create_verified_user(client, fake)
    comment = await create_test_comment(client, answerer["headers"], post_id, content="답변입니다.")
    comment_id = comment["comment_id"]

    res = await client.patch(
        f"/v1/posts/{post_id}/accepted-answer",
        json={"comment_id": comment_id},
        headers=author["headers"],
    )

    assert res.status_code == 400


# ---------------------------------------------------------------------------
# 루트 댓글만 채택 가능
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_only_root_comment_can_be_accepted(client: AsyncClient, fake):
    """대댓글(reply)을 채택하려 하면 400을 반환한다."""
    author = await create_verified_user(client, fake)
    post = await create_test_post(client, author["headers"], category_id=2)
    post_id = post["post_id"]

    answerer = await create_verified_user(client, fake)
    root_comment = await create_test_comment(client, answerer["headers"], post_id, content="답변입니다.")

    # 대댓글 생성
    reply = await create_test_comment(
        client,
        answerer["headers"],
        post_id,
        content="대댓글입니다.",
        parent_id=root_comment["comment_id"],
    )

    res = await client.patch(
        f"/v1/posts/{post_id}/accepted-answer",
        json={"comment_id": reply["comment_id"]},
        headers=author["headers"],
    )

    assert res.status_code == 400


# ---------------------------------------------------------------------------
# 게시글 상세에서 is_accepted 확인
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_detail_shows_is_accepted(client: AsyncClient, fake):
    """게시글 상세 조회 시 채택된 댓글에 is_accepted=True가 표시된다."""
    author = await create_verified_user(client, fake)
    post = await create_test_post(client, author["headers"], category_id=2)
    post_id = post["post_id"]

    answerer = await create_verified_user(client, fake)
    comment = await create_test_comment(client, answerer["headers"], post_id, content="답변입니다.")
    comment_id = comment["comment_id"]

    # 비채택 댓글도 생성
    await create_test_comment(client, answerer["headers"], post_id, content="다른 답변입니다.")

    # 채택
    accept_res = await client.patch(
        f"/v1/posts/{post_id}/accepted-answer",
        json={"comment_id": comment_id},
        headers=author["headers"],
    )
    assert accept_res.status_code == 200

    # 게시글 상세 조회
    detail_res = await client.get(f"/v1/posts/{post_id}", headers=author["headers"])
    assert detail_res.status_code == 200

    detail_data = detail_res.json()["data"]

    # 게시글에 accepted_answer_id가 표시됨
    assert detail_data["post"]["accepted_answer_id"] == comment_id

    # 댓글 중 채택된 댓글에 is_accepted=True
    comments = detail_data["comments"]
    accepted = [c for c in comments if c["comment_id"] == comment_id]
    assert len(accepted) == 1
    assert accepted[0]["is_accepted"] is True

    # 비채택 댓글에는 is_accepted=False
    not_accepted = [c for c in comments if c["comment_id"] != comment_id]
    assert len(not_accepted) >= 1
    assert all(c["is_accepted"] is False for c in not_accepted)
