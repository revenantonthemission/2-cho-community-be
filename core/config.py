import logging
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# config.py 기준으로 .env 경로를 결정 (CWD에 의존하지 않음)
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

# 프로덕션에서 사용 금지되는 취약한 시크릿 키 패턴
_WEAK_SECRET_KEYS = frozenset(
    {
        "your-secret-key-here",
        "dev-secret-key-change-in-production",
        "secret",
        "changeme",
    }
)


class Settings(BaseSettings):
    """애플리케이션 설정을 관리하는 클래스.

    환경 변수에서 설정을 로드하며, 기본값을 제공합니다.

    Attributes:
        SECRET_KEY: JWT 토큰 서명 키.
        ALLOWED_ORIGINS: CORS 허용 오리진 목록.
        DB_HOST: MySQL 호스트 주소.
        DB_PORT: MySQL 포트 번호.
        DB_USER: MySQL 사용자명.
        DB_PASSWORD: MySQL 비밀번호.
        DB_NAME: MySQL 데이터베이스 이름.
    """

    SECRET_KEY: str = Field(min_length=16)
    HTTPS_ONLY: bool = False
    ALLOWED_ORIGINS: list[str] = [
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
    ]

    DB_HOST: str = Field(min_length=1)
    DB_PORT: int = Field(ge=1, le=65535)
    DB_USER: str = Field(min_length=1)
    DB_PASSWORD: str = ""
    DB_NAME: str = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_production_settings(self) -> "Settings":
        """프로덕션 환경에서 위험한 설정을 차단합니다."""
        if not self.DEBUG:
            if self.SECRET_KEY in _WEAK_SECRET_KEYS:
                raise ValueError(
                    "프로덕션 환경에서 취약한 SECRET_KEY 사용이 감지되었습니다. 최소 32자 이상의 랜덤 키를 설정하세요."
                )
            if not self.DB_PASSWORD:
                raise ValueError("프로덕션 환경에서 빈 DB_PASSWORD는 허용되지 않습니다.")
        return self

    JWT_ACCESS_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_EXPIRE_DAYS: int = 7

    DEBUG: bool = False
    TESTING: bool = False

    IMAGE_UPLOAD_DIR: str = "assets/posts"
    PROFILE_IMAGE_UPLOAD_DIR: str = "assets/profiles"

    RATE_LIMIT_BACKEND: str = "memory"
    RATE_LIMIT_MAX_IPS: int = 10000
    TRUSTED_PROXIES: set[str] = set()

    REDIS_URL: str = ""

    EMAIL_BACKEND: str = "smtp"
    EMAIL_FROM: str = "noreply@my-community.shop"
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SES_REGION: str = "ap-northeast-2"

    REQUIRE_EMAIL_VERIFICATION: bool = True

    FRONTEND_URL: str = "http://127.0.0.1:3000"

    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    GITHUB_REDIRECT_URI: str = ""

    INTERNAL_API_KEY: str = ""

    WS_BACKEND: str = "redis"

    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8", extra="ignore")


settings = Settings()  # type: ignore[call-arg]  # pydantic-settings는 .env에서 환경 변수를 불러옴.
