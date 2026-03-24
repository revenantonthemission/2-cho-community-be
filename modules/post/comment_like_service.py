"""comment_like_service: 댓글 좋아요 관련 비즈니스 로직을 처리하는 서비스."""

from pymysql.err import IntegrityError

from core.utils.error_codes import ErrorCode
from core.utils.exceptions import conflict_error, not_found_error, safe_notify
from modules.post import comment_like_models, post_models
from modules.post.comment_models import get_comment_by_id


class CommentLikeService:
    """댓글 좋아요 관리 서비스."""

    @staticmethod
    async def like_comment(
        post_id: int,
        comment_id: int,
        user_id: int,
        actor_nickname: str,
        timestamp: str,
    ) -> dict:
        """댓글 좋아요 추가.

        Args:
            post_id: 댓글이 속한 게시글 ID.
            comment_id: 좋아요할 댓글 ID.
            user_id: 좋아요하는 사용자 ID.
            actor_nickname: 알림에 표시할 사용자 닉네임.
            timestamp: 요청 타임스탬프.

        Returns:
            좋아요 개수가 포함된 결과 딕셔너리.

        Raises:
            HTTPException: 게시글/댓글 없으면 404, 이미 좋아요했으면 409.
        """
        post = await post_models.get_post_by_id(post_id)
        if not post:
            raise not_found_error("post", timestamp)

        # 댓글 존재 + 해당 게시글 소속 확인
        comment = await get_comment_by_id(comment_id)
        if not comment or comment.post_id != post_id:
            raise not_found_error("comment", timestamp)

        # IntegrityError는 transactional() 밖에서 처리
        try:
            await comment_like_models.add_comment_like(comment_id, user_id)
        except IntegrityError:
            raise conflict_error(ErrorCode.ALREADY_COMMENT_LIKED, timestamp, "이미 좋아요를 누른 댓글입니다.") from None

        likes_count = await comment_like_models.get_comment_likes_count(comment_id)

        # 자기 댓글이 아닌 경우 알림 생성
        if comment.author_id and comment.author_id != user_id:
            await safe_notify(
                user_id=comment.author_id,
                notification_type="like",
                actor_id=user_id,
                actor_nickname=actor_nickname,
                post_id=post_id,
                comment_id=comment_id,
            )

        return {"likes_count": likes_count}

    @staticmethod
    async def unlike_comment(
        post_id: int,
        comment_id: int,
        user_id: int,
        timestamp: str,
    ) -> dict:
        """댓글 좋아요 취소.

        Args:
            post_id: 댓글이 속한 게시글 ID.
            comment_id: 좋아요 취소할 댓글 ID.
            user_id: 좋아요 취소하는 사용자 ID.
            timestamp: 요청 타임스탬프.

        Returns:
            좋아요 개수가 포함된 결과 딕셔너리.

        Raises:
            HTTPException: 게시글/댓글 없으면 404, 좋아요 기록 없으면 404.
        """
        post = await post_models.get_post_by_id(post_id)
        if not post:
            raise not_found_error("post", timestamp)

        comment = await get_comment_by_id(comment_id)
        if not comment or comment.post_id != post_id:
            raise not_found_error("comment", timestamp)

        removed = await comment_like_models.remove_comment_like(comment_id, user_id)
        if not removed:
            raise not_found_error("comment_like", timestamp)

        likes_count = await comment_like_models.get_comment_likes_count(comment_id)

        return {"likes_count": likes_count}
