"""main: FastAPI 애플리케이션의 메인 진입점.

애플리케이션 설정, 미들웨어 구성, 라우터 등록, 전역 예외 핸들러를 설정합니다.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.auth_router import auth_router
from routers.user_router import user_router
from routers.post_router import post_router
from routers.terms_router import terms_router
from routers.category_router import category_router
from routers.report_router import report_router
from routers import notification_router
from middleware import TimingMiddleware, LoggingMiddleware, RateLimitMiddleware
from middleware.exception_handler import (
    global_exception_handler,
    request_validation_exception_handler,
)
from core.config import settings
from database.connection import init_db, close_db
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from mangum import Mangum


_TOKEN_CLEANUP_INTERVAL_HOURS = 1

logger = logging.getLogger("api")


async def _periodic_token_cleanup() -> None:
    """만료된 토큰을 주기적으로 정리하는 백그라운드 작업.

    Refresh Token과 이메일 인증 토큰을 함께 정리합니다.
    """
    from models.token_models import cleanup_expired_tokens
    from models.verification_models import cleanup_expired_verification_tokens

    while True:
        await asyncio.sleep(_TOKEN_CLEANUP_INTERVAL_HOURS * 3600)
        try:
            await cleanup_expired_tokens()
        except Exception:
            logger.exception("Refresh Token 정리 중 오류 발생")
        try:
            await cleanup_expired_verification_tokens()
        except Exception:
            logger.exception("이메일 인증 토큰 정리 중 오류 발생")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리.

    시작 시 데이터베이스 연결 풀을 초기화하고,
    만료 토큰 정리 작업을 스케줄링하며,
    종료 시 백그라운드 작업과 연결 풀을 정리합니다.
    """
    await init_db()
    cleanup_task = asyncio.create_task(_periodic_token_cleanup())
    yield
    cleanup_task.cancel()
    await close_db()


app = FastAPI(
    title="2cho Community API",
    description="커뮤니티 백엔드 API 서버",
    version="1.0.0",
    lifespan=lifespan,
)

# 각 요청에 타임스탬프를 주입하여 request.state에서 접근 가능하게 함
app.add_middleware(TimingMiddleware)

app.add_middleware(LoggingMiddleware)

# 브루트포스 공격 방지를 위한 IP 기반 요청 속도 제한
app.add_middleware(RateLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# nginx 등 리버스 프록시 뒤에서 X-Forwarded-Proto를 신뢰하여
# HTTPS 리다이렉트가 올바른 프로토콜을 사용하도록 함.
# trusted_hosts="*"는 IP 스푸핑 위험이 있으므로 명시적 IP만 허용
_proxy_trusted_hosts = list(settings.TRUSTED_PROXIES) if settings.TRUSTED_PROXIES else ["127.0.0.1", "::1"]
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=_proxy_trusted_hosts)

app.include_router(auth_router)
app.include_router(user_router)
app.include_router(post_router)
app.include_router(terms_router)
app.include_router(category_router)
app.include_router(report_router)
app.include_router(notification_router.router)

# Lambda 환경에서는 /var/task가 읽기 전용
# Docker 이미지에 assets/profiles/default_profile.jpg가 포함됨
if os.environ.get("AWS_LAMBDA_EXEC") != "true":
    os.makedirs("assets", exist_ok=True)
if os.path.isdir("assets"):
    app.mount("/assets", StaticFiles(directory="assets"), name="assets")

# 업로드 파일 서빙 (Lambda: EFS /mnt/uploads, Docker: UPLOAD_DIR 환경변수)
_upload_dir = os.environ.get("UPLOAD_DIR")
if _upload_dir:
    if os.environ.get("AWS_LAMBDA_EXEC") != "true":
        os.makedirs(_upload_dir, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=_upload_dir), name="uploads")


@app.get("/health", status_code=200)
async def health_check():
    """서버 상태 및 DB 연결 확인."""
    from database.connection import test_connection

    if await test_connection():
        return {"status": "ok", "database": "connected"}
    return {"status": "error", "database": "disconnected"}


app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(RequestValidationError, request_validation_exception_handler)  # type: ignore[arg-type]

# AWS 핸들러 설정
handler = Mangum(app)