# user_router: 사용자 관련 라우터

from fastapi import APIRouter, Depends, Request, status
from controllers import user_controller
from dependencies.auth import get_current_user, get_optional_user
from models.user_models import User
from schemas.user_schemas import (
    CreateUserRequest,
    UpdateUserRequest,
    ChangePasswordRequest,
    WithdrawRequest,
)


# 라우터 생성
user_router = APIRouter(prefix="/v1/users", tags=["users"])


# 사용자 등록
@user_router.post("/", status_code=status.HTTP_201_CREATED)
async def create_user(user_data: CreateUserRequest, request: Request):
    return await user_controller.create_user(user_data, request)


# 내 정보 조회
@user_router.get("/me", status_code=status.HTTP_200_OK)
async def get_my_info(request: Request, current_user: User = Depends(get_current_user)):
    return await user_controller.get_my_info(current_user, request)


# 사용자 조회
@user_router.get("/{nickname}", status_code=status.HTTP_200_OK)
async def get_user(
    nickname: str,
    request: Request,
    current_user: User | None = Depends(get_optional_user),
):
    # 본인의 프로필을 조회할 때는 get_my_info를 호출한다.
    if current_user and nickname == current_user.nickname:
        return await user_controller.get_my_info(current_user, request)
    # 다른 사용자의 프로필을 조회할 때는 get_user_info를 호출한다.
    if current_user:
        return await user_controller.get_user_info(nickname, current_user, request)
    # 인증되지 않은 요청은 get_user를 호출한다.
    return await user_controller.get_user(nickname, request)


# 사용자 정보 수정
@user_router.patch("/me", status_code=status.HTTP_200_OK)
async def update_user(
    update_data: UpdateUserRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    return await user_controller.update_user(update_data, current_user, request)


# 비밀번호 변경
@user_router.put("/me/password", status_code=status.HTTP_200_OK)
async def change_password(
    password_data: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    return await user_controller.change_password(password_data, current_user, request)


# 사용자 탈퇴
@user_router.delete("/me", status_code=status.HTTP_200_OK)
async def withdraw_user(
    withdraw_data: WithdrawRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    return await user_controller.withdraw_user(withdraw_data, current_user, request)
