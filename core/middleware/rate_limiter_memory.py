"""rate_limiter_memory: 인메모리 Rate Limiter 구현.

로컬 개발 환경용. 단일 프로세스에서만 동작하며, 수평 확장 시 상태가 공유되지 않는다.
"""

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timedelta

from core.config import settings

logger = logging.getLogger(__name__)


class MemoryRateLimiter:
    """메모리 기반 Rate Limiter (LRU 메모리 보호 적용).

    로컬 개발 및 단일 프로세스 환경 전용. 분산 환경에서는 RedisRateLimiter를 사용한다.
    """

    def __init__(self, max_tracked_ips: int | None = None):
        """MemoryRateLimiter 초기화.

        Args:
            max_tracked_ips: 최대 추적 IP 수 (기본: settings.RATE_LIMIT_MAX_IPS).
        """
        # {ip: [timestamp, ...]}
        self._requests: dict[str, list] = defaultdict(list)
        self._lock = asyncio.Lock()
        self.max_tracked_ips = max_tracked_ips if max_tracked_ips is not None else settings.RATE_LIMIT_MAX_IPS

    async def is_rate_limited(self, ip: str, max_requests: int, window_seconds: int) -> tuple[bool, int]:
        """요청이 속도 제한에 걸리는지 확인한다.

        배치 제거 방식으로 메모리를 보호한다:
        1. IP 수가 max_tracked_ips를 초과하면 오래된 IP 10% 일괄 제거
        2. O(1) 평균 성능 보장 (배치 제거로 인한 분할 상환)
        3. "unknown" IP는 더 엄격한 제한 적용

        Args:
            ip: 클라이언트 IP 주소.
            max_requests: 윈도우 내 최대 요청 수.
            window_seconds: 시간 윈도우 (초).

        Returns:
            (제한 여부, 남은 요청 수) 튜플.
        """
        async with self._lock:
            # 메모리 보호: 배치 제거 방식 (성능 최적화)
            if len(self._requests) >= self.max_tracked_ips:
                # 10% (1000개)의 오래된 IP를 일괄 제거
                eviction_count = max(1, self.max_tracked_ips // 10)

                # IP를 마지막 요청 시간 기준으로 정렬 (오래된 순)
                sorted_ips = sorted(self._requests.items(), key=lambda item: max(item[1]) if item[1] else datetime.min)

                # 가장 오래된 IP부터 제거
                for ip_to_remove, _ in sorted_ips[:eviction_count]:
                    del self._requests[ip_to_remove]

                logger.warning(f"Rate Limiter 배치 제거: {eviction_count}개 IP 제거 (남은 IP: {len(self._requests)}개)")

            now = datetime.now()
            window_start = now - timedelta(seconds=window_seconds)

            # 윈도우 내의 요청만 유지
            self._requests[ip] = [req_time for req_time in self._requests[ip] if req_time > window_start]

            current_count = len(self._requests[ip])

            # "unknown" IP는 더 엄격한 제한 적용 (10회로 제한)
            if ip in ("unknown", "0.0.0.0", ""):
                max_requests = min(max_requests, 10)
                logger.warning(f"Unknown IP 감지: {ip}, 엄격한 제한 적용 (최대 {max_requests}회)")

            if current_count >= max_requests:
                return True, 0

            # 새 요청 기록
            self._requests[ip].append(now)
            return False, max_requests - current_count - 1
