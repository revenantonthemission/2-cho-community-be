"""tag_models: 태그 관련 데이터 모델 및 함수 모듈."""

import re

from core.database.connection import get_cursor, transactional
from core.utils.pagination import escape_like

_TAG_NAME_RE = re.compile(r"[^a-z0-9가-힣ㄱ-ㅎㅏ-ㅣ_-]")


def normalize_tag_name(name: str) -> str:
    """태그 이름을 정규화합니다. 소문자 변환, 공백/특수문자 제거."""
    return _TAG_NAME_RE.sub("", name.strip().lower())


async def get_or_create_tags(tag_names: list[str]) -> list[int]:
    """태그 이름 목록에 대해 존재하지 않는 태그는 생성하고 ID 목록을 반환합니다."""
    if not tag_names:
        return []
    tag_ids: list[int] = []
    for name in tag_names:
        async with transactional() as cur:
            await cur.execute("INSERT IGNORE INTO tag (name) VALUES (%s)", (name,))
            await cur.execute("SELECT id FROM tag WHERE name = %s", (name,))
            row = await cur.fetchone()
            assert row is not None
            tag_ids.append(row["id"])
    return tag_ids


async def save_post_tags(post_id: int, tag_ids: list[int]) -> None:
    """게시글의 태그를 교체합니다."""
    async with transactional() as cur:
        await cur.execute("DELETE FROM post_tag WHERE post_id = %s", (post_id,))
        for tag_id in tag_ids:
            await cur.execute(
                "INSERT IGNORE INTO post_tag (post_id, tag_id) VALUES (%s, %s)",
                (post_id, tag_id),
            )


async def get_post_tags(post_id: int) -> list[dict]:
    """게시글의 태그 목록을 조회합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT t.id, t.name FROM tag t INNER JOIN post_tag pt"
            " ON t.id = pt.tag_id WHERE pt.post_id = %s ORDER BY t.name ASC",
            (post_id,),
        )
        return [dict(row) for row in await cur.fetchall()]


async def get_posts_tags(post_ids: list[int]) -> dict[int, list[dict]]:
    """여러 게시글의 태그를 벌크 조회합니다."""
    if not post_ids:
        return {}
    async with get_cursor() as cur:
        placeholders = ", ".join(["%s"] * len(post_ids))
        await cur.execute(
            f"SELECT pt.post_id, t.id, t.name FROM post_tag pt INNER JOIN tag t"
            f" ON pt.tag_id = t.id WHERE pt.post_id IN ({placeholders}) ORDER BY t.name ASC",
            post_ids,
        )
        result: dict[int, list[dict]] = {pid: [] for pid in post_ids}
        for row in await cur.fetchall():
            result[row["post_id"]].append({"id": row["id"], "name": row["name"]})
        return result


async def search_tags(search: str, limit: int = 10) -> list[dict]:
    """태그 자동완성 검색. 게시글 수 포함."""
    async with get_cursor() as cur:
        await cur.execute(
            """
                SELECT t.id, t.name, COUNT(pt.post_id) AS post_count
                FROM tag t
                LEFT JOIN post_tag pt ON t.id = pt.tag_id
                LEFT JOIN post p ON pt.post_id = p.id AND p.deleted_at IS NULL
                WHERE t.name LIKE %s
                GROUP BY t.id, t.name
                ORDER BY post_count DESC, t.name ASC
                LIMIT %s
                """,
            (f"%{escape_like(search)}%", limit),
        )
        return [dict(row) for row in await cur.fetchall()]
