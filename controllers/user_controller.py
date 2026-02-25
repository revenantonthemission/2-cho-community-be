"""user_controller: 사용자 관련 컨트롤러 모듈.

사용자 등록, 조회, 수정, 비밀번호 변경, 탈퇴 등의 기능을 제공합니다.
"""

from fastapi import HTTPException, Request, status, UploadFile
from models.user_models import User
from schemas.user_schemas import (
    CreateUserRequest,
    UpdateUserRequest,
    ChangePasswordRequest,
    WithdrawRequest,
)
from schemas.common import create_response, serialize_user
from dependencies.request_context import get_request_timestamp
from utils.storage import save_uploaded_file
from core.config import settings
from services.user_service import UserService

# 프로필 이미지 저장 경로 (설정에서 로드)
PROFILE_IMAGE_UPLOAD_DIR = settings.PROFILE_IMAGE_UPLOAD_DIR


async def get_user(user_id: int, request: Request) -> dict:
    """사용자 ID를 사용하여 사용자를 조회합니다.

    참고: get_user는 인증 없이 접근 가능한 공개 프로필 조회(혹은 존재 확인) 용도로 추정되나,
    실제 요구사항에 따라 UserService를 통해 조회합니다.
    """
    timestamp = get_request_timestamp(request)

    if not user_id or user_id < 1:
        # Service에서 처리할 수도 있으나, controller 레벨의 기본 유효성 검사로 남겨둠
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_user_id",
                "timestamp": timestamp,
            },
        )

    # Service Layer 호출
    # Service는 실패 시 예외를 발생시킴
    user = await UserService.get_user_by_id(user_id, timestamp)

    # 여기서 Exception Handler가 포착하지 못하는 예외는 Service 내부에서 발생하므로
    # 별도 try-except 없이 처리 가능 (Global Handler 위임).
    # 단, get_user는 Service에서 user_models.get_user_by_id 호출 후 None이면 not_found_error raise함.

    return create_response(
        "AUTH_SUCCESS",
        "사용자 조회에 성공했습니다.",
        data={"user": serialize_user(user)},
        timestamp=timestamp,
    )


async def create_user(
    user_data: CreateUserRequest, profile_image: UploadFile | None, request: Request
) -> dict:
    """새로운 사용자를 생성합니다."""
    timestamp = get_request_timestamp(request)

    # 프로필 이미지 업로드 처리
    # 이미지 업로드는 Controller에서 처리하고 URL만 Service로 넘기는 패턴 유지
    # (파일 처리는 웹 프레임워크 종속적이므로 Controller에 두는 것이 일반적)
    profile_image_url = user_data.profileImageUrl
    if profile_image:
        try:
            profile_image_url = await save_uploaded_file(profile_image, folder="profiles")
        except HTTPException as e:
            if isinstance(e.detail, dict):
                e.detail["timestamp"] = timestamp
            raise e
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "image_upload_failed",
                    "message": str(e),
                    "timestamp": timestamp,
                },
            )

    # Service Layer 호출
    await UserService.create_user(user_data, profile_image_url, timestamp)

    return create_response(
        "SIGNUP_SUCCESS", "사용자 생성에 성공했습니다.", timestamp=timestamp
    )


async def get_my_info(current_user: User, request: Request) -> dict:
    """현재 로그인 중인 사용자의 정보를 반환합니다."""
    timestamp = get_request_timestamp(request)

    return create_response(
        "AUTH_SUCCESS",
        "현재 로그인 중인 상태입니다.",
        data={"user": serialize_user(current_user)},
        timestamp=timestamp,
    )


async def get_user_info(user_id: int, current_user: User, request: Request) -> dict:
    """사용자 ID를 사용하여 다른 사용자 정보를 조회합니다."""
    timestamp = get_request_timestamp(request)

    # Service Layer 호출
    user = await UserService.get_user_by_id(user_id, timestamp)

    return create_response(
        "QUERY_SUCCESS",
        "유저 조회에 성공했습니다.",
        data={"user": serialize_user(user)},
        timestamp=timestamp,
    )


async def update_user(
    update_data: UpdateUserRequest, current_user: User, request: Request
) -> dict:
    """현재 로그인 중인 사용자의 정보를 수정합니다."""
    timestamp = get_request_timestamp(request)

    # Service Layer 호출
    # profileImageUrl은 str | None으로 변환됨
    profile_image_url: str | None = update_data.profileImageUrl  # type: ignore[assignment]
    updated_user = await UserService.update_user(
        user_id=current_user.id,
        nickname=update_data.nickname,
        profile_image_url=profile_image_url,
        current_user=current_user,
        timestamp=timestamp,
    )

    # 세션 정보 업데이트 (닉네임 변경 시)
    if update_data.nickname is not None:
        request.session["nickname"] = update_data.nickname

    return create_response(
        "UPDATE_SUCCESS",
        "유저 정보 수정에 성공했습니다.",
        data={"user": serialize_user(updated_user)},
        timestamp=timestamp,
    )


async def change_password(
    password_data: ChangePasswordRequest, current_user: User, request: Request
) -> dict:
    """현재 로그인 중인 사용자의 비밀번호를 변경합니다."""
    timestamp = get_request_timestamp(request)

    # Service Layer 호출
    await UserService.change_password(
        user_id=current_user.id,
        new_password=password_data.new_password,
        new_password_confirm=password_data.new_password_confirm,
        stored_password_hash=current_user.password,
        timestamp=timestamp,
    )

    return create_response(
        "PASSWORD_CHANGE_SUCCESS", "비밀번호 변경에 성공했습니다.", timestamp=timestamp
    )


async def withdraw_user(
    withdraw_data: WithdrawRequest, current_user: User, request: Request
) -> dict:
    """회원 탈퇴를 처리합니다."""
    timestamp = get_request_timestamp(request)

    # Service Layer 호출
    await UserService.withdraw_user(
        user_id=current_user.id,
        password=withdraw_data.password,
        current_user=current_user,
        timestamp=timestamp,
    )

    # 세션 초기화 (로그아웃)
    request.session.clear()

    return create_response(
        "WITHDRAWAL_ACCEPTED", "탈퇴 신청이 접수되었습니다.", timestamp=timestamp
    )


async def upload_profile_image(
    file: UploadFile,
    current_user: User,
    request: Request,
) -> dict:
    """프로필 이미지를 업로드합니다.

    참고: 이 함수는 단순히 이미지 업로드만 수행하고 URL을 반환하는 유틸리티성 엔드포인트입니다.
    """
    timestamp = get_request_timestamp(request)

    try:
        url = await save_uploaded_file(file, folder="profiles")
    except HTTPException as e:
        if isinstance(e.detail, dict):
            e.detail["timestamp"] = timestamp
        raise e

    return create_response(
        "IMAGE_UPLOADED",
        "프로필 이미지가 업로드되었습니다.",
        data={"url": url},
        timestamp=timestamp,
    )
