"""block_models: 사용자 차단 관련 데이터 모델 및 함수 모듈."""

from dataclasses import dataclass
from datetime import datetime

from core.database.connection import get_cursor, transactional


@dataclass
class Block:
    """사용자 차단 데이터 클래스."""

    id: int
    blocker_id: int
    blocked_id: int
    created_at: datetime


async def add_block(blocker_id: int, blocked_id: int) -> Block:
    """사용자를 차단합니다.

    Raises:
        IntegrityError: 이미 차단한 경우.
    """
    async with transactional() as cur:
        await cur.execute(
            "INSERT INTO user_block (blocker_id, blocked_id) VALUES (%s, %s)",
            (blocker_id, blocked_id),
        )
        block_id = cur.lastrowid

        await cur.execute(
            "SELECT id, blocker_id, blocked_id, created_at FROM user_block WHERE id = %s",
            (block_id,),
        )
        row = await cur.fetchone()

        if not row:
            raise RuntimeError(
                f"차단 삽입 직후 조회 실패: block_id={block_id}, blocker_id={blocker_id}, blocked_id={blocked_id}"
            )

        return Block(**row)


async def remove_block(blocker_id: int, blocked_id: int) -> bool:
    """사용자 차단을 해제합니다."""
    async with transactional() as cur:
        await cur.execute(
            "DELETE FROM user_block WHERE blocker_id = %s AND blocked_id = %s",
            (blocker_id, blocked_id),
        )
        return cur.rowcount > 0


async def get_blocked_user_ids(blocker_id: int) -> set[int]:
    """차단한 사용자 ID 집합을 반환합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT blocked_id FROM user_block WHERE blocker_id = %s",
            (blocker_id,),
        )
        rows = await cur.fetchall()
        return {row["blocked_id"] for row in rows}


async def get_my_blocks(blocker_id: int, offset: int = 0, limit: int = 10) -> tuple[list[dict], int]:
    """차단 목록을 페이지네이션하여 반환합니다."""
    async with get_cursor() as cur:
        await cur.execute(
            "SELECT COUNT(*) AS cnt FROM user_block WHERE blocker_id = %s",
            (blocker_id,),
        )
        total_count = (await cur.fetchone())["cnt"]

        await cur.execute(
            """
                SELECT ub.id AS block_id, ub.blocked_id AS user_id,
                       u.nickname, u.profile_img, ub.created_at
                FROM user_block ub
                JOIN user u ON ub.blocked_id = u.id
                WHERE ub.blocker_id = %s
                ORDER BY ub.created_at DESC
                LIMIT %s OFFSET %s
                """,
            (blocker_id, limit, offset),
        )
        rows = await cur.fetchall()

    return [dict(r) for r in rows], total_count
