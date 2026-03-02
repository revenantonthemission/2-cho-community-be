"""report_models: 신고 관련 데이터 모델 및 함수 모듈."""

from dataclasses import dataclass
from datetime import datetime

from database.connection import get_connection, transactional


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


def _row_to_report(row: tuple) -> Report:
    """데이터베이스 행을 Report 객체로 변환합니다."""
    return Report(
        id=row[0],
        reporter_id=row[1],
        target_type=row[2],
        target_id=row[3],
        reason=row[4],
        description=row[5],
        status=row[6],
        resolved_by=row[7],
        resolved_at=row[8],
        created_at=row[9],
    )


async def create_report(
    reporter_id: int,
    target_type: str,
    target_id: int,
    reason: str,
    description: str | None = None,
) -> Report:
    """신고를 생성합니다.

    IntegrityError는 전파하여 controller에서 처리합니다 (중복 신고).
    """
    async with transactional() as cur:
        await cur.execute(
            """
            INSERT INTO report (reporter_id, target_type, target_id, reason, description)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (reporter_id, target_type, target_id, reason, description),
        )
        report_id = cur.lastrowid

        await cur.execute(
            """
            SELECT id, reporter_id, target_type, target_id, reason, description,
                   status, resolved_by, resolved_at, created_at
            FROM report WHERE id = %s
            """,
            (report_id,),
        )
        row = await cur.fetchone()
        return _row_to_report(row)


async def get_reports(
    status: str | None = None,
    offset: int = 0,
    limit: int = 20,
) -> list[dict]:
    """신고 목록을 reporter 닉네임과 함께 조회합니다."""
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            where = "1=1"
            params: list = []

            if status:
                where += " AND r.status = %s"
                params.append(status)

            params.extend([limit, offset])

            await cur.execute(
                f"""
                SELECT r.id, r.reporter_id, r.target_type, r.target_id,
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
            rows = await cur.fetchall()

            return [
                {
                    "report_id": row[0],
                    "reporter_id": row[1],
                    "target_type": row[2],
                    "target_id": row[3],
                    "reason": row[4],
                    "description": row[5],
                    "status": row[6],
                    "resolved_by": row[7],
                    "resolved_at": row[8],
                    "created_at": row[9],
                    "reporter_nickname": row[10],
                }
                for row in rows
            ]


async def get_reports_count(status: str | None = None) -> int:
    """신고 총 개수를 반환합니다."""
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            where = "1=1"
            params: list = []

            if status:
                where += " AND status = %s"
                params.append(status)

            await cur.execute(
                f"SELECT COUNT(*) FROM report WHERE {where}",
                params,
            )
            row = await cur.fetchone()
            return row[0] if row else 0


async def get_report_by_id(report_id: int) -> Report | None:
    """ID로 신고를 조회합니다."""
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, reporter_id, target_type, target_id, reason, description,
                       status, resolved_by, resolved_at, created_at
                FROM report WHERE id = %s
                """,
                (report_id,),
            )
            row = await cur.fetchone()
            return _row_to_report(row) if row else None


async def resolve_report(
    report_id: int,
    admin_id: int,
    new_status: str,
) -> Report | None:
    """신고를 처리합니다. pending 상태만 처리 가능합니다."""
    async with transactional() as cur:
        await cur.execute(
            """
            UPDATE report
            SET status = %s, resolved_by = %s, resolved_at = NOW()
            WHERE id = %s AND status = 'pending'
            """,
            (new_status, admin_id, report_id),
        )

        if cur.rowcount == 0:
            return None

        await cur.execute(
            """
            SELECT id, reporter_id, target_type, target_id, reason, description,
                   status, resolved_by, resolved_at, created_at
            FROM report WHERE id = %s
            """,
            (report_id,),
        )
        row = await cur.fetchone()
        return _row_to_report(row) if row else None
