"""routers: FastAPI 라우터 패키지.

인증, 사용자, 게시글, 이용약관, 알림 관련 API 엔드포인트를 정의하는 라우터 모듈을 제공합니다.
"""

from .auth_router import auth_router
from .user_router import user_router
from .post_router import post_router
from .terms_router import terms_router
from . import notification_router

__all__ = [
    "auth_router",
    "user_router",
    "post_router",
    "terms_router",
    "notification_router",
]
