"""seed_data.py: 개발/테스트용 더미 데이터 생성 스크립트.

사용법:
    source .venv/bin/activate
    python database/seed_data.py [--scale small|medium|large]

생성되는 데이터 (small 기준):
    - 50 users (이메일 인증 완료, admin 1명 포함)
    - 200 posts (마크다운 콘텐츠, 카테고리, 태그 포함)
    - 800 comments (대댓글 20% 포함)
    - 500 post_likes, 200 bookmarks, 300 comment_likes
    - 100 follows, 10 blocks
    - 30 tags, 20 polls, 100 notifications
    - 15 reports, 300 view_logs
    - 10 DM conversations with ~50 messages
"""

import argparse
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

# 규모 프리셋
SCALE_PRESETS = {
    "small": {
        "users": 50,
        "posts": 200,
        "comments": 800,
        "post_likes": 500,
        "bookmarks": 200,
        "comment_likes": 300,
        "follows": 100,
        "blocks": 10,
        "tags": 30,
        "polls": 20,
        "notifications": 100,
        "reports": 15,
        "view_logs": 300,
        "dm_conversations": 10,
        "dm_messages_per_conv": 5,
    },
    "medium": {
        "users": 500,
        "posts": 2000,
        "comments": 8000,
        "post_likes": 5000,
        "bookmarks": 2000,
        "comment_likes": 3000,
        "follows": 1000,
        "blocks": 50,
        "tags": 80,
        "polls": 100,
        "notifications": 1000,
        "reports": 100,
        "view_logs": 5000,
        "dm_conversations": 50,
        "dm_messages_per_conv": 10,
    },
    "large": {
        "users": 10000,
        "posts": 50000,
        "comments": 200000,
        "post_likes": 100000,
        "bookmarks": 30000,
        "comment_likes": 50000,
        "follows": 20000,
        "blocks": 500,
        "tags": 200,
        "polls": 500,
        "notifications": 10000,
        "reports": 500,
        "view_logs": 100000,
        "dm_conversations": 500,
        "dm_messages_per_conv": 15,
    },
}

# 미리 해시된 비밀번호 (Test1234!)
HASHED_PASSWORD = hash_password("Test1234!")

# 마크다운 콘텐츠 템플릿
MARKDOWN_CONTENTS = [
    """## 개발 환경 세팅 가이드

최근 새 프로젝트를 시작하면서 정리한 개발 환경 세팅 방법입니다.

### 필수 도구
- **VS Code** — 가장 널리 쓰이는 에디터
- **Git** — 버전 관리 필수
- **Docker** — 컨테이너 기반 개발

### 추천 확장 프로그램
1. Prettier
2. ESLint
3. GitLens

> 처음 세팅할 때 시간이 좀 걸리지만, 한 번 해두면 편합니다!

```bash
# Docker Compose 실행
docker-compose up -d
```""",
    """오늘 알고리즘 문제를 풀다가 재미있는 패턴을 발견했습니다.

**투 포인터** 기법을 활용하면 O(n²)을 O(n)으로 줄일 수 있더라고요.

| 방법 | 시간복잡도 | 공간복잡도 |
|------|-----------|-----------|
| 브루트포스 | O(n²) | O(1) |
| 해시맵 | O(n) | O(n) |
| 투 포인터 | O(n) | O(1) |

특히 정렬된 배열에서 두 수의 합을 찾을 때 유용합니다.""",
    """### 코드 리뷰에서 배운 것들

이번 주 코드 리뷰를 받으면서 몇 가지 중요한 피드백을 받았습니다:

1. **변수명은 의도를 드러내야 한다** — `data`보다 `userProfiles`가 낫다
2. **함수는 한 가지 일만** — 100줄짜리 함수를 3개로 분리
3. **에러 처리를 빠뜨리지 말 것** — happy path만 생각하면 안 됨

```python
# Before
def process(data):
    # 100줄의 코드...

# After
def validate_input(data):
    ...

def transform_data(validated):
    ...

def save_result(transformed):
    ...
```

다음 리뷰에서는 더 나아진 코드를 보여주고 싶네요! 💪""",
    """면접 준비하면서 정리한 **REST API 설계 원칙**입니다.

### 핵심 원칙
- URI는 **명사**를 사용 (동사 X)
- HTTP 메서드로 행위를 표현
- 적절한 **상태 코드** 반환

### 자주 하는 실수
~~`GET /getUsers`~~ → `GET /users`
~~`POST /deleteUser/1`~~ → `DELETE /users/1`

이 정도만 기억해도 면접에서 기본은 한다고 봅니다.""",
    """## 스터디 모집합니다! 📚

**주제**: 시스템 디자인 면접 준비
**기간**: 4주 (매주 토요일)
**인원**: 4~6명

### 커리큘럼
- 1주차: URL 단축기 설계
- 2주차: 뉴스 피드 시스템
- 3주차: 채팅 시스템
- 4주차: 검색 자동완성

관심 있으신 분은 댓글 남겨주세요!""",
    """오늘 겪은 버그 해결 과정을 공유합니다.

### 증상
API 응답이 간헐적으로 **5초 이상** 걸림.

### 원인 분석
1. 로그 확인 → DB 쿼리 자체는 빠름
2. `EXPLAIN` 실행 → 풀 테이블 스캔 발견!
3. 인덱스 확인 → `WHERE` 조건 컬럼에 인덱스 없음

### 해결
```sql
CREATE INDEX idx_post_author ON post (author_id, created_at);
```

인덱스 하나로 5초 → 50ms로 개선되었습니다.

> 항상 `EXPLAIN`을 습관처럼 확인하세요!""",
    """프론트엔드 성능 최적화 팁 모음입니다.

- **이미지 lazy loading** 적용하기
- 번들 사이즈 **코드 스플리팅**으로 줄이기
- `requestAnimationFrame` 활용한 부드러운 애니메이션
- CSS `will-change` 속성으로 GPU 가속

특히 이미지가 많은 페이지에서 lazy loading만 적용해도 체감 속도가 확 달라집니다.""",
    """취업 준비 6개월 회고록입니다.

처음에는 막막했지만 하나씩 준비하다 보니 결국 해냈습니다.

### 타임라인
1. 1~2개월: CS 기초 공부 (운영체제, 네트워크, DB)
2. 3~4개월: 알고리즘 매일 1문제씩
3. 5개월: 포트폴리오 프로젝트
4. 6개월: 면접 준비 + 지원

### 가장 도움이 된 것
- 매일 **커밋 습관** 기르기
- 기술 블로그 **주 1회** 작성
- 스터디 그룹에서 **모의 면접**

포기하지 않으면 반드시 길이 열립니다.""",
]

# 일반 콘텐츠 (비마크다운)
PLAIN_CONTENTS = [
    "오늘 개발하다가 재미있는 것을 발견했습니다. 여러분도 한번 시도해보세요.",
    "이 방법이 정말 효율적인지 궁금합니다. 경험 있으신 분 의견 부탁드립니다.",
    "프로젝트를 마무리하고 나서 느낀 점을 공유합니다. 처음부터 설계를 잘 해야 나중에 편하더라고요.",
    "최근에 배운 기술을 실무에 적용해봤는데 생각보다 잘 동작해서 놀랐습니다.",
    "개발자로 일하면서 가장 힘든 점은 의사소통인 것 같아요. 기술보다 사람이 더 어렵습니다.",
    "새로운 라이브러리를 써봤는데 문서가 잘 되어 있어서 금방 적용할 수 있었습니다.",
    "이번 주말에 사이드 프로젝트를 시작했습니다. 아직 초기 단계지만 완성이 기대됩니다.",
    "코딩 테스트 후기입니다. 알고리즘 공부를 꾸준히 해야겠다고 다시 한번 느꼈습니다.",
]

TITLES = [
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
    "DB 최적화 경험담",
    "프론트엔드 성능 개선",
    "백엔드 아키텍처 고민",
    "CI/CD 파이프라인 구축",
]

COMMENT_TEMPLATES = [
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
    "이런 방법도 있군요!",
    "저는 좀 다르게 생각하는데, 의견 나눠봐요.",
    "실무에서도 이렇게 하시나요?",
    "정리가 잘 되어 있네요.",
]

TAG_NAMES = [
    "python", "javascript", "typescript", "react", "nextjs",
    "fastapi", "django", "flask", "nodejs", "docker",
    "kubernetes", "aws", "terraform", "mysql", "postgresql",
    "redis", "git", "cicd", "알고리즘", "자료구조",
    "면접준비", "취업", "사이드프로젝트", "코드리뷰", "성능최적화",
    "보안", "테스트", "tdd", "디자인패턴", "아키텍처",
]

POLL_QUESTIONS = [
    ("가장 선호하는 프로그래밍 언어는?", ["Python", "JavaScript", "TypeScript", "Java", "Go"]),
    ("개발 시 가장 중요한 것은?", ["코드 품질", "속도 (빠른 구현)", "테스트 커버리지", "문서화"]),
    ("주로 사용하는 에디터는?", ["VS Code", "IntelliJ", "Vim/Neovim", "기타"]),
    ("프론트엔드 프레임워크 선호도", ["React", "Vue", "Svelte", "Angular", "Vanilla JS"]),
    ("백엔드 프레임워크 선호도", ["FastAPI", "Django", "Express", "Spring Boot", "NestJS"]),
    ("DB 선호도", ["MySQL", "PostgreSQL", "MongoDB", "SQLite"]),
    ("개발 경력은?", ["학생/취준", "1~2년차", "3~5년차", "5년 이상"]),
    ("재택 vs 출근?", ["완전 재택", "하이브리드", "완전 출근", "상관없음"]),
    ("주 몇 시간 코딩하시나요?", ["20시간 이하", "20~40시간", "40~60시간", "60시간 이상"]),
    ("사이드 프로젝트 하시나요?", ["현재 진행 중", "계획 중", "과거에 했음", "안 함"]),
]

REPORT_REASONS = ["spam", "abuse", "inappropriate", "other"]


def _random_past(max_days: int = 90) -> datetime:
    """과거 랜덤 시각 생성."""
    return datetime.now() - timedelta(
        days=random.randint(1, max_days),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )


def _unique_pairs(n: int, max_a: int, max_b: int, exclude_same: bool = False) -> list[tuple[int, int]]:
    """중복 없는 (a, b) 쌍 생성."""
    seen: set[tuple[int, int]] = set()
    attempts = 0
    max_attempts = n * 5
    while len(seen) < n and attempts < max_attempts:
        a = random.randint(1, max_a)
        b = random.randint(1, max_b)
        if exclude_same and a == b:
            attempts += 1
            continue
        if (a, b) not in seen:
            seen.add((a, b))
        attempts += 1
    return list(seen)


# ─────────────────────────────────────────────
# 데이터 초기화
# ─────────────────────────────────────────────


async def clear_existing_data():
    """기존 데이터 삭제 (개발 환경 전용)."""
    print("기존 데이터 삭제 중...")
    async with transactional() as cur:
        await cur.execute("SET FOREIGN_KEY_CHECKS = 0")
        # 패키지
        await cur.execute("TRUNCATE TABLE package_review")
        await cur.execute("TRUNCATE TABLE package")
        # DM
        await cur.execute("TRUNCATE TABLE dm_message")
        await cur.execute("TRUNCATE TABLE dm_conversation")
        # 투표
        await cur.execute("TRUNCATE TABLE poll_vote")
        await cur.execute("TRUNCATE TABLE poll_option")
        await cur.execute("TRUNCATE TABLE poll")
        # 태그
        await cur.execute("TRUNCATE TABLE post_tag")
        await cur.execute("TRUNCATE TABLE tag")
        # 소셜
        await cur.execute("TRUNCATE TABLE user_follow")
        await cur.execute("TRUNCATE TABLE user_block")
        await cur.execute("TRUNCATE TABLE comment_like")
        await cur.execute("TRUNCATE TABLE post_bookmark")
        # 콘텐츠
        await cur.execute("TRUNCATE TABLE post_image")
        await cur.execute("TRUNCATE TABLE notification")
        await cur.execute("TRUNCATE TABLE report")
        await cur.execute("TRUNCATE TABLE post_view_log")
        await cur.execute("TRUNCATE TABLE post_like")
        await cur.execute("TRUNCATE TABLE comment")
        await cur.execute("TRUNCATE TABLE post")
        # 인증
        await cur.execute("TRUNCATE TABLE email_verification")
        await cur.execute("TRUNCATE TABLE refresh_token")
        await cur.execute("TRUNCATE TABLE image")
        await cur.execute("TRUNCATE TABLE category")
        await cur.execute("TRUNCATE TABLE user")
        await cur.execute("SET FOREIGN_KEY_CHECKS = 1")

        # 카테고리 시드 재삽입
        await cur.execute("""
            INSERT INTO category (name, slug, description, sort_order) VALUES
                ('배포판', 'distro', 'Ubuntu, Fedora, Arch 등 배포판별 토론 공간입니다.', 1),
                ('Q&A', 'qna', '리눅스 트러블슈팅, 설치, 설정 관련 질문과 답변입니다.', 2),
                ('뉴스/소식', 'news', '리눅스 생태계의 최신 소식을 공유합니다.', 3),
                ('프로젝트/쇼케이스', 'showcase', 'dotfiles, 스크립트, 오픈소스 기여를 공유합니다.', 4),
                ('팁/가이드', 'guide', '리눅스 튜토리얼과 How-to 가이드입니다.', 5),
                ('공지사항', 'notice', '관리자 공지사항입니다.', 6)
        """)
    print("✓ 기존 데이터 삭제 완료")


# ─────────────────────────────────────────────
# 사용자
# ─────────────────────────────────────────────


async def seed_users(cfg: dict):
    """사용자 데이터 생성 (이메일 인증 완료 상태)."""
    n = cfg["users"]
    print(f"사용자 {n}명 생성 중...")

    users_data = []
    for i in range(1, n + 1):
        email = f"user{i}@example.com"
        nickname = f"user_{i:05d}"
        role = "admin" if i == 1 else "user"
        created_at = _random_past(365)
        # email_verified=1 — 글쓰기 가능하도록
        users_data.append((email, 1, nickname, HASHED_PASSWORD, None, role, created_at, created_at))

    async with transactional() as cur:
        await cur.executemany(
            """INSERT INTO user (email, email_verified, nickname, password, profile_img, role, created_at, terms_agreed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            users_data,
        )
    print(f"  ✓ 사용자 {n}명 (admin: user1, 비밀번호: Test1234!)")


# ─────────────────────────────────────────────
# 게시글
# ─────────────────────────────────────────────


async def seed_posts(cfg: dict):
    """게시글 데이터 생성 (마크다운 콘텐츠 포함)."""
    n = cfg["posts"]
    print(f"게시글 {n}개 생성 중...")

    posts_data = []
    for i in range(1, n + 1):
        author_id = random.randint(1, cfg["users"])
        title = f"{random.choice(TITLES)} #{i}"

        # 30% 확률로 마크다운 콘텐츠
        if random.random() < 0.3:
            content = random.choice(MARKDOWN_CONTENTS)
        else:
            content = random.choice(PLAIN_CONTENTS) + "\n\n" + fake.paragraph(nb_sentences=random.randint(2, 5))

        views = random.randint(0, 500)
        # 공지사항(id=6)은 admin만
        category_id = random.randint(1, 5) if author_id != 1 else random.randint(1, 6)
        created_at = _random_past(180)

        posts_data.append((title, content, None, author_id, category_id, views, created_at))

    async with transactional() as cur:
        await cur.executemany(
            """INSERT INTO post (title, content, image_url, author_id, category_id, views, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            posts_data,
        )
    print(f"  ✓ 게시글 {n}개 (마크다운 ~30%)")


# ─────────────────────────────────────────────
# 댓글 (대댓글 포함)
# ─────────────────────────────────────────────


async def seed_comments(cfg: dict):
    """댓글 데이터 생성 (20% 대댓글 포함)."""
    n = cfg["comments"]
    print(f"댓글 {n}개 생성 중...")

    # 1단계: 루트 댓글 (80%)
    root_count = int(n * 0.8)
    root_data = []
    for _ in range(root_count):
        content = random.choice(COMMENT_TEMPLATES) + " " + fake.sentence()
        author_id = random.randint(1, cfg["users"])
        post_id = random.randint(1, cfg["posts"])
        created_at = _random_past(60)
        root_data.append((content, author_id, post_id, None, created_at))

    async with transactional() as cur:
        await cur.executemany(
            """INSERT INTO comment (content, author_id, post_id, parent_id, created_at)
            VALUES (%s, %s, %s, %s, %s)""",
            root_data,
        )

    # 2단계: 대댓글 (20%) — 루트 댓글의 id를 parent_id로 참조
    reply_count = n - root_count
    reply_data = []
    for _ in range(reply_count):
        parent_id = random.randint(1, root_count)
        content = random.choice(COMMENT_TEMPLATES) + " " + fake.sentence()
        author_id = random.randint(1, cfg["users"])
        # parent_id에 해당하는 댓글의 post_id를 알 수 없으므로 조회 필요
        reply_data.append((content, author_id, parent_id, created_at))

    if reply_data:
        async with transactional() as cur:
            # 대댓글의 post_id를 부모 댓글에서 가져와 삽입
            for content, author_id, parent_id, _ in reply_data:
                await cur.execute("SELECT post_id FROM comment WHERE id = %s", (parent_id,))
                row = await cur.fetchone()
                if row:
                    created_at = _random_past(30)
                    await cur.execute(
                        """INSERT INTO comment (content, author_id, post_id, parent_id, created_at)
                        VALUES (%s, %s, %s, %s, %s)""",
                        (content, author_id, row[0], parent_id, created_at),
                    )

    print(f"  ✓ 댓글 {n}개 (루트 {root_count}, 대댓글 {reply_count})")


# ─────────────────────────────────────────────
# 좋아요 / 북마크 / 댓글 좋아요
# ─────────────────────────────────────────────


async def seed_post_likes(cfg: dict):
    """게시글 좋아요 생성."""
    n = cfg["post_likes"]
    pairs = _unique_pairs(n, cfg["users"], cfg["posts"])
    print(f"게시글 좋아요 {len(pairs)}개 생성 중...")

    data = [(u, p, _random_past(60)) for u, p in pairs]
    async with transactional() as cur:
        await cur.executemany(
            "INSERT IGNORE INTO post_like (user_id, post_id, created_at) VALUES (%s, %s, %s)",
            data,
        )
    print(f"  ✓ 게시글 좋아요 {len(pairs)}개")


async def seed_bookmarks(cfg: dict):
    """북마크 생성."""
    n = cfg["bookmarks"]
    pairs = _unique_pairs(n, cfg["users"], cfg["posts"])
    print(f"북마크 {len(pairs)}개 생성 중...")

    data = [(u, p, _random_past(60)) for u, p in pairs]
    async with transactional() as cur:
        await cur.executemany(
            "INSERT IGNORE INTO post_bookmark (user_id, post_id, created_at) VALUES (%s, %s, %s)",
            data,
        )
    print(f"  ✓ 북마크 {len(pairs)}개")


async def seed_comment_likes(cfg: dict):
    """댓글 좋아요 생성."""
    n = cfg["comment_likes"]
    # 댓글 총 수를 사용
    pairs = _unique_pairs(n, cfg["users"], cfg["comments"])
    print(f"댓글 좋아요 {len(pairs)}개 생성 중...")

    data = [(u, c, _random_past(30)) for u, c in pairs]
    async with transactional() as cur:
        await cur.executemany(
            "INSERT IGNORE INTO comment_like (user_id, comment_id, created_at) VALUES (%s, %s, %s)",
            data,
        )
    print(f"  ✓ 댓글 좋아요 {len(pairs)}개")


# ─────────────────────────────────────────────
# 팔로우 / 차단
# ─────────────────────────────────────────────


async def seed_follows(cfg: dict):
    """팔로우 관계 생성."""
    n = cfg["follows"]
    pairs = _unique_pairs(n, cfg["users"], cfg["users"], exclude_same=True)
    print(f"팔로우 {len(pairs)}개 생성 중...")

    data = [(a, b, _random_past(90)) for a, b in pairs]
    async with transactional() as cur:
        await cur.executemany(
            "INSERT IGNORE INTO user_follow (follower_id, following_id, created_at) VALUES (%s, %s, %s)",
            data,
        )
    print(f"  ✓ 팔로우 {len(pairs)}개")


async def seed_blocks(cfg: dict):
    """사용자 차단 생성."""
    n = cfg["blocks"]
    pairs = _unique_pairs(n, cfg["users"], cfg["users"], exclude_same=True)
    print(f"차단 {len(pairs)}개 생성 중...")

    data = [(a, b, _random_past(60)) for a, b in pairs]
    async with transactional() as cur:
        await cur.executemany(
            "INSERT IGNORE INTO user_block (blocker_id, blocked_id, created_at) VALUES (%s, %s, %s)",
            data,
        )
    print(f"  ✓ 차단 {len(pairs)}개")


# ─────────────────────────────────────────────
# 태그
# ─────────────────────────────────────────────


async def seed_tags(cfg: dict):
    """태그 + 게시글-태그 연결 생성."""
    n = min(cfg["tags"], len(TAG_NAMES))
    print(f"태그 {n}개 + 게시글 연결 생성 중...")

    tags = TAG_NAMES[:n]
    async with transactional() as cur:
        await cur.executemany(
            "INSERT IGNORE INTO tag (name) VALUES (%s)",
            [(t,) for t in tags],
        )

        # 각 게시글에 0~3개 태그 연결 (약 60% 게시글에 태그 부여)
        post_tag_data = []
        for post_id in range(1, cfg["posts"] + 1):
            if random.random() < 0.6:
                num_tags = random.randint(1, min(3, n))
                selected_tag_ids = random.sample(range(1, n + 1), num_tags)
                for tag_id in selected_tag_ids:
                    post_tag_data.append((post_id, tag_id))

        if post_tag_data:
            await cur.executemany(
                "INSERT IGNORE INTO post_tag (post_id, tag_id) VALUES (%s, %s)",
                post_tag_data,
            )

    print(f"  ✓ 태그 {n}개, 연결 {len(post_tag_data)}개")


# ─────────────────────────────────────────────
# 투표
# ─────────────────────────────────────────────


async def seed_polls(cfg: dict):
    """투표 (poll + option + vote) 생성."""
    n = min(cfg["polls"], len(POLL_QUESTIONS), cfg["posts"])
    print(f"투표 {n}개 생성 중...")

    # 투표를 붙일 게시글 선택 (앞쪽 게시글에서 순서대로)
    poll_post_ids = random.sample(range(1, cfg["posts"] + 1), n)
    poll_post_ids.sort()

    async with transactional() as cur:
        for idx, post_id in enumerate(poll_post_ids):
            question, options = POLL_QUESTIONS[idx % len(POLL_QUESTIONS)]

            # 50% 확률로 만료일 설정 (미래)
            expires_at = (datetime.now() + timedelta(days=random.randint(1, 30))) if random.random() < 0.5 else None

            await cur.execute(
                "INSERT INTO poll (post_id, question, expires_at) VALUES (%s, %s, %s)",
                (post_id, question, expires_at),
            )
            poll_id = cur.lastrowid

            # 선택지 삽입
            option_ids = []
            for sort_order, opt_text in enumerate(options):
                await cur.execute(
                    "INSERT INTO poll_option (poll_id, option_text, sort_order) VALUES (%s, %s, %s)",
                    (poll_id, opt_text, sort_order),
                )
                option_ids.append(cur.lastrowid)

            # 투표 참여 (랜덤 사용자 5~15명)
            voter_count = min(random.randint(5, 15), cfg["users"])
            voters = random.sample(range(1, cfg["users"] + 1), voter_count)
            for voter_id in voters:
                chosen_option = random.choice(option_ids)
                await cur.execute(
                    "INSERT IGNORE INTO poll_vote (poll_id, option_id, user_id) VALUES (%s, %s, %s)",
                    (poll_id, chosen_option, voter_id),
                )

    print(f"  ✓ 투표 {n}개 (각 5~15명 참여)")


# ─────────────────────────────────────────────
# 알림
# ─────────────────────────────────────────────


async def seed_notifications(cfg: dict):
    """알림 데이터 생성."""
    n = cfg["notifications"]
    print(f"알림 {n}개 생성 중...")

    notif_types = ["comment", "like", "mention", "follow"]
    data = []
    for _ in range(n):
        user_id = random.randint(1, cfg["users"])
        actor_id = random.randint(1, cfg["users"])
        # 자기 자신에게 알림 안 감
        while actor_id == user_id:
            actor_id = random.randint(1, cfg["users"])

        ntype = random.choice(notif_types)
        post_id = random.randint(1, cfg["posts"])
        comment_id = random.randint(1, cfg["comments"]) if ntype in ("comment", "mention") else None
        is_read = 1 if random.random() < 0.6 else 0
        created_at = _random_past(30)

        data.append((user_id, ntype, post_id, comment_id, actor_id, is_read, created_at))

    async with transactional() as cur:
        await cur.executemany(
            """INSERT INTO notification (user_id, type, post_id, comment_id, actor_id, is_read, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            data,
        )
    print(f"  ✓ 알림 {n}개 (60% 읽음)")


# ─────────────────────────────────────────────
# 신고
# ─────────────────────────────────────────────


async def seed_reports(cfg: dict):
    """신고 데이터 생성."""
    n = cfg["reports"]
    print(f"신고 {n}개 생성 중...")

    data = []
    seen: set[tuple[int, str, int]] = set()
    for _ in range(n):
        reporter_id = random.randint(1, cfg["users"])
        target_type = random.choice(["post", "comment"])
        target_id = random.randint(1, cfg["posts"] if target_type == "post" else cfg["comments"])
        key = (reporter_id, target_type, target_id)
        if key in seen:
            continue
        seen.add(key)

        reason = random.choice(REPORT_REASONS)
        description = fake.sentence() if reason == "other" else None
        status = random.choice(["pending", "pending", "pending", "resolved", "dismissed"])  # 60% pending
        resolved_by = 1 if status != "pending" else None  # admin이 처리
        resolved_at = _random_past(7) if status != "pending" else None
        created_at = _random_past(30)

        data.append((reporter_id, target_type, target_id, reason, description, status, resolved_by, resolved_at, created_at))

    async with transactional() as cur:
        await cur.executemany(
            """INSERT IGNORE INTO report
            (reporter_id, target_type, target_id, reason, description, status, resolved_by, resolved_at, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            data,
        )
    print(f"  ✓ 신고 {len(data)}개 (~60% pending)")


# ─────────────────────────────────────────────
# 조회 로그 (읽은 글 표시)
# ─────────────────────────────────────────────


async def seed_view_logs(cfg: dict):
    """게시글 조회 로그 생성 (읽은 글 표시용)."""
    n = cfg["view_logs"]
    pairs = _unique_pairs(n, cfg["users"], cfg["posts"])
    print(f"조회 로그 {len(pairs)}개 생성 중...")

    data = [(u, p, _random_past(14)) for u, p in pairs]
    async with transactional() as cur:
        await cur.executemany(
            "INSERT IGNORE INTO post_view_log (user_id, post_id, created_at) VALUES (%s, %s, %s)",
            data,
        )
    print(f"  ✓ 조회 로그 {len(pairs)}개")


# ─────────────────────────────────────────────
# DM (쪽지)
# ─────────────────────────────────────────────


async def seed_dms(cfg: dict):
    """DM 대화 + 메시지 생성."""
    n_conv = cfg["dm_conversations"]
    n_msg = cfg["dm_messages_per_conv"]
    print(f"DM 대화 {n_conv}개 (대화당 ~{n_msg}개 메시지) 생성 중...")

    # 중복 없는 대화 쌍 생성 (participant1 < participant2 정규화)
    conv_pairs = _unique_pairs(n_conv, cfg["users"], cfg["users"], exclude_same=True)

    total_messages = 0
    async with transactional() as cur:
        for a, b in conv_pairs:
            p1, p2 = min(a, b), max(a, b)
            created_at = _random_past(30)

            await cur.execute(
                """INSERT IGNORE INTO dm_conversation (participant1_id, participant2_id, last_message_at, created_at)
                VALUES (%s, %s, %s, %s)""",
                (p1, p2, None, created_at),
            )
            conv_id = cur.lastrowid
            if not conv_id:
                continue

            # 메시지 생성
            msg_count = random.randint(max(1, n_msg - 2), n_msg + 3)
            last_msg_at = created_at
            for j in range(msg_count):
                sender = p1 if j % 2 == 0 else p2
                content = fake.sentence()
                msg_at = last_msg_at + timedelta(minutes=random.randint(1, 120))
                is_read = 1 if j < msg_count - 1 else (1 if random.random() < 0.5 else 0)

                await cur.execute(
                    """INSERT INTO dm_message (conversation_id, sender_id, content, is_read, created_at)
                    VALUES (%s, %s, %s, %s, %s)""",
                    (conv_id, sender, content, is_read, msg_at),
                )
                last_msg_at = msg_at
                total_messages += 1

            # last_message_at 업데이트
            await cur.execute(
                "UPDATE dm_conversation SET last_message_at = %s WHERE id = %s",
                (last_msg_at, conv_id),
            )

    print(f"  ✓ DM 대화 {n_conv}개, 메시지 {total_messages}개")


# ─────────────────────────────────────────────
# 패키지
# ─────────────────────────────────────────────


# 패키지 시드 데이터
PACKAGES = [
    ('vim', 'Vim', '터미널 기반 텍스트 에디터', 'https://www.vim.org', 'editor', 'apt'),
    ('neovim', 'Neovim', 'Vim 기반 하이퍼 확장 에디터', 'https://neovim.io', 'editor', 'apt'),
    ('docker', 'Docker', '컨테이너 플랫폼', 'https://www.docker.com', 'devtool', 'apt'),
    ('git', 'Git', '분산 버전 관리 시스템', 'https://git-scm.com', 'devtool', 'apt'),
    ('tmux', 'tmux', '터미널 멀티플렉서', 'https://github.com/tmux/tmux', 'terminal', 'apt'),
    ('zsh', 'Zsh', 'Z 셸', 'https://www.zsh.org', 'terminal', 'apt'),
    ('htop', 'htop', '대화형 프로세스 뷰어', 'https://htop.dev', 'system', 'apt'),
    ('fzf', 'fzf', '커맨드라인 퍼지 파인더', 'https://github.com/junegunn/fzf', 'utility', 'apt'),
    ('ripgrep', 'ripgrep', '초고속 검색 도구', 'https://github.com/BurntSushi/ripgrep', 'utility', 'apt'),
    ('alacritty', 'Alacritty', 'GPU 가속 터미널 에뮬레이터', 'https://alacritty.org', 'terminal', 'apt'),
    ('nginx', 'nginx', '웹 서버 및 리버스 프록시', 'https://nginx.org', 'system', 'apt'),
    ('vlc', 'VLC', '멀티미디어 플레이어', 'https://www.videolan.org', 'multimedia', 'apt'),
    ('gimp', 'GIMP', 'GNU 이미지 편집기', 'https://www.gimp.org', 'multimedia', 'apt'),
    ('ufw', 'UFW', '간편 방화벽', 'https://launchpad.net/ufw', 'security', 'apt'),
    ('gnome-shell', 'GNOME Shell', 'GNOME 데스크톱 환경', 'https://www.gnome.org', 'desktop', 'apt'),
]


async def seed_packages():
    """샘플 패키지 데이터 생성 (admin user id=1이 등록)."""
    print(f"패키지 {len(PACKAGES)}개 생성 중...")

    async with transactional() as cur:
        await cur.executemany(
            """INSERT IGNORE INTO package
            (name, display_name, description, homepage_url, category, package_manager, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, 1)""",
            PACKAGES,
        )
    print(f"  ✓ 패키지 {len(PACKAGES)}개 (created_by=admin)")


# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────


async def main():
    """메인 실행 함수."""
    parser = argparse.ArgumentParser(description="커뮤니티 시드 데이터 생성")
    parser.add_argument(
        "--scale",
        choices=["small", "medium", "large"],
        default="small",
        help="데이터 규모 (기본: small)",
    )
    parser.add_argument(
        "--no-confirm",
        action="store_true",
        help="확인 없이 기존 데이터 삭제",
    )
    args = parser.parse_args()
    cfg = SCALE_PRESETS[args.scale]

    print("=" * 50)
    print(f"시드 데이터 생성 (규모: {args.scale})")
    print("=" * 50)
    print(f"  사용자: {cfg['users']}, 게시글: {cfg['posts']}")
    print(f"  댓글: {cfg['comments']}, 좋아요: {cfg['post_likes']}")
    print(f"  태그: {cfg['tags']}, 투표: {cfg['polls']}, DM: {cfg['dm_conversations']}")
    print("=" * 50)

    await init_db()

    try:
        if args.no_confirm:
            await clear_existing_data()
        else:
            confirm = input("기존 데이터를 삭제하고 새로 생성할까요? (yes/no): ")
            if confirm.lower() == "yes":
                await clear_existing_data()
            else:
                print("기존 데이터 유지. 중복 시 무시됩니다.")

        start = datetime.now()

        # 순서 중요: FK 의존성에 따라 부모 먼저
        await seed_users(cfg)
        await seed_packages()
        await seed_posts(cfg)
        await seed_comments(cfg)
        await seed_tags(cfg)
        await seed_polls(cfg)
        await seed_post_likes(cfg)
        await seed_bookmarks(cfg)
        await seed_comment_likes(cfg)
        await seed_follows(cfg)
        await seed_blocks(cfg)
        await seed_notifications(cfg)
        await seed_reports(cfg)
        await seed_view_logs(cfg)
        await seed_dms(cfg)

        elapsed = datetime.now() - start
        print("=" * 50)
        print(f"✓ 시드 완료! 소요 시간: {elapsed.total_seconds():.1f}초")
        print("=" * 50)
        print("  로그인: user1@example.com / Test1234! (admin)")
        print(f"  일반: user2@example.com ~ user{cfg['users']}@example.com / Test1234!")
        print("=" * 50)

    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
