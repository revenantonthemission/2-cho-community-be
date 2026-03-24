"""E2E 테스트 전용 API.

TESTING=true 환경에서만 main.py에 등록됩니다.
프로덕션 환경에서는 이 라우터가 등록되지 않아 엔드포인트 자체가 존재하지 않습니다.
"""


# 보안: TESTING=true 없이는 이 모듈이 import되지 않음 (main.py 조건부 import)
# 추가 방어는 main.py에서 TESTING + DEBUG 이중 체크로 처리

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from core.database.connection import get_connection, transactional

test_router = APIRouter(prefix="/v1/test", tags=["test"])


class FindUserRequest(BaseModel):
    email: str


class VerifyEmailRequest(BaseModel):
    user_id: int


class SetRoleRequest(BaseModel):
    user_id: int
    role: Literal["user", "admin"] = "admin"


class SuspendRequest(BaseModel):
    user_id: int
    duration_days: int = 7
    reason: str = "테스트 정지"


class UnsuspendRequest(BaseModel):
    user_id: int


@test_router.post("/users/find")
async def find_user(req: FindUserRequest):
    """이메일로 사용자 ID 조회"""
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id FROM user WHERE email = %s AND deleted_at IS NULL",
            (req.email,),
        )
        row = await cur.fetchone()
    if not row:
        return {"code": "USER_NOT_FOUND", "data": None}
    return {"code": "USER_FOUND", "data": {"user_id": row[0]}}


@test_router.post("/users/verify-email")
async def verify_email(req: VerifyEmailRequest):
    """이메일 인증 바이패스"""
    async with transactional() as cur:
        await cur.execute(
            "UPDATE user SET email_verified = 1 WHERE id = %s",
            (req.user_id,),
        )
    return {"code": "EMAIL_VERIFIED", "data": {"user_id": req.user_id}}


@test_router.post("/users/set-role")
async def set_role(req: SetRoleRequest):
    """사용자 역할 변경 (admin 등)"""
    async with transactional() as cur:
        await cur.execute(
            "UPDATE user SET role = %s WHERE id = %s",
            (req.role, req.user_id),
        )
    return {"code": "ROLE_UPDATED", "data": {"user_id": req.user_id, "role": req.role}}


@test_router.post("/users/suspend")
async def suspend_user(req: SuspendRequest):
    """사용자 정지"""
    async with transactional() as cur:
        await cur.execute(
            "UPDATE user SET suspended_until = DATE_ADD(NOW(), INTERVAL %s DAY), suspended_reason = %s WHERE id = %s",
            (req.duration_days, req.reason, req.user_id),
        )
    return {"code": "USER_SUSPENDED", "data": {"user_id": req.user_id}}


@test_router.delete("/users/suspend")
async def unsuspend_user(req: UnsuspendRequest):
    """사용자 정지 해제"""
    async with transactional() as cur:
        await cur.execute(
            "UPDATE user SET suspended_until = NULL, suspended_reason = NULL WHERE id = %s",
            (req.user_id,),
        )
    return {"code": "USER_UNSUSPENDED", "data": {"user_id": req.user_id}}


@test_router.post("/cleanup")
async def cleanup_database():
    """테스트 데이터 정리 (31개 테이블 TRUNCATE + 카테고리 시드)"""
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute("SET FOREIGN_KEY_CHECKS = 0")
        tables = [
            "package_review",
            "package",
            "user_post_score",
            "dm_message",
            "dm_conversation",
            "post_tag",
            "tag",
            "comment_like",
            "post_bookmark",
            "notification",
            "report",
            "post_view_log",
            "post_image",
            "image",
            "poll_vote",
            "poll_option",
            "poll",
            "user_block",
            "user_follow",
            "comment",
            "post_like",
            "post",
            "refresh_token",
            "email_verification",
            "category",
            "user",
        ]
        for table in tables:
            await cur.execute(f"TRUNCATE TABLE {table}")
        await cur.execute("SET FOREIGN_KEY_CHECKS = 1")
        await cur.execute(
            "INSERT INTO category (name, slug, description, sort_order) VALUES "
            "('배포판', 'distro', 'Ubuntu, Fedora, Arch 등 배포판별 토론 공간입니다.', 1), "
            "('Q&A', 'qna', '리눅스 트러블슈팅, 설치, 설정 관련 질문과 답변입니다.', 2), "
            "('뉴스/소식', 'news', '리눅스 생태계의 최신 소식을 공유합니다.', 3), "
            "('프로젝트/쇼케이스', 'showcase', 'dotfiles, 스크립트, 오픈소스 기여를 공유합니다.', 4), "
            "('팁/가이드', 'guide', '리눅스 튜토리얼과 How-to 가이드입니다.', 5), "
            "('공지사항', 'notice', '관리자 공지사항입니다.', 6)"
        )
        await conn.commit()
    return {"code": "DATABASE_CLEANED"}
