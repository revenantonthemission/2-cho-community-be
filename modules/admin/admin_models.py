"""admin_models: 관리자 대시보드 데이터 조회 모듈."""

from core.database.connection import get_connection
from core.utils.pagination import escape_like


async def get_dashboard_summary() -> dict:
    """대시보드 요약 통계를 조회합니다."""
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT COUNT(*) FROM user WHERE deleted_at IS NULL")
        total_users = (await cur.fetchone())[0]

        await cur.execute("SELECT COUNT(*) FROM post WHERE deleted_at IS NULL")
        total_posts = (await cur.fetchone())[0]

        await cur.execute("SELECT COUNT(*) FROM comment WHERE deleted_at IS NULL")
        total_comments = (await cur.fetchone())[0]

        await cur.execute("SELECT COUNT(*) FROM user WHERE deleted_at IS NULL AND DATE(created_at) = CURDATE()")
        today_signups = (await cur.fetchone())[0]

    return {
        "total_users": total_users,
        "total_posts": total_posts,
        "total_comments": total_comments,
        "today_signups": today_signups,
    }


async def get_daily_stats(days: int = 30) -> list[dict]:
    """최근 N일간 일별 통계를 조회합니다."""
    async with get_connection() as conn, conn.cursor() as cur:
        query = """
                WITH RECURSIVE dates AS (
                    SELECT CURDATE() AS d, 0 AS seq
                    UNION ALL
                    SELECT d - INTERVAL 1 DAY, seq + 1
                    FROM dates
                    WHERE seq < %s - 1
                )
                SELECT
                    dates.d AS date,
                    COALESCE(s.cnt, 0) AS signups,
                    COALESCE(p.cnt, 0) AS posts,
                    COALESCE(c.cnt, 0) AS comments
                FROM dates
                LEFT JOIN (
                    SELECT DATE(created_at) AS d, COUNT(*) AS cnt
                    FROM user WHERE deleted_at IS NULL
                    GROUP BY DATE(created_at)
                ) s ON dates.d = s.d
                LEFT JOIN (
                    SELECT DATE(created_at) AS d, COUNT(*) AS cnt
                    FROM post WHERE deleted_at IS NULL
                    GROUP BY DATE(created_at)
                ) p ON dates.d = p.d
                LEFT JOIN (
                    SELECT DATE(created_at) AS d, COUNT(*) AS cnt
                    FROM comment WHERE deleted_at IS NULL
                    GROUP BY DATE(created_at)
                ) c ON dates.d = c.d
                ORDER BY dates.d DESC
            """
        await cur.execute(query, (days,))
        rows = await cur.fetchall()

    return [
        {
            "date": row[0].isoformat() if row[0] else None,
            "signups": row[1],
            "posts": row[2],
            "comments": row[3],
        }
        for row in rows
    ]


async def get_users_list(offset: int = 0, limit: int = 20, search: str | None = None) -> tuple[list[dict], int]:
    """사용자 목록을 조회합니다 (관리자용)."""
    async with get_connection() as conn, conn.cursor() as cur:
        where = "WHERE u.deleted_at IS NULL"
        params: list = []

        if search:
            where += " AND (u.nickname LIKE %s OR u.email LIKE %s)"
            like_param = f"%{escape_like(search)}%"
            params.extend([like_param, like_param])

        # 전체 수
        await cur.execute(f"SELECT COUNT(*) FROM user u {where}", params)
        total_count = (await cur.fetchone())[0]

        # 목록
        query = f"""
                SELECT u.id, u.email, u.nickname, u.profile_img, u.role,
                       u.suspended_until, u.suspended_reason, u.created_at, u.email_verified
                FROM user u
                {where}
                ORDER BY u.created_at DESC
                LIMIT %s OFFSET %s
            """
        await cur.execute(query, [*params, limit, offset])
        rows = await cur.fetchall()

    users = [
        {
            "user_id": r[0],
            "email": r[1],
            "nickname": r[2],
            "profile_img": r[3],
            "role": r[4],
            "suspended_until": r[5].isoformat() if r[5] else None,
            "suspended_reason": r[6],
            "created_at": r[7].isoformat() if r[7] else None,
            "email_verified": bool(r[8]),
        }
        for r in rows
    ]
    return users, total_count
