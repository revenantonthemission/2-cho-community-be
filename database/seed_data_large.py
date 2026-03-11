"""seed_data_large.py: 대규모 시드 데이터 생성 스크립트.

5만 사용자, 15만 게시글, 50만 댓글 등 대규모 데이터를 생성하여
추천 피드, 검색, 페이지네이션 등의 성능을 검증합니다.

사용법:
    source .venv/bin/activate

    # SSH 터널 경유 RDS 시딩
    python database/seed_data_large.py --db-user admin --db-password SECRET --dry-run

    # 로컬 MySQL 시딩
    python database/seed_data_large.py --db-host 127.0.0.1 --db-port 3306 \\
        --db-user root --db-password root --no-confirm

사용자 티어:
    - Power (5%): 게시글/댓글 다수 생성
    - Regular (25%): 일반적 활동
    - Reader (70%): 주로 조회/좋아요만
"""

import argparse
import asyncio
import math
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 프로젝트 루트를 PYTHONPATH에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

import aiomysql
from faker import Faker

from utils.password import hash_password

fake = Faker("ko_KR")
Faker.seed(42)  # 재현 가능한 데이터
random.seed(42)

# ─────────────────────────────────────────────
# 태그 상수
# ─────────────────────────────────────────────

TAG_NAMES = [
    # 인기 태그 (상위 10개 — post_tag의 50% 차지)
    "python", "javascript", "react", "typescript", "docker",
    "aws", "mysql", "알고리즘", "취업", "사이드프로젝트",
    # 중간 인기 (11~25)
    "fastapi", "django", "nodejs", "nextjs", "flask",
    "kubernetes", "terraform", "postgresql", "redis", "git",
    "cicd", "자료구조", "면접준비", "코드리뷰", "성능최적화",
    # 일반 (26~50)
    "보안", "테스트", "tdd", "디자인패턴", "아키텍처",
    "linux", "네트워크", "운영체제", "데이터베이스", "api설계",
    "클린코드", "리팩토링", "모니터링", "로깅", "배포",
    "마이크로서비스", "메시지큐", "캐싱", "인증인가", "graphql",
    "rust", "go", "java", "kotlin", "swift",
]

# 미리 해시된 비밀번호 (Test1234!)
HASHED_PASSWORD = hash_password("Test1234!")

# ─────────────────────────────────────────────
# 사용자 티어 상수
# ─────────────────────────────────────────────

TOTAL_USERS = 50_000
POWER_RATIO = 0.05   # 2,500명 — 게시글/댓글 다수 생성
REGULAR_RATIO = 0.25  # 12,500명 — 일반적 활동
READER_RATIO = 0.70   # 35,000명 — 주로 조회/좋아요

POWER_COUNT = int(TOTAL_USERS * POWER_RATIO)      # 2,500
REGULAR_COUNT = int(TOTAL_USERS * REGULAR_RATIO)   # 12,500
READER_COUNT = TOTAL_USERS - POWER_COUNT - REGULAR_COUNT  # 35,000

# 1-indexed ID 범위
POWER_IDS = range(1, POWER_COUNT + 1)                              # 1 ~ 2,500
REGULAR_IDS = range(POWER_COUNT + 1, POWER_COUNT + REGULAR_COUNT + 1)  # 2,501 ~ 15,000
READER_IDS = range(POWER_COUNT + REGULAR_COUNT + 1, TOTAL_USERS + 1)   # 15,001 ~ 50,000

# 배치 크기
BATCH_SIZE = 5_000


# ─────────────────────────────────────────────
# DB 연결
# ─────────────────────────────────────────────


async def create_pool(args) -> aiomysql.Pool:
    """CLI 인자로부터 aiomysql 커넥션 풀 생성.

    SSH 터널 경유 시 커넥션 수를 적게 유지 (minsize=5, maxsize=10).
    """
    print(f"DB 연결: {args.db_user}@{args.db_host}:{args.db_port}/{args.db_name}")
    pool = await aiomysql.create_pool(
        host=args.db_host,
        port=args.db_port,
        user=args.db_user,
        password=args.db_password,
        db=args.db_name,
        minsize=5,
        maxsize=10,
        connect_timeout=10,
        charset="utf8mb4",
        autocommit=True,
    )
    print(f"  커넥션 풀 생성 완료 (min=5, max=10)")
    return pool


# ─────────────────────────────────────────────
# 고성능 배치 INSERT 헬퍼
# ─────────────────────────────────────────────


async def batch_insert_raw(
    pool: aiomysql.Pool,
    table: str,
    columns: list[str],
    data: list[tuple],
    batch_size: int = BATCH_SIZE,
    ignore: bool = True,
) -> int:
    """대량 INSERT를 배치 단위로 실행.

    한 배치의 모든 행을 하나의 INSERT 문에 담아 실행하여
    네트워크 왕복을 최소화합니다.

    Args:
        pool: aiomysql 커넥션 풀
        table: 대상 테이블명
        columns: 컬럼 이름 리스트
        data: 삽입할 튜플 리스트
        batch_size: 배치당 행 수
        ignore: INSERT IGNORE 사용 여부

    Returns:
        삽입 성공 행 수 합계
    """
    if not data:
        return 0

    cols_str = ", ".join(columns)
    n_cols = len(columns)
    single_row_placeholder = "(" + ", ".join(["%s"] * n_cols) + ")"
    ignore_str = " IGNORE" if ignore else ""
    total_inserted = 0
    total_batches = math.ceil(len(data) / batch_size)

    for batch_idx in range(total_batches):
        start = batch_idx * batch_size
        end = min(start + batch_size, len(data))
        batch = data[start:end]

        # 다중 행 VALUES 절 생성
        values_str = ", ".join([single_row_placeholder] * len(batch))
        sql = f"INSERT{ignore_str} INTO {table} ({cols_str}) VALUES {values_str}"

        # 튜플 리스트를 평탄화
        flat_params = []
        for row in batch:
            flat_params.extend(row)

        conn = await pool.acquire()
        try:
            async with conn.cursor() as cur:
                await cur.execute("BEGIN")
                try:
                    await cur.execute(sql, flat_params)
                    affected = cur.rowcount
                    await cur.execute("COMMIT")
                    total_inserted += affected
                except Exception as e:
                    await cur.execute("ROLLBACK")
                    print(f"  [경고] {table} 배치 {batch_idx + 1}/{total_batches} 실패: {e}")
        finally:
            pool.release(conn)

        # 이벤트 루프 양보
        await asyncio.sleep(0)

    return total_inserted


# ─────────────────────────────────────────────
# 시간 분포 헬퍼
# ─────────────────────────────────────────────


def growth_curve_timestamp(max_days: int = 365) -> datetime:
    """최근에 가중치를 둔 이차 분포 타임스탬프.

    r = random() ** 2 → 0에 가까운 값이 많음 → 최근 날짜가 많이 생성됨.
    """
    r = random.random() ** 2
    days_ago = r * max_days
    return datetime.now(timezone.utc) - timedelta(
        days=days_ago,
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
    )


def recent_timestamp(max_days: int = 7) -> datetime:
    """최근 N일 내 균등 분포 타임스탬프 (추천 피드 후보용)."""
    return datetime.now(timezone.utc) - timedelta(
        days=random.uniform(0, max_days),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
    )


# ─────────────────────────────────────────────
# 사용자 티어 헬퍼
# ─────────────────────────────────────────────


def get_user_tier(user_id: int) -> str:
    """사용자 ID로 티어 반환."""
    if user_id <= POWER_COUNT:
        return "power"
    elif user_id <= POWER_COUNT + REGULAR_COUNT:
        return "regular"
    else:
        return "reader"


def weighted_user_id(power_weight: float = 0.4, regular_weight: float = 0.4) -> int:
    """티어 가중치에 따른 랜덤 사용자 ID 반환.

    기본: power 40%, regular 40%, reader 20%
    → power 사용자가 활동의 대부분을 차지하도록 설계.
    """
    roll = random.random()
    if roll < power_weight:
        return random.choice(POWER_IDS)
    elif roll < power_weight + regular_weight:
        return random.choice(REGULAR_IDS)
    else:
        return random.choice(READER_IDS)


# ─────────────────────────────────────────────
# 진행률 표시 헬퍼
# ─────────────────────────────────────────────


def progress(current: int, total: int, label: str = "") -> None:
    """콘솔 진행률 바 출력."""
    if total <= 0:
        return
    pct = current / total
    bar_len = 30
    filled = int(bar_len * pct)
    bar = "\u2588" * filled + "\u2591" * (bar_len - filled)
    suffix = f" {label}" if label else ""
    print(f"\r  {bar} {pct * 100:5.1f}%{suffix}", end="", flush=True)
    if current >= total:
        print()  # 완료 시 개행


# ─────────────────────────────────────────────
# CLI 인자 파서
# ─────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    """커맨드 라인 인자 파싱."""
    parser = argparse.ArgumentParser(
        description="대규모 시드 데이터 생성 (5만 사용자, 15만 게시글 등)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
예시:
  # 로컬 MySQL
  python database/seed_data_large.py --db-user root --db-password root --db-port 3306

  # SSH 터널 경유 RDS (기본 포트 3307)
  python database/seed_data_large.py --db-user admin --db-password SECRET

  # 기존 데이터 삭제 후 시딩
  python database/seed_data_large.py --db-user admin --db-password SECRET --clean --no-confirm
""",
    )
    parser.add_argument("--db-host", default="127.0.0.1", help="DB 호스트 (기본: 127.0.0.1)")
    parser.add_argument("--db-port", type=int, default=3307, help="DB 포트 (기본: 3307, SSH 터널용)")
    parser.add_argument("--db-user", required=True, help="DB 사용자명")
    parser.add_argument("--db-password", required=True, help="DB 비밀번호")
    parser.add_argument("--db-name", default="community_service", help="DB 이름 (기본: community_service)")
    parser.add_argument("--no-confirm", action="store_true", help="확인 프롬프트 생략")
    parser.add_argument("--clean", action="store_true", help="시딩 전 기존 데이터 TRUNCATE")
    parser.add_argument("--dry-run", action="store_true", help="DB 접속 없이 설정 확인만")
    parser.add_argument("--recompute-url", default=None, help="시딩 후 추천 피드 재계산 API URL")
    return parser.parse_args()


# ─────────────────────────────────────────────
# 게시글 콘텐츠 상수
# ─────────────────────────────────────────────

TOTAL_POSTS = 250_000

TITLE_PREFIXES = [
    "개발 공부 팁", "코딩 질문", "프로젝트 후기", "취업 준비",
    "알고리즘 풀이", "블로그 추천", "오류 해결", "면접 준비",
    "개발자 일상", "코딩 테스트 후기", "스터디 모집", "커리어 고민",
    "오픈소스 기여", "도구 추천", "신기술 소개", "코드 리뷰 요청",
    "DB 최적화", "프론트 성능 개선", "백엔드 아키텍처", "CI/CD 구축",
    "Docker 활용", "AWS 배포", "보안 이슈", "테스트 작성법",
    "API 설계", "클린 코드", "디자인 패턴", "시스템 설계",
    "트러블슈팅", "성능 튜닝", "데이터 모델링", "인증 구현",
    "배포 자동화", "모니터링 구축", "로깅 전략", "캐시 전략",
    "비동기 처리", "웹소켓 구현", "파일 업로드", "검색 최적화",
]

TITLE_SUFFIXES = [
    "공유합니다", "질문입니다", "후기", "정리", "가이드",
    "삽질기", "해결 방법", "비교 분석", "추천", "회고",
    "모집합니다", "고민", "경험담", "노하우", "팁",
    "", "", "", "", "",
]

MARKDOWN_CONTENTS = [
    "## 개발 환경 세팅 가이드\n\n최근 새 프로젝트를 시작하면서 정리한 개발 환경 세팅 방법입니다.\n\n### 필수 도구\n- **VS Code** — 가장 널리 쓰이는 에디터\n- **Git** — 버전 관리 필수\n- **Docker** — 컨테이너 기반 개발\n\n```bash\ndocker-compose up -d\n```",
    "오늘 알고리즘 문제를 풀다가 재미있는 패턴을 발견했습니다.\n\n**투 포인터** 기법을 활용하면 O(n²)을 O(n)으로 줄일 수 있더라고요.\n\n| 방법 | 시간복잡도 | 공간복잡도 |\n|------|-----------|----------|\n| 브루트포스 | O(n²) | O(1) |\n| 투 포인터 | O(n) | O(1) |",
    "### 코드 리뷰에서 배운 것들\n\n1. **변수명은 의도를 드러내야 한다**\n2. **함수는 한 가지 일만**\n3. **에러 처리를 빠뜨리지 말 것**\n\n```python\ndef validate_input(data):\n    ...\ndef transform_data(validated):\n    ...\n```",
    "면접 준비하면서 정리한 **REST API 설계 원칙**입니다.\n\n### 핵심 원칙\n- URI는 **명사**를 사용\n- HTTP 메서드로 행위를 표현\n- 적절한 **상태 코드** 반환\n\n~~`GET /getUsers`~~ → `GET /users`",
    "## 스터디 모집합니다!\n\n**주제**: 시스템 디자인 면접 준비\n**기간**: 4주\n\n### 커리큘럼\n- 1주차: URL 단축기 설계\n- 2주차: 뉴스 피드 시스템\n- 3주차: 채팅 시스템\n- 4주차: 검색 자동완성",
    "오늘 겪은 버그 해결 과정을 공유합니다.\n\n### 증상\nAPI 응답이 간헐적으로 **5초 이상** 걸림.\n\n### 해결\n```sql\nCREATE INDEX idx_post_author ON post (author_id, created_at);\n```\n인덱스 하나로 5초 → 50ms 개선.",
    "프론트엔드 성능 최적화 팁 모음입니다.\n\n- **이미지 lazy loading** 적용\n- 번들 사이즈 **코드 스플리팅**\n- `requestAnimationFrame` 활용\n- CSS `will-change` 속성으로 GPU 가속",
    "취업 준비 6개월 회고록입니다.\n\n### 타임라인\n1. 1~2개월: CS 기초\n2. 3~4개월: 알고리즘 매일 1문제\n3. 5개월: 포트폴리오 프로젝트\n4. 6개월: 면접 + 지원\n\n포기하지 않으면 반드시 길이 열립니다.",
]

PLAIN_CONTENTS = [
    "오늘 개발하다가 재미있는 것을 발견했습니다. 여러분도 한번 시도해보세요.",
    "이 방법이 정말 효율적인지 궁금합니다. 경험 있으신 분 의견 부탁드립니다.",
    "프로젝트를 마무리하고 나서 느낀 점을 공유합니다.",
    "최근에 배운 기술을 실무에 적용해봤는데 생각보다 잘 동작해서 놀랐습니다.",
    "개발자로 일하면서 가장 힘든 점은 의사소통인 것 같아요.",
    "새로운 라이브러리를 써봤는데 문서가 잘 되어 있어서 금방 적용할 수 있었습니다.",
    "이번 주말에 사이드 프로젝트를 시작했습니다.",
    "코딩 테스트 후기입니다. 알고리즘 공부를 꾸준히 해야겠다고 느꼈습니다.",
]

# ─────────────────────────────────────────────
# 게시글 헬퍼
# ─────────────────────────────────────────────

POSTS_POWER_AVG = 40    # 파워유저 평균 게시글
POSTS_REGULAR_AVG = 10  # 일반유저 평균
POSTS_READER_AVG = 0.7  # 읽기전용 평균


def _generate_title(idx: int) -> str:
    """고유 제목 생성."""
    prefix = random.choice(TITLE_PREFIXES)
    suffix = random.choice(TITLE_SUFFIXES)
    if suffix:
        return f"{prefix} {suffix} #{idx}"
    return f"{prefix} #{idx}"


def _generate_content() -> str:
    """게시글 본문 생성."""
    r = random.random()
    if r < 0.2:  # 20% 마크다운
        return random.choice(MARKDOWN_CONTENTS)
    elif r < 0.5:  # 30% 짧은 글
        return random.choice(PLAIN_CONTENTS)
    else:  # 50% 중간 (plain + faker paragraph)
        base = random.choice(PLAIN_CONTENTS)
        extra = fake.paragraph(nb_sentences=random.randint(2, 5))
        return f"{base}\n\n{extra}"


def _assign_author_for_posts() -> list[int]:
    """계층별 비율에 맞게 게시글 작성자 ID 리스트 생성.

    파워유저: ~40개/인 × 2,500명 = ~100,000
    일반유저: ~10개/인 × 12,500명 = ~125,000
    읽기전용: ~0.7개/인 × 35,000명 = ~25,000
    합계 ~250,000
    """
    authors = []

    for uid in POWER_IDS:
        count = max(1, int(random.gauss(POSTS_POWER_AVG, 10)))
        authors.extend([uid] * count)

    for uid in REGULAR_IDS:
        count = max(0, int(random.gauss(POSTS_REGULAR_AVG, 3)))
        authors.extend([uid] * count)

    for uid in READER_IDS:
        if random.random() < POSTS_READER_AVG:
            authors.append(uid)

    random.shuffle(authors)

    # Trim or pad to TOTAL_POSTS
    if len(authors) > TOTAL_POSTS:
        authors = authors[:TOTAL_POSTS]
    while len(authors) < TOTAL_POSTS:
        authors.append(weighted_user_id(0.5, 0.35))

    return authors


# ─────────────────────────────────────────────
# 스텁 함수 (후속 Task에서 구현)
# ─────────────────────────────────────────────


async def clean_all_data(pool: aiomysql.Pool) -> None:
    """기존 데이터 전체 삭제 (TRUNCATE).

    FK 안전 순서로 모든 테이블을 TRUNCATE한 뒤 카테고리 시드를 재삽입합니다.
    """
    # FK 자식 → 부모 순서
    tables = [
        "user_post_score", "dm_message", "dm_conversation",
        "poll_vote", "poll_option", "poll",
        "post_tag", "tag", "user_follow", "user_block",
        "comment_like", "post_bookmark", "post_image",
        "notification", "report", "post_view_log",
        "post_like", "comment", "post",
        "email_verification", "refresh_token", "image",
        "category", "user",
    ]

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SET FOREIGN_KEY_CHECKS = 0")
            for table in tables:
                await cur.execute(f"TRUNCATE TABLE {table}")
                print(f"  TRUNCATE {table}")
            await cur.execute("SET FOREIGN_KEY_CHECKS = 1")

            # 카테고리 시드 재삽입
            await cur.execute("""
                INSERT INTO category (name, slug, description, sort_order) VALUES
                    ('자유게시판', 'free', '자유롭게 이야기하는 공간입니다.', 1),
                    ('질문답변', 'qna', '궁금한 것을 질문하고 답변합니다.', 2),
                    ('정보공유', 'info', '유용한 정보를 공유합니다.', 3),
                    ('공지사항', 'notice', '관리자 공지사항입니다.', 4)
            """)
            print("  카테고리 시드 재삽입 완료 (4개)")
    print("  전체 TRUNCATE 완료")


async def seed_categories(pool: aiomysql.Pool) -> None:
    """카테고리 시드 데이터 삽입.

    이미 4개 이상 존재하면 스킵합니다.
    """
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT COUNT(*) FROM category")
            (count,) = await cur.fetchone()

    if count >= 4:
        print(f"  카테고리: 이미 {count}개 존재 — 스킵")
        return

    data = [
        ("자유게시판", "free", "자유롭게 이야기하는 공간입니다.", 1),
        ("질문답변", "qna", "궁금한 것을 질문하고 답변합니다.", 2),
        ("정보공유", "info", "유용한 정보를 공유합니다.", 3),
        ("공지사항", "notice", "관리자 공지사항입니다.", 4),
    ]
    inserted = await batch_insert_raw(
        pool, "category",
        ["name", "slug", "description", "sort_order"],
        data, ignore=True,
    )
    print(f"  카테고리: {inserted}개 삽입")


async def seed_tags(pool: aiomysql.Pool) -> None:
    """태그 50개 삽입 (INSERT IGNORE)."""
    data = [(name,) for name in TAG_NAMES]
    inserted = await batch_insert_raw(
        pool, "tag", ["name"], data, ignore=True,
    )
    print(f"  태그: {inserted}개 삽입 (총 {len(TAG_NAMES)}개 시도)")


async def seed_users(pool: aiomysql.Pool) -> None:
    """사용자 5만 명 생성.

    user 1은 admin 역할, 나머지는 일반 사용자.
    전원 이메일 인증 완료 상태.
    """
    print(f"  사용자 데이터 생성 중 ({TOTAL_USERS:,}명)...")
    data: list[tuple] = []
    for i in range(1, TOTAL_USERS + 1):
        email = f"user{i}@example.com"
        nickname = f"user_{i:05d}"
        role = "admin" if i == 1 else "user"
        created_at = growth_curve_timestamp(365)
        data.append((email, HASHED_PASSWORD, nickname, role, 1, created_at))

        # 생성 진행률 표시 (1만 명마다)
        if i % 10_000 == 0:
            print(f"    생성: {i:>6,} / {TOTAL_USERS:,}")

    print(f"  사용자 INSERT 시작...")
    inserted = await batch_insert_raw(
        pool, "user",
        ["email", "password", "nickname", "role", "email_verified", "created_at"],
        data, ignore=True,
    )
    print(f"  사용자: {inserted:,}명 삽입 완료")


async def seed_posts(pool: aiomysql.Pool) -> None:
    """게시글 ~250,000개 생성 (성장 곡선 + 계층별 분포)."""
    print(f"  게시글 {TOTAL_POSTS:,}개 생성 중...")

    authors = _assign_author_for_posts()
    data = []

    # 최근 7일 게시글 비율 (~8% = 20,000개) — 피드 후보 풀 확보
    recent_count = int(TOTAL_POSTS * 0.08)

    for i in range(TOTAL_POSTS):
        post_idx = i + 1
        author_id = authors[i]
        title = _generate_title(post_idx)
        content = _generate_content()
        views = random.randint(0, 500)

        # 카테고리: 공지사항(id=4)은 admin(user1)만
        if author_id == 1:
            category_id = random.randint(1, 4)
        else:
            r = random.random()
            if r < 0.4:
                category_id = 1  # 자유게시판 40%
            elif r < 0.7:
                category_id = 2  # 질문답변 30%
            else:
                category_id = 3  # 정보공유 30%

        # 시간: 8%는 최근 7일 (피드 후보), 나머지는 성장 곡선
        if i < recent_count:
            created_at = recent_timestamp(7)
        else:
            created_at = growth_curve_timestamp(365)

        data.append((title, content, None, author_id, category_id, views, created_at))

        if (i + 1) % 50_000 == 0:
            progress(i + 1, TOTAL_POSTS, "게시글 데이터 생성")

    progress(TOTAL_POSTS, TOTAL_POSTS, "게시글 데이터 생성")

    count = await batch_insert_raw(
        pool, "post",
        ["title", "content", "image_url", "author_id", "category_id", "views", "created_at"],
        data,
        ignore=False,  # post 테이블에 UNIQUE 제약 없음
    )
    print(f"  ✓ 게시글 {count:,}개 삽입 완료")


async def seed_post_tags(pool: aiomysql.Pool) -> None:
    """게시글-태그 연결 생성."""
    pass


async def seed_post_images(pool: aiomysql.Pool) -> None:
    """게시글 이미지 연결 생성."""
    pass


async def seed_polls(pool: aiomysql.Pool) -> None:
    """투표 데이터 생성."""
    pass


async def seed_comments(pool: aiomysql.Pool) -> None:
    """댓글 50만 개 생성."""
    pass


async def seed_post_likes(pool: aiomysql.Pool) -> None:
    """게시글 좋아요 생성."""
    pass


async def seed_bookmarks(pool: aiomysql.Pool) -> None:
    """북마크 생성."""
    pass


async def seed_comment_likes(pool: aiomysql.Pool) -> None:
    """댓글 좋아요 생성."""
    pass


async def seed_view_logs(pool: aiomysql.Pool) -> None:
    """조회 로그 생성."""
    pass


async def seed_poll_votes(pool: aiomysql.Pool) -> None:
    """투표 참여 데이터 생성."""
    pass


async def seed_follows(pool: aiomysql.Pool) -> None:
    """팔로우 관계 생성."""
    pass


async def seed_blocks(pool: aiomysql.Pool) -> None:
    """사용자 차단 생성."""
    pass


async def seed_notifications(pool: aiomysql.Pool) -> None:
    """알림 데이터 생성."""
    pass


async def seed_reports(pool: aiomysql.Pool) -> None:
    """신고 데이터 생성."""
    pass


async def seed_dms(pool: aiomysql.Pool) -> None:
    """DM 대화 + 메시지 생성."""
    pass


async def verify_data(pool: aiomysql.Pool) -> None:
    """시딩 결과 검증 (테이블별 행 수 출력)."""
    pass


async def trigger_recompute(url: str) -> None:
    """추천 피드 재계산 API 호출."""
    pass


# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────


async def main() -> None:
    """대규모 시드 데이터 생성 메인 함수."""
    args = parse_args()

    # 배너 출력
    print("=" * 60)
    print("  대규모 시드 데이터 생성")
    print("=" * 60)
    print(f"  대상 DB: {args.db_user}@{args.db_host}:{args.db_port}/{args.db_name}")
    print(f"  옵션: clean={args.clean}, dry_run={args.dry_run}")
    print("-" * 60)
    print(f"  사용자: {TOTAL_USERS:>10,}명")
    print(f"    - Power  ({POWER_RATIO:.0%}): {POWER_COUNT:>10,}명")
    print(f"    - Regular({REGULAR_RATIO:.0%}): {REGULAR_COUNT:>10,}명")
    print(f"    - Reader ({READER_RATIO:.0%}): {READER_COUNT:>10,}명")
    print(f"  배치 크기: {BATCH_SIZE:,}")
    print("=" * 60)

    # Dry-run 모드: 설정만 확인하고 종료
    if args.dry_run:
        print("\n[dry-run] DB 접속 없이 종료합니다.")
        return

    # 확인 프롬프트
    if not args.no_confirm:
        confirm = input("\n시딩을 시작할까요? (yes/no): ")
        if confirm.lower() != "yes":
            print("취소되었습니다.")
            return

    # DB 연결
    pool = await create_pool(args)
    start_time = time.time()

    try:
        # 기존 데이터 카운트 확인
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT COUNT(*) FROM user")
                (user_count,) = await cur.fetchone()
                print(f"\n현재 user 테이블: {user_count:,}행")

        # 기존 데이터 삭제
        if args.clean:
            print("\n[Phase 0] 기존 데이터 삭제")
            await clean_all_data(pool)

        # Phase 1: 기초 데이터 (순차 — FK 의존성)
        print("\n[Phase 1] 기초 데이터: 사용자, 카테고리, 태그")
        await seed_users(pool)
        await seed_categories(pool)
        await seed_tags(pool)

        # Phase 2: 게시글 관련 (순차 — post_id FK 의존)
        print("\n[Phase 2] 게시글 관련: 게시글, 태그 연결, 이미지, 투표")
        await seed_posts(pool)
        await seed_post_tags(pool)
        await seed_post_images(pool)
        await seed_polls(pool)

        # Phase 3: 게시글/댓글 인터랙션 (병렬 — 서로 독립)
        print("\n[Phase 3] 인터랙션: 댓글, 좋아요, 북마크, 조회")
        await seed_comments(pool)  # 댓글은 먼저 (comment_likes가 의존)
        await asyncio.gather(
            seed_post_likes(pool),
            seed_bookmarks(pool),
            seed_comment_likes(pool),
            seed_view_logs(pool),
            seed_poll_votes(pool),
        )

        # Phase 4: 소셜/기타 (병렬 — 서로 독립)
        print("\n[Phase 4] 소셜: 팔로우, 차단, 알림, 신고, DM")
        await asyncio.gather(
            seed_follows(pool),
            seed_blocks(pool),
            seed_notifications(pool),
            seed_reports(pool),
            seed_dms(pool),
        )

        # Phase 5: 검증 + 추천 피드 재계산
        print("\n[Phase 5] 검증 및 후처리")
        await verify_data(pool)

        if args.recompute_url:
            await trigger_recompute(args.recompute_url)

        # 완료 요약
        elapsed = time.time() - start_time
        minutes = int(elapsed // 60)
        seconds = elapsed % 60
        print("\n" + "=" * 60)
        print(f"  시딩 완료! 소요 시간: {minutes}분 {seconds:.1f}초")
        print("=" * 60)
        print("  로그인 정보:")
        print("    - admin: user1@example.com / Test1234!")
        print(f"    - 일반: user2@example.com ~ user{TOTAL_USERS}@example.com / Test1234!")
        print("=" * 60)

    finally:
        pool.close()
        await pool.wait_closed()
        print("DB 커넥션 풀 종료")


if __name__ == "__main__":
    asyncio.run(main())
