"""category_router: 카테고리 관련 라우터 모듈."""

from fastapi import APIRouter, Request, status
from controllers import category_controller

category_router = APIRouter(prefix="/v1/categories", tags=["categories"])


@category_router.get("/", status_code=status.HTTP_200_OK)
async def get_categories(request: Request) -> dict:
    """카테고리 목록을 조회합니다. 인증 불필요."""
    return await category_controller.get_categories(request)
