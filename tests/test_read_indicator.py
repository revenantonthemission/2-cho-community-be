"""읽은 게시글 표시 테스트."""
import pytest


class TestReadIndicator:
    """게시글 읽음 상태 테스트."""

    @pytest.mark.asyncio
    async def test_unread_post_in_list(self, authorized_user):
        """미열람 게시글은 is_read=false."""
        client, _, _ = authorized_user
        res = await client.post("/v1/posts/", json={
            "title": "읽지 않은 게시글",
            "content": "아직 열어보지 않았습니다.",
            "category_id": 1,
        })
        assert res.status_code == 201

        list_res = await client.get("/v1/posts/")
        assert list_res.status_code == 200
        posts = list_res.json()["data"]["posts"]
        my_post = [p for p in posts if p["title"] == "읽지 않은 게시글"]
        assert len(my_post) == 1
        assert my_post[0]["is_read"] is False

    @pytest.mark.asyncio
    async def test_read_post_after_view(self, authorized_user):
        """게시글 상세 조회 후 목록에서 is_read=true."""
        client, _, _ = authorized_user
        res = await client.post("/v1/posts/", json={
            "title": "읽을 게시글",
            "content": "열어볼 예정입니다.",
            "category_id": 1,
        })
        post_id = res.json()["data"]["post_id"]

        # 상세 조회 (post_view_log에 기록됨)
        await client.get(f"/v1/posts/{post_id}")

        # 목록에서 is_read 확인
        list_res = await client.get("/v1/posts/")
        posts = list_res.json()["data"]["posts"]
        my_post = [p for p in posts if p["post_id"] == post_id]
        assert len(my_post) == 1
        assert my_post[0]["is_read"] is True

    @pytest.mark.asyncio
    async def test_anonymous_user_always_unread(self, authorized_user, client):
        """비로그인 사용자는 항상 is_read=false."""
        auth_client, _, _ = authorized_user
        await auth_client.post("/v1/posts/", json={
            "title": "익명 테스트 게시글",
            "content": "비로그인 사용자 테스트.",
            "category_id": 1,
        })

        # 비로그인 클라이언트로 조회
        response = await client.get("/v1/posts/")
        assert response.status_code == 200
        posts = response.json()["data"]["posts"]
        for post in posts:
            assert post["is_read"] is False
