"""comment_like_models: 댓글 좋아요 관련 데이터 모델 및 함수 모듈.

post_like 패턴을 미러링합니다.
"""

from dataclasses import dataclass
from datetime import datetime

from core.database.connection import get_cursor, transactional


@dataclass
class CommentLike:
    """댓글 좋아요 데이터 클래스."""

    id: int
    user_id: int
    comment_id: int
    created_at: datetime


async def get_comment_like(comment_id: int, user_id: int) -> CommentLike | None:
    """특정 사용자가 특정 댓글에 남긴 좋아요를 조회합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT id, user_id, comment_id, created_at FROM comment_like WHERE comment_id = %s AND user_id = %s",
            (comment_id, user_id),
        )
        row = await cur.fetchone()
        return CommentLike(**row) if row else None


async def get_comment_likes_count(comment_id: int) -> int:
    """댓글의 좋아요 수를 조회합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT COUNT(*) AS cnt FROM comment_like WHERE comment_id = %s",
            (comment_id,),
        )
        row = await cur.fetchone()
        return row["cnt"] if row else 0


async def get_liked_comment_ids(user_id: int, post_id: int) -> set[int]:
    """특정 사용자가 특정 게시글의 댓글 중 좋아요한 댓글 ID 집합을 반환합니다.

    N+1 방지를 위한 벌크 조회.
    """
    async with get_cursor() as cur:
        await cur.execute(
            """
                SELECT cl.comment_id
                FROM comment_like cl
                JOIN comment c ON cl.comment_id = c.id
                WHERE cl.user_id = %s AND c.post_id = %s
                """,
            (user_id, post_id),
        )
        rows = await cur.fetchall()
        return {row["comment_id"] for row in rows}


async def add_comment_like(comment_id: int, user_id: int) -> CommentLike:
    """댓글에 좋아요를 추가합니다.

    Raises:
        IntegrityError: 이미 좋아요한 경우.
    """
    async with transactional() as cur:
        await cur.execute(
            "INSERT INTO comment_like (user_id, comment_id) VALUES (%s, %s)",
            (user_id, comment_id),
        )
        like_id = cur.lastrowid

        await cur.execute(
            "SELECT id, user_id, comment_id, created_at FROM comment_like WHERE id = %s",
            (like_id,),
        )
        row = await cur.fetchone()

        if not row:
            raise RuntimeError(
                f"댓글 좋아요 삽입 직후 조회 실패: like_id={like_id}, comment_id={comment_id}, user_id={user_id}"
            )

        return CommentLike(**row)


async def remove_comment_like(comment_id: int, user_id: int) -> bool:
    """댓글 좋아요를 취소합니다."""
    async with transactional() as cur:
        await cur.execute(
            "DELETE FROM comment_like WHERE comment_id = %s AND user_id = %s",
            (comment_id, user_id),
        )
        return cur.rowcount > 0
