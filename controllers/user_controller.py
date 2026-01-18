# user_controller: 사용자 관련 컨트롤러 모듈

from fastapi import HTTPException, Request, status
from models import user_models
from models.user_models import User
from schemas.user_schemas import (
    CreateUserRequest,
    UpdateUserRequest,
    ChangePasswordRequest,
    WithdrawRequest,
)
from dependencies.request_context import get_request_timestamp


# 사용자 ID를 사용하여 사용자 조회
async def get_user(user_id: int, request: Request) -> dict:
    timestamp = get_request_timestamp(request)

    if not user_id or user_id < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_user_id",
                "timestamp": timestamp,
            },
        )

    user = user_models.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "user_not_found",
                "timestamp": timestamp,
            },
        )

    return {
        "code": "AUTH_SUCCESS",
        "message": "사용자 조회에 성공했습니다.",
        "data": {
            "user": {
                "user_id": user.id,
                "email": user.email,
                "name": user.name,
                "nickname": user.nickname,
                "profileImageUrl": user.profileImageUrl,
            }
        },
        "errors": [],
        "timestamp": timestamp,
    }


# 새로운 사용자 생성
async def create_user(user_data: CreateUserRequest, request: Request) -> dict:
    timestamp = get_request_timestamp(request)

    # 이메일 중복 확인
    if user_models.get_user_by_email(user_data.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "email_already_exists",
                "timestamp": timestamp,
            },
        )

    # 닉네임 중복 확인
    if user_models.get_user_by_nickname(user_data.nickname):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "nickname_already_exists",
                "timestamp": timestamp,
            },
        )

    # 새로운 사용자 생성
    new_user = user_models.User(
        id=len(user_models.get_users()) + 1,
        name=user_data.name,
        email=user_data.email,
        password=user_data.password,
        nickname=user_data.nickname,
        profileImageUrl=user_data.profileImageUrl or "/assets/default_profile.png",
    )
    user_models.add_user(new_user)

    return {
        "code": "SIGNUP_SUCCESS",
        "message": "사용자 생성에 성공했습니다.",
        "data": {},
        "errors": [],
        "timestamp": timestamp,
    }


# 현재 로그인 중인 사용자의 정보를 반환
async def get_my_info(current_user: User, request: Request) -> dict:
    timestamp = get_request_timestamp(request)

    return {
        "code": "AUTH_SUCCESS",
        "message": "현재 로그인 중인 상태입니다.",
        "data": {
            "user": {
                "user_id": current_user.id,
                "email": current_user.email,
                "nickname": current_user.nickname,
                "profileImageUrl": current_user.profileImageUrl,
            },
        },
        "errors": [],
        "timestamp": timestamp,
    }


# 사용자 ID를 사용하여 사용자 정보 조회
async def get_user_info(user_id: int, current_user: User, request: Request) -> dict:
    timestamp = get_request_timestamp(request)
    user = user_models.get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "user_not_found",
                "timestamp": timestamp,
            },
        )

    return {
        "code": "QUERY_SUCCESS",
        "message": "유저 조회에 성공했습니다.",
        "data": {
            "user": {
                "user_id": user.id,
                "email": user.email,
                "nickname": user.nickname,
                "profileImageUrl": user.profileImageUrl,
            },
        },
        "errors": [],
        "timestamp": timestamp,
    }


# 현재 로그인 중인 사용자의 정보를 수정
async def update_user(
    update_data: UpdateUserRequest, current_user: User, request: Request
) -> dict:
    timestamp = get_request_timestamp(request)

    updates = {}
    if update_data.nickname is not None:
        updates["nickname"] = update_data.nickname
    if update_data.email is not None:
        updates["email"] = update_data.email

    # 변경 사항이 없는 경우
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "no_changes_provided",
                "timestamp": timestamp,
            },
        )

    # 닉네임 중복 확인
    if "nickname" in updates:
        existing_user = user_models.get_user_by_nickname(updates["nickname"])
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "nickname_already_exists",
                    "timestamp": timestamp,
                },
            )

    # 이메일 중복 확인
    if "email" in updates:
        existing_user = user_models.get_user_by_email(updates["email"])
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "email_already_exists",
                    "timestamp": timestamp,
                },
            )

    # 사용자 정보 수정
    updated_user = user_models.update_user(current_user.id, **updates)

    # 세션 정보 수정
    if "nickname" in updates:
        request.session["nickname"] = updates["nickname"]
    if "email" in updates:
        request.session["email"] = updates["email"]

    return {
        "code": "UPDATE_SUCCESS",
        "message": "유저 정보 수정에 성공했습니다.",
        "data": {
            "user": {
                "user_id": updated_user.id,
                "email": updated_user.email,
                "nickname": updated_user.nickname,
                "profileImageUrl": updated_user.profileImageUrl,
            }
        },
        "errors": [],
        "timestamp": timestamp,
    }


# 현재 로그인 중인 사용자의 비밀번호 변경
async def change_password(
    password_data: ChangePasswordRequest, current_user: User, request: Request
) -> dict:
    timestamp = get_request_timestamp(request)

    # 현재 비밀번호 확인
    if current_user.password != password_data.current_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "invalid_current_password",
                "timestamp": timestamp,
            },
        )

    # 새 비밀번호 확인
    if password_data.new_password != password_data.new_password_confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "password_mismatch",
                "timestamp": timestamp,
            },
        )

    # 새 비밀번호가 현재 비밀번호와 같은지 확인
    if password_data.new_password == current_user.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "same_password",
                "timestamp": timestamp,
            },
        )

    # 비밀번호 변경
    user_models.update_password(current_user.id, password_data.new_password)

    return {
        "code": "PASSWORD_CHANGE_SUCCESS",
        "message": "비밀번호 변경에 성공했습니다.",
        "data": {},
        "errors": [],
        "timestamp": timestamp,
    }


# 회원 탈퇴
async def withdraw_user(
    withdraw_data: WithdrawRequest, current_user: User, request: Request
) -> dict:
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

    # 비밀번호 확인
    if withdraw_data.password != current_user.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_password",
                "timestamp": timestamp,
            },
        )

    # 동의 여부는 Pydantic 스키마에서 처리

    return {
        "code": "WITHDRAWAL_ACCEPTED",
        "message": "탈퇴 신청이 접수되었습니다.",
        "data": {},
        "errors": [],
        "timestamp": timestamp,
    }
