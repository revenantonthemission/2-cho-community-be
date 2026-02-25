import sys
import os

# Rate Limiter 우회를 위한 테스트 환경 변수 설정
os.environ["TESTING"] = "true"

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from main import app
from database.connection import get_connection, init_db, close_db
from faker import Faker


async def clear_all_data() -> None:
    """테스트용 헬퍼: 모든 데이터를 삭제합니다."""
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SET FOREIGN_KEY_CHECKS = 0")
            await cur.execute("TRUNCATE TABLE post_view_log")
            await cur.execute("TRUNCATE TABLE post_like")
            await cur.execute("TRUNCATE TABLE comment")
            await cur.execute("TRUNCATE TABLE post")
            await cur.execute("TRUNCATE TABLE refresh_token")
            await cur.execute("TRUNCATE TABLE user")
            await cur.execute("SET FOREIGN_KEY_CHECKS = 1")


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest_asyncio.fixture(scope="function")
async def db():
    """각 테스트 함수 실행 전 데이터 초기화 및 DB 연결 관리"""
    await init_db()
    try:
        await clear_all_data()
        yield
    finally:
        await close_db()


@pytest_asyncio.fixture
async def client(db):
    """API 테스트를 위한 Async Client"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def fake():
    return Faker("ko_KR")


@pytest.fixture
def user_payload(fake):
    """회원가입용 페이로드 생성"""
    return {
        "email": fake.email(),
        "password": "Password123!",
        # 닉네임 길이 5~10자 보장
        "nickname": fake.lexify(text="?????") + str(fake.random_int(10, 99)),
    }


@pytest_asyncio.fixture
async def authorized_user(client, user_payload):
    """회원가입 및 로그인이 완료된 클라이언트와 유저 정보 반환.

    JWT Bearer Token을 Authorization 헤더에 설정한 새 클라이언트를 반환합니다.
    """
    # 회원가입 (Form)
    signup_res = await client.post("/v1/users/", data=user_payload)

    if signup_res.status_code != 201:
        print(f"Signup failed: {signup_res.status_code}, {signup_res.text}")

    assert signup_res.status_code == 201

    # 로그인 (JSON)
    login_res = await client.post(
        "/v1/auth/session",
        json={"email": user_payload["email"], "password": user_payload["password"]},
    )
    assert login_res.status_code == 200

    login_data = login_res.json()
    access_token = login_data["data"]["access_token"]
    user_info = login_data["data"]["user"]

    # Bearer Token이 설정된 새 클라이언트 생성
    transport = ASGITransport(app=app)
    auth_client = AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {access_token}"},
        cookies=login_res.cookies,  # refresh_token 쿠키 전달
    )

    async with auth_client as ac:
        yield ac, user_info, user_payload
