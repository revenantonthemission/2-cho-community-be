"""auth: FastAPI 의존성 주입을 위한 인증 모듈.

세션 기반 사용자 인증 및 권한 확인 기능을 제공합니다.
"""

from datetime import datetime, timezone
from fastapi import HTTPException, Request, status
from models import user_models
from models.user_models import User


async def get_current_user(request: Request) -> User:
    """세션에서 현재 사용자를 추출하고 검증합니다.

    세션에 저장된 이메일로 사용자를 조회하여 반환합니다.

    Args:
        request: FastAPI Request 객체.

    Returns:
        인증된 사용자 객체.

    Raises:
        HTTPException: 세션이 없으면 401, 사용자가 없으면 403.
    """
    session_id = request.session.get("session_id")

    # 세션이 존재하지 않음
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "unauthorized",
                "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )

    # DB에서 세션과 사용자 정보를 한 번에 조회 (JOIN 사용)
    result = await user_models.get_user_and_session(session_id)

    # 세션이나 사용자가 존재하지 않음 (Strict Validation)
    if not result:
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "unauthorized",
                "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )

    expires_at = result["expires_at"]
    user = result["user"]

    # 세션 만료 확인 (타임존 통일)
    now = datetime.now(timezone.utc)
    # DB에서 가져온 expires_at이 naive datetime이면 UTC로 가정
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        await user_models.delete_session(session_id)
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "session_expired",
                "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )

    # 탈퇴한 사용자 확인
    # get_user_and_session은 deleted_at을 필터링하지 않으므로 여기서 명시적으로 확인합니다.
    # 이는 탈퇴 처리된 사용자가 유효한 세션을 가지고 있더라도 접근을 차단하기 위함입니다.

    if user.deleted_at:
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "unauthorized",
                "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )

    return user


async def get_optional_user(request: Request) -> User | None:
    """선택적으로 현재 사용자를 추출합니다.

    인증되지 않은 요청에서도 에러를 발생시키지 않고 None을 반환합니다.

    Args:
        request: FastAPI Request 객체.

    Returns:
        인증된 사용자 객체, 인증되지 않은 경우 None.
    """
    session_id = request.session.get("session_id")

    # 세션이 존재하지 않으면 None 반환
    if not session_id:
        return None

    # DB 세션과 사용자 확인
    result = await user_models.get_user_and_session(session_id)
    if not result:
        return None

    expires_at = result["expires_at"]
    user = result["user"]

    # 만료 확인 (타임존 통일)
    now = datetime.now(timezone.utc)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        return None

    # 삭제된 사용자 확인
    if user.deleted_at:
        return None

    return user
