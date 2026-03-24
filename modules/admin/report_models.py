"""report_models: 신고 관련 데이터 모델 및 함수 모듈."""

from dataclasses import dataclass
from datetime import datetime

from core.database.connection import get_cursor, transactional

_REPORT_COLUMNS = (
    "id, reporter_id, target_type, target_id, reason, description, status, resolved_by, resolved_at, created_at"
)


@dataclass(frozen=True)
class Report:
    """신고 데이터 클래스."""

    id: int
    reporter_id: int
    target_type: str
    target_id: int
    reason: str
    description: str | None
    status: str
    resolved_by: int | None
    resolved_at: datetime | None
    created_at: datetime | None = None


async def create_report(
    reporter_id: int,
    target_type: str,
    target_id: int,
    reason: str,
    description: str | None = None,
) -> Report:
    """신고를 생성합니다. IntegrityError는 전파하여 controller에서 처리합니다."""
    async with transactional() as cur:
        await cur.execute(
            "INSERT INTO report (reporter_id, target_type, target_id, reason, description) VALUES (%s, %s, %s, %s, %s)",
            (reporter_id, target_type, target_id, reason, description),
        )
        report_id = cur.lastrowid

        await cur.execute(f"SELECT {_REPORT_COLUMNS} FROM report WHERE id = %s", (report_id,))
        row = await cur.fetchone()
        return Report(**row)


async def get_reports(
    status: str | None = None,
    offset: int = 0,
    limit: int = 20,
) -> list[dict]:
    """신고 목록을 reporter 닉네임과 함께 조회합니다."""
    async with get_cursor() as cur:
        where = "1=1"
        params: list = []

        if status:
            where += " AND r.status = %s"
            params.append(status)

        params.extend([limit, offset])

        await cur.execute(
            f"""
                SELECT r.id AS report_id, r.reporter_id, r.target_type, r.target_id,
                       r.reason, r.description, r.status,
                       r.resolved_by, r.resolved_at, r.created_at,
                       u.nickname AS reporter_nickname
                FROM report r
                LEFT JOIN user u ON r.reporter_id = u.id
                WHERE {where}
                ORDER BY r.created_at DESC
                LIMIT %s OFFSET %s
                """,
            params,
        )
        return [dict(row) for row in await cur.fetchall()]


async def get_reports_count(status: str | None = None) -> int:
    """신고 총 개수를 반환합니다."""
    async with get_cursor() as cur:
        where = "1=1"
        params: list = []

        if status:
            where += " AND status = %s"
            params.append(status)

        await cur.execute(f"SELECT COUNT(*) AS cnt FROM report WHERE {where}", params)
        row = await cur.fetchone()
        return row["cnt"] if row else 0


async def get_report_by_id(report_id: int) -> Report | None:
    """ID로 신고를 조회합니다."""
    async with get_cursor() as cur:
        await cur.execute(f"SELECT {_REPORT_COLUMNS} FROM report WHERE id = %s", (report_id,))
        row = await cur.fetchone()
        return Report(**row) if row else None


async def resolve_report(report_id: int, admin_id: int, new_status: str) -> Report | None:
    """신고를 처리합니다. pending 상태만 처리 가능합니다."""
    async with transactional() as cur:
        await cur.execute(
            "UPDATE report SET status = %s, resolved_by = %s, resolved_at = NOW() WHERE id = %s AND status = 'pending'",
            (new_status, admin_id, report_id),
        )
        if cur.rowcount == 0:
            return None

        await cur.execute(f"SELECT {_REPORT_COLUMNS} FROM report WHERE id = %s", (report_id,))
        row = await cur.fetchone()
        return Report(**row) if row else None


async def reopen_report(report_id: int) -> Report | None:
    """처리된 신고를 다시 pending 상태로 되돌립니다."""
    async with transactional() as cur:
        await cur.execute(
            "UPDATE report SET status = 'pending', resolved_by = NULL, resolved_at = NULL "
            "WHERE id = %s AND status != 'pending'",
            (report_id,),
        )
        if cur.rowcount == 0:
            return None

        await cur.execute(f"SELECT {_REPORT_COLUMNS} FROM report WHERE id = %s", (report_id,))
        row = await cur.fetchone()
        return Report(**row) if row else None
