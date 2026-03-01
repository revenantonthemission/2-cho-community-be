"""locustfile.py: 커뮤니티 포럼 백엔드 부하 테스트.

대상: AWS 배포 환경 (API Gateway → Lambda → RDS MySQL)
도구: Locust (Python)
규모: 동시 50-200명

사전 준비:
    1. uv pip install locust
    2. seed_data.py로 테스트 계정이 대상 DB에 존재해야 합니다.
       (user1@example.com ~ user250@example.com / Test1234!)

실행:
    # UI 모드 (브라우저에서 localhost:8089 접속)
    cd 2-cho-community-be
    locust -f load_tests/locustfile.py --host=https://api.my-community.shop

    # Headless 모드 (CLI에서 직접 결과 확인)
    locust -f load_tests/locustfile.py \
        --host=https://api.my-community.shop \
        --users=100 --spawn-rate=5 --run-time=10m --headless

    # 로컬 테스트
    locust -f load_tests/locustfile.py --host=http://127.0.0.1:8000

    # 특정 사용자 프로필만 실행
    locust -f load_tests/locustfile.py --host=http://127.0.0.1:8000 ReaderUser

주의사항:
    - Rate Limiter: Lambda 인스턴스마다 독립적인 인메모리 카운터 사용
      → 여러 인스턴스에 분산되면 실제 제한보다 관대하게 적용됨
    - Access Token 30분 만료: 테스트를 30분 이내로 제한하거나
      만료 후 401 비율 증가를 감안하여 결과를 분석하세요
    - 첫 30초는 Lambda 콜드 스타트 워밍업 구간입니다.
      P99 분석 시 이 구간을 제외하는 것을 권장합니다.
"""

import logging
import random

import gevent
from locust import HttpUser, between, events, task
from locust.exception import StopUser

from load_tests.accounts import account_pool, post_store
from load_tests.config import (
    ACTIVE_WAIT,
    COMMENT_CONTENTS,
    LOGIN_RETRY_WAIT,
    POST_CONTENTS,
    POST_LIST_LIMIT,
    POST_LIST_MAX_OFFSET,
    POST_TITLES,
    READER_WAIT,
    REQUEST_TIMEOUT,
    WRITER_WAIT,
)

logger = logging.getLogger(__name__)


# ============================================================
# 이벤트 핸들러
# ============================================================

@events.test_start.add_listener
def on_test_start(_environment, **_kwargs) -> None:
    """테스트 시작 전 사전 검증."""
    available = account_pool.available
    logger.info(f"=== 부하 테스트 시작 === (사용 가능한 계정: {available}개)")
    if available == 0:
        logger.error("계정 풀이 비어있습니다! seed_data.py로 계정을 먼저 생성하세요.")


@events.test_stop.add_listener
def on_test_stop(_environment, **_kwargs) -> None:
    """테스트 종료 후 요약."""
    logger.info(
        f"=== 부하 테스트 종료 === "
        f"(남은 계정: {account_pool.available}개, "
        f"게시글 캐시: {post_store.size}개)"
    )


# ============================================================
# 기반 클래스: 로그인/로그아웃 공통 처리
# ============================================================

class CommunityUser(HttpUser):
    """커뮤니티 사용자 기반 클래스.

    on_start(): 계정 풀에서 고유 계정 확보 → 로그인 → Bearer 토큰 세팅
    on_stop(): 로그아웃 → 계정 반납

    하위 클래스에서 @task와 wait_time만 정의하면 됩니다.
    """

    abstract = True

    def on_start(self) -> None:
        """계정 확보 및 로그인.

        Rate Limit(5회/분) 방어: on_start에서 1회만 로그인합니다.
        429 응답 시 윈도우 리셋을 기다린 후 재시도합니다.
        """
        self._account = account_pool.acquire()
        self._access_token: str | None = None
        self._liked_posts: set[int] = set()

        self._do_login()

    def on_stop(self) -> None:
        """로그아웃 및 계정 반납."""
        if self._access_token:
            self.client.delete(
                "/v1/auth/session",
                headers=self._auth_headers(),
                timeout=REQUEST_TIMEOUT,
                name="/v1/auth/session [logout]",
            )

        if self._account:
            account_pool.release(self._account)

    def _do_login(self) -> None:
        """로그인 수행. 429 시 최대 2회 재시도.

        모든 시도가 실패하면 StopUser를 발생시켜 이 사용자를 깨끗하게 중단합니다.
        on_stop()에서 계정이 풀에 반납됩니다.
        """
        for attempt in range(3):
            with self.client.post(
                "/v1/auth/session",
                json={
                    "email": self._account["email"],
                    "password": self._account["password"],
                },
                timeout=REQUEST_TIMEOUT,
                catch_response=True,
                name="/v1/auth/session [login]",
            ) as resp:
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    self._access_token = data.get("access_token", "")
                    resp.success()
                    return
                elif resp.status_code == 429 and attempt < 2:
                    resp.failure(f"Rate Limited (시도 {attempt + 1}/3)")
                    # gevent.sleep: gevent 허브에 제어를 반환하여 다른 greenlet이 실행됨
                    # time.sleep을 쓰면 전체 워커 프로세스가 블록됨
                    gevent.sleep(LOGIN_RETRY_WAIT)
                else:
                    resp.failure(f"로그인 실패: {resp.status_code}")
                    # 디버깅: 상태 코드 + 응답 본문 포함
                    body = resp.text[:200] if resp.text else "(빈 응답)"
                    logger.error(
                        f"로그인 실패: {self._account['email']} "
                        f"(HTTP {resp.status_code}: {body})"
                    )
                    raise StopUser()

    def _auth_headers(self) -> dict:
        """Authorization 헤더를 반환합니다."""
        if self._access_token:
            return {"Authorization": f"Bearer {self._access_token}"}
        return {}

    @property
    def _is_authenticated(self) -> bool:
        return self._access_token is not None and self._access_token != ""

    # ── 공통 태스크 함수 (하위 클래스의 @task에서 호출) ────

    def _browse_posts(self) -> None:
        """게시글 목록을 조회하고 post_id를 캐시에 등록합니다."""
        max_page = POST_LIST_MAX_OFFSET // POST_LIST_LIMIT
        offset = random.randint(0, max_page) * POST_LIST_LIMIT
        with self.client.get(
            f"/v1/posts/?offset={offset}&limit={POST_LIST_LIMIT}",
            timeout=REQUEST_TIMEOUT,
            catch_response=True,
            name="/v1/posts/ [list]",
        ) as resp:
            if resp.status_code == 200:
                posts = resp.json().get("data", {}).get("posts", [])
                if posts:
                    post_store.push_many([p["post_id"] for p in posts if "post_id" in p])
                resp.success()
            else:
                resp.failure(f"목록 조회 실패: {resp.status_code}")

    def _view_post_detail(self) -> None:
        """게시글 상세를 조회합니다."""
        post_id = post_store.sample()
        if post_id is None:
            self._browse_posts()
            return

        with self.client.get(
            f"/v1/posts/{post_id}",
            headers=self._auth_headers(),
            timeout=REQUEST_TIMEOUT,
            catch_response=True,
            name="/v1/posts/{id} [detail]",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code == 404:
                post_store.remove(post_id)
                resp.success()
            else:
                resp.failure(f"상세 조회 실패: {resp.status_code}")

    def _check_auth(self) -> None:
        """인증 상태를 확인합니다 (GET /v1/auth/me)."""
        if not self._is_authenticated:
            return

        with self.client.get(
            "/v1/auth/me",
            headers=self._auth_headers(),
            timeout=REQUEST_TIMEOUT,
            catch_response=True,
            name="/v1/auth/me [check]",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code == 401:
                # Access Token 만료 (30분)
                self._access_token = None
                resp.failure("Access Token 만료")
            else:
                resp.failure(f"인증 확인 실패: {resp.status_code}")

    def _create_post(self) -> None:
        """게시글을 작성합니다."""
        if not self._is_authenticated:
            return

        title = random.choice(POST_TITLES)
        content = random.choice(POST_CONTENTS) + f" ({random.randint(1000, 9999)})"

        with self.client.post(
            "/v1/posts/",
            json={"title": title, "content": content},
            headers=self._auth_headers(),
            timeout=REQUEST_TIMEOUT,
            catch_response=True,
            name="/v1/posts/ [create]",
        ) as resp:
            if resp.status_code == 201:
                post_id = resp.json().get("data", {}).get("post_id")
                if post_id:
                    post_store.push(post_id)
                resp.success()
            elif resp.status_code == 429:
                # Rate Limit(10회/분)은 정상 방어 동작
                resp.failure("Rate Limited: 게시글 작성")
            elif resp.status_code == 401:
                self._access_token = None
                resp.failure("인증 만료")
            else:
                resp.failure(f"게시글 작성 실패: {resp.status_code}")

    def _create_comment(self) -> None:
        """게시글에 댓글을 작성합니다."""
        if not self._is_authenticated:
            return

        post_id = post_store.sample()
        if post_id is None:
            return

        content = random.choice(COMMENT_CONTENTS)

        with self.client.post(
            f"/v1/posts/{post_id}/comments",
            json={"content": content},
            headers=self._auth_headers(),
            timeout=REQUEST_TIMEOUT,
            catch_response=True,
            name="/v1/posts/{id}/comments [create]",
        ) as resp:
            if resp.status_code == 201:
                resp.success()
            elif resp.status_code == 404:
                post_store.remove(post_id)
                resp.success()
            elif resp.status_code == 429:
                resp.failure("Rate Limited: 댓글 작성")
            elif resp.status_code == 401:
                self._access_token = None
                resp.failure("인증 만료")
            else:
                resp.failure(f"댓글 작성 실패: {resp.status_code}")

    def _toggle_like(self) -> None:
        """게시글 좋아요를 토글합니다.

        _liked_posts set으로 상태를 추적하여 like/unlike를 번갈아 실행합니다.
        409(이미 좋아요)는 상태 동기화 후 성공으로 처리합니다.
        """
        if not self._is_authenticated:
            return

        post_id = post_store.sample()
        if post_id is None:
            return

        if post_id in self._liked_posts:
            # 좋아요 취소
            with self.client.delete(
                f"/v1/posts/{post_id}/likes",
                headers=self._auth_headers(),
                timeout=REQUEST_TIMEOUT,
                catch_response=True,
                name="/v1/posts/{id}/likes [unlike]",
            ) as resp:
                if resp.status_code == 200:
                    self._liked_posts.discard(post_id)
                    resp.success()
                elif resp.status_code == 404:
                    # 404는 "게시글 삭제" 또는 "좋아요 기록 없음" 두 가지 경우
                    # 좋아요 상태만 정리하고, 게시글은 스토어에서 제거하지 않음
                    # (다른 사용자가 여전히 접근 가능한 게시글일 수 있음)
                    self._liked_posts.discard(post_id)
                    resp.success()
                elif resp.status_code == 401:
                    self._access_token = None
                    resp.failure("인증 만료")
                else:
                    resp.failure(f"좋아요 취소 실패: {resp.status_code}")
        else:
            # 좋아요 추가
            with self.client.post(
                f"/v1/posts/{post_id}/likes",
                headers=self._auth_headers(),
                timeout=REQUEST_TIMEOUT,
                catch_response=True,
                name="/v1/posts/{id}/likes [like]",
            ) as resp:
                if resp.status_code == 201:
                    self._liked_posts.add(post_id)
                    resp.success()
                elif resp.status_code == 409:
                    # 이미 좋아요 상태 — 로컬 상태 동기화
                    self._liked_posts.add(post_id)
                    resp.success()
                elif resp.status_code == 404:
                    post_store.remove(post_id)
                    resp.success()
                elif resp.status_code == 401:
                    self._access_token = None
                    resp.failure("인증 만료")
                else:
                    resp.failure(f"좋아요 실패: {resp.status_code}")


# ============================================================
# 시나리오 1: ReaderUser (60%)
# 읽기 전용 — 로그인 후 목록/상세만 반복 조회
# GET 요청은 Rate Limit 대상 아님
# ============================================================

class ReaderUser(CommunityUser):
    """읽기 전용 사용자 (눈팅족).

    실제 커뮤니티 트래픽의 대부분을 차지합니다.
    게시글 목록과 상세 페이지를 반복적으로 탐색합니다.
    """

    weight = 6
    wait_time = between(*READER_WAIT)

    @task(5)
    def browse_posts(self) -> None:
        self._browse_posts()

    @task(3)
    def view_post_detail(self) -> None:
        self._view_post_detail()

    @task(2)
    def check_auth(self) -> None:
        self._check_auth()


# ============================================================
# 시나리오 2: WriterUser (20%)
# 게시글 작성 + 댓글 — POST Rate Limit(10회/분) 주요 발생원
# wait_time을 길게 설정하여 Rate Limit 준수
# ============================================================

class WriterUser(CommunityUser):
    """작성자 사용자.

    게시글을 적극적으로 작성하고, 자신의 글에 댓글을 답니다.
    Rate Limit:
        POST /v1/posts: 10회/분 → wait_time 8-20초로 최대 4-7회/분 유지
    """

    weight = 2
    wait_time = between(*WRITER_WAIT)

    @task(3)
    def browse_posts(self) -> None:
        self._browse_posts()

    @task(2)
    def view_post_detail(self) -> None:
        self._view_post_detail()

    @task(3)
    def create_post(self) -> None:
        self._create_post()

    @task(2)
    def create_comment(self) -> None:
        self._create_comment()

    @task(1)
    def check_auth(self) -> None:
        self._check_auth()


# ============================================================
# 시나리오 3: ActiveUser (20%)
# 댓글 + 좋아요 중심 — 인터랙션 집중 사용자
# ============================================================

class ActiveUser(CommunityUser):
    """활성 참여 사용자.

    댓글과 좋아요를 적극적으로 수행하며,
    게시글도 가끔 작성합니다.
    """

    weight = 2
    wait_time = between(*ACTIVE_WAIT)

    @task(2)
    def browse_posts(self) -> None:
        self._browse_posts()

    @task(1)
    def view_post_detail(self) -> None:
        self._view_post_detail()

    @task(3)
    def create_comment(self) -> None:
        self._create_comment()

    @task(3)
    def toggle_like(self) -> None:
        self._toggle_like()

    @task(1)
    def check_auth(self) -> None:
        self._check_auth()
