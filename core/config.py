import logging
import os

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


def _resolve_ssm_secrets() -> None:
    """Lambda 환경에서 SSM Parameter Store의 SecureString 값을 환경 변수로 설정합니다.

    SSM 파라미터 이름은 Lambda 환경변수 DB_PASSWORD_SSM_NAME, SECRET_KEY_SSM_NAME에 지정.
    pydantic-settings가 환경변수에서 값을 읽기 전에 호출해야 합니다.
    """
    if os.getenv("AWS_LAMBDA_EXEC") != "true":
        return

    ssm_mappings = {
        "DB_PASSWORD": os.getenv("DB_PASSWORD_SSM_NAME"),
        "SECRET_KEY": os.getenv("SECRET_KEY_SSM_NAME"),
    }

    params_to_fetch = {k: v for k, v in ssm_mappings.items() if v}
    if not params_to_fetch:
        return

    import boto3  # Lambda 런타임에 기본 포함

    ssm = boto3.client("ssm")
    for env_var, ssm_name in params_to_fetch.items():
        try:
            response = ssm.get_parameter(Name=ssm_name, WithDecryption=True)
            os.environ[env_var] = response["Parameter"]["Value"]
        except Exception:
            logger.exception("SSM 파라미터 조회 실패: %s", ssm_name)
            raise


# Settings 인스턴스 생성 전에 SSM에서 시크릿을 환경변수로 설정
_resolve_ssm_secrets()


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

    # 프로덕션에서는 False로 설정하여 상세 에러 메시지 노출 방지
    DEBUG: bool = True

    IMAGE_UPLOAD_DIR: str = "assets/posts"
    PROFILE_IMAGE_UPLOAD_DIR: str = "assets/profiles"

    RATE_LIMIT_MAX_IPS: int = 10000  # 메모리 보호를 위한 최대 추적 IP 수
    TRUSTED_PROXIES: set[str] = set()  # 프로덕션에서 nginx 등의 프록시 IP 설정 필요

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()  # type: ignore[call-arg]  # pydantic-settings는 .env에서 환경 변수를 불러옴.
