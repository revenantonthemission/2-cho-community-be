import sys
import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from main import app
from database.connection import init_db, close_db
from models.post_models import clear_all_data
from faker import Faker

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
        "nickname": fake.lexify(text="?????") + str(fake.random_int(10, 99))
    }

@pytest_asyncio.fixture
async def authorized_user(client, user_payload):
    """회원가입 및 로그인이 완료된 클라이언트와 유저 정보 반환"""
    # 회원가입 (Form)
    signup_res = await client.post("/v1/users/", data=user_payload)
    
    if signup_res.status_code != 201:
        print(f"Signup failed: {signup_res.status_code}, {signup_res.text}")
        
    assert signup_res.status_code == 201
    
    # 로그인 (JSON)
    login_res = await client.post("/v1/auth/session", json={
        "email": user_payload["email"],
        "password": user_payload["password"]
    })
    assert login_res.status_code == 200
    
    user_info = login_res.json()["data"]["user"]
    return client, user_info, user_payload