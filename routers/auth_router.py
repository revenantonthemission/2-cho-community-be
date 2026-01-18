# auth_router: 인증 관련 라우터

from fastapi import APIRouter, Depends, Request, status
from controllers import auth_controller
from dependencies.auth import get_current_user
from models.user_models import User
from schemas.auth_schemas import LoginRequest


# 라우터 생성
auth_router = APIRouter(prefix="/v1/auth", tags=["auth"])


# 로그인
@auth_router.post("/session", status_code=status.HTTP_200_OK)
async def login(credentials: LoginRequest, request: Request):
    return await auth_controller.login(credentials, request)


# 로그아웃
@auth_router.delete("/session", status_code=status.HTTP_200_OK)
async def logout(request: Request, current_user: User = Depends(get_current_user)):
    return await auth_controller.logout(current_user, request)


# 내 정보 조회
@auth_router.get("/me", status_code=status.HTTP_200_OK)
async def get_my_info(request: Request, current_user: User = Depends(get_current_user)):
    return await auth_controller.get_my_info(current_user, request)
