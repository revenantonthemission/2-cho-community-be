"""database.connection: MySQL 데이터베이스 연결 관리 모듈.

aiomysql을 사용하여 비동기 MySQL 연결 풀을 관리합니다.
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import aiomysql

from core.config import settings

logger = logging.getLogger(__name__)

# 전역 연결 풀
_pool: aiomysql.Pool | None = None


async def init_db() -> None:
    """데이터베이스 연결 풀을 초기화합니다.

    애플리케이션 시작 시 호출되어야 합니다.

    트랜잭션 격리 수준:
    - READ COMMITTED: Dirty Read 방지, REPEATABLE READ보다 가벼움
    - 웹 애플리케이션에 적합한 수준
    """
    global _pool
    try:
        _pool = await aiomysql.create_pool(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            db=settings.DB_NAME,
            charset="utf8mb4",
            autocommit=True,
            minsize=5,
            maxsize=50,
            connect_timeout=5,  # 5초 연결 타임아웃
            # 트랜잭션 격리 수준 설정
            init_command="SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED",
        )
        logger.info(
            f"MySQL 연결 풀 초기화 완료: {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME} "
            f"(격리 수준: READ COMMITTED, 풀 크기: 5-50)"
        )
    except Exception as e:
        logger.error(f"MySQL 연결 풀 초기화 실패: {e}")
        raise


async def close_db() -> None:
    """데이터베이스 연결 풀을 종료합니다."""
    global _pool
    if _pool:
        _pool.close()
        await _pool.wait_closed()
        _pool = None
        logger.info("MySQL 연결 풀 종료")


def get_pool() -> aiomysql.Pool:
    """현재 연결 풀을 반환합니다. 초기화되지 않은 경우 RuntimeError."""
    if _pool is None:
        raise RuntimeError("데이터베이스 연결 풀이 초기화되지 않았습니다.")
    return _pool


@asynccontextmanager
async def _acquire_dict_cursor() -> AsyncGenerator[tuple[aiomysql.Connection, aiomysql.DictCursor], None]:
    """풀에서 연결을 획득하고 DictCursor를 여는 내부 헬퍼.

    get_cursor()와 transactional()이 공유하여 중복을 제거합니다.
    """
    pool = get_pool()
    async with pool.acquire() as conn, conn.cursor(aiomysql.DictCursor) as cur:
        yield conn, cur


@asynccontextmanager
async def get_connection() -> AsyncGenerator[aiomysql.Connection, None]:
    """데이터베이스 연결을 컨텍스트 매니저로 제공합니다. (하위 호환성용)"""
    pool = get_pool()
    async with pool.acquire() as conn:
        yield conn


@asynccontextmanager
async def get_cursor() -> AsyncGenerator[aiomysql.DictCursor, None]:
    """DictCursor를 컨텍스트 매니저로 제공합니다. (읽기 전용 쿼리용)"""
    async with _acquire_dict_cursor() as (_conn, cur):
        yield cur


@asynccontextmanager
async def transactional() -> AsyncGenerator[aiomysql.DictCursor, None]:
    """트랜잭션 컨텍스트 매니저. 예외 시 롤백, 정상 종료 시 커밋. DictCursor 반환."""
    async with _acquire_dict_cursor() as (conn, cur):
        try:
            await conn.begin()
            yield cur
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise


async def test_connection() -> bool:
    """데이터베이스 연결을 테스트합니다."""
    try:
        async with get_cursor() as cur:
            await cur.execute("SELECT 1")
            result = await cur.fetchone()
            logger.info(f"데이터베이스 연결 테스트 성공: {result}")
            return True
    except Exception as e:
        logger.error(f"데이터베이스 연결 테스트 실패: {e}")
        return False
