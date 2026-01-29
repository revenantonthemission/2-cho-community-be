"""user_router: 사용자 관련 라우터 모듈.

사용자 등록, 조회, 수정, 비밀번호 변경, 탈퇴 엔드포인트를 제공합니다.
"""

from fastapi import APIRouter, Depends, Request, status, UploadFile, File
from controllers import user_controller
from dependencies.auth import get_current_user, get_optional_user
from models.user_models import User
from schemas.user_schemas import (
    CreateUserRequest,
    UpdateUserRequest,
    ChangePasswordRequest,
    WithdrawRequest,
)


user_router = APIRouter(prefix="/v1/users", tags=["users"])
"""사용자 관련 라우터 인스턴스."""


@user_router.post("/", status_code=status.HTTP_201_CREATED)
async def create_user(user_data: CreateUserRequest, request: Request) -> dict:
    """새 사용자를 등록합니다.

    Args:
        user_data: 사용자 등록 정보.
        request: FastAPI Request 객체.

    Returns:
        사용자 생성 성공 응답.
    """
    return await user_controller.create_user(user_data, request)


@user_router.get("/me", status_code=status.HTTP_200_OK)
async def get_my_info(
    request: Request, current_user: User = Depends(get_current_user)
) -> dict:
    """현재 로그인 중인 사용자의 정보를 조회합니다.

    Args:
        request: FastAPI Request 객체.
        current_user: 현재 인증된 사용자.

    Returns:
        사용자 정보가 포함된 응답.
    """
    return await user_controller.get_my_info(current_user, request)


@user_router.get("/{user_id}", status_code=status.HTTP_200_OK)
async def get_user(
    user_id: int,
    request: Request,
    current_user: User | None = Depends(get_optional_user),
) -> dict:
    """특정 사용자의 정보를 조회합니다.

    인증 상태에 따라 다른 수준의 정보를 반환합니다.

    Args:
        user_id: 조회할 사용자 ID.
        request: FastAPI Request 객체.
        current_user: 현재 인증된 사용자 (선택).

    Returns:
        사용자 정보가 포함된 응답.
    """
    # 본인의 프로필을 조회할 때는 get_my_info를 호출
    if current_user and user_id == current_user.id:
        return await user_controller.get_my_info(current_user, request)
    # 다른 사용자의 프로필을 조회할 때는 get_user_info를 호출
    if current_user:
        return await user_controller.get_user_info(user_id, current_user, request)
    # 인증되지 않은 요청은 get_user를 호출
    return await user_controller.get_user(user_id, request)


@user_router.patch("/me", status_code=status.HTTP_200_OK)
async def update_user(
    update_data: UpdateUserRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict:
    """현재 로그인 중인 사용자의 정보를 수정합니다.

    Args:
        update_data: 수정할 정보 (닉네임, 이메일).
        request: FastAPI Request 객체.
        current_user: 현재 인증된 사용자.

    Returns:
        수정된 사용자 정보가 포함된 응답.
    """
    return await user_controller.update_user(update_data, current_user, request)


@user_router.put("/me/password", status_code=status.HTTP_200_OK)
async def change_password(
    password_data: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict:
    """현재 로그인 중인 사용자의 비밀번호를 변경합니다.

    Args:
        password_data: 비밀번호 변경 정보.
        request: FastAPI Request 객체.
        current_user: 현재 인증된 사용자.

    Returns:
        비밀번호 변경 성공 응답.
    """
    return await user_controller.change_password(password_data, current_user, request)


@user_router.delete("/me", status_code=status.HTTP_200_OK)
async def withdraw_user(
    withdraw_data: WithdrawRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict:
    """현재 로그인 중인 사용자의 계정을 탈퇴합니다.

    Args:
        withdraw_data: 탈퇴 요청 정보 (비밀번호, 동의).
        request: FastAPI Request 객체.
        current_user: 현재 인증된 사용자.

    Returns:
        탈퇴 신청 접수 응답.
    """
    return await user_controller.withdraw_user(withdraw_data, current_user, request)


@user_router.post("/profile/image", status_code=status.HTTP_201_CREATED)
async def upload_profile_image(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> dict:
    """프로필 이미지를 업로드합니다.

    Args:
        request: FastAPI Request 객체.
        file: 업로드할 이미지 파일.
        current_user: 현재 인증된 사용자.

    Returns:
        업로드된 이미지 URL이 포함된 응답.
    """
    return await user_controller.upload_profile_image(file, current_user, request)
