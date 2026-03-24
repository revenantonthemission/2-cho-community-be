"""poll_models: 투표 관련 데이터 모델 및 함수 모듈."""

from datetime import UTC, datetime

from database.connection import get_connection, transactional


async def create_poll(
    post_id: int,
    question: str,
    options: list[str],
    expires_at: datetime | None = None,
) -> int:
    """투표를 생성합니다. 반환값: poll_id."""
    async with transactional() as cur:
        await cur.execute(
            "INSERT INTO poll (post_id, question, expires_at) VALUES (%s, %s, %s)",
            (post_id, question, expires_at),
        )
        poll_id = cur.lastrowid
        for i, option_text in enumerate(options):
            await cur.execute(
                "INSERT INTO poll_option (poll_id, option_text, sort_order) VALUES (%s, %s, %s)",
                (poll_id, option_text, i),
            )
    return poll_id


async def get_poll_by_post_id(post_id: int, current_user_id: int | None = None) -> dict | None:
    """게시글의 투표 데이터를 조회합니다."""
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id, question, expires_at, created_at FROM poll WHERE post_id = %s",
            (post_id,),
        )
        poll_row = await cur.fetchone()
        if not poll_row:
            return None

        poll_id = poll_row[0]
        expires_at = poll_row[2]

        # 만료 여부 확인
        is_expired = False
        if expires_at:
            now = datetime.now(UTC)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            is_expired = now > expires_at

        # 옵션별 투표 수 조회
        await cur.execute(
            """
                SELECT po.id, po.option_text, po.sort_order,
                       COUNT(pv.id) AS vote_count
                FROM poll_option po
                LEFT JOIN poll_vote pv ON po.id = pv.option_id
                WHERE po.poll_id = %s
                GROUP BY po.id, po.option_text, po.sort_order
                ORDER BY po.sort_order
                """,
            (poll_id,),
        )
        option_rows = await cur.fetchall()

        total_votes = sum(r[3] for r in option_rows)

        # 현재 사용자의 투표 확인
        my_vote = None
        if current_user_id:
            await cur.execute(
                "SELECT option_id FROM poll_vote WHERE poll_id = %s AND user_id = %s",
                (poll_id, current_user_id),
            )
            vote_row = await cur.fetchone()
            if vote_row:
                my_vote = vote_row[0]

    options = [
        {
            "option_id": r[0],
            "option_text": r[1],
            "sort_order": r[2],
            "vote_count": r[3],
        }
        for r in option_rows
    ]

    return {
        "poll_id": poll_id,
        "question": poll_row[1],
        "expires_at": poll_row[2].isoformat() if poll_row[2] else None,
        "is_expired": is_expired,
        "options": options,
        "total_votes": total_votes,
        "my_vote": my_vote,
    }


async def vote(poll_id: int, option_id: int, user_id: int) -> None:
    """투표합니다.

    Raises:
        IntegrityError: 이미 투표한 경우.
    """
    async with transactional() as cur:
        await cur.execute(
            "INSERT INTO poll_vote (poll_id, option_id, user_id) VALUES (%s, %s, %s)",
            (poll_id, option_id, user_id),
        )


async def delete_vote(poll_id: int, user_id: int) -> bool:
    """투표를 취소합니다. 삭제된 행이 있으면 True 반환."""
    async with transactional() as cur:
        await cur.execute(
            "DELETE FROM poll_vote WHERE poll_id = %s AND user_id = %s",
            (poll_id, user_id),
        )
        return cur.rowcount > 0


async def change_vote(poll_id: int, option_id: int, user_id: int) -> bool:
    """투표를 변경합니다. 변경된 행이 있으면 True 반환."""
    async with transactional() as cur:
        await cur.execute(
            "UPDATE poll_vote SET option_id = %s WHERE poll_id = %s AND user_id = %s",
            (option_id, poll_id, user_id),
        )
        return cur.rowcount > 0


async def option_belongs_to_poll(option_id: int, poll_id: int) -> bool:
    """옵션이 해당 투표에 속하는지 확인합니다."""
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT 1 FROM poll_option WHERE id = %s AND poll_id = %s",
            (option_id, poll_id),
        )
        return await cur.fetchone() is not None


async def get_poll_id_by_post_id(post_id: int) -> int | None:
    """게시글의 투표 ID를 조회합니다."""
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT id FROM poll WHERE post_id = %s", (post_id,))
        row = await cur.fetchone()
        return row[0] if row else None
