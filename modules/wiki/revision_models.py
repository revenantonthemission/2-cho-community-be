"""revision_models: 위키 페이지 리비전 관련 데이터 모델 및 함수 모듈."""

from core.database.connection import get_cursor
from core.utils.formatters import format_datetime


async def get_next_revision_number(cursor, wiki_page_id: int) -> int:
    """다음 리비전 번호를 반환합니다. 트랜잭션 내에서 FOR UPDATE 잠금을 사용하여 경쟁 조건을 방지합니다."""
    await cursor.execute(
        "SELECT COALESCE(MAX(revision_number), 0) + 1 AS next_rev "
        "FROM wiki_page_revision WHERE wiki_page_id = %s FOR UPDATE",
        (wiki_page_id,),
    )
    row = await cursor.fetchone()
    return row["next_rev"]


async def create_revision(
    cursor,
    wiki_page_id: int,
    revision_number: int,
    title: str,
    content: str,
    edit_summary: str,
    editor_id: int,
) -> int:
    """위키 리비전을 생성합니다. 기존 트랜잭션의 커서를 사용합니다."""
    await cursor.execute(
        "INSERT INTO wiki_page_revision "
        "(wiki_page_id, revision_number, title, content, edit_summary, editor_id) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (wiki_page_id, revision_number, title, content, edit_summary, editor_id),
    )
    return cursor.lastrowid


async def get_revisions(wiki_page_id: int, offset: int, limit: int) -> list[dict]:
    """위키 페이지의 리비전 목록을 조회합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            """
                SELECT wpr.revision_number, wpr.edit_summary, wpr.created_at,
                       u.id AS user_id, u.nickname, u.distro
                FROM wiki_page_revision wpr
                LEFT JOIN user u ON wpr.editor_id = u.id
                WHERE wpr.wiki_page_id = %s
                ORDER BY wpr.revision_number DESC
                LIMIT %s OFFSET %s
                """,
            (wiki_page_id, limit, offset),
        )
        rows = await cur.fetchall()
        return [
            {
                "revision_number": row["revision_number"],
                "editor": {
                    "user_id": row["user_id"],
                    "nickname": row["nickname"],
                    "distro": row["distro"],
                },
                "edit_summary": row["edit_summary"],
                "created_at": format_datetime(row["created_at"]),
            }
            for row in rows
        ]


async def get_revisions_count(wiki_page_id: int) -> int:
    """위키 페이지의 리비전 총 개수를 반환합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT COUNT(*) AS cnt FROM wiki_page_revision WHERE wiki_page_id = %s",
            (wiki_page_id,),
        )
        row = await cur.fetchone()
        return row["cnt"] if row else 0


async def get_revision(wiki_page_id: int, revision_number: int) -> dict | None:
    """특정 리비전의 전체 내용과 메타데이터를 조회합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            """
                SELECT wpr.revision_number, wpr.title, wpr.content,
                       wpr.edit_summary, wpr.created_at,
                       u.id AS user_id, u.nickname, u.distro
                FROM wiki_page_revision wpr
                LEFT JOIN user u ON wpr.editor_id = u.id
                WHERE wpr.wiki_page_id = %s AND wpr.revision_number = %s
                """,
            (wiki_page_id, revision_number),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return {
            "revision_number": row["revision_number"],
            "title": row["title"],
            "content": row["content"],
            "editor": {
                "user_id": row["user_id"],
                "nickname": row["nickname"],
                "distro": row["distro"],
            },
            "edit_summary": row["edit_summary"],
            "created_at": format_datetime(row["created_at"]),
        }


async def get_current_revision_number(wiki_page_id: int) -> int:
    """위키 페이지의 현재(최신) 리비전 번호를 반환합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT COALESCE(MAX(revision_number), 0) AS current_rev FROM wiki_page_revision WHERE wiki_page_id = %s",
            (wiki_page_id,),
        )
        row = await cur.fetchone()
        return row["current_rev"]
