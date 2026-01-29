"""post_models: 게시글, 댓글, 좋아요 관련 데이터 모델 및 함수 모듈.

게시글, 댓글, 좋아요 데이터 클래스와 MySQL 데이터베이스를 관리하는 함수들을 제공합니다.
"""

from dataclasses import dataclass
from datetime import datetime

from database.connection import get_connection


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


@dataclass
class Comment:
    """댓글 데이터 클래스.

    Attributes:
        id: 댓글 고유 식별자.
        post_id: 게시글 ID.
        author_id: 작성자 ID.
        content: 내용.
        created_at: 생성 시간.
        updated_at: 수정 시간.
        deleted_at: 삭제 시간.
    """

    id: int
    post_id: int
    author_id: int
    content: str
    created_at: datetime
    updated_at: datetime | None
    deleted_at: datetime | None

    @property
    def is_deleted(self) -> bool:
        """댓글이 삭제되었는지 확인합니다."""
        return self.deleted_at is not None


@dataclass
class Like:
    """좋아요 데이터 클래스.

    Attributes:
        id: 좋아요 고유 식별자.
        post_id: 게시글 ID.
        user_id: 사용자 ID.
        created_at: 생성 시간.
    """

    id: int
    post_id: int
    user_id: int
    created_at: datetime


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


def _row_to_comment(row: tuple) -> Comment:
    """데이터베이스 행을 Comment 객체로 변환합니다."""
    return Comment(
        id=row[0],
        content=row[1],
        author_id=row[2],
        post_id=row[3],
        created_at=row[4],
        updated_at=row[5],
        deleted_at=row[6],
    )


def _row_to_like(row: tuple) -> Like:
    """데이터베이스 행을 Like 객체로 변환합니다."""
    return Like(
        id=row[0],
        user_id=row[1],
        post_id=row[2],
        created_at=row[3],
    )


# ============ 게시글 관련 함수 ============


async def get_posts(page: int = 0, limit: int = 10) -> list[Post]:
    """게시글 목록을 조회합니다.

    삭제되지 않은 게시글을 최신순으로 정렬하여 페이지네이션을 적용합니다.

    Args:
        page: 페이지 번호 (0부터 시작).
        limit: 페이지당 게시글 수 (기본 10개).

    Returns:
        게시글 목록.
    """
    offset = page * limit
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, title, content, image_url, author_id, views,
                       created_at, updated_at, deleted_at
                FROM post
                WHERE deleted_at IS NULL
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            )
            rows = await cur.fetchall()
            return [_row_to_post(row) for row in rows]


async def get_posts_by_offset(offset: int = 0, limit: int = 10) -> list[Post]:
    """offset 기반으로 게시글 목록을 조회합니다.

    삭제되지 않은 게시글을 최신순으로 정렬하여 offset 기반 페이지네이션을 적용합니다.

    Args:
        offset: 시작 위치 (0부터 시작).
        limit: 조회할 게시글 수 (기본 10개).

    Returns:
        게시글 목록.
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, title, content, image_url, author_id, views,
                       created_at, updated_at, deleted_at
                FROM post
                WHERE deleted_at IS NULL
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            )
            rows = await cur.fetchall()
            return [_row_to_post(row) for row in rows]


async def get_total_posts_count() -> int:
    """삭제되지 않은 게시글의 총 개수를 반환합니다.

    Returns:
        게시글 총 개수.
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT COUNT(*) FROM post WHERE deleted_at IS NULL
                """
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
    async with get_connection() as conn:
        async with conn.cursor() as cur:
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

    params.append(post_id)

    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f"""
                UPDATE post
                SET {", ".join(updates)}
                WHERE id = %s AND deleted_at IS NULL
                """,
                tuple(params),
            )

            return await get_post_by_id(post_id)


async def delete_post(post_id: int) -> bool:
    """게시글을 삭제합니다.

    소프트 삭제를 수행하여 deleted_at을 현재 시간으로 설정합니다.

    Args:
        post_id: 삭제할 게시글 ID.

    Returns:
        삭제 성공 여부.
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
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
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            try:
                # 조회 기록 삽입 시도 (중복 시 무시)
                await cur.execute(
                    """
                    INSERT INTO post_view_log (user_id, post_id)
                    VALUES (%s, %s)
                    """,
                    (user_id, post_id),
                )

                # 조회수 증가
                await cur.execute(
                    """
                    UPDATE post SET views = views + 1 WHERE id = %s
                    """,
                    (post_id,),
                )
                return True
            except Exception:
                # 중복 조회 (오늘 이미 조회함)
                return False


# ============ 좋아요 관련 함수 ============


async def get_like(post_id: int, user_id: int) -> Like | None:
    """특정 사용자가 특정 게시글에 남긴 좋아요를 조회합니다.

    Args:
        post_id: 게시글 ID.
        user_id: 사용자 ID.

    Returns:
        좋아요 객체, 없으면 None.
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, user_id, post_id, created_at
                FROM post_like
                WHERE post_id = %s AND user_id = %s
                """,
                (post_id, user_id),
            )
            row = await cur.fetchone()
            return _row_to_like(row) if row else None


async def get_post_likes_count(post_id: int) -> int:
    """게시글의 좋아요 개수를 조회합니다.

    Args:
        post_id: 게시글 ID.

    Returns:
        좋아요 개수.
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT COUNT(*) FROM post_like WHERE post_id = %s
                """,
                (post_id,),
            )
            row = await cur.fetchone()
            return row[0] if row else 0


async def add_like(post_id: int, user_id: int) -> Like | None:
    """게시글에 좋아요를 추가합니다.

    Args:
        post_id: 게시글 ID.
        user_id: 사용자 ID.

    Returns:
        생성된 좋아요 객체, 이미 좋아요한 경우 None.
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            try:
                await cur.execute(
                    """
                    INSERT INTO post_like (user_id, post_id)
                    VALUES (%s, %s)
                    """,
                    (user_id, post_id),
                )
                like_id = cur.lastrowid

                await cur.execute(
                    """
                    SELECT id, user_id, post_id, created_at
                    FROM post_like
                    WHERE id = %s
                    """,
                    (like_id,),
                )
                row = await cur.fetchone()
                return _row_to_like(row) if row else None
            except Exception:
                # 중복 좋아요
                return None


async def remove_like(post_id: int, user_id: int) -> bool:
    """게시글 좋아요를 취소합니다.

    Args:
        post_id: 게시글 ID.
        user_id: 사용자 ID.

    Returns:
        취소 성공 여부.
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                DELETE FROM post_like
                WHERE post_id = %s AND user_id = %s
                """,
                (post_id, user_id),
            )
            return cur.rowcount > 0


# ============ 댓글 관련 함수 ============


async def get_comments_by_post(post_id: int) -> list[Comment]:
    """특정 게시글의 댓글 목록을 조회합니다.

    삭제되지 않은 댓글을 작성순으로 정렬하여 반환합니다.

    Args:
        post_id: 게시글 ID.

    Returns:
        댓글 목록.
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, content, author_id, post_id, created_at, updated_at, deleted_at
                FROM comment
                WHERE post_id = %s AND deleted_at IS NULL
                ORDER BY created_at ASC
                """,
                (post_id,),
            )
            rows = await cur.fetchall()
            return [_row_to_comment(row) for row in rows]


async def get_comments_count_by_post(post_id: int) -> int:
    """특정 게시글의 댓글 수를 조회합니다.

    Args:
        post_id: 게시글 ID.

    Returns:
        댓글 수.
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT COUNT(*) FROM comment
                WHERE post_id = %s AND deleted_at IS NULL
                """,
                (post_id,),
            )
            row = await cur.fetchone()
            return row[0] if row else 0


async def get_comment_by_id(comment_id: int) -> Comment | None:
    """ID로 댓글을 조회합니다.

    Args:
        comment_id: 조회할 댓글 ID.

    Returns:
        댓글 객체, 없거나 삭제된 경우 None.
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, content, author_id, post_id, created_at, updated_at, deleted_at
                FROM comment
                WHERE id = %s AND deleted_at IS NULL
                """,
                (comment_id,),
            )
            row = await cur.fetchone()
            return _row_to_comment(row) if row else None


async def create_comment(post_id: int, author_id: int, content: str) -> Comment:
    """새 댓글을 생성합니다.

    Args:
        post_id: 게시글 ID.
        author_id: 작성자 ID.
        content: 내용.

    Returns:
        생성된 댓글 객체.
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO comment (content, author_id, post_id)
                VALUES (%s, %s, %s)
                """,
                (content, author_id, post_id),
            )
            comment_id = cur.lastrowid

            await cur.execute(
                """
                SELECT id, content, author_id, post_id, created_at, updated_at, deleted_at
                FROM comment
                WHERE id = %s
                """,
                (comment_id,),
            )
            row = await cur.fetchone()
            return _row_to_comment(row)


async def update_comment(comment_id: int, content: str) -> Comment | None:
    """댓글을 수정합니다.

    Args:
        comment_id: 수정할 댓글 ID.
        content: 새 내용.

    Returns:
        수정된 댓글 객체, 없거나 삭제된 경우 None.
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE comment
                SET content = %s
                WHERE id = %s AND deleted_at IS NULL
                """,
                (content, comment_id),
            )

            if cur.rowcount == 0:
                return None

            return await get_comment_by_id(comment_id)


async def delete_comment(comment_id: int) -> bool:
    """댓글을 삭제합니다.

    소프트 삭제를 수행하여 deleted_at을 현재 시간으로 설정합니다.

    Args:
        comment_id: 삭제할 댓글 ID.

    Returns:
        삭제 성공 여부.
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE comment
                SET deleted_at = NOW()
                WHERE id = %s AND deleted_at IS NULL
                """,
                (comment_id,),
            )
            return cur.rowcount > 0


# ============ 테스트 헬퍼 함수 ============


async def clear_all_data() -> None:
    """테스트용 헬퍼 함수로, 모든 데이터를 삭제합니다.

    주의: 이 함수는 테스트 환경에서만 사용해야 합니다.
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SET FOREIGN_KEY_CHECKS = 0")
            await cur.execute("TRUNCATE TABLE post_view_log")
            await cur.execute("TRUNCATE TABLE post_like")
            await cur.execute("TRUNCATE TABLE comment")
            await cur.execute("TRUNCATE TABLE post")
            await cur.execute("SET FOREIGN_KEY_CHECKS = 1")
