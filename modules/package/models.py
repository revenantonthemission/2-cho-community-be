"""package_models: 패키지 관련 데이터 모델 및 함수 모듈."""

from dataclasses import dataclass
from datetime import datetime

from core.database.connection import get_cursor, transactional
from core.utils.formatters import format_datetime
from core.utils.pagination import escape_like
from schemas.common import build_author_dict

PACKAGE_CATEGORIES = frozenset(
    {"editor", "terminal", "devtool", "system", "desktop", "utility", "multimedia", "security"}
)

ALLOWED_SORT_OPTIONS = {
    "latest": "p.created_at DESC",
    "name": "p.name ASC",
    "rating": "avg_rating DESC, p.created_at DESC",
    "reviews": "reviews_count DESC, p.created_at DESC",
}

ALLOWED_PACKAGE_COLUMNS = {
    "display_name",
    "description",
    "homepage_url",
    "category",
    "package_manager",
    "updated_at",
}

_PKG_COLUMNS = (
    "id, name, display_name, description, homepage_url, category, package_manager, created_by, created_at, updated_at"
)


@dataclass(frozen=True)
class Package:
    """패키지 데이터 클래스."""

    id: int
    name: str
    display_name: str
    description: str | None
    homepage_url: str | None
    category: str
    package_manager: str | None
    created_by: int | None
    created_at: datetime | None = None
    updated_at: datetime | None = None


async def create_package(
    name: str,
    display_name: str,
    description: str | None,
    homepage_url: str | None,
    category: str,
    package_manager: str | None,
    created_by: int,
) -> int:
    """새 패키지를 등록합니다."""
    async with transactional() as cur:
        await cur.execute(
            """
            INSERT INTO package (name, display_name, description, homepage_url,
                                 category, package_manager, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (name, display_name, description, homepage_url, category, package_manager, created_by),
        )
        return cur.lastrowid


async def get_package_by_id(package_id: int) -> Package | None:
    """ID로 패키지를 조회합니다."""
    async with get_cursor() as cur:
        await cur.execute(f"SELECT {_PKG_COLUMNS} FROM package WHERE id = %s", (package_id,))
        row = await cur.fetchone()
        return Package(**row) if row else None


async def get_package_by_name(name: str) -> Package | None:
    """이름으로 패키지를 조회합니다 (중복 검사용)."""
    async with get_cursor() as cur:
        await cur.execute(f"SELECT {_PKG_COLUMNS} FROM package WHERE name = %s", (name,))
        row = await cur.fetchone()
        return Package(**row) if row else None


async def get_packages_with_stats(
    offset: int = 0,
    limit: int = 10,
    sort: str = "latest",
    category: str | None = None,
    search: str | None = None,
) -> list[dict]:
    """패키지 목록을 평균 평점 및 리뷰 수와 함께 조회합니다."""
    sort_clause = ALLOWED_SORT_OPTIONS.get(sort, ALLOWED_SORT_OPTIONS["latest"])

    where = "1=1"
    params: list = []

    if category:
        where += " AND p.category = %s"
        params.append(category)

    if search:
        where += " AND (p.name LIKE %s OR p.display_name LIKE %s OR p.description LIKE %s)"
        like_pattern = f"%{escape_like(search)}%"
        params.extend([like_pattern, like_pattern, like_pattern])

    params.extend([limit, offset])

    async with get_cursor() as cur:
        await cur.execute(
            f"""
                SELECT p.id AS package_id, p.name, p.display_name, p.description,
                       p.homepage_url, p.category, p.package_manager, p.created_at,
                       u.id AS creator_id, u.nickname AS creator_nickname,
                       COALESCE(rs.avg_rating, 0) AS avg_rating,
                       COALESCE(rs.reviews_count, 0) AS reviews_count
                FROM package p
                LEFT JOIN user u ON p.created_by = u.id
                LEFT JOIN (
                    SELECT package_id,
                           AVG(rating) AS avg_rating,
                           COUNT(*) AS reviews_count
                    FROM package_review
                    WHERE deleted_at IS NULL
                    GROUP BY package_id
                ) rs ON p.id = rs.package_id
                WHERE {where}
                ORDER BY {sort_clause}
                LIMIT %s OFFSET %s
                """,
            params,
        )
        rows = await cur.fetchall()

        return [
            {
                "package_id": row["package_id"],
                "name": row["name"],
                "display_name": row["display_name"],
                "description": row["description"],
                "homepage_url": row["homepage_url"],
                "category": row["category"],
                "package_manager": row["package_manager"],
                "created_at": format_datetime(row["created_at"]),
                "creator": build_author_dict(row["creator_id"], row["creator_nickname"], None),
                "avg_rating": float(row["avg_rating"]),
                "reviews_count": row["reviews_count"],
            }
            for row in rows
        ]


async def get_packages_count(category: str | None = None, search: str | None = None) -> int:
    """패키지 총 개수를 반환합니다."""
    where = "1=1"
    params: list = []

    if category:
        where += " AND category = %s"
        params.append(category)

    if search:
        where += " AND (name LIKE %s OR display_name LIKE %s OR description LIKE %s)"
        like_pattern = f"%{escape_like(search)}%"
        params.extend([like_pattern, like_pattern, like_pattern])

    async with get_cursor() as cur:
        await cur.execute(f"SELECT COUNT(*) AS cnt FROM package WHERE {where}", params)
        row = await cur.fetchone()
        return row["cnt"] if row else 0


async def update_package(package_id: int, **kwargs: str | None) -> bool:
    """패키지 정보를 수정합니다."""
    updates: list[str] = []
    params: list = []

    for key, value in kwargs.items():
        if value is not None and key in ALLOWED_PACKAGE_COLUMNS:
            updates.append(f"{key} = %s")
            params.append(value)

    if not updates:
        return False

    params.append(package_id)

    async with transactional() as cur:
        await cur.execute(
            f"UPDATE package SET {', '.join(updates)} WHERE id = %s",
            params,
        )
        return cur.rowcount > 0
