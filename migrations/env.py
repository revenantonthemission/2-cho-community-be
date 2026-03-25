"""Alembic 환경 설정.

core.config.settings에서 DB URL을 로드하여 환경변수 이중 관리를 방지합니다.
pymysql을 동기 드라이버로 사용합니다 (Alembic은 동기 실행).
"""

import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가하여 core 패키지 import 가능하게 함
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from core.config import settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

DB_URL = (
    f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}"
    f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
    f"?charset=utf8mb4"
)


def run_migrations_offline() -> None:
    """오프라인 모드: SQL 스크립트만 생성 (DB 연결 없음)."""
    context.configure(url=DB_URL, target_metadata=None, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """온라인 모드: DB에 직접 마이그레이션 실행."""
    configuration = {"sqlalchemy.url": DB_URL}
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
