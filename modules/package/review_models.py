"""package_review_models: 패키지 리뷰 관련 데이터 모델 및 함수 모듈."""

from core.database.connection import get_cursor, transactional
from core.utils.formatters import format_datetime
from schemas.common import DEFAULT_PROFILE_IMAGE

ALLOWED_REVIEW_SORT_OPTIONS = {
    "latest": "pr.created_at DESC",
    "oldest": "pr.created_at ASC",
    "highest": "pr.rating DESC, pr.created_at DESC",
    "lowest": "pr.rating ASC, pr.created_at DESC",
}


async def create_review(
    package_id: int,
    user_id: int,
    rating: int,
    title: str,
    content: str,
) -> int:
    """패키지 리뷰를 생성합니다. 중복 시 IntegrityError가 발생합니다."""
    async with transactional() as cur:
        await cur.execute(
            "INSERT INTO package_review (package_id, user_id, rating, title, content) VALUES (%s, %s, %s, %s, %s)",
            (package_id, user_id, rating, title, content),
        )
        return cur.lastrowid


async def get_review_by_id(review_id: int) -> dict | None:
    """리뷰를 작성자 정보와 함께 조회합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            """
                SELECT pr.id AS review_id, pr.package_id, pr.rating, pr.title,
                       pr.content, pr.created_at, pr.updated_at,
                       u.id AS user_id, u.nickname, u.profile_img, u.distro
                FROM package_review pr
                LEFT JOIN user u ON pr.user_id = u.id
                WHERE pr.id = %s AND pr.deleted_at IS NULL
                """,
            (review_id,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return {
            "review_id": row["review_id"],
            "package_id": row["package_id"],
            "rating": row["rating"],
            "title": row["title"],
            "content": row["content"],
            "created_at": format_datetime(row["created_at"]),
            "updated_at": format_datetime(row["updated_at"]),
            "author": {
                "user_id": row["user_id"],
                "nickname": row["nickname"],
                "profileImageUrl": row["profile_img"] or DEFAULT_PROFILE_IMAGE,
                "distro": row["distro"],
            },
        }


async def get_reviews_by_package(
    package_id: int,
    offset: int = 0,
    limit: int = 10,
    sort: str = "latest",
) -> list[dict]:
    """패키지의 리뷰 목록을 작성자 정보와 함께 조회합니다."""
    sort_clause = ALLOWED_REVIEW_SORT_OPTIONS.get(sort, ALLOWED_REVIEW_SORT_OPTIONS["latest"])

    async with get_cursor() as cur:
        await cur.execute(
            f"""
                SELECT pr.id AS review_id, pr.rating, pr.title, pr.content,
                       pr.created_at, pr.updated_at,
                       u.id AS user_id, u.nickname, u.profile_img, u.distro
                FROM package_review pr
                LEFT JOIN user u ON pr.user_id = u.id
                WHERE pr.package_id = %s AND pr.deleted_at IS NULL
                ORDER BY {sort_clause}
                LIMIT %s OFFSET %s
                """,
            (package_id, limit, offset),
        )
        rows = await cur.fetchall()

        return [
            {
                "review_id": row["review_id"],
                "rating": row["rating"],
                "title": row["title"],
                "content": row["content"],
                "created_at": format_datetime(row["created_at"]),
                "updated_at": format_datetime(row["updated_at"]),
                "author": {
                    "user_id": row["user_id"],
                    "nickname": row["nickname"],
                    "profileImageUrl": row["profile_img"] or DEFAULT_PROFILE_IMAGE,
                    "distro": row["distro"],
                },
            }
            for row in rows
        ]


async def get_reviews_count(package_id: int) -> int:
    """패키지의 리뷰 수를 조회합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT COUNT(*) AS cnt FROM package_review WHERE package_id = %s AND deleted_at IS NULL",
            (package_id,),
        )
        row = await cur.fetchone()
        return row["cnt"] if row else 0


async def update_review(
    review_id: int,
    rating: int | None = None,
    title: str | None = None,
    content: str | None = None,
) -> bool:
    """리뷰를 수정합니다."""
    updates: list[str] = []
    params: list = []

    if rating is not None:
        updates.append("rating = %s")
        params.append(rating)
    if title is not None:
        updates.append("title = %s")
        params.append(title)
    if content is not None:
        updates.append("content = %s")
        params.append(content)

    if not updates:
        return False

    params.append(review_id)

    async with transactional() as cur:
        await cur.execute(
            f"UPDATE package_review SET {', '.join(updates)} WHERE id = %s AND deleted_at IS NULL",
            params,
        )
        return cur.rowcount > 0


async def delete_review(review_id: int) -> bool:
    """리뷰를 소프트 삭제합니다."""
    async with transactional() as cur:
        await cur.execute(
            "UPDATE package_review SET deleted_at = NOW() WHERE id = %s AND deleted_at IS NULL",
            (review_id,),
        )
        return cur.rowcount > 0
