"""wiki_models: 위키 페이지 관련 데이터 모델 및 함수 모듈."""

from core.database.connection import get_cursor, transactional
from core.utils.formatters import format_datetime
from schemas.common import build_author_dict

ALLOWED_SORT_OPTIONS = {
    "latest": "wp.created_at DESC",
    "views": "wp.views_count DESC, wp.created_at DESC",
    "updated": "COALESCE(wp.updated_at, wp.created_at) DESC",
}


async def create_wiki_page(title: str, slug: str, content: str, author_id: int) -> int:
    """새 위키 페이지를 생성합니다."""
    async with transactional() as cur:
        await cur.execute(
            "INSERT INTO wiki_page (title, slug, content, author_id) VALUES (%s, %s, %s, %s)",
            (title, slug, content, author_id),
        )
        return cur.lastrowid


async def get_wiki_page_by_slug(slug: str) -> dict | None:
    """슬러그로 위키 페이지를 상세 조회합니다 (작성자·편집자 정보 포함)."""
    async with get_cursor() as cur:
        await cur.execute(
            """
                SELECT wp.id AS wiki_page_id, wp.title, wp.slug, wp.content,
                       wp.author_id, wp.last_edited_by, wp.views_count,
                       wp.created_at, wp.updated_at,
                       u.nickname AS author_nickname, u.profile_img AS author_profile_img,
                       u.distro AS author_distro,
                       ed.nickname AS editor_nickname
                FROM wiki_page wp
                LEFT JOIN user u ON wp.author_id = u.id
                LEFT JOIN user ed ON wp.last_edited_by = ed.id
                WHERE wp.slug = %s AND wp.deleted_at IS NULL
                """,
            (slug,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return {
            "wiki_page_id": row["wiki_page_id"],
            "title": row["title"],
            "slug": row["slug"],
            "content": row["content"],
            "author_id": row["author_id"],
            "last_edited_by": row["last_edited_by"],
            "views_count": row["views_count"],
            "created_at": format_datetime(row["created_at"]),
            "updated_at": format_datetime(row["updated_at"]),
            "author": build_author_dict(
                row["author_id"],
                row["author_nickname"],
                row["author_profile_img"],
                row["author_distro"],
            ),
            "editor_nickname": row["editor_nickname"],
        }


async def slug_exists(slug: str, exclude_id: int | None = None) -> bool:
    """슬러그 중복 여부를 확인합니다."""
    async with get_cursor() as cur:
        if exclude_id is not None:
            await cur.execute(
                "SELECT 1 FROM wiki_page WHERE slug = %s AND id != %s AND deleted_at IS NULL LIMIT 1",
                (slug, exclude_id),
            )
        else:
            await cur.execute(
                "SELECT 1 FROM wiki_page WHERE slug = %s AND deleted_at IS NULL LIMIT 1",
                (slug,),
            )
        return await cur.fetchone() is not None


async def get_wiki_pages(
    offset: int = 0,
    limit: int = 10,
    sort: str = "latest",
    search: str | None = None,
    tag: str | None = None,
) -> list[dict]:
    """위키 페이지 목록을 조회합니다."""
    sort_clause = ALLOWED_SORT_OPTIONS.get(sort, ALLOWED_SORT_OPTIONS["latest"])

    joins = "LEFT JOIN user u ON wp.author_id = u.id"
    where = "wp.deleted_at IS NULL"
    params: list = []

    if tag:
        joins += " INNER JOIN wiki_page_tag wpt ON wp.id = wpt.wiki_page_id INNER JOIN tag t ON wpt.tag_id = t.id"
        where += " AND t.name = %s"
        params.append(tag)

    if search:
        where += " AND MATCH(wp.title, wp.content) AGAINST(%s IN BOOLEAN MODE)"
        params.append(search)

    params.extend([limit, offset])

    async with get_cursor() as cur:
        await cur.execute(
            f"""
                SELECT wp.id AS wiki_page_id, wp.title, wp.slug, wp.views_count,
                       wp.created_at, wp.updated_at,
                       u.id AS author_id, u.nickname, u.profile_img, u.distro
                FROM wiki_page wp
                {joins}
                WHERE {where}
                ORDER BY {sort_clause}
                LIMIT %s OFFSET %s
                """,
            params,
        )
        rows = await cur.fetchall()

        return [
            {
                "wiki_page_id": row["wiki_page_id"],
                "title": row["title"],
                "slug": row["slug"],
                "views_count": row["views_count"],
                "created_at": format_datetime(row["created_at"]),
                "updated_at": format_datetime(row["updated_at"]),
                "author": build_author_dict(
                    row["author_id"],
                    row["nickname"],
                    row["profile_img"],
                    row["distro"],
                ),
            }
            for row in rows
        ]


async def get_wiki_pages_count(search: str | None = None, tag: str | None = None) -> int:
    """위키 페이지 총 개수를 반환합니다."""
    joins = ""
    where = "wp.deleted_at IS NULL"
    params: list = []

    if tag:
        joins += " INNER JOIN wiki_page_tag wpt ON wp.id = wpt.wiki_page_id INNER JOIN tag t ON wpt.tag_id = t.id"
        where += " AND t.name = %s"
        params.append(tag)

    if search:
        where += " AND MATCH(wp.title, wp.content) AGAINST(%s IN BOOLEAN MODE)"
        params.append(search)

    async with get_cursor() as cur:
        await cur.execute(
            f"SELECT COUNT(*) AS cnt FROM wiki_page wp {joins} WHERE {where}",
            params,
        )
        row = await cur.fetchone()
        return row["cnt"] if row else 0


async def update_wiki_page(
    wiki_page_id: int,
    editor_id: int,
    title: str | None = None,
    content: str | None = None,
) -> bool:
    """위키 페이지를 수정합니다."""
    updates = ["last_edited_by = %s"]
    params: list = [editor_id]

    if title is not None:
        updates.append("title = %s")
        params.append(title)
    if content is not None:
        updates.append("content = %s")
        params.append(content)

    params.append(wiki_page_id)

    async with transactional() as cur:
        await cur.execute(
            f"UPDATE wiki_page SET {', '.join(updates)} WHERE id = %s AND deleted_at IS NULL",
            params,
        )
        return cur.rowcount > 0


async def delete_wiki_page(wiki_page_id: int) -> bool:
    """위키 페이지를 소프트 삭제합니다."""
    async with transactional() as cur:
        await cur.execute(
            "UPDATE wiki_page SET deleted_at = CURRENT_TIMESTAMP WHERE id = %s AND deleted_at IS NULL",
            (wiki_page_id,),
        )
        return cur.rowcount > 0


async def increment_views(wiki_page_id: int) -> None:
    """위키 페이지 조회수를 1 증가시킵니다."""
    async with transactional() as cur:
        await cur.execute(
            "UPDATE wiki_page SET views_count = views_count + 1 WHERE id = %s AND deleted_at IS NULL",
            (wiki_page_id,),
        )


async def save_wiki_page_tags(wiki_page_id: int, tag_ids: list[int]) -> None:
    """위키 페이지의 태그를 교체합니다."""
    async with transactional() as cur:
        await cur.execute("DELETE FROM wiki_page_tag WHERE wiki_page_id = %s", (wiki_page_id,))
        for tag_id in tag_ids:
            await cur.execute(
                "INSERT IGNORE INTO wiki_page_tag (wiki_page_id, tag_id) VALUES (%s, %s)",
                (wiki_page_id, tag_id),
            )


async def get_popular_wiki_tags(limit: int = 10) -> list[dict]:
    """위키 페이지에서 가장 많이 사용된 태그를 반환합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            """
                SELECT t.id, t.name, COUNT(wpt.wiki_page_id) AS page_count
                FROM tag t
                INNER JOIN wiki_page_tag wpt ON t.id = wpt.tag_id
                INNER JOIN wiki_page wp ON wpt.wiki_page_id = wp.id AND wp.deleted_at IS NULL
                GROUP BY t.id, t.name
                ORDER BY page_count DESC, t.name ASC
                LIMIT %s
                """,
            (limit,),
        )
        return [dict(row) for row in await cur.fetchall()]


async def get_wiki_page_tags(wiki_page_id: int) -> list[dict]:
    """위키 페이지의 태그 목록을 조회합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            """
                SELECT t.id, t.name
                FROM tag t
                INNER JOIN wiki_page_tag wpt ON t.id = wpt.tag_id
                WHERE wpt.wiki_page_id = %s
                ORDER BY t.name ASC
                """,
            (wiki_page_id,),
        )
        return [dict(row) for row in await cur.fetchall()]


async def get_wiki_pages_tags(wiki_page_ids: list[int]) -> dict[int, list[dict]]:
    """여러 위키 페이지의 태그를 벌크 조회합니다."""
    if not wiki_page_ids:
        return {}
    async with get_cursor() as cur:
        placeholders = ", ".join(["%s"] * len(wiki_page_ids))
        await cur.execute(
            f"""
                SELECT wpt.wiki_page_id, t.id, t.name
                FROM wiki_page_tag wpt
                INNER JOIN tag t ON wpt.tag_id = t.id
                WHERE wpt.wiki_page_id IN ({placeholders})
                ORDER BY t.name ASC
                """,
            wiki_page_ids,
        )
        result: dict[int, list[dict]] = {pid: [] for pid in wiki_page_ids}
        for row in await cur.fetchall():
            result[row["wiki_page_id"]].append({"id": row["id"], "name": row["name"]})
        return result
