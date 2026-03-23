"""package_models: 패키지 관련 데이터 모델 및 함수 모듈."""

from dataclasses import dataclass
from datetime import datetime

from database.connection import get_connection, transactional
from schemas.common import build_author_dict
from utils.formatters import format_datetime

PACKAGE_CATEGORIES = frozenset(
    {
        "editor",
        "terminal",
        "devtool",
        "system",
        "desktop",
        "utility",
        "multimedia",
        "security",
    }
)

# SQL Injection 방지: 허용된 정렬 옵션 whitelist
ALLOWED_SORT_OPTIONS = {
    "latest": "p.created_at DESC",
    "name": "p.name ASC",
    "rating": "avg_rating DESC, p.created_at DESC",
    "reviews": "reviews_count DESC, p.created_at DESC",
}

# SQL Injection 방지: 허용된 UPDATE 컬럼명 whitelist
ALLOWED_PACKAGE_COLUMNS = {
    "display_name",
    "description",
    "homepage_url",
    "category",
    "package_manager",
    "updated_at",
}


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
    """새 패키지를 등록합니다.

    Args:
        name: 패키지 이름 (고유).
        display_name: 표시 이름.
        description: 설명.
        homepage_url: 홈페이지 URL.
        category: 카테고리.
        package_manager: 패키지 매니저.
        created_by: 등록자 ID.

    Returns:
        생성된 패키지 ID.
    """
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
    """ID로 패키지를 조회합니다.

    Args:
        package_id: 조회할 패키지 ID.

    Returns:
        패키지 객체, 없으면 None.
    """
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
                SELECT id, name, display_name, description, homepage_url,
                       category, package_manager, created_by, created_at, updated_at
                FROM package
                WHERE id = %s
                """,
            (package_id,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return Package(
            id=row[0],
            name=row[1],
            display_name=row[2],
            description=row[3],
            homepage_url=row[4],
            category=row[5],
            package_manager=row[6],
            created_by=row[7],
            created_at=row[8],
            updated_at=row[9],
        )


async def get_package_by_name(name: str) -> Package | None:
    """이름으로 패키지를 조회합니다 (중복 검사용).

    Args:
        name: 패키지 이름.

    Returns:
        패키지 객체, 없으면 None.
    """
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
                SELECT id, name, display_name, description, homepage_url,
                       category, package_manager, created_by, created_at, updated_at
                FROM package
                WHERE name = %s
                """,
            (name,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return Package(
            id=row[0],
            name=row[1],
            display_name=row[2],
            description=row[3],
            homepage_url=row[4],
            category=row[5],
            package_manager=row[6],
            created_by=row[7],
            created_at=row[8],
            updated_at=row[9],
        )


async def get_packages_with_stats(
    offset: int = 0,
    limit: int = 10,
    sort: str = "latest",
    category: str | None = None,
    search: str | None = None,
) -> list[dict]:
    """패키지 목록을 평균 평점 및 리뷰 수와 함께 조회합니다.

    서브쿼리 패턴으로 Cartesian Product를 방지합니다.

    Args:
        offset: 시작 위치.
        limit: 조회할 개수.
        sort: 정렬 옵션 (latest, name, rating, reviews).
        category: 카테고리 필터 (선택).
        search: 검색어 (패키지명/설명, 선택).

    Returns:
        패키지 상세 정보 딕셔너리 목록.
    """
    sort_clause = ALLOWED_SORT_OPTIONS.get(sort, ALLOWED_SORT_OPTIONS["latest"])

    where = "1=1"
    params: list = []

    if category:
        where += " AND p.category = %s"
        params.append(category)

    if search:
        where += " AND (p.name LIKE %s OR p.display_name LIKE %s OR p.description LIKE %s)"
        like_pattern = f"%{search}%"
        params.extend([like_pattern, like_pattern, like_pattern])

    params.extend([limit, offset])

    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
                SELECT p.id, p.name, p.display_name, p.description, p.homepage_url,
                       p.category, p.package_manager, p.created_at,
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
                "package_id": row[0],
                "name": row[1],
                "display_name": row[2],
                "description": row[3],
                "homepage_url": row[4],
                "category": row[5],
                "package_manager": row[6],
                "created_at": format_datetime(row[7]),
                "creator": build_author_dict(row[8], row[9], None),
                "avg_rating": float(row[10]),
                "reviews_count": row[11],
            }
            for row in rows
        ]


async def get_packages_count(
    category: str | None = None,
    search: str | None = None,
) -> int:
    """패키지 총 개수를 반환합니다 (페이지네이션용).

    Args:
        category: 카테고리 필터 (선택).
        search: 검색어 (선택).

    Returns:
        패키지 총 개수.
    """
    where = "1=1"
    params: list = []

    if category:
        where += " AND category = %s"
        params.append(category)

    if search:
        where += " AND (name LIKE %s OR display_name LIKE %s OR description LIKE %s)"
        like_pattern = f"%{search}%"
        params.extend([like_pattern, like_pattern, like_pattern])

    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"SELECT COUNT(*) FROM package WHERE {where}",
            params,
        )
        row = await cur.fetchone()
        return row[0] if row else 0


async def update_package(package_id: int, **kwargs: str | None) -> bool:
    """패키지 정보를 수정합니다.

    Args:
        package_id: 수정할 패키지 ID.
        **kwargs: 수정할 필드와 값.

    Returns:
        수정 성공 여부.
    """
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
            f"""
            UPDATE package
            SET {", ".join(updates)}
            WHERE id = %s
            """,
            params,
        )
        return cur.rowcount > 0
