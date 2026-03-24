"""하위 호환 re-export 스텁 — 실제 구현은 modules.auth.social_router로 이동."""

from modules.auth.social_router import *  # noqa: F403
from modules.auth.social_router import _make_state, router

__all__ = ["_make_state", "router"]
