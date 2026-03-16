import logging
import os

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


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
        "http://127.0.0.1:8080",  # 로컬 개발 (프론트엔드)
        "http://localhost:8080",  # 로컬 개발 (프론트엔드)
    ]

    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str

    JWT_ACCESS_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_EXPIRE_DAYS: int = 7

    # 로컬 개발 시 .env에서 DEBUG=True로 설정. 기본값 False로 프로덕션 안전성 보장
    DEBUG: bool = False
    TESTING: bool = False

    IMAGE_UPLOAD_DIR: str = "assets/posts"
    PROFILE_IMAGE_UPLOAD_DIR: str = "assets/profiles"

    RATE_LIMIT_BACKEND: str = "memory"  # "memory" (로컬) | "redis" (K8s 프로덕션)
    RATE_LIMIT_MAX_IPS: int = 10000  # 메모리 보호를 위한 최대 추적 IP 수
    TRUSTED_PROXIES: set[str] = set()  # 프로덕션에서 nginx 등의 프록시 IP 설정 필요

    # Redis (K8s 환경)
    REDIS_URL: str = ""

    # 이메일 발송 설정
    EMAIL_BACKEND: str = "smtp"  # "ses" (프로덕션) | "smtp" (로컬)
    EMAIL_FROM: str = "noreply@my-community.shop"
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SES_REGION: str = "ap-northeast-2"

    # 프론트엔드 URL (이메일 인증 링크 등에 사용)
    FRONTEND_URL: str = "http://localhost:8080"

    # 소셜 로그인 (GitHub)
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    GITHUB_REDIRECT_URI: str = ""

    # 내부 API 인증 키 (CronJob 등 자동화된 호출에서 사용)
    INTERNAL_API_KEY: str = ""

    # WebSocket 백엔드 ("redis" 프로덕션, 로컬은 DEBUG 모드)
    WS_BACKEND: str = "redis"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()  # type: ignore[call-arg]  # pydantic-settings는 .env에서 환경 변수를 불러옴.
