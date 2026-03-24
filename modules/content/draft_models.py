"""draft_models: 게시글 임시저장 모델.

사용자당 최대 1개의 임시저장을 관리합니다 (UPSERT).
"""

from core.database.connection import get_cursor, transactional
from core.utils.formatters import format_datetime


async def get_draft(user_id: int) -> dict | None:
    """사용자의 임시저장을 조회합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT id AS draft_id, title, content, category_id, updated_at FROM post_draft WHERE user_id = %s",
            (user_id,),
        )
        row = await cur.fetchone()

    if not row:
        return None

    return {
        "draft_id": row["draft_id"],
        "title": row["title"],
        "content": row["content"],
        "category_id": row["category_id"],
        "updated_at": format_datetime(row["updated_at"]),
    }


async def save_draft(
    user_id: int,
    title: str | None = None,
    content: str | None = None,
    category_id: int | None = None,
) -> dict:
    """임시저장을 생성하거나 갱신합니다 (UPSERT)."""
    async with transactional() as cur:
        await cur.execute(
            """
            INSERT INTO post_draft (user_id, title, content, category_id)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                title = VALUES(title),
                content = VALUES(content),
                category_id = VALUES(category_id)
            """,
            (user_id, title, content, category_id),
        )

        await cur.execute(
            "SELECT id AS draft_id, title, content, category_id, updated_at FROM post_draft WHERE user_id = %s",
            (user_id,),
        )
        row = await cur.fetchone()

    return {
        "draft_id": row["draft_id"],
        "title": row["title"],
        "content": row["content"],
        "category_id": row["category_id"],
        "updated_at": format_datetime(row["updated_at"]),
    }


async def delete_draft(user_id: int) -> bool:
    """임시저장을 삭제합니다."""
    async with transactional() as cur:
        await cur.execute("DELETE FROM post_draft WHERE user_id = %s", (user_id,))
        return cur.rowcount > 0
