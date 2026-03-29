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
from core.database.connection import close_db, init_db
from core.logging_config import setup_logging
from core.middleware import RateLimitMiddleware, TimingMiddleware
from core.middleware.exception_handler import (
    global_exception_handler,
    request_validation_exception_handler,
)
from core.middleware.request_id import RequestIdMiddleware
from modules.admin.router import report_router
from modules.auth.router import auth_router
from modules.auth.social_router import router as social_auth_router
from modules.content.category_router import category_router
from modules.content.draft_router import router as draft_router
from modules.content.tag_router import tag_router
from modules.content.terms_router import terms_router
from modules.dm.router import router as dm_router
from modules.notification.router import router as notification_router
from modules.package.router import package_router
from modules.post.router import post_router
from modules.reputation.router import reputation_router
from modules.user.router import user_router
from modules.wiki.router import wiki_router

# 구조화된 로깅 설정 (JSON in prod, human-readable in dev)
setup_logging(debug=settings.DEBUG)

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
    # Redis 연결 종료 (레이트리밋, WebSocket pusher가 사용)
    from core.utils.redis_client import close_redis

    await close_redis()
    await close_db()


app = FastAPI(
    title="Camp Linux API",
    description="Camp Linux 커뮤니티 백엔드 API 서버",
    version="1.0.0",
    lifespan=lifespan,
)

# 요청 상관 ID — 모든 로그에 request_id를 주입 (가장 바깥 미들웨어)
app.add_middleware(RequestIdMiddleware)

# 각 요청에 타임스탬프를 주입하여 request.state에서 접근 가능하게 함
app.add_middleware(TimingMiddleware)

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
app.include_router(notification_router)
app.include_router(dm_router)
app.include_router(social_auth_router)
app.include_router(draft_router)
app.include_router(package_router)
app.include_router(wiki_router)
app.include_router(reputation_router)

# 로컬 개발 전용 WebSocket 엔드포인트 (K8s WS Pod이 담당)
if settings.DEBUG:
    from routers.websocket_router import router as ws_router

    app.include_router(ws_router)

# E2E 테스트 전용 API (TESTING=true일 때만 등록)
# 이중 게이트: TESTING=true + (DEBUG=true OR CI 환경)에서만 허용
if settings.TESTING:
    if not settings.DEBUG and not os.environ.get("CI"):
        raise RuntimeError(
            "TESTING=true이지만 DEBUG=false이고 CI 환경이 아닙니다. "
            "프로덕션에서 테스트 라우터 활성화는 허용되지 않습니다."
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


@app.get("/livez", status_code=200)
async def liveness():
    """프로세스 생존 확인 — K8s liveness probe용. DB 상태와 무관."""
    return {"status": "ok"}


async def _check_readiness():
    """DB 연결 확인 공통 로직. 실패 시 503 반환."""
    from fastapi.responses import JSONResponse

    from core.database.connection import test_connection

    if await test_connection():
        return {"status": "ok", "database": "connected"}
    return JSONResponse(
        status_code=503,
        content={"status": "error", "database": "disconnected"},
    )


@app.get("/readyz", status_code=200)
async def readiness():
    """트래픽 수신 가능 여부 — K8s readiness probe용. DB 연결 실패 시 503."""
    return await _check_readiness()


@app.get("/health", status_code=200)
async def health_check():
    """하위 호환 헬스체크 — /readyz와 동일."""
    return await _check_readiness()


app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(RequestValidationError, request_validation_exception_handler)  # type: ignore[arg-type]

# K8s: Prometheus 메트릭 엔드포인트
try:
    from prometheus_fastapi_instrumentator import Instrumentator

    Instrumentator().instrument(app).expose(app)
except ImportError:
    pass  # K8s 의존성 미설치 시 무시 (로컬 개발)
