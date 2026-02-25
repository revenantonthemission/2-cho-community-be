from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """애플리케이션 설정을 관리하는 클래스.

    환경 변수에서 설정을 로드하며, 기본값을 제공합니다.

    Attributes:
        SECRET_KEY: 세션 암호화 키.
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
        "http://127.0.0.1:8080",  # Local dev (frontend)
        "http://localhost:8080",  # Local dev (frontend)
        # EC2 + nginx reverse proxy deployment:
        # "http://your-frontend-ec2-ip",
        # "https://your-frontend-ec2-domain",
        # CloudFront + S3 deployment (Approach A: CloudFront proxies /v1/*):
        # Requests appear same-origin via CloudFront, so CORS is not strictly required,
        # but adding the domain is good practice and protects local dev CORS.
        # "https://d1234abcd.cloudfront.net",
        "https://my-community.shop",
    ]

    # MySQL Database Settings
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str

    # Auth Settings
    SESSION_EXPIRE_HOURS: int = 24

    # Debug Mode (프로덕션에서는 False로 설정하여 상세 에러 숨김)
    DEBUG: bool = True

    # File Upload Settings
    IMAGE_UPLOAD_DIR: str = "assets/posts"
    PROFILE_IMAGE_UPLOAD_DIR: str = "assets/profiles"

    # Rate Limiting Settings
    RATE_LIMIT_MAX_IPS: int = 10000  # 메모리 보호를 위한 최대 추적 IP 수
    TRUSTED_PROXIES: set[str] = set()  # 신뢰할 수 있는 프록시 IP (프로덕션에서 설정)

    # AWS S3 Settings (optional - only needed for S3 storage)
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "ap-northeast-2"
    AWS_S3_BUCKET_NAME: str = ""
    CLOUDFRONT_DOMAIN: str = ""

    # Storage type: "local" or "s3"
    STORAGE_TYPE: str = "local"  # e.g. "d1234abcd.cloudfront.net" — set in production .env

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()  # type: ignore[call-arg]  # pydantic-settings는 .env에서 환경 변수를 불러옴.
