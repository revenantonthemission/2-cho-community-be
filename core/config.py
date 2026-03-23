import logging
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# config.py 기준으로 .env 경로를 결정 (CWD에 의존하지 않음)
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


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

    SECRET_KEY: str
    HTTPS_ONLY: bool = False
    ALLOWED_ORIGINS: list[str] = [
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
    ]

    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str

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
