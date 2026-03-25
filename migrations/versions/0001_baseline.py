"""기존 schema.sql 기반 베이스라인.

이 마이그레이션은 SQL을 실행하지 않습니다.
기존 환경: alembic stamp head로 버전만 마킹.
신규 환경: schema.sql 실행 후 alembic stamp head.

Revision ID: 0001
Revises:
Create Date: 2026-03-25
"""

from collections.abc import Sequence

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 기존 schema.sql이 이미 적용된 상태를 베이스라인으로 설정.
    # 실제 DDL은 schema.sql에서 처리됨.
    pass


def downgrade() -> None:
    # 베이스라인은 롤백 불가
    raise RuntimeError("베이스라인 마이그레이션은 롤백할 수 없습니다.")
