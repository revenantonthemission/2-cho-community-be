"""태그 테이블에 description, body, updated_at, updated_by 컬럼 추가.

태그에 설명(description)과 본문(body)을 저장할 수 있도록 확장.
updated_at/updated_by로 최종 수정 이력 추적.

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-29
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # description 컬럼 존재 여부로 멱등성 판단
    result = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = 'tag' "
            "AND column_name = 'description'"
        )
    )
    if not result.scalar():
        conn.execute(text("ALTER TABLE tag ADD COLUMN description VARCHAR(200) NULL AFTER name"))
        conn.execute(text("ALTER TABLE tag ADD COLUMN body TEXT NULL AFTER description"))
        conn.execute(
            text("ALTER TABLE tag ADD COLUMN updated_at TIMESTAMP NULL ON UPDATE CURRENT_TIMESTAMP AFTER created_at")
        )
        conn.execute(text("ALTER TABLE tag ADD COLUMN updated_by INT UNSIGNED NULL AFTER updated_at"))
        conn.execute(
            text("ALTER TABLE tag ADD CONSTRAINT fk_tag_updated_by FOREIGN KEY (updated_by) REFERENCES user(id)")
        )


def downgrade() -> None:
    conn = op.get_bind()

    # FK 제거 후 컬럼 삭제
    conn.execute(text("ALTER TABLE tag DROP FOREIGN KEY IF EXISTS fk_tag_updated_by"))
    conn.execute(text("ALTER TABLE tag DROP COLUMN IF EXISTS updated_by"))
    conn.execute(text("ALTER TABLE tag DROP COLUMN IF EXISTS updated_at"))
    conn.execute(text("ALTER TABLE tag DROP COLUMN IF EXISTS body"))
    conn.execute(text("ALTER TABLE tag DROP COLUMN IF EXISTS description"))
