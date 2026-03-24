"""bookmark_models: 북마크 관련 데이터 모델 및 함수 모듈.

post_like 패턴을 미러링합니다:
- transactional() 내에서 INSERT+SELECT 원자적 처리
- IntegrityError는 모델에서 catch하지 않고 컨트롤러로 전파
"""

from dataclasses import dataclass
from datetime import datetime

from core.database.connection import get_connection, transactional


@dataclass
class Bookmark:
    """북마크 데이터 클래스."""

    id: int
    user_id: int
    post_id: int
    created_at: datetime


def _row_to_bookmark(row: tuple) -> Bookmark:
    """데이터베이스 행을 Bookmark 객체로 변환합니다."""
    return Bookmark(
        id=row[0],
        user_id=row[1],
        post_id=row[2],
        created_at=row[3],
    )


async def get_bookmark(post_id: int, user_id: int) -> Bookmark | None:
    """특정 사용자가 특정 게시글에 추가한 북마크를 조회합니다."""
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
                SELECT id, user_id, post_id, created_at
                FROM post_bookmark
                WHERE post_id = %s AND user_id = %s
                """,
            (post_id, user_id),
        )
        row = await cur.fetchone()
        return _row_to_bookmark(row) if row else None


async def get_post_bookmarks_count(post_id: int) -> int:
    """게시글의 북마크 수를 조회합니다."""
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT COUNT(*) FROM post_bookmark WHERE post_id = %s",
            (post_id,),
        )
        row = await cur.fetchone()
        return row[0] if row else 0


async def add_bookmark(post_id: int, user_id: int) -> Bookmark:
    """게시글을 북마크에 추가합니다.

    Raises:
        IntegrityError: 이미 북마크한 경우 (중복 Unique constraint).
    """
    async with transactional() as cur:
        await cur.execute(
            """
            INSERT INTO post_bookmark (user_id, post_id)
            VALUES (%s, %s)
            """,
            (user_id, post_id),
        )

        bookmark_id = cur.lastrowid

        await cur.execute(
            """
            SELECT id, user_id, post_id, created_at
            FROM post_bookmark
            WHERE id = %s
            """,
            (bookmark_id,),
        )
        row = await cur.fetchone()

        if not row:
            raise RuntimeError(
                f"북마크 삽입 직후 조회 실패: bookmark_id={bookmark_id}, post_id={post_id}, user_id={user_id}"
            )

        return _row_to_bookmark(row)


async def remove_bookmark(post_id: int, user_id: int) -> bool:
    """북마크를 해제합니다.

    Returns:
        해제 성공 여부.
    """
    async with transactional() as cur:
        await cur.execute(
            """
            DELETE FROM post_bookmark
            WHERE post_id = %s AND user_id = %s
            """,
            (post_id, user_id),
        )
        return cur.rowcount > 0
