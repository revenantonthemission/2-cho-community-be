"""package_review_models: 패키지 리뷰 관련 데이터 모델 및 함수 모듈."""

from database.connection import get_connection, transactional
from schemas.common import DEFAULT_PROFILE_IMAGE
from utils.formatters import format_datetime


# SQL Injection 방지: 허용된 리뷰 정렬 옵션 whitelist
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
    """패키지 리뷰를 생성합니다.

    UNIQUE KEY (package_id, user_id)에 의해 중복 리뷰 시 IntegrityError가 발생합니다.
    IntegrityError는 컨트롤러에서 처리합니다.

    Args:
        package_id: 패키지 ID.
        user_id: 작성자 ID.
        rating: 평점 (1~5).
        title: 리뷰 제목.
        content: 리뷰 내용.

    Returns:
        생성된 리뷰 ID.
    """
    async with transactional() as cur:
        await cur.execute(
            """
            INSERT INTO package_review (package_id, user_id, rating, title, content)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (package_id, user_id, rating, title, content),
        )
        return cur.lastrowid


async def get_review_by_id(review_id: int) -> dict | None:
    """리뷰를 작성자 정보와 함께 조회합니다.

    Args:
        review_id: 조회할 리뷰 ID.

    Returns:
        리뷰 딕셔너리, 없거나 삭제된 경우 None.
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT pr.id, pr.package_id, pr.rating, pr.title, pr.content,
                       pr.created_at, pr.updated_at,
                       u.id, u.nickname, u.profile_img, u.distro
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
                "review_id": row[0],
                "package_id": row[1],
                "rating": row[2],
                "title": row[3],
                "content": row[4],
                "created_at": format_datetime(row[5]),
                "updated_at": format_datetime(row[6]),
                "author": {
                    "user_id": row[7],
                    "nickname": row[8],
                    "profileImageUrl": row[9] or DEFAULT_PROFILE_IMAGE,
                    "distro": row[10],
                },
            }


async def get_reviews_by_package(
    package_id: int,
    offset: int = 0,
    limit: int = 10,
    sort: str = "latest",
) -> list[dict]:
    """패키지의 리뷰 목록을 작성자 정보와 함께 조회합니다.

    Args:
        package_id: 패키지 ID.
        offset: 시작 위치.
        limit: 조회할 개수.
        sort: 정렬 옵션 (latest, oldest, highest, lowest).

    Returns:
        리뷰 딕셔너리 목록.
    """
    sort_clause = ALLOWED_REVIEW_SORT_OPTIONS.get(
        sort, ALLOWED_REVIEW_SORT_OPTIONS["latest"]
    )

    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f"""
                SELECT pr.id, pr.rating, pr.title, pr.content,
                       pr.created_at, pr.updated_at,
                       u.id, u.nickname, u.profile_img, u.distro
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
                    "review_id": row[0],
                    "rating": row[1],
                    "title": row[2],
                    "content": row[3],
                    "created_at": format_datetime(row[4]),
                    "updated_at": format_datetime(row[5]),
                    "author": {
                        "user_id": row[6],
                        "nickname": row[7],
                        "profileImageUrl": row[8] or DEFAULT_PROFILE_IMAGE,
                        "distro": row[9],
                    },
                }
                for row in rows
            ]


async def get_reviews_count(package_id: int) -> int:
    """패키지의 리뷰 수를 조회합니다.

    Args:
        package_id: 패키지 ID.

    Returns:
        리뷰 수.
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT COUNT(*) FROM package_review
                WHERE package_id = %s AND deleted_at IS NULL
                """,
                (package_id,),
            )
            row = await cur.fetchone()
            return row[0] if row else 0


async def get_user_review(package_id: int, user_id: int) -> dict | None:
    """사용자가 특정 패키지에 작성한 리뷰를 조회합니다.

    Args:
        package_id: 패키지 ID.
        user_id: 사용자 ID.

    Returns:
        리뷰 딕셔너리, 없으면 None.
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT pr.id, pr.rating, pr.title, pr.content,
                       pr.created_at, pr.updated_at
                FROM package_review pr
                WHERE pr.package_id = %s AND pr.user_id = %s AND pr.deleted_at IS NULL
                """,
                (package_id, user_id),
            )
            row = await cur.fetchone()
            if not row:
                return None
            return {
                "review_id": row[0],
                "rating": row[1],
                "title": row[2],
                "content": row[3],
                "created_at": format_datetime(row[4]),
                "updated_at": format_datetime(row[5]),
            }


async def update_review(
    review_id: int,
    rating: int | None = None,
    title: str | None = None,
    content: str | None = None,
) -> bool:
    """리뷰를 수정합니다.

    Args:
        review_id: 수정할 리뷰 ID.
        rating: 새 평점 (선택).
        title: 새 제목 (선택).
        content: 새 내용 (선택).

    Returns:
        수정 성공 여부.
    """
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
            f"""
            UPDATE package_review
            SET {", ".join(updates)}
            WHERE id = %s AND deleted_at IS NULL
            """,
            params,
        )
        return cur.rowcount > 0


async def delete_review(review_id: int) -> bool:
    """리뷰를 소프트 삭제합니다.

    Args:
        review_id: 삭제할 리뷰 ID.

    Returns:
        삭제 성공 여부.
    """
    async with transactional() as cur:
        await cur.execute(
            """
            UPDATE package_review
            SET deleted_at = NOW()
            WHERE id = %s AND deleted_at IS NULL
            """,
            (review_id,),
        )
        return cur.rowcount > 0
