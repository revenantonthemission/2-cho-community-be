"""test_mention: 멘션 파싱 유틸리티 및 알림 통합 테스트."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from controllers.comment_controller import create_comment
from schemas.comment_schemas import CreateCommentRequest
from utils.mention import extract_mentions


class TestExtractMentions:
    """extract_mentions() 함수 테스트."""

    def test_single_mention(self):
        assert extract_mentions("안녕 @홍길동 반가워") == ["홍길동"]

    def test_multiple_mentions(self):
        result = extract_mentions("@유저A 그리고 @유저B 안녕")
        assert result == ["유저A", "유저B"]

    def test_duplicate_mentions_deduplicated(self):
        result = extract_mentions("@홍길동 님 @홍길동 님")
        assert result == ["홍길동"]

    def test_no_mentions(self):
        assert extract_mentions("멘션 없는 텍스트") == []

    def test_empty_string(self):
        assert extract_mentions("") == []

    def test_mention_at_start(self):
        assert extract_mentions("@유저 안녕하세요") == ["유저"]

    def test_mention_at_end(self):
        assert extract_mentions("안녕하세요 @유저") == ["유저"]


class TestMentionNotification:
    """댓글 생성 시 멘션 알림 통합 테스트."""

    def _make_request(self):
        """테스트용 Request mock 생성."""
        request = MagicMock()
        request.state = MagicMock()
        request.state.request_timestamp = "2026-03-05T00:00:00Z"
        return request

    def _make_user(self, user_id=1, nickname="작성자"):
        """테스트용 User mock 생성."""
        user = MagicMock()
        user.id = user_id
        user.nickname = nickname
        return user

    @pytest.mark.asyncio
    async def test_mention_creates_notification(self):
        """@멘션된 사용자에게 알림이 생성된다."""
        mentioned_user = self._make_user(user_id=99, nickname="타겟유저")
        post = MagicMock()
        post.author_id = 2
        comment = MagicMock()
        comment.id = 10
        comment.content = "@타겟유저 안녕"
        comment.parent_id = None
        comment.created_at = "2026-03-05T00:00:00Z"

        with patch("services.comment_service.post_models.get_post_by_id", new_callable=AsyncMock, return_value=post), \
             patch("services.comment_service.comment_models.create_comment", new_callable=AsyncMock, return_value=comment), \
             patch("models.notification_models.create_notification", new_callable=AsyncMock) as mock_notify, \
             patch("services.comment_service.get_user_by_nickname", new_callable=AsyncMock, return_value=mentioned_user):

            request = self._make_request()
            current_user = self._make_user(user_id=1)
            data = CreateCommentRequest(content="@타겟유저 안녕")

            await create_comment(post_id=1, comment_data=data, current_user=current_user, request=request)

            # comment 알림 (게시글 작성자) + mention 알림 (멘션된 사용자)
            assert mock_notify.call_count == 2
            mention_call = mock_notify.call_args_list[1]
            assert mention_call.kwargs["notification_type"] == "mention"

    @pytest.mark.asyncio
    async def test_mention_self_excluded(self):
        """자기 자신을 멘션하면 알림이 생성되지 않는다."""
        post = MagicMock()
        post.author_id = 2
        comment = MagicMock()
        comment.id = 10
        comment.content = "@나자신 안녕"
        comment.parent_id = None
        comment.created_at = "2026-03-05T00:00:00Z"

        self_user = self._make_user(user_id=1, nickname="나자신")

        with patch("services.comment_service.post_models.get_post_by_id", new_callable=AsyncMock, return_value=post), \
             patch("services.comment_service.comment_models.create_comment", new_callable=AsyncMock, return_value=comment), \
             patch("models.notification_models.create_notification", new_callable=AsyncMock) as mock_notify, \
             patch("services.comment_service.get_user_by_nickname", new_callable=AsyncMock, return_value=self_user):

            request = self._make_request()
            data = CreateCommentRequest(content="@나자신 안녕")

            await create_comment(post_id=1, comment_data=data, current_user=self_user, request=request)

            # comment 알림만 (게시글 작성자에게), 멘션 알림 없음 (자기 자신)
            assert mock_notify.call_count == 1

    @pytest.mark.asyncio
    async def test_mention_post_author_not_duplicated(self):
        """게시글 작성자를 멘션하면 comment 알림만 가고 mention 알림은 중복 생성되지 않는다."""
        post_author = self._make_user(user_id=2, nickname="게시글작성자")
        post = MagicMock()
        post.author_id = 2
        comment = MagicMock()
        comment.id = 10
        comment.content = "@게시글작성자 확인해주세요"
        comment.parent_id = None
        comment.created_at = "2026-03-05T00:00:00Z"

        with patch("services.comment_service.post_models.get_post_by_id", new_callable=AsyncMock, return_value=post), \
             patch("services.comment_service.comment_models.create_comment", new_callable=AsyncMock, return_value=comment), \
             patch("models.notification_models.create_notification", new_callable=AsyncMock) as mock_notify, \
             patch("services.comment_service.get_user_by_nickname", new_callable=AsyncMock, return_value=post_author):

            request = self._make_request()
            current_user = self._make_user(user_id=1)
            data = CreateCommentRequest(content="@게시글작성자 확인해주세요")

            await create_comment(post_id=1, comment_data=data, current_user=current_user, request=request)

            # comment 알림 1회만 (이미 알림 받으므로 mention 중복 없음)
            assert mock_notify.call_count == 1

    @pytest.mark.asyncio
    async def test_mention_nonexistent_user_ignored(self):
        """존재하지 않는 닉네임 멘션은 무시된다."""
        post = MagicMock()
        post.author_id = 2
        comment = MagicMock()
        comment.id = 10
        comment.content = "@없는유저 안녕"
        comment.parent_id = None
        comment.created_at = "2026-03-05T00:00:00Z"

        with patch("services.comment_service.post_models.get_post_by_id", new_callable=AsyncMock, return_value=post), \
             patch("services.comment_service.comment_models.create_comment", new_callable=AsyncMock, return_value=comment), \
             patch("models.notification_models.create_notification", new_callable=AsyncMock) as mock_notify, \
             patch("services.comment_service.get_user_by_nickname", new_callable=AsyncMock, return_value=None):

            request = self._make_request()
            current_user = self._make_user(user_id=1)
            data = CreateCommentRequest(content="@없는유저 안녕")

            await create_comment(post_id=1, comment_data=data, current_user=current_user, request=request)

            # comment 알림만 (멘션 알림 없음 — 유저 미존재)
            assert mock_notify.call_count == 1
