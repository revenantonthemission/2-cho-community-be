"""follow_models: 사용자 팔로우 관련 데이터 모델 및 함수 모듈."""

from dataclasses import dataclass
from datetime import datetime

from core.database.connection import get_connection, transactional


@dataclass
class Follow:
    """팔로우 데이터 클래스."""

    id: int
    follower_id: int
    following_id: int
    created_at: datetime


def _row_to_follow(row: tuple) -> Follow:
    """데이터베이스 행을 Follow 객체로 변환합니다."""
    return Follow(
        id=row[0],
        follower_id=row[1],
        following_id=row[2],
        created_at=row[3],
    )


async def add_follow(follower_id: int, following_id: int) -> Follow:
    """팔로우를 추가합니다.

    Raises:
        IntegrityError: 이미 팔로우한 경우.
    """
    async with transactional() as cur:
        await cur.execute(
            """
            INSERT INTO user_follow (follower_id, following_id)
            VALUES (%s, %s)
            """,
            (follower_id, following_id),
        )

        follow_id = cur.lastrowid

        await cur.execute(
            """
            SELECT id, follower_id, following_id, created_at
            FROM user_follow
            WHERE id = %s
            """,
            (follow_id,),
        )
        row = await cur.fetchone()

        if not row:
            raise RuntimeError(
                f"팔로우 삽입 직후 조회 실패: follow_id={follow_id}, "
                f"follower_id={follower_id}, following_id={following_id}"
            )

        return _row_to_follow(row)


async def remove_follow(follower_id: int, following_id: int) -> bool:
    """팔로우를 해제합니다.

    Returns:
        해제 성공 여부.
    """
    async with transactional() as cur:
        await cur.execute(
            """
            DELETE FROM user_follow
            WHERE follower_id = %s AND following_id = %s
            """,
            (follower_id, following_id),
        )
        return cur.rowcount > 0


async def get_follower_ids(user_id: int) -> set[int]:
    """사용자의 팔로워 ID 집합을 반환합니다."""
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT follower_id FROM user_follow WHERE following_id = %s",
            (user_id,),
        )
        rows = await cur.fetchall()
        return {row[0] for row in rows}


async def get_following_ids(user_id: int) -> set[int]:
    """사용자가 팔로우하는 ID 집합을 반환합니다."""
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT following_id FROM user_follow WHERE follower_id = %s",
            (user_id,),
        )
        rows = await cur.fetchall()
        return {row[0] for row in rows}


async def is_following(follower_id: int, following_id: int) -> bool:
    """팔로우 여부를 확인합니다."""
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT 1 FROM user_follow WHERE follower_id = %s AND following_id = %s",
            (follower_id, following_id),
        )
        return await cur.fetchone() is not None


async def get_follow_counts(user_id: int) -> dict:
    """팔로워/팔로잉 수를 반환합니다."""
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT COUNT(*) FROM user_follow WHERE following_id = %s",
            (user_id,),
        )
        followers = (await cur.fetchone())[0]

        await cur.execute(
            "SELECT COUNT(*) FROM user_follow WHERE follower_id = %s",
            (user_id,),
        )
        following = (await cur.fetchone())[0]

    return {"followers_count": followers, "following_count": following}


async def get_my_following(user_id: int, offset: int = 0, limit: int = 10) -> tuple[list[dict], int]:
    """팔로잉 목록을 조회합니다."""
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT COUNT(*) FROM user_follow WHERE follower_id = %s",
            (user_id,),
        )
        total_count = (await cur.fetchone())[0]

        await cur.execute(
            """
                SELECT uf.id, uf.following_id, u.nickname, u.profile_img, uf.created_at
                FROM user_follow uf
                JOIN user u ON uf.following_id = u.id
                WHERE uf.follower_id = %s AND u.deleted_at IS NULL
                ORDER BY uf.created_at DESC
                LIMIT %s OFFSET %s
                """,
            (user_id, limit, offset),
        )
        rows = await cur.fetchall()

    following = []
    for r in rows:
        following.append(
            {
                "follow_id": r[0],
                "user_id": r[1],
                "nickname": r[2],
                "profile_img": r[3],
                "created_at": r[4],
            }
        )

    return following, total_count


async def get_my_followers(user_id: int, offset: int = 0, limit: int = 10) -> tuple[list[dict], int]:
    """팔로워 목록을 조회합니다."""
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT COUNT(*) FROM user_follow WHERE following_id = %s",
            (user_id,),
        )
        total_count = (await cur.fetchone())[0]

        await cur.execute(
            """
                SELECT uf.id, uf.follower_id, u.nickname, u.profile_img, uf.created_at
                FROM user_follow uf
                JOIN user u ON uf.follower_id = u.id
                WHERE uf.following_id = %s AND u.deleted_at IS NULL
                ORDER BY uf.created_at DESC
                LIMIT %s OFFSET %s
                """,
            (user_id, limit, offset),
        )
        rows = await cur.fetchall()

    followers = []
    for r in rows:
        followers.append(
            {
                "follow_id": r[0],
                "user_id": r[1],
                "nickname": r[2],
                "profile_img": r[3],
                "created_at": r[4],
            }
        )

    return followers, total_count
