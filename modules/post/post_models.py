"""post_models: 게시글, 댓글, 좋아요 관련 데이터 모델 및 함수 모듈.

게시글, 댓글, 좋아요 데이터 클래스와 MySQL 데이터베이스를 관리하는 함수들을 제공합니다.
"""

import re
from dataclasses import dataclass
from datetime import datetime

from core.database.connection import get_connection, transactional
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
    """게시글 데이터 클래스.

    Attributes:
        id: 게시글 고유 식별자.
        author_id: 작성자 ID.
        title: 제목.
        content: 내용.
        views: 조회수.
        created_at: 생성 시간.
        updated_at: 수정 시간.
        deleted_at: 삭제 시간.
        image_url: 첨부 이미지 URL (최대 1개).
    """

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


def _row_to_post(row: tuple) -> Post:
    """데이터베이스 행을 Post 객체로 변환합니다."""
    return Post(
        id=row[0],
        title=row[1],
        content=row[2],
        image_url=row[3],
        author_id=row[4],
        category_id=row[5],
        is_pinned=bool(row[6]),
        views=row[7],
        created_at=row[8],
        updated_at=row[9],
        deleted_at=row[10],
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
    """삭제되지 않은 게시글의 총 개수를 반환합니다.

    Args:
        search: 검색어 (제목+내용 FULLTEXT 검색). None이면 전체 조회.
        author_id: 작성자 ID로 필터링. None이면 전체 조회.
        category_id: 카테고리 ID로 필터링. None이면 전체 조회.
        blocked_user_ids: 차단된 사용자 ID 집합. 해당 사용자의 게시글 제외.
        tag: 태그 이름으로 필터링. None이면 전체 조회.
        author_ids: 작성자 ID 집합으로 필터링 (팔로잉 피드). None이면 전체 조회.

    Returns:
        게시글 총 개수.
    """
    async with get_connection() as conn, conn.cursor() as cur:
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
            f"SELECT COUNT(*) FROM post WHERE {where}",
            params,
        )
        row = await cur.fetchone()
        return row[0] if row else 0


async def get_post_by_id(post_id: int) -> Post | None:
    """ID로 게시글을 조회합니다.

    Args:
        post_id: 조회할 게시글 ID.

    Returns:
        게시글 객체, 없거나 삭제된 경우 None.
    """
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
                SELECT id, title, content, image_url, author_id, category_id,
                       is_pinned, views, created_at, updated_at, deleted_at
                FROM post
                WHERE id = %s AND deleted_at IS NULL
                """,
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
    """새 게시글을 생성합니다.

    Args:
        author_id: 작성자 ID.
        title: 제목.
        content: 내용.
        image_url: 첨부 이미지 URL (선택, 최대 1개).
        category_id: 카테고리 ID (선택).

    Returns:
        생성된 게시글 객체.
    """
    async with transactional() as cur:
        await cur.execute(
            """
            INSERT INTO post (title, content, image_url, author_id, category_id)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (title, content, image_url, author_id, category_id),
        )
        post_id = cur.lastrowid

        await cur.execute(
            """
            SELECT id, title, content, image_url, author_id, category_id,
                   is_pinned, views, created_at, updated_at, deleted_at
            FROM post
            WHERE id = %s
            """,
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
    """게시글을 수정합니다.

    Args:
        post_id: 수정할 게시글 ID.
        title: 새 제목 (선택).
        content: 새 내용 (선택).
        image_url: 새 이미지 URL (선택).
        category_id: 새 카테고리 ID (선택).

    Returns:
        수정된 게시글 객체, 없거나 삭제된 경우 None.
    """
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
            f"""
            UPDATE post
            SET {", ".join(updates)}
            WHERE id = %s AND deleted_at IS NULL
            """,
            (*params, post_id),
        )

        if cur.rowcount == 0:
            return None

        # 같은 트랜잭션 내에서 수정된 게시글 조회
        await cur.execute(
            """
            SELECT id, title, content, image_url, author_id, category_id,
                   is_pinned, views, created_at, updated_at, deleted_at
            FROM post
            WHERE id = %s
            """,
            (post_id,),
        )
        row = await cur.fetchone()
        return _row_to_post(row) if row else None


async def delete_post(post_id: int) -> bool:
    """게시글을 삭제합니다.

    소프트 삭제를 수행하여 deleted_at을 현재 시간으로 설정합니다.

    Args:
        post_id: 삭제할 게시글 ID.

    Returns:
        삭제 성공 여부.
    """
    async with transactional() as cur:
        await cur.execute(
            """
            UPDATE post
            SET deleted_at = NOW()
            WHERE id = %s AND deleted_at IS NULL
            """,
            (post_id,),
        )
        return cur.rowcount > 0


async def increment_view_count(post_id: int, user_id: int) -> bool:
    """게시글 조회수를 증가시킵니다.

    하루에 한 번만 조회수가 증가합니다 (post_view_log 테이블 사용).

    Args:
        post_id: 게시글 ID.
        user_id: 사용자 ID.

    Returns:
        조회수 증가 성공 여부.
    """
    async with transactional() as cur:
        # 조회 기록 삽입 시도 (중복 시 무시)
        await cur.execute(
            """
            INSERT IGNORE INTO post_view_log (user_id, post_id)
            VALUES (%s, %s)
            """,
            (user_id, post_id),
        )

        # INSERT가 성공한 경우에만 조회수 증가 (rowcount > 0)
        if cur.rowcount > 0:
            await cur.execute(
                """
                UPDATE post SET views = views + 1 WHERE id = %s
                """,
                (post_id,),
            )
            return True

        # 이미 오늘 조회한 경우
        return False


async def get_read_post_ids(user_id: int, post_ids: list[int]) -> set[int]:
    """사용자가 조회한 게시글 ID 집합을 반환합니다."""
    if not post_ids:
        return set()
    async with get_connection() as conn, conn.cursor() as cur:
        placeholders = ", ".join(["%s"] * len(post_ids))
        await cur.execute(
            f"SELECT DISTINCT post_id FROM post_view_log WHERE user_id = %s AND post_id IN ({placeholders})",
            [user_id, *post_ids],
        )
        return {row[0] for row in await cur.fetchall()}


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
    """게시글 목록을 작성자 정보, 좋아요 수, 댓글 수, 북마크 수와 함께 조회합니다.

    N+1 문제를 해결하기 위해 서브쿼리를 사용합니다.
    Cartesian Product를 방지하여 대량의 데이터에서도 빠른 성능을 보장합니다.
    고정 게시글은 항상 상단에 표시됩니다.

    Args:
        offset: 시작 위치.
        limit: 조회할 개수.
        search: 검색어 (제목+내용 FULLTEXT 검색). None이면 전체 조회.
        sort: 정렬 옵션 (latest, likes, views, comments, hot).
        author_id: 작성자 ID로 필터링. None이면 전체 조회.
        category_id: 카테고리 ID로 필터링. None이면 전체 조회.
        blocked_user_ids: 차단된 사용자 ID 집합. 해당 사용자의 게시글 제외.
        tag: 태그 이름으로 필터링. None이면 전체 조회.
        author_ids: 작성자 ID 집합으로 필터링 (팔로잉 피드). None이면 전체 조회.

    Returns:
        게시글 상세 정보 딕셔너리 목록.
    """
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

    # 차단된 사용자 게시글 필터링
    if blocked_user_ids:
        placeholders = ", ".join(["%s"] * len(blocked_user_ids))
        where += f" AND (p.author_id NOT IN ({placeholders}) OR p.author_id IS NULL)"
        params.extend(blocked_user_ids)

    # 팔로잉 피드: 특정 작성자 ID 집합으로 필터링
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

    params.extend([limit, offset])

    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
                SELECT
                    p.id, p.title, p.content, p.image_url, p.views,
                    p.created_at, p.updated_at,
                    u.id, u.nickname, u.profile_img, u.distro,
                    COALESCE(likes.count, 0) as likes_count,
                    COALESCE(comments.count, 0) as comments_count,
                    p.is_pinned, p.category_id, cat.name AS category_name,
                    COALESCE(bk.count, 0) as bookmarks_count,
                    (COALESCE(likes.count, 0) * 3
                     + COALESCE(comments.count, 0) * 2
                     + p.views * 0.5)
                    / POW(TIMESTAMPDIFF(HOUR, p.created_at, NOW()) + 2, 1.5)
                    AS hot_score
                    {upc_select}
                FROM post p
                LEFT JOIN user u ON p.author_id = u.id
                LEFT JOIN category cat ON p.category_id = cat.id
                LEFT JOIN (
                    SELECT post_id, COUNT(*) as count
                    FROM post_like
                    GROUP BY post_id
                ) likes ON p.id = likes.post_id
                LEFT JOIN (
                    SELECT post_id, COUNT(*) as count
                    FROM comment
                    WHERE deleted_at IS NULL
                    GROUP BY post_id
                ) comments ON p.id = comments.post_id
                LEFT JOIN (
                    SELECT post_id, COUNT(*) as count
                    FROM post_bookmark
                    GROUP BY post_id
                ) bk ON p.id = bk.post_id
                {upc_join}
                WHERE {where}
                ORDER BY p.is_pinned DESC, {order_by}
                LIMIT %s OFFSET %s
                """,
            [*join_params, *params],
        )
        rows = await cur.fetchall()

        return [
            {
                "post_id": row[0],
                "title": row[1],
                "content": row[2],
                "image_url": row[3],
                "views_count": row[4],
                "created_at": row[5],
                "updated_at": row[6],
                "author": build_author_dict(row[7], row[8], row[9], row[10]),
                "likes_count": row[11],
                "comments_count": row[12],
                "is_pinned": bool(row[13]),
                "category_id": row[14],
                "category_name": row[15],
                "bookmarks_count": row[16],
            }
            for row in rows
        ]


async def get_post_with_details(post_id: int) -> dict | None:
    """특정 게시글을 작성자 정보, 좋아요 수, 북마크 수와 함께 조회합니다.

    Args:
        post_id: 게시글 ID.

    Returns:
        게시글 상세 정보 딕셔너리, 없으면 None.
    """
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
                SELECT p.id, p.title, p.content, p.image_url, p.views, p.created_at, p.updated_at,
                       u.id, u.nickname, u.profile_img, u.distro,
                       (SELECT COUNT(*) FROM post_like WHERE post_id = p.id) as likes_count,
                       p.is_pinned, p.category_id, cat.name AS category_name,
                       (SELECT COUNT(*) FROM post_bookmark WHERE post_id = p.id) as bookmarks_count
                FROM post p
                LEFT JOIN user u ON p.author_id = u.id
                LEFT JOIN category cat ON p.category_id = cat.id
                WHERE p.id = %s AND p.deleted_at IS NULL
                """,
            (post_id,),
        )
        row = await cur.fetchone()

        if not row:
            return None

        return {
            "post_id": row[0],
            "title": row[1],
            "content": row[2],
            "image_url": row[3],
            "views_count": row[4],
            "created_at": row[5],
            "updated_at": row[6],
            "author": build_author_dict(row[7], row[8], row[9], row[10]),
            "likes_count": row[11],
            "is_pinned": bool(row[12]),
            "category_id": row[13],
            "category_name": row[14],
            "bookmarks_count": row[15],
        }


async def pin_post(post_id: int) -> bool:
    """게시글을 고정합니다."""
    async with transactional() as cur:
        await cur.execute(
            """
            UPDATE post SET is_pinned = 1
            WHERE id = %s AND deleted_at IS NULL
            """,
            (post_id,),
        )
        return cur.rowcount > 0


async def unpin_post(post_id: int) -> bool:
    """게시글 고정을 해제합니다."""
    async with transactional() as cur:
        await cur.execute(
            """
            UPDATE post SET is_pinned = 0
            WHERE id = %s AND deleted_at IS NULL
            """,
            (post_id,),
        )
        return cur.rowcount > 0


# ============ 게시글 이미지 관련 함수 ============


async def save_post_images(post_id: int, image_urls: list[str]) -> None:
    """게시글 이미지를 저장합니다.

    기존 이미지를 모두 삭제하고 새 이미지를 순서대로 삽입합니다.
    최대 5개까지 허용합니다.
    """
    async with transactional() as cur:
        await cur.execute(
            "DELETE FROM post_image WHERE post_id = %s",
            (post_id,),
        )
        for idx, url in enumerate(image_urls[:MAX_POST_IMAGES]):
            await cur.execute(
                """
                INSERT INTO post_image (post_id, image_url, sort_order)
                VALUES (%s, %s, %s)
                """,
                (post_id, url, idx),
            )


async def get_post_images(post_id: int) -> list[dict]:
    """게시글의 이미지 목록을 순서대로 반환합니다."""
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
                SELECT id, image_url, sort_order
                FROM post_image
                WHERE post_id = %s
                ORDER BY sort_order
                """,
            (post_id,),
        )
        rows = await cur.fetchall()
        return [{"id": row[0], "image_url": row[1], "sort_order": row[2]} for row in rows]


async def get_related_posts(
    current_post_id: int,
    category_id: int | None,
    tag_ids: list[int],
    limit: int = 5,
    blocked_user_ids: set[int] | None = None,
) -> list[dict]:
    """현재 게시글과 관련된 게시글을 태그/카테고리 기반으로 조회합니다.

    태그 매칭 수 → 같은 카테고리 → hot score 순으로 정렬합니다.

    Args:
        current_post_id: 현재 게시글 ID (결과에서 제외).
        category_id: 현재 게시글의 카테고리 ID.
        tag_ids: 현재 게시글의 태그 ID 목록.
        limit: 최대 반환 개수.
        blocked_user_ids: 차단된 사용자 ID 집합.

    Returns:
        연관 게시글 딕셔너리 목록.
    """
    where = "p.deleted_at IS NULL AND p.id != %s"
    params: list = [current_post_id]

    if blocked_user_ids:
        placeholders = ", ".join(["%s"] * len(blocked_user_ids))
        where += f" AND (p.author_id NOT IN ({placeholders}) OR p.author_id IS NULL)"
        params.extend(blocked_user_ids)

    # 태그 매칭 서브쿼리: tag_ids가 있으면 LEFT JOIN으로 매칭 수 계산
    if tag_ids:
        tag_placeholders = ", ".join(["%s"] * len(tag_ids))
        tag_join = f"LEFT JOIN post_tag pt ON p.id = pt.post_id AND pt.tag_id IN ({tag_placeholders})"
        tag_select = "COUNT(pt.tag_id) AS matched_tags"
        tag_params = list(tag_ids)
    else:
        tag_join = ""
        tag_select = "0 AS matched_tags"
        tag_params = []

    # 같은 카테고리 보너스
    if category_id is not None:
        same_category = "CASE WHEN p.category_id = %s THEN 1 ELSE 0 END AS same_category"
        cat_params = [category_id]
    else:
        same_category = "0 AS same_category"
        cat_params = []

    params.extend([limit])

    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
                SELECT
                    p.id, p.title, p.content, p.image_url, p.views,
                    p.created_at, p.updated_at,
                    u.id, u.nickname, u.profile_img, u.distro,
                    COALESCE(likes.count, 0) AS likes_count,
                    COALESCE(comments.count, 0) AS comments_count,
                    p.is_pinned, p.category_id, cat.name AS category_name,
                    COALESCE(bk.count, 0) AS bookmarks_count,
                    {tag_select},
                    {same_category},
                    (COALESCE(likes.count, 0) * 3
                     + COALESCE(comments.count, 0) * 2
                     + p.views * 0.5)
                    / POW(TIMESTAMPDIFF(HOUR, p.created_at, NOW()) + 2, 1.5)
                    AS hot_score
                FROM post p
                LEFT JOIN user u ON p.author_id = u.id
                LEFT JOIN category cat ON p.category_id = cat.id
                {tag_join}
                LEFT JOIN (
                    SELECT post_id, COUNT(*) AS count
                    FROM post_like
                    GROUP BY post_id
                ) likes ON p.id = likes.post_id
                LEFT JOIN (
                    SELECT post_id, COUNT(*) AS count
                    FROM comment
                    WHERE deleted_at IS NULL
                    GROUP BY post_id
                ) comments ON p.id = comments.post_id
                LEFT JOIN (
                    SELECT post_id, COUNT(*) AS count
                    FROM post_bookmark
                    GROUP BY post_id
                ) bk ON p.id = bk.post_id
                WHERE {where}
                GROUP BY p.id
                ORDER BY matched_tags DESC, same_category DESC, hot_score DESC
                LIMIT %s
                """,
            # 파라미터 순서: cat_params(SELECT CASE), tag_params(JOIN IN), params(WHERE+LIMIT)
            [*cat_params, *tag_params, *params],
        )
        rows = await cur.fetchall()

        return [
            {
                "post_id": row[0],
                "title": row[1],
                "content": row[2],
                "image_url": row[3],
                "views_count": row[4],
                "created_at": row[5],
                "updated_at": row[6],
                "author": build_author_dict(row[7], row[8], row[9], row[10]),
                "likes_count": row[11],
                "comments_count": row[12],
                "is_pinned": bool(row[13]),
                "category_id": row[14],
                "category_name": row[15],
                "bookmarks_count": row[16],
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
    "unpin_post",
    "update_post",
]
