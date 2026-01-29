"""auth_controller: 인증 관련 컨트롤러 모듈.

로그인, 로그아웃, 사용자 인증 상태 확인 등의 기능을 제공합니다.
"""

import uuid
from fastapi import HTTPException, Request, status
from models import user_models
from models.user_models import User
from schemas.auth_schemas import LoginRequest
from dependencies.request_context import get_request_timestamp


async def get_my_info(current_user: User, request: Request) -> dict:
    """현재 로그인 중인 사용자의 정보를 반환합니다.

    Args:
        current_user: 현재 인증된 사용자 객체.
        request: FastAPI Request 객체.

    Returns:
        사용자 정보가 포함된 응답 딕셔너리.
    """
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


async def login(credentials: LoginRequest, request: Request) -> dict:
    """이메일과 비밀번호를 사용하여 로그인합니다.

    Args:
        credentials: 로그인 자격 증명 (이메일, 비밀번호).
        request: FastAPI Request 객체.

    Returns:
        로그인 성공 시 사용자 정보가 포함된 응답 딕셔너리.

    Raises:
        HTTPException: 인증 실패 시 401 Unauthorized.
    """
    timestamp = get_request_timestamp(request)

    user = await user_models.get_user_by_email(credentials.email)

    if not user or user.password != credentials.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "unauthorized",
                "timestamp": timestamp,
            },
        )

    # 세션이 존재하지 않으면 새로 생성
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


async def logout(current_user: User, request: Request) -> dict:
    """세션을 삭제하여 로그아웃합니다.

    Args:
        current_user: 현재 인증된 사용자 객체.
        request: FastAPI Request 객체.

    Returns:
        로그아웃 성공 응답 딕셔너리.
    """
    timestamp = get_request_timestamp(request)
    request.session.clear()

    return {
        "code": "LOGOUT_SUCCESS",
        "message": "로그아웃에 성공했습니다.",
        "data": {},
        "errors": [],
        "timestamp": timestamp,
    }
