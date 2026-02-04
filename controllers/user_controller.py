"""user_controller: 사용자 관련 컨트롤러 모듈.

사용자 등록, 조회, 수정, 비밀번호 변경, 탈퇴 등의 기능을 제공합니다.
"""

from fastapi import HTTPException, Request, status, UploadFile
from models import user_models
from models.user_models import User
from schemas.user_schemas import (
    CreateUserRequest,
    UpdateUserRequest,
    ChangePasswordRequest,
    WithdrawRequest,
)
from schemas.common import create_response, serialize_user
from dependencies.request_context import get_request_timestamp
from utils.password import hash_password, verify_password
from utils.file_utils import save_upload_file
from pymysql.err import IntegrityError
from core.config import settings
import logging

# 프로필 이미지 저장 경로 (설정에서 로드)
PROFILE_IMAGE_UPLOAD_DIR = settings.PROFILE_IMAGE_UPLOAD_DIR


async def get_user(user_id: int, request: Request) -> dict:
    """사용자 ID를 사용하여 사용자를 조회합니다.

    인증되지 않은 요청에서 사용됩니다.

    Args:
        user_id: 조회할 사용자 ID.
        request: FastAPI Request 객체.

    Returns:
        사용자 정보가 포함된 응답 딕셔너리.

    Raises:
        HTTPException: 잘못된 ID면 400, 사용자가 없으면 404.
    """
    timestamp = get_request_timestamp(request)

    if not user_id or user_id < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_user_id",
                "timestamp": timestamp,
            },
        )

    user = await user_models.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "user_not_found",
                "timestamp": timestamp,
            },
        )

    return create_response(
        "AUTH_SUCCESS",
        "사용자 조회에 성공했습니다.",
        data={"user": serialize_user(user)},
        timestamp=timestamp,
    )


async def create_user(
    user_data: CreateUserRequest, profile_image: UploadFile | None, request: Request
) -> dict:
    """새로운 사용자를 생성합니다.

    Args:
        user_data: 사용자 등록 정보.
        profile_image: 프로필 이미지 파일 (선택).
        request: FastAPI Request 객체.

    Returns:
        사용자 생성 성공 응답 딕셔너리.

    Raises:
        HTTPException: 이메일/닉네임 중복 시 409 Conflict.
    """
    timestamp = get_request_timestamp(request)

    # 이메일 중복 확인
    if await user_models.get_user_by_email(user_data.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "email_already_exists",
                "timestamp": timestamp,
            },
        )

    # 닉네임 중복 확인
    if await user_models.get_user_by_nickname(user_data.nickname):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "nickname_already_exists",
                "timestamp": timestamp,
            },
        )

    # 프로필 이미지 업로드 처리
    profile_image_url = user_data.profileImageUrl
    if profile_image:
        try:
            profile_image_url = await save_upload_file(
                profile_image, PROFILE_IMAGE_UPLOAD_DIR
            )
        except HTTPException as e:
            if isinstance(e.detail, dict):
                e.detail["timestamp"] = timestamp
            raise e
        except Exception as e:
            # 예상치 못한 업로드 에러
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "image_upload_failed",
                    "message": str(e),
                    "timestamp": timestamp,
                },
            )

    # 비밀번호 해싱 후 새로운 사용자 생성
    hashed_password = hash_password(user_data.password)

    logger = logging.getLogger(__name__)

    try:
        await user_models.register_user(
            email=user_data.email,
            password=hashed_password,
            nickname=user_data.nickname,
            profile_image_url=profile_image_url,
        )
    except IntegrityError as e:
        # 중복 엔트리 에러 (1062)
        if e.args[0] == 1062:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "conflict",
                    "message": "이미 존재하는 이메일 또는 닉네임입니다.",
                    "timestamp": timestamp,
                },
            )
        else:
            logger.exception(f"Unhandled IntegrityError: {e}")
            raise e
    except Exception as e:
        logger.exception(f"Unexpected error in create_user: {e}")
        raise e

    return create_response(
        "SIGNUP_SUCCESS", "사용자 생성에 성공했습니다.", timestamp=timestamp
    )


async def get_my_info(current_user: User, request: Request) -> dict:
    """현재 로그인 중인 사용자의 정보를 반환합니다.

    Args:
        current_user: 현재 인증된 사용자 객체.
        request: FastAPI Request 객체.

    Returns:
        사용자 정보가 포함된 응답 딕셔너리.
    """
    timestamp = get_request_timestamp(request)

    return create_response(
        "AUTH_SUCCESS",
        "현재 로그인 중인 상태입니다.",
        data={"user": serialize_user(current_user)},
        timestamp=timestamp,
    )


async def get_user_info(user_id: int, current_user: User, request: Request) -> dict:
    """사용자 ID를 사용하여 다른 사용자 정보를 조회합니다.

    인증된 사용자가 다른 사용자를 조회할 때 사용됩니다.

    Args:
        user_id: 조회할 사용자 ID.
        current_user: 현재 인증된 사용자 객체.
        request: FastAPI Request 객체.

    Returns:
        사용자 정보가 포함된 응답 딕셔너리.

    Raises:
        HTTPException: 사용자가 없으면 404 Not Found.
    """
    timestamp = get_request_timestamp(request)
    user = await user_models.get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "user_not_found",
                "timestamp": timestamp,
            },
        )

    return create_response(
        "QUERY_SUCCESS",
        "유저 조회에 성공했습니다.",
        data={"user": serialize_user(user)},
        timestamp=timestamp,
    )


async def update_user(
    update_data: UpdateUserRequest, current_user: User, request: Request
) -> dict:
    """현재 로그인 중인 사용자의 정보를 수정합니다.

    Args:
        update_data: 수정할 정보 (닉네임, 프로필 이미지).
        current_user: 현재 인증된 사용자 객체.
        request: FastAPI Request 객체.

    Returns:
        수정된 사용자 정보가 포함된 응답 딕셔너리.

    Raises:
        HTTPException: 변경 사항 없으면 400, 중복이면 409.
    """
    timestamp = get_request_timestamp(request)

    # 변경 사항이 없는 경우
    if update_data.nickname is None and update_data.profileImageUrl is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "no_changes_provided",
                "timestamp": timestamp,
            },
        )

    # 닉네임 중복 확인
    if update_data.nickname is not None:
        existing_user = await user_models.get_user_by_nickname(update_data.nickname)
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "nickname_already_exists",
                    "timestamp": timestamp,
                },
            )

    # 사용자 정보 수정
    updated_user = await user_models.update_user(
        current_user.id,
        nickname=update_data.nickname,
        profile_image_url=update_data.profileImageUrl,
    )

    # 세션 정보 수정
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
    """현재 로그인 중인 사용자의 비밀번호를 변경합니다.

    Args:
        password_data: 비밀번호 변경 정보 (현재, 새 비밀번호).
        current_user: 현재 인증된 사용자 객체.
        request: FastAPI Request 객체.

    Returns:
        비밀번호 변경 성공 응답 딕셔너리.

    Raises:
        HTTPException: 현재 비밀번호 불일치 시 401, 검증 실패 시 400.
    """
    timestamp = get_request_timestamp(request)

    # 새 비밀번호 확인
    if password_data.new_password != password_data.new_password_confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "password_mismatch",
                "timestamp": timestamp,
            },
        )

    # 새 비밀번호가 현재 비밀번호와 같은지 확인 (해싱된 비밀번호와 비교)
    if verify_password(password_data.new_password, current_user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "same_password",
                "timestamp": timestamp,
            },
        )

    # 비밀번호 해싱 후 변경
    hashed_new_password = hash_password(password_data.new_password)
    await user_models.update_password(current_user.id, hashed_new_password)

    return create_response(
        "PASSWORD_CHANGE_SUCCESS", "비밀번호 변경에 성공했습니다.", timestamp=timestamp
    )


async def withdraw_user(
    withdraw_data: WithdrawRequest, current_user: User, request: Request
) -> dict:
    """회원 탈퇴를 처리합니다.

    Args:
        withdraw_data: 탈퇴 요청 정보 (비밀번호, 동의 여부).
        current_user: 현재 인증된 사용자 객체.
        request: FastAPI Request 객체.

    Returns:
        탈퇴 신청 접수 응답 딕셔너리.

    Raises:
        HTTPException: 비활성 사용자면 400, 비밀번호 불일치 시 400.
    """
    timestamp = get_request_timestamp(request)

    # 현재 로그인 중인 사용자가 활성화 상태인지 확인
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "inactive_user",
                "timestamp": timestamp,
            },
        )

    # 비밀번호 확인 (해싱된 비밀번호와 비교)
    if not verify_password(withdraw_data.password, current_user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_password",
                "timestamp": timestamp,
            },
        )

    # 동의 여부는 Pydantic 스키마에서 처리

    # 회원 탈퇴 처리 (Soft Delete)
    await user_models.withdraw_user(current_user.id)

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

    Args:
        file: 업로드할 이미지 파일.
        current_user: 현재 인증된 사용자.
        request: FastAPI Request 객체.

    Returns:
        업로드된 이미지 URL이 포함된 응답 딕셔너리.

    Raises:
        HTTPException: 잘못된 파일 형식이면 400, 파일 크기 초과면 400.
    """
    timestamp = get_request_timestamp(request)

    try:
        url = await save_upload_file(file, PROFILE_IMAGE_UPLOAD_DIR)
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
