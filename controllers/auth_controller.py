# auth_controller: 인증 관련 컨트롤러 모듈

import uuid
from fastapi import HTTPException, Request, status
from models import user_models
from models.user_models import User
from schemas.auth_schemas import LoginRequest
from dependencies.request_context import get_request_timestamp


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


# 이메일과 비밀번호를 사용하여 로그인
async def login(credentials: LoginRequest, request: Request) -> dict:
    timestamp = get_request_timestamp(request)

    user = user_models.get_user_by_email(credentials.email)

    if not user or user.password != credentials.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "unauthorized",
                "timestamp": timestamp,
            },
        )

    # 세션이 존재하지 않으면 새로 만든다.
    session_id = request.session.get("session_id")
    if not session_id:
        session_id = str(uuid.uuid4())
        request.session["session_id"] = session_id
        request.session["email"] = credentials.email
        request.session["nickname"] = user.nickname

    return {
        "code": "LOGIN_SUCCESS",
        "message": "로그인에 성공했습니다.",
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


# 세션을 삭제하여 로그아웃
async def logout(current_user: User, request: Request) -> dict:
    timestamp = get_request_timestamp(request)
    request.session.clear()

    return {
        "code": "LOGOUT_SUCCESS",
        "message": "로그아웃에 성공했습니다.",
        "data": {},
        "errors": [],
        "timestamp": timestamp,
    }
