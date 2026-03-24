import os
import sys

# Rate Limiter 우회를 위한 테스트 환경 변수 설정
os.environ["TESTING"] = "true"

import pytest
import pytest_asyncio
from faker import Faker
from httpx import ASGITransport, AsyncClient

from core.database.connection import close_db, get_connection, init_db
from main import app

# ---------------------------------------------------------------------------
# 데이터 초기화
# ---------------------------------------------------------------------------


async def clear_all_data() -> None:
    """테스트용 헬퍼: 31개 테이블 전체 TRUNCATE + 카테고리 시드 재삽입."""
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute("SET FOREIGN_KEY_CHECKS = 0")
        await cur.execute("TRUNCATE TABLE wiki_page_tag")
        await cur.execute("TRUNCATE TABLE wiki_page")
        await cur.execute("TRUNCATE TABLE package_review")
        await cur.execute("TRUNCATE TABLE package")
        await cur.execute("TRUNCATE TABLE user_post_score")
        await cur.execute("TRUNCATE TABLE dm_message")
        await cur.execute("TRUNCATE TABLE dm_conversation")
        await cur.execute("TRUNCATE TABLE poll_vote")
        await cur.execute("TRUNCATE TABLE poll_option")
        await cur.execute("TRUNCATE TABLE poll")
        await cur.execute("TRUNCATE TABLE report")
        await cur.execute("TRUNCATE TABLE social_account")
        await cur.execute("TRUNCATE TABLE post_draft")
        await cur.execute("TRUNCATE TABLE notification_setting")
        await cur.execute("TRUNCATE TABLE notification")
        await cur.execute("TRUNCATE TABLE image")
        await cur.execute("TRUNCATE TABLE email_verification")
        await cur.execute("TRUNCATE TABLE post_view_log")
        await cur.execute("TRUNCATE TABLE post_bookmark")
        await cur.execute("TRUNCATE TABLE comment_like")
        await cur.execute("TRUNCATE TABLE post_image")
        await cur.execute("TRUNCATE TABLE post_tag")
        await cur.execute("TRUNCATE TABLE post_like")
        await cur.execute("TRUNCATE TABLE comment")
        await cur.execute("TRUNCATE TABLE post")
        await cur.execute("TRUNCATE TABLE tag")
        await cur.execute("TRUNCATE TABLE user_block")
        await cur.execute("TRUNCATE TABLE user_follow")
        await cur.execute("TRUNCATE TABLE refresh_token")
        await cur.execute("TRUNCATE TABLE category")
        await cur.execute("TRUNCATE TABLE user")
        await cur.execute("SET FOREIGN_KEY_CHECKS = 1")
        # 카테고리 시드 데이터 삽입
        await cur.execute("""
                INSERT INTO category (name, slug, description, sort_order) VALUES
                    ('배포판', 'distro', 'Ubuntu, Fedora, Arch 등 배포판별 토론 공간입니다.', 1),
                    ('Q&A', 'qna', '리눅스 트러블슈팅, 설치, 설정 관련 질문과 답변입니다.', 2),
                    ('뉴스/소식', 'news', '리눅스 생태계의 최신 소식을 공유합니다.', 3),
                    ('프로젝트/쇼케이스', 'showcase', 'dotfiles, 스크립트, 오픈소스 기여를 공유합니다.', 4),
                    ('팁/가이드', 'guide', '리눅스 튜토리얼과 How-to 가이드입니다.', 5),
                    ('공지사항', 'notice', '관리자 공지사항입니다.', 6)
            """)


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# 핵심 픽스처 (db, client, fake)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def db():
    """각 테스트 함수 실행 전 데이터 초기화 및 DB 연결 관리."""
    await init_db()
    try:
        await clear_all_data()
        yield
    finally:
        await close_db()


@pytest_asyncio.fixture
async def client(db):
    """API 테스트를 위한 Async Client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def fake():
    return Faker("ko_KR")


# ---------------------------------------------------------------------------
# 페이로드 생성 헬퍼
# ---------------------------------------------------------------------------


def _make_user_payload(fake: Faker, **overrides) -> dict:
    """회원가입용 페이로드를 생성한다. overrides로 개별 필드 덮어쓰기 가능."""
    payload = {
        "email": fake.email(),
        "password": "Password123!",
        # 닉네임 길이 5~10자 보장
        "nickname": fake.lexify(text="?????") + str(fake.random_int(10, 99)),
        "terms_agreed": "true",
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# 공통 헬퍼 함수 (픽스처가 아닌 async 함수)
# ---------------------------------------------------------------------------


async def create_verified_user(client: AsyncClient, fake: Faker, **overrides) -> dict:
    """회원가입 → 이메일 인증 → 로그인까지 완료된 사용자 dict를 반환한다.

    반환 dict 키:
        client, user_id, email, nickname, token, headers, payload
    """
    payload = _make_user_payload(fake, **overrides)

    # 회원가입 (Form)
    signup_res = await client.post("/v1/users/", data=payload)
    assert signup_res.status_code == 201, f"회원가입 실패: {signup_res.status_code}, {signup_res.text}"

    # 이메일 인증 — DB 직접 업데이트
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE user SET email_verified = 1 WHERE email = %s",
            (payload["email"],),
        )

    # 로그인 (JSON)
    login_res = await client.post(
        "/v1/auth/session",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert login_res.status_code == 200, f"로그인 실패: {login_res.status_code}, {login_res.text}"

    login_data = login_res.json()
    access_token = login_data["data"]["access_token"]
    user_info = login_data["data"]["user"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # Bearer Token이 설정된 새 클라이언트 생성
    transport = ASGITransport(app=app)
    auth_client = AsyncClient(
        transport=transport,
        base_url="http://test",
        headers=headers,
        cookies=login_res.cookies,
    )

    return {
        "client": auth_client,
        "user_id": user_info["user_id"],
        "email": payload["email"],
        "nickname": user_info["nickname"],
        "token": access_token,
        "headers": headers,
        "payload": payload,
    }


async def create_admin_user(client: AsyncClient, fake: Faker) -> dict:
    """인증 완료 + admin 역할이 부여된 사용자 dict를 반환한다."""
    user = await create_verified_user(client, fake)

    # DB에서 역할을 admin으로 변경
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE user SET role = 'admin' WHERE id = %s",
            (user["user_id"],),
        )

    return user


async def create_test_post(client: AsyncClient, headers: dict, **overrides) -> dict:
    """게시글을 생성하고 응답 데이터를 반환한다."""
    post_data = {
        "title": overrides.pop("title", "테스트 게시글"),
        "content": overrides.pop("content", "테스트 내용입니다."),
        "category_id": overrides.pop("category_id", 1),
    }
    post_data.update(overrides)

    res = await client.post("/v1/posts/", json=post_data, headers=headers)
    assert res.status_code == 201, f"게시글 생성 실패: {res.status_code}, {res.text}"
    return res.json()["data"]


async def create_test_comment(client: AsyncClient, headers: dict, post_id: int, **overrides) -> dict:
    """댓글을 생성하고 응답 데이터를 반환한다."""
    comment_data = {
        "content": overrides.pop("content", "테스트 댓글입니다."),
    }
    comment_data.update(overrides)

    res = await client.post(f"/v1/posts/{post_id}/comments", json=comment_data, headers=headers)
    assert res.status_code == 201, f"댓글 생성 실패: {res.status_code}, {res.text}"
    return res.json()["data"]


# ---------------------------------------------------------------------------
# 레거시 호환 픽스처 (기존 테스트의 tuple 언패킹 유지)
# ---------------------------------------------------------------------------


@pytest.fixture
def user_payload(fake):
    """회원가입용 페이로드 생성."""
    return _make_user_payload(fake)


@pytest_asyncio.fixture
async def authorized_user(client, user_payload):
    """회원가입 및 로그인이 완료된 클라이언트와 유저 정보 반환.

    기존 테스트 호환을 위해 (client, user_info, user_payload) 튜플을 yield한다.
    """
    # 회원가입 (Form)
    signup_res = await client.post("/v1/users/", data=user_payload)

    if signup_res.status_code != 201:
        print(f"Signup failed: {signup_res.status_code}, {signup_res.text}")

    assert signup_res.status_code == 201

    # 이메일 인증 완료 처리
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE user SET email_verified = 1 WHERE email = %s",
            (user_payload["email"],),
        )

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
        cookies=login_res.cookies,
    )

    async with auth_client as ac:
        yield ac, user_info, user_payload


@pytest.fixture
def second_user_payload(fake):
    """두 번째 사용자용 페이로드 생성 (unverified_user 등에서 사용)."""
    return _make_user_payload(fake)


@pytest_asyncio.fixture
async def unverified_user(client, second_user_payload):
    """회원가입 및 로그인이 완료되었지만 이메일 미인증 상태인 클라이언트와 유저 정보 반환.

    authorized_user와 별도의 user_payload를 사용하여 동시 사용 시 충돌을 방지한다.
    기존 테스트 호환을 위해 (client, user_info, user_payload) 튜플을 yield한다.
    """
    user_payload = second_user_payload

    # 회원가입 (Form)
    signup_res = await client.post("/v1/users/", data=user_payload)

    if signup_res.status_code != 201:
        print(f"Signup failed: {signup_res.status_code}, {signup_res.text}")

    assert signup_res.status_code == 201

    # 로그인 (JSON) — 이메일 미인증 상태
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
        cookies=login_res.cookies,
    )

    async with auth_client as ac:
        yield ac, user_info, user_payload
