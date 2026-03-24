"""bookmark_service: 북마크 관련 비즈니스 로직을 처리하는 서비스."""

from pymysql.err import IntegrityError

from core.utils.error_codes import ErrorCode
from core.utils.exceptions import conflict_error, not_found_error, safe_notify
from modules.post import bookmark_models, post_models


class BookmarkService:
    """게시글 북마크 관리 서비스."""

    @staticmethod
    async def add_bookmark(
        post_id: int,
        user_id: int,
        actor_nickname: str,
        timestamp: str,
    ) -> dict:
        """게시글 북마크 추가.

        Args:
            post_id: 북마크할 게시글 ID.
            user_id: 북마크하는 사용자 ID.
            actor_nickname: 알림에 표시할 사용자 닉네임.
            timestamp: 요청 타임스탬프.

        Returns:
            북마크 개수가 포함된 결과 딕셔너리.

        Raises:
            HTTPException: 게시글 없으면 404, 이미 북마크했으면 409.
        """
        post = await post_models.get_post_by_id(post_id)
        if not post:
            raise not_found_error("post", timestamp)

        # IntegrityError는 transactional() 밖에서 처리
        try:
            await bookmark_models.add_bookmark(post_id, user_id)
        except IntegrityError:
            raise conflict_error(ErrorCode.ALREADY_BOOKMARKED, timestamp, "이미 북마크한 게시글입니다.") from None

        bookmarks_count = await bookmark_models.get_post_bookmarks_count(post_id)

        # 자기 글이 아닌 경우 알림 생성
        if post.author_id and post.author_id != user_id:
            await safe_notify(
                user_id=post.author_id,
                notification_type="bookmark",
                actor_id=user_id,
                actor_nickname=actor_nickname,
                post_id=post_id,
            )

        return {"bookmarks_count": bookmarks_count}

    @staticmethod
    async def remove_bookmark(
        post_id: int,
        user_id: int,
        timestamp: str,
    ) -> dict:
        """게시글 북마크 취소.

        Args:
            post_id: 북마크 취소할 게시글 ID.
            user_id: 북마크 취소하는 사용자 ID.
            timestamp: 요청 타임스탬프.

        Returns:
            북마크 개수가 포함된 결과 딕셔너리.

        Raises:
            HTTPException: 게시글 없으면 404, 북마크 기록 없으면 404.
        """
        post = await post_models.get_post_by_id(post_id)
        if not post:
            raise not_found_error("post", timestamp)

        removed = await bookmark_models.remove_bookmark(post_id, user_id)
        if not removed:
            raise not_found_error("bookmark", timestamp)

        bookmarks_count = await bookmark_models.get_post_bookmarks_count(post_id)

        return {"bookmarks_count": bookmarks_count}
