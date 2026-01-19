"""main: FastAPI 애플리케이션의 메인 진입점.

애플리케이션 설정, 미들웨어 구성, 라우터 등록, 전역 예외 핸들러를 설정합니다.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv
from os import getenv
from routers.auth_router import auth_router
from routers.user_router import user_router
from routers.post_router import post_router
from routers.terms_router import terms_router
from middleware import TimingMiddleware, LoggingMiddleware
from middleware.exception_handler import global_exception_handler


# .env 로드
load_dotenv()

# FastAPI 인스턴스 생성
app = FastAPI(
    title="2cho Community API",
    description="커뮤니티 백엔드 API 서버",
    version="1.0.0",
)
"""FastAPI 애플리케이션 인스턴스."""

# 미들웨어 추가

# TimingMiddleware: 각 요청에 타임스탬프를 주입
app.add_middleware(TimingMiddleware)

# LoggingMiddleware: 요청/응답을 로깅
app.add_middleware(LoggingMiddleware)

# SessionMiddleware: 모든 요청과 응답에서 세션을 처리
# 프로젝트 루트에 .env 파일이 있어야 하고 그 안에 SECRET_KEY="..."가 있어야 함
app.add_middleware(
    SessionMiddleware,
    secret_key=getenv("SECRET_KEY"),
    max_age=24 * 60 * 60,
    same_site="lax",
    https_only=False,
)

# 허용된 origin 목록
origins = [
    "http://localhost",
    "http://localhost:8000",
]

# CORSMiddleware: CORS 정책을 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 추가
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(post_router)
app.include_router(terms_router)

# 전역 예외 핸들러 등록
app.add_exception_handler(Exception, global_exception_handler)
