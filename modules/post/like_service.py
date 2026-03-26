"""like_service: 좋아요 관련 비즈니스 로직을 처리하는 서비스."""

import logging

from pymysql.err import IntegrityError

from core.utils.error_codes import ErrorCode
from core.utils.exceptions import conflict_error, not_found_error, safe_notify
from modules.post import like_models, post_models

logger = logging.getLogger(__name__)


class LikeService:
    """게시글 좋아요 관리 서비스."""

    @staticmethod
    async def like_post(
        post_id: int,
        user_id: int,
        actor_nickname: str,
        timestamp: str,
    ) -> dict:
        """게시글 좋아요 추가.

        Args:
            post_id: 좋아요할 게시글 ID.
            user_id: 좋아요하는 사용자 ID.
            actor_nickname: 알림에 표시할 사용자 닉네임.
            timestamp: 요청 타임스탬프.

        Returns:
            좋아요 개수가 포함된 결과 딕셔너리.

        Raises:
            HTTPException: 게시글 없으면 404, 이미 좋아요했으면 409.
        """
        post = await post_models.get_post_by_id(post_id)
        if not post:
            raise not_found_error("post", timestamp)

        # IntegrityError는 transactional() 밖에서 처리
        try:
            await like_models.add_like(post_id, user_id)
        except IntegrityError:
            raise conflict_error(ErrorCode.ALREADY_LIKED, timestamp, "이미 좋아요를 누른 게시글입니다.") from None

        likes_count = await like_models.get_post_likes_count(post_id)

        # 자기 글이 아닌 경우 알림 생성
        if post.author_id and post.author_id != user_id:
            await safe_notify(
                user_id=post.author_id,
                notification_type="like",
                actor_id=user_id,
                actor_nickname=actor_nickname,
                post_id=post_id,
            )

        # 평판 포인트 부여 (best-effort)
        try:
            from modules.reputation.service import ReputationService

            await ReputationService.award_points(
                user_id=post.author_id,
                event_type="post_liked",
                points=10,
                source_user_id=user_id,
                source_type="post",
                source_id=post_id,
            )
            await ReputationService.award_points(
                user_id=user_id,
                event_type="post_like_given",
                points=1,
                source_type="post",
                source_id=post_id,
            )
        except Exception:
            logger.warning("평판 포인트 부여 실패 (like_post)", exc_info=True)

        return {"likes_count": likes_count}

    @staticmethod
    async def unlike_post(
        post_id: int,
        user_id: int,
        timestamp: str,
    ) -> dict:
        """게시글 좋아요 취소.

        Args:
            post_id: 좋아요 취소할 게시글 ID.
            user_id: 좋아요 취소하는 사용자 ID.
            timestamp: 요청 타임스탬프.

        Returns:
            좋아요 개수가 포함된 결과 딕셔너리.

        Raises:
            HTTPException: 게시글 없으면 404, 좋아요 기록 없으면 404.
        """
        post = await post_models.get_post_by_id(post_id)
        if not post:
            raise not_found_error("post", timestamp)

        removed = await like_models.remove_like(post_id, user_id)
        if not removed:
            raise not_found_error("like", timestamp)

        likes_count = await like_models.get_post_likes_count(post_id)

        # 평판 포인트 회수 (best-effort)
        try:
            from modules.reputation.service import ReputationService

            await ReputationService.revoke_points(
                user_id=post.author_id,
                event_type="post_liked",
                source_type="post",
                source_id=post_id,
            )
            await ReputationService.revoke_points(
                user_id=user_id,
                event_type="post_like_given",
                source_type="post",
                source_id=post_id,
            )
        except Exception:
            logger.warning("평판 포인트 회수 실패 (unlike_post)", exc_info=True)

        return {"likes_count": likes_count}
