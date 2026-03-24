"""category_models: 카테고리 관련 데이터 모델 및 함수 모듈."""

from dataclasses import dataclass
from datetime import datetime

from core.database.connection import get_cursor


@dataclass(frozen=True)
class Category:
    """카테고리 데이터 클래스."""

    id: int
    name: str
    slug: str
    description: str | None
    sort_order: int
    created_at: datetime | None = None


async def get_all_categories() -> list[Category]:
    """모든 카테고리를 정렬 순서대로 조회합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT id, name, slug, description, sort_order, created_at FROM category ORDER BY sort_order ASC"
        )
        rows = await cur.fetchall()
        return [Category(**row) for row in rows]


async def get_category_by_id(category_id: int) -> Category | None:
    """ID로 카테고리를 조회합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT id, name, slug, description, sort_order, created_at FROM category WHERE id = %s",
            (category_id,),
        )
        row = await cur.fetchone()
        return Category(**row) if row else None
