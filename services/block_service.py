"""block_service: 사용자 차단 관련 비즈니스 로직을 처리하는 서비스."""

from pymysql.err import IntegrityError

from models import block_models
from models.user_models import get_user_by_id
from utils.error_codes import ErrorCode
from utils.exceptions import bad_request_error, conflict_error, not_found_error
from utils.formatters import format_datetime


class BlockService:
    """사용자 차단 관리 서비스."""

    @staticmethod
    async def block_user(
        user_id: int,
        target_id: int,
        timestamp: str,
    ) -> None:
        """사용자를 차단합니다.

        Args:
            user_id: 차단하는 사용자 ID.
            target_id: 차단 대상 사용자 ID.
            timestamp: 요청 타임스탬프.

        Raises:
            HTTPException: 자기 차단(400), 대상 없음(404), 이미 차단(409).
        """
        if target_id == user_id:
            raise bad_request_error(
                ErrorCode.CANNOT_BLOCK_SELF,
                timestamp,
                "자기 자신을 차단할 수 없습니다.",
            )

        target = await get_user_by_id(target_id)
        if not target:
            raise not_found_error("user", timestamp)

        # IntegrityError는 transactional() 밖에서 처리
        try:
            await block_models.add_block(user_id, target_id)
        except IntegrityError:
            raise conflict_error(ErrorCode.ALREADY_BLOCKED, timestamp, "이미 차단한 사용자입니다.")

    @staticmethod
    async def unblock_user(
        user_id: int,
        target_id: int,
        timestamp: str,
    ) -> None:
        """사용자 차단을 해제합니다.

        Args:
            user_id: 차단 해제하는 사용자 ID.
            target_id: 차단 해제 대상 사용자 ID.
            timestamp: 요청 타임스탬프.

        Raises:
            HTTPException: 차단하지 않은 경우 404.
        """
        removed = await block_models.remove_block(user_id, target_id)
        if not removed:
            raise not_found_error("block", timestamp)

    @staticmethod
    async def get_blocked_users(
        user_id: int,
        offset: int = 0,
        limit: int = 10,
    ) -> dict:
        """차단 목록을 조회합니다.

        Args:
            user_id: 조회할 사용자 ID.
            offset: 페이지네이션 오프셋.
            limit: 페이지네이션 제한.

        Returns:
            차단 목록과 페이지네이션 정보.
        """
        blocks, total_count = await block_models.get_my_blocks(
            user_id, offset, limit
        )
        has_more = offset + limit < total_count

        for block in blocks:
            block["created_at"] = format_datetime(block["created_at"])

        return {
            "blocks": blocks,
            "pagination": {"total_count": total_count, "has_more": has_more},
        }
