# FastAPI 의존성 주입을 위한 인증 모듈

from datetime import datetime
from fastapi import HTTPException, Request, status
from models import user_models
from models.user_models import User


# 세션에서 현재 사용자를 추출하고 검증합니다.
async def get_current_user(request: Request) -> User:
    session_id = request.session.get("session_id")

    # 세션이 존재하지 않음. -> 401 Unauthorized
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "unauthorized",
                "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )

    email = request.session.get("email")
    user = user_models.get_user_by_email(email)

    # 사용자 정보를 찾을 수 없음. -> 403 Forbidden
    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "access_denied",
                "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )

    # 인증된 사용자 객체 반환
    return user


# 인증되지 않은 이용자와 인증된 사용자 모두에게 적용 가능하며, 인증된 사용자가 없을 경우 None을 반환합니다.
async def get_optional_user(request: Request) -> User | None:
    session_id = request.session.get("session_id")

    # 세션이 존재하지 않음. -> None
    if not session_id:
        return None

    email = request.session.get("email")
    return user_models.get_user_by_email(email)
