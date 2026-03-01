"""test_comment_reply: 대댓글(1단계 답글) 기능 테스트."""

import pytest


@pytest.mark.asyncio
async def test_create_reply(authorized_user):
    """루트 댓글에 대댓글을 작성할 수 있다."""
    client, user_info, _ = authorized_user

    post_res = await client.post("/v1/posts/", json={"title": "테스트 게시글", "content": "내용"})
    post_id = post_res.json()["data"]["post_id"]

    comment_res = await client.post(f"/v1/posts/{post_id}/comments", json={"content": "원댓글"})
    assert comment_res.status_code == 201
    comment_id = comment_res.json()["data"]["comment_id"]

    reply_res = await client.post(
        f"/v1/posts/{post_id}/comments",
        json={"content": "대댓글입니다", "parent_id": comment_id},
    )
    assert reply_res.status_code == 201
    reply_data = reply_res.json()["data"]
    assert reply_data["parent_id"] == comment_id


@pytest.mark.asyncio
async def test_cannot_reply_to_reply(authorized_user):
    """대댓글에 다시 대댓글을 달 수 없다 (1단계 제한)."""
    client, user_info, _ = authorized_user

    post_res = await client.post("/v1/posts/", json={"title": "테스트 게시글", "content": "내용"})
    post_id = post_res.json()["data"]["post_id"]

    comment_res = await client.post(f"/v1/posts/{post_id}/comments", json={"content": "원댓글"})
    comment_id = comment_res.json()["data"]["comment_id"]

    reply_res = await client.post(
        f"/v1/posts/{post_id}/comments",
        json={"content": "대댓글", "parent_id": comment_id},
    )
    reply_id = reply_res.json()["data"]["comment_id"]

    nested_res = await client.post(
        f"/v1/posts/{post_id}/comments",
        json={"content": "대대댓글 시도", "parent_id": reply_id},
    )
    assert nested_res.status_code == 400


@pytest.mark.asyncio
async def test_cannot_reply_to_different_post_comment(authorized_user):
    """다른 게시글의 댓글에 대댓글을 달 수 없다."""
    client, user_info, _ = authorized_user

    post1_res = await client.post("/v1/posts/", json={"title": "게시글 1", "content": "내용"})
    post1_id = post1_res.json()["data"]["post_id"]

    post2_res = await client.post("/v1/posts/", json={"title": "게시글 2", "content": "내용"})
    post2_id = post2_res.json()["data"]["post_id"]

    comment_res = await client.post(f"/v1/posts/{post1_id}/comments", json={"content": "게시글1 댓글"})
    comment_id = comment_res.json()["data"]["comment_id"]

    reply_res = await client.post(
        f"/v1/posts/{post2_id}/comments",
        json={"content": "크로스 포스트 대댓글", "parent_id": comment_id},
    )
    assert reply_res.status_code == 400


@pytest.mark.asyncio
async def test_cannot_reply_to_deleted_comment(authorized_user):
    """삭제된 댓글에 대댓글을 달 수 없다."""
    client, user_info, _ = authorized_user

    post_res = await client.post("/v1/posts/", json={"title": "테스트 게시글", "content": "내용"})
    post_id = post_res.json()["data"]["post_id"]

    comment_res = await client.post(f"/v1/posts/{post_id}/comments", json={"content": "삭제될 댓글"})
    comment_id = comment_res.json()["data"]["comment_id"]

    await client.delete(f"/v1/posts/{post_id}/comments/{comment_id}")

    reply_res = await client.post(
        f"/v1/posts/{post_id}/comments",
        json={"content": "삭제된 댓글에 대댓글", "parent_id": comment_id},
    )
    assert reply_res.status_code == 400


@pytest.mark.asyncio
async def test_comment_tree_structure(authorized_user):
    """게시글 상세 조회 시 댓글이 트리 구조로 반환된다."""
    client, user_info, _ = authorized_user

    post_res = await client.post("/v1/posts/", json={"title": "테스트 게시글", "content": "내용"})
    post_id = post_res.json()["data"]["post_id"]

    c1_res = await client.post(f"/v1/posts/{post_id}/comments", json={"content": "루트 댓글 1"})
    c1_id = c1_res.json()["data"]["comment_id"]

    await client.post(f"/v1/posts/{post_id}/comments", json={"content": "루트 댓글 2"})

    await client.post(
        f"/v1/posts/{post_id}/comments",
        json={"content": "대댓글", "parent_id": c1_id},
    )

    detail_res = await client.get(f"/v1/posts/{post_id}")
    assert detail_res.status_code == 200
    comments = detail_res.json()["data"]["comments"]

    assert len(comments) == 2
    assert len(comments[0]["replies"]) == 1
    assert comments[0]["replies"][0]["content"] == "대댓글"
    assert len(comments[1]["replies"]) == 0


@pytest.mark.asyncio
async def test_deleted_parent_shows_placeholder(authorized_user):
    """삭제된 부모 댓글은 '삭제된 댓글입니다' 플레이스홀더로 표시된다."""
    client, user_info, _ = authorized_user

    post_res = await client.post("/v1/posts/", json={"title": "테스트 게시글", "content": "내용"})
    post_id = post_res.json()["data"]["post_id"]

    c_res = await client.post(f"/v1/posts/{post_id}/comments", json={"content": "삭제될 댓글"})
    c_id = c_res.json()["data"]["comment_id"]

    await client.post(
        f"/v1/posts/{post_id}/comments",
        json={"content": "살아있는 대댓글", "parent_id": c_id},
    )

    await client.delete(f"/v1/posts/{post_id}/comments/{c_id}")

    detail_res = await client.get(f"/v1/posts/{post_id}")
    comments = detail_res.json()["data"]["comments"]

    assert len(comments) == 1
    assert comments[0]["is_deleted"] is True
    assert comments[0]["content"] is None
    assert comments[0]["author"] is None
    assert len(comments[0]["replies"]) == 1
    assert comments[0]["replies"][0]["content"] == "살아있는 대댓글"


@pytest.mark.asyncio
async def test_deleted_comment_without_replies_hidden(authorized_user):
    """대댓글이 없는 삭제된 댓글은 목록에서 제외된다."""
    client, user_info, _ = authorized_user

    post_res = await client.post("/v1/posts/", json={"title": "테스트 게시글", "content": "내용"})
    post_id = post_res.json()["data"]["post_id"]

    c1_res = await client.post(f"/v1/posts/{post_id}/comments", json={"content": "삭제될 댓글"})
    c1_id = c1_res.json()["data"]["comment_id"]
    await client.post(f"/v1/posts/{post_id}/comments", json={"content": "살아있는 댓글"})

    await client.delete(f"/v1/posts/{post_id}/comments/{c1_id}")

    detail_res = await client.get(f"/v1/posts/{post_id}")
    comments = detail_res.json()["data"]["comments"]

    assert len(comments) == 1
    assert comments[0]["content"] == "살아있는 댓글"
