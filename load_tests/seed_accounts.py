"""seed_accounts.py: 부하 테스트 계정을 대상 환경에 시딩합니다.

load_tests/config.py에 정의된 계정 패턴(user1@example.com ~ user250@example.com)을
회원가입 API 또는 직접 DB 접속으로 생성합니다.

사용법:
    cd 2-cho-community-be

    # 모드 1: API를 통한 시딩 (DB 접근 불필요, 권장)
    python -m load_tests.seed_accounts \\
        --mode api --host https://api.my-community.shop

    # 로컬 서버 대상
    python -m load_tests.seed_accounts \\
        --mode api --host http://127.0.0.1:8000

    # 모드 2: DB 직접 접속 (SSH 터널 필요, 빠름)
    python -m load_tests.seed_accounts \\
        --mode db --db-user admin --db-password <pw> --db-name community

주의사항:
    - API 모드: Rate Limit(3회/분/Lambda인스턴스) 적용됨.
      Lambda 인스턴스 수에 따라 15~25분 소요 (250개 기준).
    - DB 모드: Bastion SSH 터널 필요. 수 초 내 완료.
    - 이미 존재하는 계정은 건너뜁니다 (멱등성 보장).
"""

import argparse
import asyncio
import sys
import time
from datetime import datetime, timedelta
import random

from load_tests.config import (
    ACCOUNT_COUNT,
    ACCOUNT_EMAIL_PATTERN,
    ACCOUNT_PASSWORD,
    ACCOUNT_START_INDEX,
)


# ============================================================
# 모드 1: API를 통한 시딩
# ============================================================

def seed_via_api(host: str) -> None:
    """회원가입 API(POST /v1/users/)를 통해 계정을 생성합니다.

    Rate Limit(3회/분/Lambda인스턴스)을 자동 처리합니다.
    429 응답 시 Retry-After 헤더만큼 대기 후 재시도합니다.
    """
    import requests

    base_url = host.rstrip("/")
    session = requests.Session()

    end = ACCOUNT_START_INDEX + ACCOUNT_COUNT
    total = ACCOUNT_COUNT
    created = 0
    skipped = 0
    rate_limited_waits = 0

    print(f"=== API 모드: 부하 테스트 계정 시딩 ===")
    print(f"대상: {base_url}")
    print(f"계정: {total}개 "
          f"({ACCOUNT_EMAIL_PATTERN.format(ACCOUNT_START_INDEX)} ~ "
          f"{ACCOUNT_EMAIL_PATTERN.format(end - 1)})")
    print(f"비밀번호: {ACCOUNT_PASSWORD}")
    print()
    print("Rate Limit에 의해 15~25분 소요될 수 있습니다.")
    print("Ctrl+C로 중단해도 이미 생성된 계정은 유지됩니다.")
    print()

    start_time = time.time()

    for i in range(ACCOUNT_START_INDEX, end):
        email = ACCOUNT_EMAIL_PATTERN.format(i)
        nickname = f"user_{i:05d}"
        done = (i - ACCOUNT_START_INDEX)
        progress = done / total * 100

        # 경과 시간 및 ETA 계산
        elapsed = time.time() - start_time
        if done > 0:
            eta_seconds = (elapsed / done) * (total - done)
            eta_str = f"{eta_seconds / 60:.1f}분"
        else:
            eta_str = "계산 중..."

        print(
            f"\r  [{progress:5.1f}%] {done}/{total} "
            f"(생성: {created}, 건너뜀: {skipped}, "
            f"429대기: {rate_limited_waits}회, "
            f"남은시간: {eta_str})",
            end="", flush=True,
        )

        # 재시도 루프 (429 Rate Limit 대응)
        while True:
            try:
                resp = session.post(
                    f"{base_url}/v1/users/",
                    data={
                        "email": email,
                        "password": ACCOUNT_PASSWORD,
                        "nickname": nickname,
                    },
                    timeout=15,
                )
            except requests.RequestException as e:
                print(f"\n  연결 오류: {e}")
                print("  5초 후 재시도...")
                time.sleep(5)
                continue

            if resp.status_code == 201:
                created += 1
                break

            elif resp.status_code == 409:
                # 이미 존재하는 계정
                skipped += 1
                break

            elif resp.status_code == 429:
                # Rate Limited — Retry-After 헤더 또는 기본 65초 대기
                retry_after = int(resp.headers.get("Retry-After", 65))
                rate_limited_waits += 1
                print(
                    f"\n  429 Rate Limited ({email}). "
                    f"{retry_after}초 대기 중...",
                    end="", flush=True,
                )
                time.sleep(retry_after)
                # 줄바꿈 없이 다시 진행률 표시

            else:
                body = resp.text[:150] if resp.text else "(빈 응답)"
                print(f"\n  예상치 못한 오류 ({email}): "
                      f"HTTP {resp.status_code}: {body}")
                # 계속 진행 (다음 계정으로)
                break

    # 최종 결과
    elapsed = time.time() - start_time
    print()
    print()
    print(f"=== 시딩 완료 ({elapsed:.0f}초) ===")
    print(f"  새로 생성: {created}개")
    print(f"  건너뜀 (이미 존재): {skipped}개")
    print(f"  Rate Limit 대기: {rate_limited_waits}회")
    print()
    print("부하 테스트 실행:")
    print(f"  locust -f load_tests/locustfile.py --host={base_url}")


# ============================================================
# 모드 2: DB 직접 접속
# ============================================================

async def seed_via_db(
    db_host: str,
    db_port: int,
    db_user: str,
    db_password: str,
    db_name: str,
) -> None:
    """MySQL DB에 직접 접속하여 계정을 INSERT IGNORE합니다.

    사전 준비 (AWS RDS):
        1. SSH 터널: ssh -L 3306:<rds-endpoint>:3306 ec2-user@<bastion-ip> -i <key> -N
        2. 엔드포인트 확인: terraform output rds_endpoint
    """
    import aiomysql
    import bcrypt

    print(f"=== DB 모드: 부하 테스트 계정 시딩 ===")
    print(f"대상: {db_user}@{db_host}:{db_port}/{db_name}")

    end = ACCOUNT_START_INDEX + ACCOUNT_COUNT
    print(f"계정: {ACCOUNT_COUNT}개 "
          f"({ACCOUNT_EMAIL_PATTERN.format(ACCOUNT_START_INDEX)} ~ "
          f"{ACCOUNT_EMAIL_PATTERN.format(end - 1)})")
    print()

    # 비밀번호 해싱 (1회)
    print(f"비밀번호 해싱 중... ('{ACCOUNT_PASSWORD}')")
    hashed = bcrypt.hashpw(
        ACCOUNT_PASSWORD.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")
    print(f"해시 완료: {hashed[:20]}...")
    print()

    # DB 연결
    print(f"DB 연결 중...")
    try:
        conn = await aiomysql.connect(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_password,
            db=db_name,
            connect_timeout=10,
            charset="utf8mb4",
        )
    except Exception as e:
        print(f"DB 연결 실패: {e}")
        print()
        print("확인사항:")
        print("  1. SSH 터널이 실행 중인지 확인하세요")
        print("  2. DB 자격 증명이 올바른지 확인하세요")
        print("  3. 데이터베이스가 존재하는지 확인하세요")
        sys.exit(1)

    print("DB 연결 성공!")
    print()

    try:
        random.seed(42)
        now = datetime.now()
        accounts = []
        for i in range(ACCOUNT_START_INDEX, end):
            email = ACCOUNT_EMAIL_PATTERN.format(i)
            nickname = f"user_{i:05d}"
            created_at = now - timedelta(days=random.randint(1, 30))
            accounts.append((email, nickname, hashed, None, created_at))

        print(f"계정 삽입 중... ({len(accounts)}개)")
        async with conn.cursor() as cur:
            await cur.executemany(
                """
                INSERT IGNORE INTO user (email, nickname, password, profile_img, created_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                accounts,
            )
            await conn.commit()
            inserted = cur.rowcount

        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT COUNT(*) FROM user WHERE email LIKE 'user%@example.com' "
                "AND deleted_at IS NULL"
            )
            row = await cur.fetchone()
            total_in_db = row[0] if row else 0

        print()
        print(f"=== 시딩 완료 ===")
        print(f"  새로 생성: {inserted}개")
        print(f"  건너뜀 (이미 존재): {len(accounts) - inserted}개")
        print(f"  DB 내 테스트 계정 총: {total_in_db}개")
        print()
        print("부하 테스트 실행:")
        print("  locust -f load_tests/locustfile.py --host=https://api.my-community.shop")

    finally:
        conn.close()


# ============================================================
# CLI
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="부하 테스트 계정을 대상 환경에 시딩합니다.",
    )
    parser.add_argument(
        "--mode", choices=["api", "db"], default="api",
        help="시딩 방식: api(회원가입 API) 또는 db(직접 DB 접속) (기본: api)",
    )

    # API 모드 옵션
    parser.add_argument("--host", help="API 서버 URL (api 모드, 예: https://api.my-community.shop)")

    # DB 모드 옵션
    parser.add_argument("--db-host", default="127.0.0.1", help="DB 호스트 (db 모드, 기본: 127.0.0.1)")
    parser.add_argument("--db-port", type=int, default=3306, help="DB 포트 (db 모드, 기본: 3306)")
    parser.add_argument("--db-user", help="DB 사용자명 (db 모드)")
    parser.add_argument("--db-password", default="", help="DB 비밀번호 (db 모드)")
    parser.add_argument("--db-name", help="DB 이름 (db 모드)")

    args = parser.parse_args()

    if args.mode == "api":
        if not args.host:
            parser.error("API 모드에서는 --host가 필수입니다.")
        seed_via_api(host=args.host)

    elif args.mode == "db":
        if not args.db_user or not args.db_name:
            parser.error("DB 모드에서는 --db-user와 --db-name이 필수입니다.")
        asyncio.run(seed_via_db(
            db_host=args.db_host,
            db_port=args.db_port,
            db_user=args.db_user,
            db_password=args.db_password,
            db_name=args.db_name,
        ))


if __name__ == "__main__":
    main()
