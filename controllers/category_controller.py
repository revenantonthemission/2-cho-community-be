"""category_controller: 카테고리 관련 컨트롤러 모듈."""

from fastapi import Request
from models import category_models
from schemas.common import create_response
from dependencies.request_context import get_request_timestamp


async def get_categories(request: Request) -> dict:
    """카테고리 목록을 조회합니다."""
    timestamp = get_request_timestamp(request)

    categories = await category_models.get_all_categories()

    return create_response(
        "CATEGORIES_RETRIEVED",
        "카테고리 목록 조회에 성공했습니다.",
        data={
            "categories": [
                {
                    "category_id": cat.id,
                    "name": cat.name,
                    "slug": cat.slug,
                    "description": cat.description,
                    "sort_order": cat.sort_order,
                }
                for cat in categories
            ]
        },
        timestamp=timestamp,
    )
