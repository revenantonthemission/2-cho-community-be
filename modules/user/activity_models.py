"""activity_models: 내 활동 관련 모델."""

from core.database.connection import get_cursor
from core.utils.formatters import format_datetime
from schemas.common import build_author_dict


async def get_my_posts(user_id: int, offset: int = 0, limit: int = 10) -> tuple[list[dict], int]:
    """내가 쓴 글 목록을 반환합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT COUNT(*) AS cnt FROM post WHERE author_id = %s AND deleted_at IS NULL",
            (user_id,),
        )
        total_count = (await cur.fetchone())["cnt"]

        await cur.execute(
            """
                SELECT p.id AS post_id, p.title, p.content, p.image_url,
                       p.views AS views_count,
                       p.created_at, p.updated_at,
                       u.id AS author_user_id, u.nickname AS author_nickname,
                       u.profile_img AS author_profile_img, u.distro AS author_distro,
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
        posts.append(
            {
                "post_id": row["post_id"],
                "title": row["title"],
                "content": (row["content"] or "")[:200],
                "image_url": row["image_url"],
                "views_count": row["views_count"],
                "created_at": format_datetime(row["created_at"]),
                "updated_at": format_datetime(row["updated_at"]),
                "author": build_author_dict(
                    row["author_user_id"],
                    row["author_nickname"],
                    row["author_profile_img"],
                    distro=row["author_distro"],
                ),
                "likes_count": row["likes_count"],
                "comments_count": row["comments_count"],
            }
        )

    return posts, total_count


async def get_my_comments(user_id: int, offset: int = 0, limit: int = 10) -> tuple[list[dict], int]:
    """내가 쓴 댓글 목록을 반환합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT COUNT(*) AS cnt FROM comment WHERE author_id = %s AND deleted_at IS NULL",
            (user_id,),
        )
        total_count = (await cur.fetchone())["cnt"]

        await cur.execute(
            """
                SELECT c.id AS comment_id, c.content, c.created_at, c.post_id,
                       p.title AS post_title
                FROM comment c
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
        comments.append(
            {
                "comment_id": row["comment_id"],
                "content": row["content"],
                "created_at": format_datetime(row["created_at"]),
                "post_id": row["post_id"],
                "post_title": row["post_title"] or "삭제된 게시글",
            }
        )

    return comments, total_count


async def get_my_likes(user_id: int, offset: int = 0, limit: int = 10) -> tuple[list[dict], int]:
    """좋아요한 글 목록을 반환합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            """
                SELECT COUNT(*) AS cnt FROM post_like pl
                JOIN post p ON pl.post_id = p.id
                WHERE pl.user_id = %s AND p.deleted_at IS NULL
                """,
            (user_id,),
        )
        total_count = (await cur.fetchone())["cnt"]

        await cur.execute(
            """
                SELECT p.id AS post_id, p.title, p.content, p.image_url,
                       p.views AS views_count,
                       p.created_at, p.updated_at,
                       u.id AS author_user_id, u.nickname AS author_nickname,
                       u.profile_img AS author_profile_img, u.distro AS author_distro,
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
        posts.append(
            {
                "post_id": row["post_id"],
                "title": row["title"],
                "content": (row["content"] or "")[:200],
                "image_url": row["image_url"],
                "views_count": row["views_count"],
                "created_at": format_datetime(row["created_at"]),
                "updated_at": format_datetime(row["updated_at"]),
                "author": build_author_dict(
                    row["author_user_id"],
                    row["author_nickname"],
                    row["author_profile_img"],
                    distro=row["author_distro"],
                ),
                "likes_count": row["likes_count"],
                "comments_count": row["comments_count"],
            }
        )

    return posts, total_count


async def get_my_bookmarks(user_id: int, offset: int = 0, limit: int = 10) -> tuple[list[dict], int]:
    """북마크한 글 목록을 반환합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            """
                SELECT COUNT(*) AS cnt FROM post_bookmark pb
                JOIN post p ON pb.post_id = p.id
                WHERE pb.user_id = %s AND p.deleted_at IS NULL
                """,
            (user_id,),
        )
        total_count = (await cur.fetchone())["cnt"]

        await cur.execute(
            """
                SELECT p.id AS post_id, p.title, p.content, p.image_url,
                       p.views AS views_count,
                       p.created_at, p.updated_at,
                       u.id AS author_user_id, u.nickname AS author_nickname,
                       u.profile_img AS author_profile_img, u.distro AS author_distro,
                       (SELECT COUNT(*) FROM post_like WHERE post_id = p.id) AS likes_count,
                       (SELECT COUNT(*) FROM comment
                        WHERE post_id = p.id AND deleted_at IS NULL) AS comments_count
                FROM post_bookmark pb
                JOIN post p ON pb.post_id = p.id
                LEFT JOIN user u ON p.author_id = u.id
                WHERE pb.user_id = %s AND p.deleted_at IS NULL
                ORDER BY pb.created_at DESC
                LIMIT %s OFFSET %s
                """,
            (user_id, limit, offset),
        )
        rows = await cur.fetchall()

    posts = []
    for row in rows:
        posts.append(
            {
                "post_id": row["post_id"],
                "title": row["title"],
                "content": (row["content"] or "")[:200],
                "image_url": row["image_url"],
                "views_count": row["views_count"],
                "created_at": format_datetime(row["created_at"]),
                "updated_at": format_datetime(row["updated_at"]),
                "author": build_author_dict(
                    row["author_user_id"],
                    row["author_nickname"],
                    row["author_profile_img"],
                    distro=row["author_distro"],
                ),
                "likes_count": row["likes_count"],
                "comments_count": row["comments_count"],
            }
        )

    return posts, total_count
