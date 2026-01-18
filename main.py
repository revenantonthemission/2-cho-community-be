from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv
from os import getenv
from routers.auth_router import auth_router
from routers.user_router import user_router
from middleware import TimingMiddleware, LoggingMiddleware
from middleware.exception_handler import global_exception_handler

# .env 로드
load_dotenv()

# FastAPI 인스턴스 생성
app = FastAPI()

# 미들웨어 추가 (역순으로 실행됨 - 마지막에 추가된 것이 먼저 실행)

# TimingMiddleware: 각 요청에 타임스탬프를 주입합니다.
app.add_middleware(TimingMiddleware)

# LoggingMiddleware: 요청/응답을 로깅합니다.
app.add_middleware(LoggingMiddleware)

# SessionMiddleware: 모든 요청과 응답에서 세션을 처리합니다.
# 프로젝트 루트에 .env 파일이 있어야 하고 그 안에 SECRET_KEY="..."가 있어야 합니다!
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

# CORSMiddleware: CORS 정책을 설정합니다.
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

# 전역 예외 핸들러 등록
app.add_exception_handler(Exception, global_exception_handler)
