"""auth: FastAPI 의존성 주입을 위한 인증 모듈.

세션 기반 사용자 인증 및 권한 확인 기능을 제공합니다.
"""

from datetime import datetime, timezone
from fastapi import HTTPException, Request, status
from models import user_models, session_models
from models.user_models import User


async def _validate_session(request: Request) -> User | None:
    """세션 유효성을 공통으로 검증합니다.

    Args:
        request: FastAPI Request 객체.

    Returns:
        유효한 사용자 객체, 없으면 None.
        만료된 경우 세션을 삭제합니다.
    """
    session_id = request.session.get("session_id")
    if not session_id:
        return None

    # DB에서 세션과 사용자 정보를 한 번에 조회 (JOIN 사용)
    result = await user_models.get_user_and_session(session_id)

    # 세션이나 사용자가 존재하지 않음 (Strict Validation)
    if not result:
        return None

    expires_at = result["expires_at"]
    user = result["user"]

    # 세션 만료 확인 (타임존 통일)
    now = datetime.now(timezone.utc)
    # DB에서 가져온 expires_at이 naive datetime이면 UTC로 가정
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        await session_models.delete_session(session_id)
        request.session.clear()
        return None

    # 탈퇴한 사용자 확인
    if user.deleted_at:
        request.session.clear()
        return None

    return user


async def get_current_user(request: Request) -> User:
    """세션에서 현재 사용자를 추출하고 검증합니다.

    세션에 저장된 이메일로 사용자를 조회하여 반환합니다.

    Args:
        request: FastAPI Request 객체.

    Returns:
        인증된 사용자 객체.

    Raises:
        HTTPException: 세션이 없으면 401.
    """
    user = await _validate_session(request)

    if not user:
        # _validate_session에서 이미 세션 정리(clear)가 필요한 경우 수행했으므로
        # 여기서는 단순히 예외만 발생시키면 됨.
        # 단, 세션 ID는 있었으나 DB에 없었던 경우 등도 포함되므로
        # 확실성을 위해 세션 클리어를 다시 호출할 수도 있으나,
        # _validate_session이 None을 반환하는 모든 케이스(없음, 만료, 탈퇴)가
        # 인증 실패이므로 401을 반환.

        # 만약 session_id가 애초에 없었다면 불필요한 clear()일 수 있지만 안전함.
        if request.session.get("session_id"):
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
    return await _validate_session(request)
