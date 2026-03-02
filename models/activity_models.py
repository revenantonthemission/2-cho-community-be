"""activity_models: 내 활동 관련 모델."""

from database.connection import get_connection
from schemas.common import build_author_dict
from utils.formatters import format_datetime


async def get_my_posts(
    user_id: int, offset: int = 0, limit: int = 10
) -> tuple[list[dict], int]:
    """내가 쓴 글 목록을 반환합니다."""
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT COUNT(*) FROM post
                WHERE author_id = %s AND deleted_at IS NULL
                """,
                (user_id,),
            )
            total_count = (await cur.fetchone())[0]

            await cur.execute(
                """
                SELECT p.id, p.title, p.content, p.image_url, p.views,
                       p.created_at, p.updated_at,
                       u.id, u.nickname, u.profile_img,
                       (SELECT COUNT(*) FROM post_like WHERE post_id = p.id) AS likes_count,
                       (SELECT COUNT(*) FROM comment
                        WHERE post_id = p.id AND deleted_at IS NULL) AS comments_count
                FROM post p
                LEFT JOIN user u ON p.author_id = u.id
                WHERE p.author_id = %s AND p.deleted_at IS NULL
                ORDER BY p.created_at DESC
                LIMIT %s OFFSET %s
                """,
                (user_id, limit, offset),
            )
            rows = await cur.fetchall()

    posts = []
    for row in rows:
        posts.append({
            "post_id": row[0],
            "title": row[1],
            "content": (row[2] or "")[:200],
            "image_url": row[3],
            "views_count": row[4],
            "created_at": format_datetime(row[5]),
            "updated_at": format_datetime(row[6]),
            "author": build_author_dict(row[7], row[8], row[9]),
            "likes_count": row[10],
            "comments_count": row[11],
        })

    return posts, total_count


async def get_my_comments(
    user_id: int, offset: int = 0, limit: int = 10
) -> tuple[list[dict], int]:
    """내가 쓴 댓글 목록을 반환합니다."""
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT COUNT(*) FROM comment
                WHERE author_id = %s AND deleted_at IS NULL
                """,
                (user_id,),
            )
            total_count = (await cur.fetchone())[0]

            await cur.execute(
                """
                SELECT c.id, c.content, c.created_at, c.post_id, p.title
                FROM comment c
                -- soft-deleted 게시글은 NULL로 처리 → "삭제된 게시글" 폴백
                LEFT JOIN post p ON c.post_id = p.id AND p.deleted_at IS NULL
                WHERE c.author_id = %s AND c.deleted_at IS NULL
                ORDER BY c.created_at DESC
                LIMIT %s OFFSET %s
                """,
                (user_id, limit, offset),
            )
            rows = await cur.fetchall()

    comments = []
    for row in rows:
        comments.append({
            "comment_id": row[0],
            "content": row[1],
            "created_at": format_datetime(row[2]),
            "post_id": row[3],
            "post_title": row[4] or "삭제된 게시글",
        })

    return comments, total_count


async def get_my_likes(
    user_id: int, offset: int = 0, limit: int = 10
) -> tuple[list[dict], int]:
    """좋아요한 글 목록을 반환합니다."""
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT COUNT(*) FROM post_like pl
                JOIN post p ON pl.post_id = p.id
                WHERE pl.user_id = %s AND p.deleted_at IS NULL
                """,
                (user_id,),
            )
            total_count = (await cur.fetchone())[0]

            await cur.execute(
                """
                SELECT p.id, p.title, p.content, p.image_url, p.views,
                       p.created_at, p.updated_at,
                       u.id, u.nickname, u.profile_img,
                       (SELECT COUNT(*) FROM post_like WHERE post_id = p.id) AS likes_count,
                       (SELECT COUNT(*) FROM comment
                        WHERE post_id = p.id AND deleted_at IS NULL) AS comments_count
                FROM post_like pl
                JOIN post p ON pl.post_id = p.id
                LEFT JOIN user u ON p.author_id = u.id
                WHERE pl.user_id = %s AND p.deleted_at IS NULL
                ORDER BY pl.created_at DESC
                LIMIT %s OFFSET %s
                """,
                (user_id, limit, offset),
            )
            rows = await cur.fetchall()

    posts = []
    for row in rows:
        posts.append({
            "post_id": row[0],
            "title": row[1],
            "content": (row[2] or "")[:200],
            "image_url": row[3],
            "views_count": row[4],
            "created_at": format_datetime(row[5]),
            "updated_at": format_datetime(row[6]),
            "author": build_author_dict(row[7], row[8], row[9]),
            "likes_count": row[10],
            "comments_count": row[11],
        })

    return posts, total_count
