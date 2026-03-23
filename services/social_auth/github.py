"""GitHub OAuth 2.0 프로바이더."""

import httpx

from core.config import settings
from services.social_auth.base import SocialUserInfo

GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_EMAILS_URL = "https://api.github.com/user/emails"


class GitHubProvider:
    """GitHub 소셜 로그인 제공자."""

    provider_name = "github"

    def get_authorize_url(self, state: str) -> str:
        """GitHub 인증 페이지 URL을 생성합니다."""
        params = {
            "client_id": settings.GITHUB_CLIENT_ID,
            "redirect_uri": settings.GITHUB_REDIRECT_URI,
            "state": state,
            "scope": "user:email",
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{GITHUB_AUTH_URL}?{query}"

    async def exchange_code(self, code: str) -> str:
        """authorization code → access_token 교환."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                GITHUB_TOKEN_URL,
                data={
                    "client_id": settings.GITHUB_CLIENT_ID,
                    "client_secret": settings.GITHUB_CLIENT_SECRET,
                    "code": code,
                },
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            return resp.json()["access_token"]

    async def get_user_info(self, access_token: str) -> SocialUserInfo:
        """access_token → 사용자 정보 조회."""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(GITHUB_USER_URL, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            email = data.get("email")
            email_verified = email is not None

            # 이메일 비공개 사용자: /user/emails에서 primary+verified 이메일 조회
            if not email:
                email, email_verified = await self._fetch_primary_email(client, headers)

        return SocialUserInfo(
            provider="github",
            provider_id=str(data["id"]),
            email=email,
            email_verified=email_verified,
            profile_image=data.get("avatar_url"),
        )

    @staticmethod
    async def _fetch_primary_email(client: httpx.AsyncClient, headers: dict[str, str]) -> tuple[str | None, bool]:
        """GitHub /user/emails에서 primary+verified 이메일을 가져옵니다."""
        resp = await client.get(GITHUB_EMAILS_URL, headers=headers)
        resp.raise_for_status()
        for entry in resp.json():
            if entry.get("primary") and entry.get("verified"):
                return entry["email"], True
        return None, False
