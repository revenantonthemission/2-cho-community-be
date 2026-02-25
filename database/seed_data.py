"""seed_data.py: 대규모 더미 데이터 생성 스크립트.

사용법:
    source .venv/bin/activate
    python database/seed_data.py

생성되는 데이터:
    - 10,000 users
    - 50,000 posts (user당 평균 5개)
    - 200,000 comments (post당 평균 4개)
    - 100,000 likes
"""

import asyncio
import random
from datetime import datetime, timedelta
from faker import Faker

# 프로젝트 루트를 PYTHONPATH에 추가
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.connection import init_db, close_db, transactional
from utils.password import hash_password

fake = Faker("ko_KR")
Faker.seed(42)  # 재현 가능한 데이터
random.seed(42)

# 설정
NUM_USERS = 10000
NUM_POSTS = 50000
NUM_COMMENTS = 200000
NUM_LIKES = 100000

# 미리 해시된 비밀번호 (Test1234!)
HASHED_PASSWORD = hash_password("Test1234!")


async def clear_existing_data():
    """기존 데이터 삭제 (개발 환경 전용)."""
    print("Clearing existing data...")
    async with transactional() as cur:
        await cur.execute("SET FOREIGN_KEY_CHECKS = 0")
        await cur.execute("TRUNCATE TABLE post_view_log")
        await cur.execute("TRUNCATE TABLE post_like")
        await cur.execute("TRUNCATE TABLE comment")
        await cur.execute("TRUNCATE TABLE post")
        await cur.execute("TRUNCATE TABLE user_session")
        await cur.execute("TRUNCATE TABLE image")
        await cur.execute("TRUNCATE TABLE user")
        await cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    print("Existing data cleared.")


async def seed_users():
    """사용자 데이터 생성."""
    print(f"Seeding {NUM_USERS} users...")

    batch_size = 1000
    users_data = []

    for i in range(1, NUM_USERS + 1):
        email = f"user{i}@example.com"
        nickname = f"user_{i:05d}"  # user_00001 형식
        created_at = datetime.now() - timedelta(days=random.randint(1, 365))

        users_data.append((email, nickname, HASHED_PASSWORD, None, created_at))

        if len(users_data) >= batch_size:
            await _insert_users_batch(users_data)
            users_data = []
            print(f"  {i}/{NUM_USERS} users created")

    if users_data:
        await _insert_users_batch(users_data)

    print(f"✓ {NUM_USERS} users created")


async def _insert_users_batch(users_data: list):
    """사용자 배치 삽입."""
    async with transactional() as cur:
        await cur.executemany(
            """
            INSERT INTO user (email, nickname, password, profile_img, created_at)
            VALUES (%s, %s, %s, %s, %s)
            """,
            users_data,
        )


async def seed_posts():
    """게시글 데이터 생성."""
    print(f"Seeding {NUM_POSTS} posts...")

    batch_size = 1000
    posts_data = []

    titles = [
        "개발 공부 팁 공유",
        "코딩 질문입니다",
        "프로젝트 후기",
        "취업 준비 이야기",
        "알고리즘 문제 풀이",
        "개발 블로그 추천",
        "오류 해결 방법",
        "기술 면접 준비",
        "개발자 일상",
        "코딩 테스트 후기",
        "스터디 모집합니다",
        "커리어 고민",
        "오픈소스 기여 경험",
        "개발 도구 추천",
        "신기술 소개",
        "코드 리뷰 요청",
    ]

    for i in range(1, NUM_POSTS + 1):
        author_id = random.randint(1, NUM_USERS)
        title = f"{random.choice(titles)} #{i}"
        content = fake.paragraph(nb_sentences=random.randint(3, 10))
        views = random.randint(0, 1000)
        created_at = datetime.now() - timedelta(days=random.randint(1, 180))

        posts_data.append((title, content, None, author_id, views, created_at))

        if len(posts_data) >= batch_size:
            await _insert_posts_batch(posts_data)
            posts_data = []
            print(f"  {i}/{NUM_POSTS} posts created")

    if posts_data:
        await _insert_posts_batch(posts_data)

    print(f"✓ {NUM_POSTS} posts created")


async def _insert_posts_batch(posts_data: list):
    """게시글 배치 삽입."""
    async with transactional() as cur:
        await cur.executemany(
            """
            INSERT INTO post (title, content, image_url, author_id, views, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            posts_data,
        )


async def seed_comments():
    """댓글 데이터 생성."""
    print(f"Seeding {NUM_COMMENTS} comments...")

    batch_size = 5000
    comments_data = []

    comment_templates = [
        "좋은 글 감사합니다!",
        "도움이 됐어요.",
        "저도 같은 생각이에요.",
        "공감합니다.",
        "더 자세히 알려주세요.",
        "좋은 정보 감사합니다.",
        "저도 비슷한 경험이 있어요.",
        "참고하겠습니다!",
        "응원합니다!",
        "질문이 있는데요...",
        "좋은 글이네요.",
        "감사합니다!",
    ]

    for i in range(1, NUM_COMMENTS + 1):
        content = random.choice(comment_templates) + " " + fake.sentence()
        author_id = random.randint(1, NUM_USERS)
        post_id = random.randint(1, NUM_POSTS)
        created_at = datetime.now() - timedelta(days=random.randint(1, 90))

        comments_data.append((content, author_id, post_id, created_at))

        if len(comments_data) >= batch_size:
            await _insert_comments_batch(comments_data)
            comments_data = []
            print(f"  {i}/{NUM_COMMENTS} comments created")

    if comments_data:
        await _insert_comments_batch(comments_data)

    print(f"✓ {NUM_COMMENTS} comments created")


async def _insert_comments_batch(comments_data: list):
    """댓글 배치 삽입."""
    async with transactional() as cur:
        await cur.executemany(
            """
            INSERT INTO comment (content, author_id, post_id, created_at)
            VALUES (%s, %s, %s, %s)
            """,
            comments_data,
        )


async def seed_likes():
    """좋아요 데이터 생성."""
    print(f"Seeding {NUM_LIKES} likes...")

    batch_size = 5000
    likes_data = []
    seen = set()  # 중복 방지

    attempts = 0
    max_attempts = NUM_LIKES * 3

    while len(likes_data) < NUM_LIKES and attempts < max_attempts:
        user_id = random.randint(1, NUM_USERS)
        post_id = random.randint(1, NUM_POSTS)
        key = (user_id, post_id)

        if key not in seen:
            seen.add(key)
            created_at = datetime.now() - timedelta(days=random.randint(1, 90))
            likes_data.append((user_id, post_id, created_at))

            if len(likes_data) % batch_size == 0:
                await _insert_likes_batch(likes_data[-batch_size:])
                print(f"  {len(likes_data)}/{NUM_LIKES} likes created")

        attempts += 1

    # 마지막 배치 삽입
    remaining = len(likes_data) % batch_size
    if remaining > 0:
        await _insert_likes_batch(likes_data[-remaining:])

    print(f"✓ {len(likes_data)} likes created")


async def _insert_likes_batch(likes_data: list):
    """좋아요 배치 삽입."""
    async with transactional() as cur:
        await cur.executemany(
            """
            INSERT IGNORE INTO post_like (user_id, post_id, created_at)
            VALUES (%s, %s, %s)
            """,
            likes_data,
        )


async def main():
    """메인 실행 함수."""
    print("=" * 50)
    print("Starting seed data generation...")
    print("=" * 50)
    print(f"Target: {NUM_USERS} users, {NUM_POSTS} posts,")
    print(f"        {NUM_COMMENTS} comments, {NUM_LIKES} likes")
    print("=" * 50)

    await init_db()

    try:
        # 기존 데이터 삭제 확인
        confirm = input("Clear existing data? (yes/no): ")
        if confirm.lower() == "yes":
            await clear_existing_data()

        start = datetime.now()

        await seed_users()
        await seed_posts()
        await seed_comments()
        await seed_likes()

        elapsed = datetime.now() - start
        print("=" * 50)
        print(f"✓ Seed complete! Time: {elapsed.total_seconds():.1f}s")
        print("=" * 50)

    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
