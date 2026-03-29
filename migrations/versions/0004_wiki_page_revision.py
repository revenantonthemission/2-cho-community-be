"""wiki_page_revision 테이블 추가 (전체 스냅샷 방식).

위키 페이지의 편집 이력을 리비전 단위로 저장.
기존 위키 페이지는 리비전 1로 백필.

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-29
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # 테이블 존재 여부로 멱등성 판단
    result = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = 'wiki_page_revision'"
        )
    )
    if not result.scalar():
        conn.execute(
            text(
                """
                CREATE TABLE wiki_page_revision (
                    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    wiki_page_id INT UNSIGNED NOT NULL,
                    revision_number INT UNSIGNED NOT NULL,
                    title VARCHAR(200) NOT NULL,
                    content TEXT NOT NULL,
                    edit_summary VARCHAR(500) NULL,
                    editor_id INT UNSIGNED NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (wiki_page_id) REFERENCES wiki_page(id) ON DELETE CASCADE,
                    FOREIGN KEY (editor_id) REFERENCES user(id),
                    UNIQUE KEY uk_page_revision (wiki_page_id, revision_number),
                    INDEX idx_revision_page_created (wiki_page_id, created_at DESC)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
        )

        # 기존 위키 페이지를 리비전 1로 백필
        conn.execute(
            text(
                """
                INSERT INTO wiki_page_revision
                    (wiki_page_id, revision_number, title, content, edit_summary, editor_id, created_at)
                SELECT id, 1, title, content, '초기 작성 (마이그레이션)',
                       COALESCE(last_edited_by, author_id),
                       COALESCE(updated_at, created_at)
                FROM wiki_page
                WHERE deleted_at IS NULL
                """
            )
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DROP TABLE IF EXISTS wiki_page_revision"))
