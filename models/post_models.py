"""post_models: 게시글, 댓글, 좋아요 관련 데이터 모델 및 함수 모듈.

게시글, 댓글, 좋아요 데이터 클래스와 MySQL 데이터베이스를 관리하는 함수들을 제공합니다.
"""

import re
from dataclasses import dataclass
from datetime import datetime

from database.connection import get_connection, transactional
from models.comment_models import get_comments_with_author
from schemas.common import build_author_dict


# SQL Injection 방지: 허용된 컬럼명 whitelist
ALLOWED_POST_COLUMNS = {'title', 'content', 'image_url'}

# FULLTEXT BOOLEAN MODE 특수문자 이스케이프 패턴
_FULLTEXT_SPECIAL_CHARS = re.compile(r'([+\-><()~*"@])')


def _escape_fulltext_query(query: str) -> str:
    """FULLTEXT BOOLEAN MODE 특수문자를 이스케이프합니다."""
    return _FULLTEXT_SPECIAL_CHARS.sub(r'\\\1', query.strip())


# SQL Injection 방지: 허용된 정렬 옵션 whitelist
ALLOWED_SORT_OPTIONS = {
    "latest": "p.created_at DESC, p.id DESC",
    "likes": "likes_count DESC, p.created_at DESC",
    "views": "p.views DESC, p.created_at DESC",
    "comments": "comments_count DESC, p.created_at DESC",
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
        views=row[5],
        created_at=row[6],
        updated_at=row[7],
        deleted_at=row[8],
    )


# ============ 게시글 관련 함수 ============


async def get_total_posts_count(
    search: str | None = None,
    author_id: int | None = None,
) -> int:
    """삭제되지 않은 게시글의 총 개수를 반환합니다.

    Args:
        search: 검색어 (제목+내용 FULLTEXT 검색). None이면 전체 조회.
        author_id: 작성자 ID로 필터링. None이면 전체 조회.

    Returns:
        게시글 총 개수.
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            where = "deleted_at IS NULL"
            params: list = []

            if search:
                escaped = _escape_fulltext_query(search)
                where += " AND MATCH(title, content) AGAINST(%s IN BOOLEAN MODE)"
                params.append(escaped)

            if author_id is not None:
                where += " AND author_id = %s"
                params.append(author_id)

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
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, title, content, image_url, author_id, views,
                       created_at, updated_at, deleted_at
                FROM post
                WHERE id = %s AND deleted_at IS NULL
                """,
                (post_id,),
            )
            row = await cur.fetchone()
            return _row_to_post(row) if row else None


async def create_post(
    author_id: int, title: str, content: str, image_url: str | None = None
) -> Post:
    """새 게시글을 생성합니다.

    Args:
        author_id: 작성자 ID.
        title: 제목.
        content: 내용.
        image_url: 첨부 이미지 URL (선택, 최대 1개).

    Returns:
        생성된 게시글 객체.
    """
    async with transactional() as cur:
        await cur.execute(
            """
            INSERT INTO post (title, content, image_url, author_id)
            VALUES (%s, %s, %s, %s)
            """,
            (title, content, image_url, author_id),
        )
        post_id = cur.lastrowid

        await cur.execute(
            """
            SELECT id, title, content, image_url, author_id, views,
                   created_at, updated_at, deleted_at
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
) -> Post | None:
    """게시글을 수정합니다.

    Args:
        post_id: 수정할 게시글 ID.
        title: 새 제목 (선택).
        content: 새 내용 (선택).
        image_url: 새 이미지 URL (선택).

    Returns:
        수정된 게시글 객체, 없거나 삭제된 경우 None.
    """
    updates = []
    params = []

    if title is not None:
        updates.append("title = %s")
        params.append(title)
    if content is not None:
        updates.append("content = %s")
        params.append(content)
    if image_url is not None:
        updates.append("image_url = %s")
        params.append(image_url)

    if not updates:
        return await get_post_by_id(post_id)

    # SQL Injection 방지: 컬럼명 검증
    for update_clause in updates:
        column_name = update_clause.split(' = ')[0]
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
            SELECT id, title, content, image_url, author_id, views,
                   created_at, updated_at, deleted_at
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


async def get_posts_with_details(
    offset: int = 0,
    limit: int = 10,
    search: str | None = None,
    sort: str = "latest",
    author_id: int | None = None,
) -> list[dict]:
    """게시글 목록을 작성자 정보, 좋아요 수, 댓글 수와 함께 조회합니다.

    N+1 문제를 해결하기 위해 서브쿼리를 사용합니다.
    Cartesian Product를 방지하여 대량의 데이터에서도 빠른 성능을 보장합니다.

    Args:
        offset: 시작 위치.
        limit: 조회할 개수.
        search: 검색어 (제목+내용 FULLTEXT 검색). None이면 전체 조회.
        sort: 정렬 옵션 (latest, likes, views, comments).
        author_id: 작성자 ID로 필터링. None이면 전체 조회.

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

    params.extend([limit, offset])

    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f"""
                SELECT
                    p.id, p.title, p.content, p.image_url, p.views,
                    p.created_at, p.updated_at,
                    u.id, u.nickname, u.profile_img,
                    COALESCE(likes.count, 0) as likes_count,
                    COALESCE(comments.count, 0) as comments_count
                FROM post p
                LEFT JOIN user u ON p.author_id = u.id
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
                WHERE {where}
                ORDER BY {order_by}
                LIMIT %s OFFSET %s
                """,
                params,
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
                    "author": build_author_dict(row[7], row[8], row[9]),
                    "likes_count": row[10],
                    "comments_count": row[11],
                }
                for row in rows
            ]


async def get_post_with_details(post_id: int) -> dict | None:
    """특정 게시글을 작성자 정보, 좋아요 수와 함께 조회합니다.

    Args:
        post_id: 게시글 ID.

    Returns:
        게시글 상세 정보 딕셔너리, 없으면 None.
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT p.id, p.title, p.content, p.image_url, p.views, p.created_at, p.updated_at,
                       u.id, u.nickname, u.profile_img,
                       (SELECT COUNT(*) FROM post_like WHERE post_id = p.id) as likes_count
                FROM post p
                LEFT JOIN user u ON p.author_id = u.id
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
                "author": build_author_dict(row[7], row[8], row[9]),
                "likes_count": row[10],
            }


# get_comments_with_author는 comment_models.py에서 정의됨 (상단 import 참조)
# 하위 호환성을 위해 다시 내보내기
__all__ = ["Post", "get_comments_with_author"]
