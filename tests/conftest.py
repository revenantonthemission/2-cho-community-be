import os
import sys

# Rate Limiter 우회를 위한 테스트 환경 변수 설정
os.environ["TESTING"] = "true"

import aiomysql
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
    """테스트용 헬퍼: 35개 테이블 전체 TRUNCATE + 시드 데이터 재삽입."""
    async with get_connection() as conn, conn.cursor(aiomysql.DictCursor) as cur:
        await cur.execute("SET FOREIGN_KEY_CHECKS = 0")
        # 평판 시스템 테이블 (자식 우선)
        await cur.execute("TRUNCATE TABLE user_badge")
        await cur.execute("TRUNCATE TABLE reputation_event")
        await cur.execute("TRUNCATE TABLE user_daily_visit")
        # 기존 테이블
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
        await cur.execute("TRUNCATE TABLE post_subscription")
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
        # 배지/신뢰등급 시드 데이터 확인 및 재삽입
        await cur.execute("SELECT COUNT(*) AS cnt FROM badge_definition")
        row = await cur.fetchone()
        if row["cnt"] == 0:
            # fmt: off
            await cur.execute(
                "INSERT INTO badge_definition"
                " (name,description,icon,category,trigger_type,trigger_threshold,points_awarded) VALUES"
                " ('First Post','첫 번째 게시글을 작성했습니다','edit','bronze','post_count',1,5),"
                " ('First Comment','첫 번째 댓글을 작성했습니다','comment','bronze','comment_count',1,5),"
                " ('First Like','첫 번째 좋아요를 눌렀습니다','heart','bronze','like_given_count',1,2),"
                " ('Welcome','프로필을 완성했습니다 (아바타 + 배포판)','user-check','bronze','profile_completed',1,5),"
                " ('Bookworm','첫 번째 북마크를 추가했습니다','bookmark','bronze','bookmark_count',1,2),"
                " ('Curious','10개의 게시글을 조회했습니다','eye','bronze','post_view_count',10,2),"
                " ('Supporter','10개의 좋아요를 눌렀습니다','thumbs-up','bronze','like_given_count',10,5),"
                " ('Editor','첫 번째 위키 페이지를 편집했습니다','file-text','bronze','wiki_edit_count',1,5),"
                " ('Reviewer','첫 번째 패키지 리뷰를 작성했습니다','star','bronze','package_review_count',1,5),"
                " ('Messenger','첫 번째 DM을 보냈습니다','message-circle','bronze','dm_sent_count',1,2),"
                " ('Prolific','50개의 게시글을 작성했습니다','edit-3','silver','post_count',50,20),"
                " ('Commenter','100개의 댓글을 작성했습니다','message-square','silver','comment_count',100,20),"
                " ('Helpful Answer','10개의 답변이 채택되었습니다','check-circle','silver','accepted_answer_count',10,30),"
                " ('Nice Question','하나의 게시글이 10개의 좋아요를 받았습니다','award','silver','single_post_likes',10,20),"
                " ('Popular Question','하나의 게시글이 100회 조회되었습니다','trending-up','silver','single_post_views',100,20),"
                " ('Wiki Contributor','20개의 위키 페이지를 편집했습니다','book-open','silver','wiki_edit_count',20,20),"
                " ('Socializer','25명의 팔로워를 모았습니다','users','silver','follower_count',25,15),"
                " ('Devoted','14일 연속 방문했습니다','calendar','silver','consecutive_visit_days',14,20),"
                " ('Package Critic','10개의 패키지 리뷰를 작성했습니다','package','silver','package_review_count',10,15),"
                " ('Legendary','평판 점수 5000을 달성했습니다','zap','gold','reputation_score',5000,100),"
                " ('Great Answer','하나의 답변이 50개의 좋아요를 받았습니다','shield','gold','single_comment_likes',50,50),"
                " ('Famous Question','하나의 게시글이 1000회 조회되었습니다','globe','gold','single_post_views',1000,50),"
                " ('Mentor','100개의 답변이 채택되었습니다','award','gold','accepted_answer_count',100,100),"
                " ('Wiki Master','100개의 위키 페이지를 편집했습니다','book','gold','wiki_edit_count',100,50),"
                " ('Dedicated','60일 연속 방문했습니다','sunrise','gold','consecutive_visit_days',60,50),"
                " ('Community Pillar','100명의 팔로워를 모았습니다','flag','gold','follower_count',100,50),"
                " ('Completionist','모든 Bronze + Silver 배지를 획득했습니다','crown','gold','badge_count',19,100)"
            )
            # fmt: on
        await cur.execute("SELECT COUNT(*) AS cnt FROM trust_level_definition")
        row = await cur.fetchone()
        if row["cnt"] == 0:
            await cur.execute("""
                INSERT INTO trust_level_definition (level, name, min_reputation, description) VALUES
                (0, 'New User', 0, '기본 읽기/쓰기'),
                (1, 'Member', 50, '위키 편집, 댓글 좋아요'),
                (2, 'Regular', 200, '태그 생성, 패키지 등록'),
                (3, 'Trusted', 1000, '게시글 신고 우선처리'),
                (4, 'Leader', 5000, '커뮤니티 모더레이션 보조')
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
