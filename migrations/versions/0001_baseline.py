"""schema.sql 기반 베이스라인 — 전체 테이블 자동 생성.

신규 환경: alembic upgrade head → 이 마이그레이션이 schema.sql을 실행하여 모든 테이블 생성.
기존 환경: 테이블이 이미 존재하면 CREATE TABLE IF NOT EXISTS로 안전하게 건너뜀.

Revision ID: 0001
Revises:
Create Date: 2026-03-25
"""

from collections.abc import Sequence
from pathlib import Path

from alembic import op
from sqlalchemy import text

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # 기존 환경 감지: user 테이블이 이미 있으면 스키마 적용 건너뜀
    result = conn.execute(
        text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'user'")
    )
    if result.scalar():
        return

    # 신규 환경: schema.sql에서 전체 테이블 생성
    schema_path = Path(__file__).resolve().parents[2] / "core" / "database" / "schema.sql"
    sql = schema_path.read_text(encoding="utf-8")

    # 주석 행 제거 후 세미콜론으로 분할하여 순차 실행
    lines = [line for line in sql.splitlines() if not line.strip().startswith("--")]
    clean_sql = "\n".join(lines)

    for stmt in clean_sql.split(";"):
        stmt = stmt.strip()
        if stmt:
            conn.execute(text(stmt))


def downgrade() -> None:
    # 베이스라인은 롤백 불가
    raise RuntimeError("베이스라인 마이그레이션은 롤백할 수 없습니다.")
