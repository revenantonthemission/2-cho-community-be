"""auth: FastAPI 의존성 주입을 위한 인증 모듈.

세션 기반 사용자 인증 및 권한 확인 기능을 제공합니다.
"""

from datetime import datetime
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

    email = request.session.get("email")
    user = await user_models.get_user_by_email(email)

    # 사용자 정보를 찾을 수 없음
    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "access_denied",
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

    email = request.session.get("email")
    return await user_models.get_user_by_email(email)
