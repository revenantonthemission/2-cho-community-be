"""auth_controller: 인증 관련 컨트롤러 모듈.

로그인, 로그아웃, 사용자 인증 상태 확인 등의 기능을 제공합니다.
"""

import uuid
from fastapi import HTTPException, Request, status
from models import user_models
from models.user_models import User
from schemas.auth_schemas import LoginRequest
from dependencies.request_context import get_request_timestamp
from utils.password import verify_password
from core.config import settings


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

    # 타이밍 공격 방지 (Timing Attack Mitigation)
    # 사용자가 없더라도 항상 동일한 시간이 소요되는 해시 검증 로직을 실행합니다.
    # 더미 해시는 실제 bcrypt 해시 형식이어야 합니다.
    DUMMY_HASH = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxwKc.60VF.wdz.xGto8.H82o.f2y"

    password_valid = verify_password(
        credentials.password, user.password if user else DUMMY_HASH
    )

    if not user or not password_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "unauthorized",
                "timestamp": timestamp,
            },
        )

    # 기존 세션 데이터가 있다면 파기하고 새 세션 ID 생성 (Session Fixation 방지)
    request.session.clear()
    session_id = str(uuid.uuid4())
    request.session["session_id"] = session_id
    request.session["email"] = credentials.email
    request.session["nickname"] = user.nickname

    # DB에 세션 저장 (Immediate Block 지원)
    from datetime import datetime, timedelta, timezone

    # 설정에서 만료 시간 로드
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.SESSION_EXPIRE_HOURS)
    await user_models.create_session(user.id, session_id, expires_at)

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

    # DB 세션 삭제
    session_id = request.session.get("session_id")
    if session_id:
        await user_models.delete_session(session_id)

    request.session.clear()

    return {
        "code": "LOGOUT_SUCCESS",
        "message": "로그아웃에 성공했습니다.",
        "data": {},
        "errors": [],
        "timestamp": timestamp,
    }


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
