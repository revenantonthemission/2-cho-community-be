"""accounts.py: 계정 풀 및 공유 상태 관리.

AccountPool: 사전 등록된 계정을 Locust 사용자 간에 1:1로 배분합니다.
SharedPostStore: Writer가 생성한 게시글 ID를 다른 사용자가 참조할 수 있게 공유합니다.

두 클래스 모두 프로세스 레벨 싱글턴으로 동작합니다.
Locust의 gevent 기반 동시성에서 thread-safe 자료구조가 필요합니다.
"""

import logging
import queue
import random
import threading
from collections import deque

from load_tests.config import (
    ACCOUNT_COUNT,
    ACCOUNT_EMAIL_PATTERN,
    ACCOUNT_PASSWORD,
    ACCOUNT_START_INDEX,
    SHARED_POST_STORE_MAX,
)

logger = logging.getLogger(__name__)


# ============================================================
# 계정 풀
# ============================================================

class AccountPool:
    """프로세스 레벨 계정 풀 (싱글턴).

    queue.Queue로 계정을 관리합니다.
    각 Locust 사용자는 on_start()에서 acquire(), on_stop()에서 release()를 호출합니다.
    동시 사용자 수가 계정 수를 초과하면 acquire()는 계정 반납까지 블록됩니다.
    """

    _instance: "AccountPool | None" = None
    _lock = threading.Lock()
    _initialized: bool = False

    def __new__(cls) -> "AccountPool":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        self._pool: queue.Queue[dict] = queue.Queue()
        # 패턴 기반 계정 생성: user1@example.com ~ user250@example.com
        for i in range(ACCOUNT_START_INDEX, ACCOUNT_START_INDEX + ACCOUNT_COUNT):
            self._pool.put({
                "email": ACCOUNT_EMAIL_PATTERN.format(i),
                "password": ACCOUNT_PASSWORD,
            })

        self._initialized = True
        logger.info(f"계정 풀 초기화 완료: {ACCOUNT_COUNT}개 계정")

    def acquire(self, timeout: float = 30.0) -> dict:
        """사용 가능한 계정을 가져옵니다.

        Args:
            timeout: 최대 대기 시간(초). 초과 시 RuntimeError.

        Returns:
            {"email": ..., "password": ...} 딕셔너리.
        """
        try:
            return self._pool.get(timeout=timeout)
        except queue.Empty:
            raise RuntimeError(
                f"{timeout}초 내에 사용 가능한 계정이 없습니다. "
                f"config.py의 ACCOUNT_COUNT를 늘리거나 --users 수를 줄이세요."
            )

    def release(self, account: dict) -> None:
        """계정을 풀에 반납합니다."""
        self._pool.put(account)

    @property
    def available(self) -> int:
        """현재 사용 가능한 계정 수."""
        return self._pool.qsize()


# 프로세스 레벨 싱글턴
account_pool = AccountPool()


# ============================================================
# 게시글 ID 공유 스토어
# ============================================================

class SharedPostStore:
    """게시글 ID를 Locust 사용자 간에 공유하는 스토어 (싱글턴).

    Writer가 생성하거나 Reader가 목록에서 발견한 post_id를 저장합니다.
    모든 사용자 유형이 상세 조회, 댓글, 좋아요 시 여기서 post_id를 가져갑니다.

    deque(maxlen)으로 메모리 상한을 자동 관리합니다.
    가장 오래된 항목부터 제거되므로 삭제된 게시글 ID가 자연스럽게 퇴출됩니다.
    """

    _instance: "SharedPostStore | None" = None
    _lock = threading.Lock()
    _initialized: bool = False

    def __new__(cls) -> "SharedPostStore":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        self._post_ids: deque[int] = deque(maxlen=SHARED_POST_STORE_MAX)
        self._data_lock = threading.Lock()
        self._initialized = True

    def push(self, post_id: int) -> None:
        """게시글 ID를 스토어에 추가합니다."""
        with self._data_lock:
            self._post_ids.append(post_id)

    def push_many(self, post_ids: list[int]) -> None:
        """여러 게시글 ID를 한번에 추가합니다."""
        with self._data_lock:
            self._post_ids.extend(post_ids)

    def sample(self) -> int | None:
        """랜덤 게시글 ID를 반환합니다. 스토어가 비어있으면 None."""
        with self._data_lock:
            if not self._post_ids:
                return None
            return random.choice(self._post_ids)

    def remove(self, post_id: int) -> None:
        """삭제된 게시글 ID를 스토어에서 제거합니다."""
        with self._data_lock:
            try:
                self._post_ids.remove(post_id)
            except ValueError:
                pass  # 이미 제거됨 (다른 사용자가 먼저 제거)

    @property
    def size(self) -> int:
        return len(self._post_ids)


# 프로세스 레벨 싱글턴
post_store = SharedPostStore()
