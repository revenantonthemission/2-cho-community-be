"""follow_service: 팔로우 관련 비즈니스 로직을 처리하는 서비스."""

from pymysql.err import IntegrityError

from core.utils.error_codes import ErrorCode
from core.utils.exceptions import (
    bad_request_error,
    conflict_error,
    not_found_error,
    safe_notify,
)
from core.utils.formatters import format_datetime
from modules.user import follow_models
from modules.user.models import get_user_by_id


class FollowService:
    """사용자 팔로우 관리 서비스."""

    @staticmethod
    async def follow(
        user_id: int,
        target_id: int,
        actor_nickname: str,
        timestamp: str,
    ) -> None:
        """사용자를 팔로우합니다.

        Args:
            user_id: 팔로우하는 사용자 ID.
            target_id: 팔로우 대상 사용자 ID.
            actor_nickname: 알림에 표시할 사용자 닉네임.
            timestamp: 요청 타임스탬프.

        Raises:
            HTTPException: 자기 팔로우(400), 대상 없음(404), 이미 팔로우(409).
        """
        if target_id == user_id:
            raise bad_request_error(
                ErrorCode.CANNOT_FOLLOW_SELF,
                timestamp,
                "자기 자신을 팔로우할 수 없습니다.",
            )

        target = await get_user_by_id(target_id)
        if not target:
            raise not_found_error("user", timestamp)

        # IntegrityError는 transactional() 밖에서 처리
        try:
            await follow_models.add_follow(user_id, target_id)
        except IntegrityError:
            raise conflict_error(ErrorCode.ALREADY_FOLLOWING, timestamp, "이미 팔로우한 사용자입니다.") from None

        # 팔로우 알림 (자기 자신 제외는 정의상 보장됨)
        await safe_notify(
            user_id=target_id,
            notification_type="follow",
            actor_id=user_id,
            actor_nickname=actor_nickname,
        )

    @staticmethod
    async def unfollow(
        user_id: int,
        target_id: int,
        timestamp: str,
    ) -> None:
        """팔로우를 해제합니다.

        Args:
            user_id: 팔로우 해제하는 사용자 ID.
            target_id: 팔로우 해제 대상 사용자 ID.
            timestamp: 요청 타임스탬프.

        Raises:
            HTTPException: 팔로우하지 않은 경우 404.
        """
        removed = await follow_models.remove_follow(user_id, target_id)
        if not removed:
            raise not_found_error("follow", timestamp)

    @staticmethod
    async def get_following(
        user_id: int,
        offset: int = 0,
        limit: int = 10,
    ) -> dict:
        """팔로잉 목록을 조회합니다.

        Args:
            user_id: 조회할 사용자 ID.
            offset: 페이지네이션 오프셋.
            limit: 페이지네이션 제한.

        Returns:
            팔로잉 목록과 페이지네이션 정보.
        """
        following, total_count = await follow_models.get_my_following(user_id, offset, limit)
        has_more = offset + limit < total_count

        for item in following:
            item["created_at"] = format_datetime(item["created_at"])

        return {
            "following": following,
            "pagination": {"total_count": total_count, "has_more": has_more},
        }

    @staticmethod
    async def get_followers(
        user_id: int,
        offset: int = 0,
        limit: int = 10,
    ) -> dict:
        """팔로워 목록을 조회합니다.

        Args:
            user_id: 조회할 사용자 ID.
            offset: 페이지네이션 오프셋.
            limit: 페이지네이션 제한.

        Returns:
            팔로워 목록과 페이지네이션 정보.
        """
        followers, total_count = await follow_models.get_my_followers(user_id, offset, limit)
        has_more = offset + limit < total_count

        for item in followers:
            item["created_at"] = format_datetime(item["created_at"])

        return {
            "followers": followers,
            "pagination": {"total_count": total_count, "has_more": has_more},
        }
