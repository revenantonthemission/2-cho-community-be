"""like_models: 좋아요 관련 데이터 모델 및 함수 모듈.

주요 개선사항:
- add_like 함수에 트랜잭션 적용 (경쟁 상태 방지)
- INSERT와 SELECT을 원자적으로 처리하여 Phantom Read 방지
"""

from dataclasses import dataclass
from datetime import datetime

from database.connection import get_connection, transactional
from pymysql.err import IntegrityError


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


def _row_to_like(row: tuple) -> Like:
    """데이터베이스 행을 Like 객체로 변환합니다."""
    return Like(
        id=row[0],
        user_id=row[1],
        post_id=row[2],
        created_at=row[3],
    )


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

    트랜잭션을 사용하여 INSERT와 SELECT을 원자적으로 처리합니다.
    이를 통해 경쟁 상태(Race Condition)와 Phantom Read를 방지합니다.

    개선사항:
    - transactional() 컨텍스트 매니저 사용
    - INSERT와 SELECT이 같은 트랜잭션 내에서 실행
    - 중간에 다른 트랜잭션이 개입할 수 없음
    - IntegrityError와 기타 예외를 분리 처리

    Args:
        post_id: 게시글 ID.
        user_id: 사용자 ID.

    Returns:
        생성된 좋아요 객체, 이미 좋아요한 경우 None.

    Raises:
        RuntimeError: 삽입 직후 조회 실패 시 (발생하지 않아야 함).
    """
    async with transactional() as cur:
        # INSERT 단계: IntegrityError만 처리
        try:
            await cur.execute(
                """
                INSERT INTO post_like (user_id, post_id)
                VALUES (%s, %s)
                """,
                (user_id, post_id),
            )
        except IntegrityError:
            # 중복 좋아요 (Unique constraint violation)
            # 트랜잭션은 자동으로 롤백됨
            return None

        like_id = cur.lastrowid

        # SELECT 단계: 실패 시 예외 전파 (트랜잭션 롤백됨)
        await cur.execute(
            """
            SELECT id, user_id, post_id, created_at
            FROM post_like
            WHERE id = %s
            """,
            (like_id,),
        )
        row = await cur.fetchone()

        # 삽입 직후 조회 실패는 발생하지 않아야 함
        if not row:
            raise RuntimeError(
                f"좋아요 삽입 직후 조회 실패: like_id={like_id}, "
                f"post_id={post_id}, user_id={user_id}"
            )

        return _row_to_like(row)


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
