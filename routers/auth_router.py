"""auth_router: 인증 관련 라우터 모듈.

로그인, 로그아웃, 토큰 갱신, 사용자 인증 상태 확인 엔드포인트를 제공합니다.
"""

from fastapi import APIRouter, Depends, Request, Response, status
from controllers import auth_controller
from dependencies.auth import get_current_user
from models.user_models import User
from schemas.auth_schemas import LoginRequest


auth_router = APIRouter(prefix="/v1/auth", tags=["auth"])


# NOTE: /session 경로는 프론트엔드 호환성을 위해 유지합니다.
# JWT 기반 인증이지만, 기존 프론트엔드가 이 경로를 사용합니다.
@auth_router.post("/session", status_code=status.HTTP_200_OK)
async def login(
    credentials: LoginRequest, request: Request, response: Response
) -> dict:
    """이메일과 비밀번호로 로그인합니다.

    Args:
        credentials: 로그인 자격 증명 (이메일, 비밀번호).
        request: FastAPI Request 객체.
        response: FastAPI Response 객체.

    Returns:
        access_token과 사용자 정보가 포함된 응답.
    """
    return await auth_controller.login(credentials, request, response)


@auth_router.delete("/session", status_code=status.HTTP_200_OK)
async def logout(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
) -> dict:
    """로그아웃합니다. Refresh Token을 무효화합니다.

    Args:
        request: FastAPI Request 객체.
        response: FastAPI Response 객체.
        current_user: 현재 인증된 사용자.

    Returns:
        로그아웃 성공 응답.
    """
    return await auth_controller.logout(current_user, request, response)


@auth_router.post("/token/refresh", status_code=status.HTTP_200_OK)
async def refresh_token(request: Request, response: Response) -> dict:
    """Refresh Token으로 새 Access Token을 발급합니다.

    HttpOnly 쿠키의 refresh_token을 사용하여 토큰을 갱신합니다.

    Args:
        request: FastAPI Request 객체.
        response: FastAPI Response 객체.

    Returns:
        새 access_token과 사용자 정보가 포함된 응답.
    """
    return await auth_controller.refresh_token(request, response)


@auth_router.get("/me", status_code=status.HTTP_200_OK)
async def get_my_info(
    request: Request, current_user: User = Depends(get_current_user)
) -> dict:
    """현재 로그인 중인 사용자의 정보를 조회합니다.

    Args:
        request: FastAPI Request 객체.
        current_user: 현재 인증된 사용자.

    Returns:
        사용자 정보가 포함된 응답.
    """
    return await auth_controller.get_my_info(current_user, request)
