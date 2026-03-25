"""post_models: 게시글, 댓글, 좋아요 관련 데이터 모델 및 함수 모듈.

게시글, 댓글, 좋아요 데이터 클래스와 MySQL 데이터베이스를 관리하는 함수들을 제공합니다.
"""

import re
from dataclasses import dataclass
from datetime import datetime

from core.database.connection import get_cursor, transactional
from modules.post.comment_models import get_comments_with_author
from schemas.common import build_author_dict

# 게시글당 허용되는 최대 이미지 수
MAX_POST_IMAGES = 5

# SQL Injection 방지: 허용된 컬럼명 whitelist
ALLOWED_POST_COLUMNS = {"title", "content", "image_url", "category_id", "updated_at"}

# FULLTEXT BOOLEAN MODE 특수문자 이스케이프 패턴
_FULLTEXT_SPECIAL_CHARS = re.compile(r'([+\-><()~*"@])')


def _escape_fulltext_query(query: str) -> str:
    """FULLTEXT BOOLEAN MODE 특수문자를 이스케이프합니다."""
    return _FULLTEXT_SPECIAL_CHARS.sub(r"\\\1", query.strip())


# SQL Injection 방지: 허용된 정렬 옵션 whitelist
ALLOWED_SORT_OPTIONS = {
    "latest": "p.created_at DESC, p.id DESC",
    "likes": "likes_count DESC, p.created_at DESC",
    "views": "p.views DESC, p.created_at DESC",
    "comments": "comments_count DESC, p.created_at DESC",
    "hot": "hot_score DESC, p.created_at DESC",
    "for_you": "COALESCE(upc.combined_score, 0) DESC, p.created_at DESC",
}


@dataclass
class Post:
    """게시글 데이터 클래스."""

    id: int
    author_id: int
    title: str
    content: str
    views: int
    created_at: datetime
    updated_at: datetime | None
    deleted_at: datetime | None
    image_url: str | None = None
    category_id: int | None = None
    is_pinned: bool = False

    @property
    def is_deleted(self) -> bool:
        """게시글이 삭제되었는지 확인합니다."""
        return self.deleted_at is not None


def _row_to_post(row: dict) -> Post:
    """DictCursor 결과를 Post 객체로 변환합니다. is_pinned의 bool 변환을 보장합니다."""
    return Post(
        id=row["id"],
        title=row["title"],
        content=row["content"],
        image_url=row["image_url"],
        author_id=row["author_id"],
        category_id=row["category_id"],
        is_pinned=bool(row["is_pinned"]),
        views=row["views"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        deleted_at=row["deleted_at"],
    )


_POST_COLUMNS = (
    "id, title, content, image_url, author_id, category_id, is_pinned, views, created_at, updated_at, deleted_at"
)


# ============ 게시글 관련 함수 ============


async def get_total_posts_count(
    search: str | None = None,
    author_id: int | None = None,
    category_id: int | None = None,
    blocked_user_ids: set[int] | None = None,
    tag: str | None = None,
    author_ids: set[int] | None = None,
) -> int:
    """삭제되지 않은 게시글의 총 개수를 반환합니다."""
    async with get_cursor() as cur:
        where = "deleted_at IS NULL"
        params: list = []

        if search:
            escaped = _escape_fulltext_query(search)
            where += " AND MATCH(title, content) AGAINST(%s IN BOOLEAN MODE)"
            params.append(escaped)

        if author_id is not None:
            where += " AND author_id = %s"
            params.append(author_id)

        if category_id is not None:
            where += " AND category_id = %s"
            params.append(category_id)

        if blocked_user_ids:
            placeholders = ", ".join(["%s"] * len(blocked_user_ids))
            where += f" AND (author_id NOT IN ({placeholders}) OR author_id IS NULL)"
            params.extend(blocked_user_ids)

        if author_ids:
            placeholders = ", ".join(["%s"] * len(author_ids))
            where += f" AND author_id IN ({placeholders})"
            params.extend(author_ids)

        if tag:
            where += (
                " AND EXISTS (SELECT 1 FROM post_tag pt INNER JOIN tag t"
                " ON pt.tag_id = t.id WHERE pt.post_id = post.id AND t.name = %s)"
            )
            params.append(tag)

        await cur.execute(
            f"SELECT COUNT(*) AS cnt FROM post WHERE {where}",
            params,
        )
        row = await cur.fetchone()
        return row["cnt"] if row else 0


async def get_post_by_id(post_id: int) -> Post | None:
    """ID로 게시글을 조회합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            f"SELECT {_POST_COLUMNS} FROM post WHERE id = %s AND deleted_at IS NULL",
            (post_id,),
        )
        row = await cur.fetchone()
        return _row_to_post(row) if row else None


async def create_post(
    author_id: int,
    title: str,
    content: str,
    image_url: str | None = None,
    category_id: int | None = None,
) -> Post:
    """새 게시글을 생성합니다."""
    async with transactional() as cur:
        await cur.execute(
            "INSERT INTO post (title, content, image_url, author_id, category_id) VALUES (%s, %s, %s, %s, %s)",
            (title, content, image_url, author_id, category_id),
        )
        post_id = cur.lastrowid

        await cur.execute(
            f"SELECT {_POST_COLUMNS} FROM post WHERE id = %s",
            (post_id,),
        )
        row = await cur.fetchone()
        return _row_to_post(row)


async def update_post(
    post_id: int,
    title: str | None = None,
    content: str | None = None,
    image_url: str | None = None,
    category_id: int | None = None,
) -> Post | None:
    """게시글을 수정합니다."""
    updates: list[str] = []
    params: list[str | int] = []
    content_changed = False

    if title is not None:
        updates.append("title = %s")
        params.append(title)
        content_changed = True
    if content is not None:
        updates.append("content = %s")
        params.append(content)
        content_changed = True
    if image_url is not None:
        updates.append("image_url = %s")
        params.append(image_url)
    if category_id is not None:
        updates.append("category_id = %s")
        params.append(category_id)

    if not updates:
        return await get_post_by_id(post_id)

    # 제목/내용 변경 시에만 수정 시간 기록
    if content_changed:
        updates.append("updated_at = NOW()")

    # SQL Injection 방지: 컬럼명 검증
    for update_clause in updates:
        column_name = update_clause.split(" = ")[0]
        if column_name not in ALLOWED_POST_COLUMNS:
            raise ValueError(f"Invalid column name: {column_name}")

    async with transactional() as cur:
        await cur.execute(
            f"UPDATE post SET {', '.join(updates)} WHERE id = %s AND deleted_at IS NULL",
            (*params, post_id),
        )

        if cur.rowcount == 0:
            return None

        await cur.execute(
            f"SELECT {_POST_COLUMNS} FROM post WHERE id = %s",
            (post_id,),
        )
        row = await cur.fetchone()
        return _row_to_post(row) if row else None


async def delete_post(post_id: int) -> bool:
    """게시글을 삭제합니다. 소프트 삭제를 수행하여 deleted_at을 현재 시간으로 설정합니다."""
    async with transactional() as cur:
        await cur.execute(
            "UPDATE post SET deleted_at = NOW() WHERE id = %s AND deleted_at IS NULL",
            (post_id,),
        )
        return cur.rowcount > 0


async def increment_view_count(post_id: int, user_id: int) -> bool:
    """게시글 조회수를 증가시킵니다. 하루에 한 번만 조회수가 증가합니다."""
    async with transactional() as cur:
        await cur.execute(
            "INSERT IGNORE INTO post_view_log (user_id, post_id) VALUES (%s, %s)",
            (user_id, post_id),
        )
        if cur.rowcount > 0:
            await cur.execute(
                "UPDATE post SET views = views + 1 WHERE id = %s",
                (post_id,),
            )
            return True
        return False


async def get_read_post_ids(user_id: int, post_ids: list[int]) -> set[int]:
    """사용자가 조회한 게시글 ID 집합을 반환합니다."""
    if not post_ids:
        return set()
    async with get_cursor() as cur:
        placeholders = ", ".join(["%s"] * len(post_ids))
        await cur.execute(
            f"SELECT DISTINCT post_id FROM post_view_log WHERE user_id = %s AND post_id IN ({placeholders})",
            [user_id, *post_ids],
        )
        return {row["post_id"] for row in await cur.fetchall()}


async def get_posts_with_details(
    offset: int = 0,
    limit: int = 10,
    search: str | None = None,
    sort: str = "latest",
    author_id: int | None = None,
    category_id: int | None = None,
    blocked_user_ids: set[int] | None = None,
    tag: str | None = None,
    author_ids: set[int] | None = None,
    current_user_id: int | None = None,
) -> list[dict]:
    """게시글 목록을 작성자 정보, 좋아요 수, 댓글 수, 북마크 수와 함께 조회합니다."""
    # SQL Injection 방지: whitelist 검증 후 fallback
    order_by = ALLOWED_SORT_OPTIONS.get(sort, ALLOWED_SORT_OPTIONS["latest"])

    where = "p.deleted_at IS NULL"
    params: list = []

    if search:
        escaped = _escape_fulltext_query(search)
        where += " AND MATCH(p.title, p.content) AGAINST(%s IN BOOLEAN MODE)"
        params.append(escaped)

    if author_id is not None:
        where += " AND p.author_id = %s"
        params.append(author_id)

    if category_id is not None:
        where += " AND p.category_id = %s"
        params.append(category_id)

    if blocked_user_ids:
        placeholders = ", ".join(["%s"] * len(blocked_user_ids))
        where += f" AND (p.author_id NOT IN ({placeholders}) OR p.author_id IS NULL)"
        params.extend(blocked_user_ids)

    if author_ids:
        placeholders = ", ".join(["%s"] * len(author_ids))
        where += f" AND p.author_id IN ({placeholders})"
        params.extend(author_ids)

    if tag:
        where += (
            " AND EXISTS (SELECT 1 FROM post_tag pt INNER JOIN tag t"
            " ON pt.tag_id = t.id WHERE pt.post_id = p.id AND t.name = %s)"
        )
        params.append(tag)

    # 추천 피드 JOIN 처리 (current_user_id 없으면 latest 폴백)
    upc_join = ""
    upc_select = ""
    join_params: list = []
    if sort == "for_you" and current_user_id is not None:
        upc_join = "LEFT JOIN user_post_score upc ON p.id = upc.post_id AND upc.user_id = %s"
        upc_select = ", COALESCE(upc.combined_score, 0) AS combined_score"
        join_params = [current_user_id]
    elif sort == "for_you":
        sort = "latest"

    # 구독 watching 상태 JOIN (로그인 사용자만)
    watch_join = ""
    watch_select = ", 0 AS is_watching"
    watch_params: list = []
    if current_user_id is not None:
        watch_join = (
            "LEFT JOIN post_subscription ps_watch "
            "ON ps_watch.post_id = p.id AND ps_watch.user_id = %s AND ps_watch.level = 'watching'"
        )
        watch_select = ", IF(ps_watch.user_id IS NOT NULL, 1, 0) AS is_watching"
        watch_params = [current_user_id]

    params.extend([limit, offset])

    async with get_cursor() as cur:
        await cur.execute(
            f"""
                SELECT
                    p.id AS post_id, p.title, p.content, p.image_url, p.views AS views_count,
                    p.created_at, p.updated_at,
                    u.id AS author_user_id, u.nickname AS author_nickname,
                    u.profile_img AS author_profile_img, u.distro AS author_distro,
                    COALESCE(likes.cnt, 0) AS likes_count,
                    COALESCE(comments.cnt, 0) AS comments_count,
                    p.is_pinned, p.category_id, cat.name AS category_name,
                    COALESCE(bk.cnt, 0) AS bookmarks_count,
                    (COALESCE(likes.cnt, 0) * 3
                     + COALESCE(comments.cnt, 0) * 2
                     + p.views * 0.5)
                    / POW(TIMESTAMPDIFF(HOUR, p.created_at, NOW()) + 2, 1.5)
                    AS hot_score
                    {watch_select}
                    {upc_select}
                FROM post p
                LEFT JOIN user u ON p.author_id = u.id
                LEFT JOIN category cat ON p.category_id = cat.id
                LEFT JOIN (
                    SELECT post_id, COUNT(*) AS cnt
                    FROM post_like
                    GROUP BY post_id
                ) likes ON p.id = likes.post_id
                LEFT JOIN (
                    SELECT post_id, COUNT(*) AS cnt
                    FROM comment
                    WHERE deleted_at IS NULL
                    GROUP BY post_id
                ) comments ON p.id = comments.post_id
                LEFT JOIN (
                    SELECT post_id, COUNT(*) AS cnt
                    FROM post_bookmark
                    GROUP BY post_id
                ) bk ON p.id = bk.post_id
                {watch_join}
                {upc_join}
                WHERE {where}
                ORDER BY p.is_pinned DESC, {order_by}
                LIMIT %s OFFSET %s
                """,
            [*watch_params, *join_params, *params],
        )
        rows = await cur.fetchall()

        return [
            {
                "post_id": row["post_id"],
                "title": row["title"],
                "content": row["content"],
                "image_url": row["image_url"],
                "views_count": row["views_count"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "author": build_author_dict(
                    row["author_user_id"],
                    row["author_nickname"],
                    row["author_profile_img"],
                    row["author_distro"],
                ),
                "likes_count": row["likes_count"],
                "comments_count": row["comments_count"],
                "is_pinned": bool(row["is_pinned"]),
                "category_id": row["category_id"],
                "category_name": row["category_name"],
                "bookmarks_count": row["bookmarks_count"],
                "is_watching": bool(row.get("is_watching", 0)),
            }
            for row in rows
        ]


async def get_post_with_details(post_id: int, current_user_id: int | None = None) -> dict | None:
    """특정 게시글을 작성자 정보, 좋아요 수, 북마크 수와 함께 조회합니다."""
    # 구독 watching 상태 JOIN (로그인 사용자만)
    watch_join = ""
    watch_select = ", 0 AS is_watching"
    watch_params: list = []
    if current_user_id is not None:
        watch_join = (
            "LEFT JOIN post_subscription ps_watch "
            "ON ps_watch.post_id = p.id AND ps_watch.user_id = %s AND ps_watch.level = 'watching'"
        )
        watch_select = ", IF(ps_watch.user_id IS NOT NULL, 1, 0) AS is_watching"
        watch_params = [current_user_id]

    async with get_cursor() as cur:
        await cur.execute(
            f"""
                SELECT p.id AS post_id, p.title, p.content, p.image_url,
                       p.views AS views_count, p.created_at, p.updated_at,
                       p.accepted_answer_id,
                       u.id AS author_user_id, u.nickname AS author_nickname,
                       u.profile_img AS author_profile_img, u.distro AS author_distro,
                       (SELECT COUNT(*) FROM post_like WHERE post_id = p.id) AS likes_count,
                       p.is_pinned, p.category_id, cat.name AS category_name,
                       (SELECT COUNT(*) FROM post_bookmark WHERE post_id = p.id) AS bookmarks_count
                       {watch_select}
                FROM post p
                LEFT JOIN user u ON p.author_id = u.id
                LEFT JOIN category cat ON p.category_id = cat.id
                {watch_join}
                WHERE p.id = %s AND p.deleted_at IS NULL
                """,
            [*watch_params, post_id],
        )
        row = await cur.fetchone()

        if not row:
            return None

        return {
            "post_id": row["post_id"],
            "title": row["title"],
            "content": row["content"],
            "image_url": row["image_url"],
            "views_count": row["views_count"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "accepted_answer_id": row.get("accepted_answer_id"),
            "author": build_author_dict(
                row["author_user_id"],
                row["author_nickname"],
                row["author_profile_img"],
                row["author_distro"],
            ),
            "likes_count": row["likes_count"],
            "is_pinned": bool(row["is_pinned"]),
            "category_id": row["category_id"],
            "category_name": row["category_name"],
            "bookmarks_count": row["bookmarks_count"],
            "is_watching": bool(row.get("is_watching", 0)),
        }


async def set_accepted_answer(post_id: int, comment_id: int) -> bool:
    """답변 채택 설정."""
    async with transactional() as cur:
        await cur.execute(
            "UPDATE post SET accepted_answer_id = %s WHERE id = %s AND deleted_at IS NULL",
            (comment_id, post_id),
        )
        return cur.rowcount > 0


async def unset_accepted_answer(post_id: int) -> bool:
    """답변 채택 해제."""
    async with transactional() as cur:
        await cur.execute(
            "UPDATE post SET accepted_answer_id = NULL WHERE id = %s AND deleted_at IS NULL",
            (post_id,),
        )
        return cur.rowcount > 0


async def get_comment_for_accept_validation(comment_id: int, post_id: int) -> dict | None:
    """채택 검증용 댓글 조회."""
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT id, post_id, parent_id FROM comment WHERE id = %s AND post_id = %s AND deleted_at IS NULL",
            (comment_id, post_id),
        )
        return await cur.fetchone()


async def pin_post(post_id: int) -> bool:
    """게시글을 고정합니다."""
    async with transactional() as cur:
        await cur.execute(
            "UPDATE post SET is_pinned = 1 WHERE id = %s AND deleted_at IS NULL",
            (post_id,),
        )
        return cur.rowcount > 0


async def unpin_post(post_id: int) -> bool:
    """게시글 고정을 해제합니다."""
    async with transactional() as cur:
        await cur.execute(
            "UPDATE post SET is_pinned = 0 WHERE id = %s AND deleted_at IS NULL",
            (post_id,),
        )
        return cur.rowcount > 0


# ============ 게시글 이미지 관련 함수 ============


async def save_post_images(post_id: int, image_urls: list[str]) -> None:
    """게시글 이미지를 저장합니다. 기존 이미지를 모두 삭제하고 새 이미지를 순서대로 삽입합니다."""
    async with transactional() as cur:
        await cur.execute("DELETE FROM post_image WHERE post_id = %s", (post_id,))
        for idx, url in enumerate(image_urls[:MAX_POST_IMAGES]):
            await cur.execute(
                "INSERT INTO post_image (post_id, image_url, sort_order) VALUES (%s, %s, %s)",
                (post_id, url, idx),
            )


async def get_post_images(post_id: int) -> list[dict]:
    """게시글의 이미지 목록을 순서대로 반환합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT id, image_url, sort_order FROM post_image WHERE post_id = %s ORDER BY sort_order",
            (post_id,),
        )
        return [dict(row) for row in await cur.fetchall()]


async def get_related_posts(
    current_post_id: int,
    category_id: int | None,
    tag_ids: list[int],
    limit: int = 5,
    blocked_user_ids: set[int] | None = None,
) -> list[dict]:
    """현재 게시글과 관련된 게시글을 태그/카테고리 기반으로 조회합니다."""
    where = "p.deleted_at IS NULL AND p.id != %s"
    params: list = [current_post_id]

    if blocked_user_ids:
        placeholders = ", ".join(["%s"] * len(blocked_user_ids))
        where += f" AND (p.author_id NOT IN ({placeholders}) OR p.author_id IS NULL)"
        params.extend(blocked_user_ids)

    if tag_ids:
        tag_placeholders = ", ".join(["%s"] * len(tag_ids))
        tag_join = f"LEFT JOIN post_tag pt ON p.id = pt.post_id AND pt.tag_id IN ({tag_placeholders})"
        tag_select = "COUNT(pt.tag_id) AS matched_tags"
        tag_params = list(tag_ids)
    else:
        tag_join = ""
        tag_select = "0 AS matched_tags"
        tag_params = []

    if category_id is not None:
        same_category = "CASE WHEN p.category_id = %s THEN 1 ELSE 0 END AS same_category"
        cat_params = [category_id]
    else:
        same_category = "0 AS same_category"
        cat_params = []

    params.extend([limit])

    async with get_cursor() as cur:
        await cur.execute(
            f"""
                SELECT
                    p.id AS post_id, p.title, p.content, p.image_url,
                    p.views AS views_count,
                    p.created_at, p.updated_at,
                    u.id AS author_user_id, u.nickname AS author_nickname,
                    u.profile_img AS author_profile_img, u.distro AS author_distro,
                    COALESCE(likes.cnt, 0) AS likes_count,
                    COALESCE(comments.cnt, 0) AS comments_count,
                    p.is_pinned, p.category_id, cat.name AS category_name,
                    COALESCE(bk.cnt, 0) AS bookmarks_count,
                    {tag_select},
                    {same_category},
                    (COALESCE(likes.cnt, 0) * 3
                     + COALESCE(comments.cnt, 0) * 2
                     + p.views * 0.5)
                    / POW(TIMESTAMPDIFF(HOUR, p.created_at, NOW()) + 2, 1.5)
                    AS hot_score
                FROM post p
                LEFT JOIN user u ON p.author_id = u.id
                LEFT JOIN category cat ON p.category_id = cat.id
                {tag_join}
                LEFT JOIN (
                    SELECT post_id, COUNT(*) AS cnt
                    FROM post_like
                    GROUP BY post_id
                ) likes ON p.id = likes.post_id
                LEFT JOIN (
                    SELECT post_id, COUNT(*) AS cnt
                    FROM comment
                    WHERE deleted_at IS NULL
                    GROUP BY post_id
                ) comments ON p.id = comments.post_id
                LEFT JOIN (
                    SELECT post_id, COUNT(*) AS cnt
                    FROM post_bookmark
                    GROUP BY post_id
                ) bk ON p.id = bk.post_id
                WHERE {where}
                GROUP BY p.id
                ORDER BY matched_tags DESC, same_category DESC, hot_score DESC
                LIMIT %s
                """,
            [*cat_params, *tag_params, *params],
        )
        rows = await cur.fetchall()

        return [
            {
                "post_id": row["post_id"],
                "title": row["title"],
                "content": row["content"],
                "image_url": row["image_url"],
                "views_count": row["views_count"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "author": build_author_dict(
                    row["author_user_id"],
                    row["author_nickname"],
                    row["author_profile_img"],
                    row["author_distro"],
                ),
                "likes_count": row["likes_count"],
                "comments_count": row["comments_count"],
                "is_pinned": bool(row["is_pinned"]),
                "category_id": row["category_id"],
                "category_name": row["category_name"],
                "bookmarks_count": row["bookmarks_count"],
            }
            for row in rows
        ]


# get_comments_with_author는 comment_models.py에서 정의됨 (상단 import 참조)
# 하위 호환성을 위해 다시 내보내기
__all__ = [
    "ALLOWED_POST_COLUMNS",
    "ALLOWED_SORT_OPTIONS",
    "MAX_POST_IMAGES",
    "Post",
    "create_post",
    "delete_post",
    "get_comment_for_accept_validation",
    "get_comments_with_author",
    "get_post_by_id",
    "get_post_images",
    "get_post_with_details",
    "get_posts_with_details",
    "get_read_post_ids",
    "get_related_posts",
    "get_total_posts_count",
    "increment_view_count",
    "pin_post",
    "save_post_images",
    "set_accepted_answer",
    "unpin_post",
    "unset_accepted_answer",
    "update_post",
]
