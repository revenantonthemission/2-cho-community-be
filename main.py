"""main: FastAPI 애플리케이션의 메인 진입점.

애플리케이션 설정, 미들웨어 구성, 라우터 등록, 전역 예외 핸들러를 설정합니다.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from core.config import settings
from database.connection import close_db, init_db
from middleware import LoggingMiddleware, RateLimitMiddleware, TimingMiddleware
from middleware.exception_handler import (
    global_exception_handler,
    request_validation_exception_handler,
)
from routers import draft_router, notification_router, social_auth_router
from routers.auth_router import auth_router
from routers.category_router import category_router
from routers.dm_router import router as dm_router
from routers.package_router import package_router
from routers.post_router import post_router
from routers.report_router import report_router
from routers.tag_router import tag_router
from routers.terms_router import terms_router
from routers.user_router import user_router
from routers.wiki_router import wiki_router

logger = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리.

    시작 시 데이터베이스 연결 풀을 초기화하고,
    종료 시 연결 풀을 정리합니다.

    배치 작업(토큰 정리, 피드 점수 재계산)은 K8s CronJob으로 실행됩니다.
    """
    await init_db()
    yield
    await close_db()


app = FastAPI(
    title="Camp Linux API",
    description="Camp Linux 커뮤니티 백엔드 API 서버",
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
app.include_router(tag_router)
app.include_router(report_router)
app.include_router(notification_router.router)
app.include_router(dm_router)
app.include_router(social_auth_router.router)
app.include_router(draft_router.router)
app.include_router(package_router)
app.include_router(wiki_router)

# 로컬 개발 전용 WebSocket 엔드포인트 (K8s WS Pod이 담당)
if settings.DEBUG:
    from routers.websocket_router import router as ws_router

    app.include_router(ws_router)

# E2E 테스트 전용 API (TESTING=true일 때만 등록)
# 이중 게이트: TESTING=true + (DEBUG=true OR CI 환경)에서만 허용
if settings.TESTING:
    if not settings.DEBUG and not os.environ.get("CI"):
        import logging as _logging

        _logging.getLogger(__name__).critical(
            "TESTING=true이지만 DEBUG=false입니다. 프로덕션에서 테스트 라우터가 활성화될 수 있습니다."
        )
    from routers.test_router import test_router

    app.include_router(test_router)

os.makedirs("assets", exist_ok=True)
app.mount("/assets", StaticFiles(directory="assets"), name="assets")

# 업로드 파일 서빙 (UPLOAD_DIR 환경변수)
_upload_dir = os.environ.get("UPLOAD_DIR")
if _upload_dir:
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

# K8s: Prometheus 메트릭 엔드포인트
try:
    from prometheus_fastapi_instrumentator import Instrumentator

    Instrumentator().instrument(app).expose(app)
except ImportError:
    pass  # K8s 의존성 미설치 시 무시 (로컬 개발)
