"""suspension_service: 계정 정지 관련 비즈니스 로직을 처리하는 서비스."""

from fastapi import HTTPException, status

from models import suspension_models, user_models
from utils.error_codes import ErrorCode
from utils.exceptions import bad_request_error, not_found_error
from utils.formatters import format_datetime


class SuspensionService:
    """계정 정지 관리 서비스."""

    @staticmethod
    async def suspend_user(
        user_id: int,
        duration_days: int,
        reason: str,
        admin_user_id: int,
        timestamp: str,
    ) -> dict:
        """사용자를 정지합니다.

        Args:
            user_id: 정지 대상 사용자 ID.
            duration_days: 정지 기간 (일).
            reason: 정지 사유.
            admin_user_id: 관리자 사용자 ID.
            timestamp: 요청 타임스탬프.

        Returns:
            정지된 사용자 정보.

        Raises:
            HTTPException: 자기 정지(400), 관리자 정지(400), 대상 없음(404).
        """
        # 자기 자신 정지 방지
        if user_id == admin_user_id:
            raise bad_request_error(
                ErrorCode.CANNOT_SUSPEND_SELF,
                timestamp,
                "자기 자신을 정지할 수 없습니다.",
            )

        target_user = await user_models.get_user_by_id(user_id)
        if not target_user:
            raise not_found_error("user", timestamp)

        # 다른 관리자 정지 방지
        if target_user.is_admin:
            raise bad_request_error(
                ErrorCode.CANNOT_SUSPEND_ADMIN,
                timestamp,
                "관리자를 정지할 수 없습니다.",
            )

        # 이미 정지된 사용자 — 기존 정지 정보와 함께 409 반환
        if target_user.is_suspended:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "already_suspended",
                    "message": f"이미 정지된 사용자입니다. (만료: {target_user.suspended_until})",
                    "timestamp": timestamp,
                },
            )

        success = await suspension_models.suspend_user(
            user_id=user_id,
            duration_days=duration_days,
            reason=reason,
        )

        if not success:
            raise not_found_error("user", timestamp)

        # 정지 후 사용자 정보 재조회
        updated_user = await user_models.get_user_by_id(user_id)

        return {
            "user_id": user_id,
            "suspended_until": format_datetime(updated_user.suspended_until) if updated_user else None,
            "suspended_reason": reason,
            "duration_days": duration_days,
        }

    @staticmethod
    async def unsuspend_user(
        user_id: int,
        timestamp: str,
    ) -> None:
        """사용자 정지를 해제합니다.

        Args:
            user_id: 정지 해제할 사용자 ID.
            timestamp: 요청 타임스탬프.

        Raises:
            HTTPException: 대상 없음(404), 정지 상태 아님(400).
        """
        target_user = await user_models.get_user_by_id(user_id)
        if not target_user:
            raise not_found_error("user", timestamp)

        # 정지 상태가 아닌 사용자는 해제 불필요
        if not target_user.is_suspended:
            raise bad_request_error(
                ErrorCode.USER_NOT_SUSPENDED,
                timestamp,
                "정지 상태가 아닌 사용자입니다.",
            )

        success = await suspension_models.unsuspend_user(user_id)

        if not success:
            raise not_found_error("user", timestamp)
