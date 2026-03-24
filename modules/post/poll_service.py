"""poll_service: 투표 관련 비즈니스 로직을 처리하는 서비스."""

from pymysql.err import IntegrityError

from core.utils.error_codes import ErrorCode
from core.utils.exceptions import (
    bad_request_error,
    conflict_error,
    not_found_error,
)
from modules.post import poll_models


class PollService:
    """투표 관리 서비스."""

    @staticmethod
    async def vote_on_poll(
        post_id: int,
        option_id: int,
        user_id: int,
        timestamp: str,
    ) -> None:
        """게시글의 투표에 참여합니다.

        Args:
            post_id: 게시글 ID.
            option_id: 선택한 옵션 ID.
            user_id: 투표하는 사용자 ID.
            timestamp: 요청 타임스탬프.

        Raises:
            HTTPException: 투표 없음(404), 만료(400), 옵션 불일치(400), 이미 투표(409).
        """
        poll_id = await poll_models.get_poll_id_by_post_id(post_id)
        if not poll_id:
            raise not_found_error(ErrorCode.POLL_NOT_FOUND, timestamp)

        # 만료 확인
        poll_data = await poll_models.get_poll_by_post_id(post_id)
        if poll_data and poll_data["is_expired"]:
            raise bad_request_error(
                ErrorCode.POLL_EXPIRED,
                timestamp,
                "만료된 투표입니다.",
            )

        # 옵션 소속 검증 (cross-poll vote injection 방지)
        if not await poll_models.option_belongs_to_poll(option_id, poll_id):
            raise bad_request_error(
                ErrorCode.INVALID_OPTION,
                timestamp,
                "해당 투표에 속하지 않는 옵션입니다.",
            )

        # IntegrityError는 transactional() 밖에서 처리
        try:
            await poll_models.vote(poll_id, option_id, user_id)
        except IntegrityError:
            raise conflict_error(ErrorCode.ALREADY_VOTED, timestamp, "이미 투표한 투표입니다.") from None

    @staticmethod
    async def cancel_vote(
        post_id: int,
        user_id: int,
        timestamp: str,
    ) -> None:
        """투표를 취소합니다.

        Raises:
            HTTPException: 투표 없음(404), 만료(400), 투표 기록 없음(404).
        """
        poll_id = await poll_models.get_poll_id_by_post_id(post_id)
        if not poll_id:
            raise not_found_error(ErrorCode.POLL_NOT_FOUND, timestamp)

        poll_data = await poll_models.get_poll_by_post_id(post_id)
        if poll_data and poll_data["is_expired"]:
            raise bad_request_error(
                ErrorCode.POLL_EXPIRED,
                timestamp,
                "만료된 투표는 취소할 수 없습니다.",
            )

        deleted = await poll_models.delete_vote(poll_id, user_id)
        if not deleted:
            raise not_found_error(ErrorCode.VOTE_NOT_FOUND, timestamp)

    @staticmethod
    async def change_vote(
        post_id: int,
        option_id: int,
        user_id: int,
        timestamp: str,
    ) -> None:
        """투표를 변경합니다.

        Raises:
            HTTPException: 투표 없음(404), 만료(400), 옵션 불일치(400), 투표 기록 없음(404).
        """
        poll_id = await poll_models.get_poll_id_by_post_id(post_id)
        if not poll_id:
            raise not_found_error(ErrorCode.POLL_NOT_FOUND, timestamp)

        poll_data = await poll_models.get_poll_by_post_id(post_id)
        if poll_data and poll_data["is_expired"]:
            raise bad_request_error(
                ErrorCode.POLL_EXPIRED,
                timestamp,
                "만료된 투표는 변경할 수 없습니다.",
            )

        if not await poll_models.option_belongs_to_poll(option_id, poll_id):
            raise bad_request_error(
                ErrorCode.INVALID_OPTION,
                timestamp,
                "해당 투표에 속하지 않는 옵션입니다.",
            )

        changed = await poll_models.change_vote(poll_id, option_id, user_id)
        if not changed:
            raise not_found_error(ErrorCode.VOTE_NOT_FOUND, timestamp)
