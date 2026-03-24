"""소셜 로그인 공통 인터페이스."""

from dataclasses import dataclass
from typing import Protocol


@dataclass
class SocialUserInfo:
    """소셜 제공자로부터 받은 사용자 정보."""

    provider: str
    provider_id: str
    email: str | None
    email_verified: bool
    profile_image: str | None


class SocialProvider(Protocol):
    """소셜 로그인 제공자 인터페이스."""

    provider_name: str

    def get_authorize_url(self, state: str) -> str: ...
    async def exchange_code(self, code: str) -> str: ...
    async def get_user_info(self, access_token: str) -> SocialUserInfo: ...
