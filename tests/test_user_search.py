"""사용자 검색 및 통계 모델 함수 테스트."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from controllers.user_controller import get_user, search_users
from models.user_models import get_user_stats, search_users_by_nickname


def _make_async_cursor(fetchall_result=None, fetchone_result=None):
    """비동기 커서 mock 생성 헬퍼."""
    cursor = AsyncMock()
    cursor.execute = AsyncMock()
    cursor.fetchall = AsyncMock(return_value=fetchall_result or [])
    cursor.fetchone = AsyncMock(return_value=fetchone_result)
    cursor.__aenter__ = AsyncMock(return_value=cursor)
    cursor.__aexit__ = AsyncMock(return_value=False)
    return cursor


def _make_async_conn(cursors):
    """비동기 커넥션 mock 생성 헬퍼. cursors 리스트를 순서대로 반환."""
    conn = AsyncMock()
    cursor_iter = iter(cursors)

    def cursor_factory():
        return next(cursor_iter)

    conn.cursor = cursor_factory
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    return conn


class TestSearchUsersByNickname:
    """닉네임 검색 모델 함수 테스트."""

    @pytest.mark.asyncio
    async def test_empty_query_returns_empty(self):
        """빈 쿼리는 빈 리스트를 반환한다."""
        result = await search_users_by_nickname("", set())
        assert result == []

    @pytest.mark.asyncio
    async def test_whitespace_query_returns_empty(self):
        """공백만 있는 쿼리는 빈 리스트를 반환한다."""
        result = await search_users_by_nickname("   ", set())
        assert result == []

    @pytest.mark.asyncio
    @patch("models.user_models.get_connection")
    async def test_prefix_match_returns_results(self, mock_get_conn):
        """닉네임 접두어 검색이 올바른 결과를 반환한다."""
        rows = [
            (1, "alice", None),
            (2, "alice2", "/uploads/img.jpg"),
        ]
        cursor = _make_async_cursor(fetchall_result=rows)
        conn = _make_async_conn([cursor])
        mock_get_conn.return_value = conn

        result = await search_users_by_nickname("ali", set())

        assert len(result) == 2
        assert result[0]["user_id"] == 1
        assert result[0]["nickname"] == "alice"
        # None이면 기본 프로필 이미지
        assert result[0]["profileImageUrl"] == "/assets/profiles/default_profile.jpg"
        assert result[1]["profileImageUrl"] == "/uploads/img.jpg"

    @pytest.mark.asyncio
    @patch("models.user_models.get_connection")
    async def test_exclude_user_ids_applied(self, mock_get_conn):
        """제외 ID가 SQL에 반영된다."""
        cursor = _make_async_cursor(fetchall_result=[])
        conn = _make_async_conn([cursor])
        mock_get_conn.return_value = conn

        await search_users_by_nickname("test", {10, 20})

        call_args = cursor.execute.call_args
        sql = call_args[0][0]
        params = call_args[0][1]
        assert "NOT IN" in sql
        # params: [query%, *exclude_ids, limit]
        assert params[0] == "test%"
        assert set(params[1:-1]) == {10, 20}


class TestGetUserStats:
    """사용자 활동 통계 조회 테스트."""

    @pytest.mark.asyncio
    @patch("models.user_models.get_connection")
    async def test_returns_correct_stats(self, mock_get_conn):
        """게시글, 댓글, 좋아요 수를 올바르게 반환한다."""
        cur_posts = _make_async_cursor(fetchone_result=(5,))
        cur_comments = _make_async_cursor(fetchone_result=(12,))
        cur_likes = _make_async_cursor(fetchone_result=(30,))

        conn = _make_async_conn([cur_posts, cur_comments, cur_likes])
        mock_get_conn.return_value = conn

        result = await get_user_stats(user_id=1)

        assert result == {
            "posts_count": 5,
            "comments_count": 12,
            "likes_received_count": 30,
        }

    @pytest.mark.asyncio
    @patch("models.user_models.get_connection")
    async def test_returns_zero_when_no_rows(self, mock_get_conn):
        """fetchone이 None을 반환하면 0을 반환한다."""
        cur_posts = _make_async_cursor(fetchone_result=None)
        cur_comments = _make_async_cursor(fetchone_result=None)
        cur_likes = _make_async_cursor(fetchone_result=None)

        conn = _make_async_conn([cur_posts, cur_comments, cur_likes])
        mock_get_conn.return_value = conn

        result = await get_user_stats(user_id=999)

        assert result == {
            "posts_count": 0,
            "comments_count": 0,
            "likes_received_count": 0,
        }


def _make_request():
    """request.state.request_timestamp를 가진 mock Request 생성."""
    request = MagicMock()
    request.state.request_timestamp = "2026-03-05T00:00:00Z"
    return request


def _make_user(user_id=1):
    """current_user mock 생성."""
    user = MagicMock()
    user.id = user_id
    return user


class TestSearchUsersController:
    """사용자 검색 컨트롤러 함수 테스트."""

    @pytest.mark.asyncio
    @patch("controllers.user_controller.block_models.get_blocked_user_ids", new_callable=AsyncMock)
    @patch("controllers.user_controller.user_models.search_users_by_nickname", new_callable=AsyncMock)
    async def test_search_returns_results(self, mock_search, mock_blocked):
        """검색 결과가 올바르게 반환된다."""
        mock_blocked.return_value = set()
        mock_search.return_value = [
            {"user_id": 2, "nickname": "alice", "profileImageUrl": "/img.jpg"},
        ]

        result = await search_users(
            q="ali", limit=10, current_user=_make_user(), request=_make_request()
        )

        assert len(result["data"]) == 1
        assert result["data"][0]["nickname"] == "alice"
        mock_search.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_empty_query_returns_empty(self):
        """빈 쿼리는 빈 data 리스트를 반환한다."""
        result = await search_users(
            q="", limit=10, current_user=_make_user(), request=_make_request()
        )
        assert result["data"] == []

    @pytest.mark.asyncio
    @patch("controllers.user_controller.block_models.get_blocked_user_ids", new_callable=AsyncMock)
    @patch("controllers.user_controller.user_models.search_users_by_nickname", new_callable=AsyncMock)
    async def test_search_limit_capped_at_20(self, mock_search, mock_blocked):
        """limit=50이 20으로 제한된다."""
        mock_blocked.return_value = set()
        mock_search.return_value = []

        await search_users(
            q="test", limit=50, current_user=_make_user(), request=_make_request()
        )

        # search_users_by_nickname에 전달된 limit이 20인지 확인
        call_kwargs = mock_search.call_args
        assert call_kwargs[1]["limit"] == 20


class TestGetUserProfileStats:
    """공개 프로필 응답에 활동 통계가 포함되는지 테스트."""

    @pytest.mark.asyncio
    @patch("controllers.user_controller.user_models.get_user_stats", new_callable=AsyncMock)
    @patch("controllers.user_controller.UserService.get_user_by_id", new_callable=AsyncMock)
    async def test_public_profile_includes_stats(self, mock_get_user, mock_stats):
        """비인증 공개 프로필 응답에 활동 통계가 포함된다."""
        user = MagicMock()
        user.id = 2
        user.nickname = "대상유저"
        user.profileImageUrl = "/img/default.jpg"

        mock_get_user.return_value = user
        mock_stats.return_value = {
            "posts_count": 10,
            "comments_count": 20,
            "likes_received_count": 30,
        }

        result = await get_user(user_id=2, request=_make_request())

        assert result["data"]["user"]["posts_count"] == 10
        assert result["data"]["user"]["comments_count"] == 20
        assert result["data"]["user"]["likes_received_count"] == 30
