"""user_service: 사용자 관련 비즈니스 로직을 처리하는 서비스."""

import logging
from typing import Optional
from models import user_models
from models.user_models import User
from schemas.user_schemas import CreateUserRequest
from utils.password import hash_password, verify_password
from utils.exceptions import (
    not_found_error,
    bad_request_error,
    conflict_error,
)

logger = logging.getLogger(__name__)


class UserService:
    """사용자 관리 서비스."""

    @staticmethod
    async def get_user_by_id(user_id: int, timestamp: str) -> User:
        """ID로 사용자 조회 및 존재 확인."""
        user = await user_models.get_user_by_id(user_id)
        if not user:
            raise not_found_error("user", timestamp)
        return user

    @staticmethod
    async def create_user(
        user_data: CreateUserRequest, profile_image_url: Optional[str], timestamp: str
    ) -> User:
        """사용자 생성 (회원가입)."""
        # 1. 이메일 중복 확인
        if await user_models.get_user_by_email(user_data.email):
            raise conflict_error("email_already_exists", timestamp)

        # 2. 닉네임 중복 확인
        if await user_models.get_user_by_nickname(user_data.nickname):
            raise conflict_error("nickname_already_exists", timestamp)

        # 3. 비밀번호 해싱
        hashed_password = hash_password(user_data.password)

        try:
            # 4. 사용자 생성 시도 (좀비 사용자 처리 로직 포함)
            # models.register_user는 내부적으로 좀비 사용자 정리 로직을 포함하고 있음
            # Service Layer 도입 시점에서는 모델의 로직을 그대로 활용하되,
            # 향후 순수 모델로 분리할 때 이 로직을 서비스로 가져오는 것이 좋음.
            # 현재는 리팩토링 단계이므로 모델의 register_user를 호출.
            return await user_models.register_user(
                email=user_data.email,
                password=hashed_password,
                nickname=user_data.nickname,
                profile_image_url=profile_image_url,
            )
        except Exception as e:
            # pymysql.err.IntegrityError 등은 register_user 내부에서 처리되거나 전파됨
            # 여기서는 예외 로깅 후 re-raise
            logger.exception(f"Error creating user: {e}")
            raise e

    @staticmethod
    async def update_user(
        user_id: int,
        nickname: Optional[str],
        profile_image_url: Optional[str],
        current_user: User,
        timestamp: str,
    ) -> User:
        """사용자 정보 수정."""
        # 1. 변경 사항 없음 확인
        if nickname is None and profile_image_url is None:
            raise bad_request_error("no_changes_provided", timestamp)

        # 2. 닉네임 중복 확인
        if nickname is not None:
            existing_user = await user_models.get_user_by_nickname(nickname)
            if existing_user and existing_user.id != user_id:
                raise conflict_error("nickname_already_exists", timestamp)

        # 3. 정보 수정
        updated_user = await user_models.update_user(
            user_id, nickname=nickname, profile_image_url=profile_image_url
        )

        # update_user는 변경사항이 없으면 None을 반환할 수 있음 (실제 DB 업데이트 0건)
        # 하지만 위에서 변경사항 체크를 했으므로 이론적으로는 진행됨.
        # DB 레벨에서 값이 같아서 0건인 경우는 기존 user 반환
        if not updated_user:
            return await UserService.get_user_by_id(user_id, timestamp)

        return updated_user

    @staticmethod
    async def change_password(
        user_id: int,
        new_password: str,
        new_password_confirm: str,
        stored_password_hash: str,
        timestamp: str,
    ) -> None:
        """비밀번호 변경."""
        # 1. 새 비밀번호 확인
        if new_password != new_password_confirm:
            raise bad_request_error("password_mismatch", timestamp)

        # 2. 새 비밀번호가 현재 비밀번호와 같은지 확인 (재사용 방지)
        if verify_password(new_password, stored_password_hash):
            raise bad_request_error("same_password", timestamp)

        # 3. 해싱 및 업데이트
        hashed_new_password = hash_password(new_password)
        await user_models.update_password(user_id, hashed_new_password)

    @staticmethod
    async def withdraw_user(
        user_id: int,
        password: str,
        current_user: User,
        timestamp: str,
    ) -> None:
        """회원 탈퇴."""
        # 1. 활성 상태 확인
        if not current_user.is_active:
            raise bad_request_error("inactive_user", timestamp)

        # 2. 비밀번호 확인
        if not verify_password(password, current_user.password):
            raise bad_request_error("invalid_password", timestamp)

        # 3. 탈퇴 처리 (익명화 등은 모델의 withdraw_user 위임)
        # models.withdraw_user는 트랜잭션 내에서 연결 끊기, 세션 삭제, 익명화를 수행함
        await user_models.withdraw_user(user_id)
