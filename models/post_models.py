"""post_models: 게시글, 댓글, 좋아요 관련 데이터 모델 및 함수 모듈.

게시글, 댓글, 좋아요 데이터 클래스와 MySQL 데이터베이스를 관리하는 함수들을 제공합니다.
"""

from dataclasses import dataclass
from datetime import datetime

from database.connection import get_connection
from models.comment_models import get_comments_with_author


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


async def get_posts_with_details(offset: int = 0, limit: int = 10) -> list[dict]:
    """게시글 목록을 작성자 정보, 좋아요 수, 댓글 수와 함께 조회합니다.

    N+1 문제를 해결하기 위해 JOIN과 서브쿼리를 사용합니다.

    Args:
        offset: 시작 위치.
        limit: 조회할 개수.

    Returns:
        게시글 상세 정보 딕셔너리 목록.
    """
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT p.id, p.title, p.content, p.image_url, p.views, p.created_at, p.updated_at,
                       u.id, u.nickname, u.profile_img,
                       (SELECT COUNT(*) FROM post_like WHERE post_id = p.id) as likes_count,
                       (SELECT COUNT(*) FROM comment WHERE post_id = p.id AND deleted_at IS NULL) as comments_count
                FROM post p
                LEFT JOIN user u ON p.author_id = u.id
                WHERE p.deleted_at IS NULL
                ORDER BY p.created_at DESC, p.id DESC
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            )
            rows = await cur.fetchall()

            results = []
            for row in rows:
                results.append(
                    {
                        "post_id": row[0],
                        "title": row[1],
                        "content": row[2],
                        "image_url": row[3],
                        "views_count": row[4],
                        "created_at": row[5],
                        "updated_at": row[6],
                        "author": {
                            "user_id": row[7],
                            "nickname": row[8] if row[8] else "탈퇴한 사용자",
                            "profileImageUrl": row[9]
                            or "/assets/profiles/default_profile.jpg",
                        },
                        "likes_count": row[10],
                        "comments_count": row[11],
                    }
                )
            return results


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
                "author": {
                    "user_id": row[7],
                    "nickname": row[8] if row[8] else "탈퇴한 사용자",
                    "profileImageUrl": row[9] or "/assets/profiles/default_profile.jpg",
                },
                "likes_count": row[10],
            }


# get_comments_with_author는 comment_models.py에서 정의됨 (상단 import 참조)
# 하위 호환성을 위해 다시 내보내기
__all__ = ["Post", "get_comments_with_author"]
