"""rate_limiter_base: Rate Limiter 인터페이스 정의."""

from typing import Protocol


class RateLimiterProtocol(Protocol):
    """Rate Limiter 백엔드 인터페이스.

    인메모리(로컬)와 Redis(K8s 프로덕션) 구현을 교체 가능하게 한다.
    """

    async def is_rate_limited(self, ip: str, max_requests: int, window_seconds: int) -> tuple[bool, int]:
        """요청이 속도 제한에 걸리는지 확인한다.

        Args:
            ip: rate_key (IP:METHOD:PATH 형식).
            max_requests: 윈도우 내 최대 요청 수.
            window_seconds: 시간 윈도우 (초).

        Returns:
            (제한 여부, 남은 요청 수) 튜플.
        """
        ...
