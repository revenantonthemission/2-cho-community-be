"""category_models: 카테고리 관련 데이터 모델 및 함수 모듈."""

from dataclasses import dataclass
from datetime import datetime

from database.connection import get_connection


@dataclass(frozen=True)
class Category:
    """카테고리 데이터 클래스."""

    id: int
    name: str
    slug: str
    description: str | None
    sort_order: int
    created_at: datetime | None = None


def _row_to_category(row: tuple) -> Category:
    """데이터베이스 행을 Category 객체로 변환합니다."""
    return Category(
        id=row[0],
        name=row[1],
        slug=row[2],
        description=row[3],
        sort_order=row[4],
        created_at=row[5],
    )


async def get_all_categories() -> list[Category]:
    """모든 카테고리를 정렬 순서대로 조회합니다."""
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id, name, slug, description, sort_order, created_at "
                "FROM category ORDER BY sort_order ASC"
            )
            rows = await cur.fetchall()
            return [_row_to_category(row) for row in rows]


async def get_category_by_id(category_id: int) -> Category | None:
    """ID로 카테고리를 조회합니다."""
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id, name, slug, description, sort_order, created_at "
                "FROM category WHERE id = %s",
                (category_id,),
            )
            row = await cur.fetchone()
            return _row_to_category(row) if row else None
