"""database.connection: MySQL 데이터베이스 연결 관리 모듈.

aiomysql을 사용하여 비동기 MySQL 연결 풀을 관리합니다.
"""

import aiomysql
from typing import AsyncGenerator
from contextlib import asynccontextmanager

from core.config import settings


# 전역 연결 풀
_pool: aiomysql.Pool | None = None


async def init_db() -> None:
    """데이터베이스 연결 풀을 초기화합니다.

    애플리케이션 시작 시 호출되어야 합니다.
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
            minsize=1,
            maxsize=10,
            connect_timeout=5,  # 5초 연결 타임아웃
        )
        print(
            f"MySQL 연결 풀 초기화 완료: {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
        )
    except Exception as e:
        print(f"MySQL 연결 풀 초기화 실패: {e}")
        raise


async def close_db() -> None:
    """데이터베이스 연결 풀을 종료합니다.

    애플리케이션 종료 시 호출되어야 합니다.
    """
    global _pool
    if _pool:
        _pool.close()
        await _pool.wait_closed()
        _pool = None
        print("MySQL 연결 풀 종료")


def get_pool() -> aiomysql.Pool:
    """현재 연결 풀을 반환합니다.

    Returns:
        연결 풀 객체.

    Raises:
        RuntimeError: 연결 풀이 초기화되지 않은 경우.
    """
    if _pool is None:
        raise RuntimeError("데이터베이스 연결 풀이 초기화되지 않았습니다.")
    return _pool


@asynccontextmanager
async def get_connection() -> AsyncGenerator[aiomysql.Connection, None]:
    """데이터베이스 연결을 컨텍스트 매니저로 제공합니다.

    사용 예시:
        async with get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM user")
                result = await cur.fetchall()

    Yields:
        MySQL 연결 객체.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        yield conn


@asynccontextmanager
async def transactional() -> AsyncGenerator[aiomysql.Cursor, None]:
    """트랜잭션을 관리하는 컨텍스트 매니저.

    범위 내에서 예외 발생 시 롤백, 정상 종료 시 커밋합니다.
    주의: 이 컨텍스트 매니저는 커서를 반환합니다.

    Yields:
        MySQL 커서 객체.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        try:
            await conn.begin()
            async with conn.cursor() as cur:
                yield cur
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise


async def test_connection() -> bool:
    """데이터베이스 연결을 테스트합니다.

    Returns:
        연결 성공 여부.
    """
    try:
        async with get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1")
                result = await cur.fetchone()
                print(f"데이터베이스 연결 테스트 성공: {result}")
                return True
    except Exception as e:
        print(f"데이터베이스 연결 테스트 실패: {e}")
        return False
