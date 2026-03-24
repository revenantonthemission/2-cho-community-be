"""auth_service: 인증 관련 비즈니스 로직을 처리하는 서비스.

JWT 기반 로그인, 로그아웃, 토큰 갱신의 핵심 비즈니스 로직을 담당합니다.
HTTP 관련 처리(쿠키, Request/Response)는 컨트롤러에 위임합니다.
"""

import asyncio
import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import bcrypt
from fastapi import HTTPException, status

from core.config import settings
from core.utils.jwt_utils import create_access_token, create_refresh_token, hash_refresh_token
from core.utils.password import verify_password
from modules.auth import token_models
from modules.user import models as user_models
from modules.user.models import User

logger = logging.getLogger(__name__)

# 타이밍 공격 방지: 존재하지 않는 사용자에 대해서도 bcrypt 비교를 수행하여 응답 시간 차이로
# 사용자 존재 여부가 노출되지 않도록 함
# 시작 시 랜덤 더미 해시 생성 — 공개된 해시값 사용 방지
_TIMING_ATTACK_DUMMY_HASH = bcrypt.hashpw(secrets.token_hex(16).encode(), bcrypt.gensalt()).decode()


@dataclass
class AuthResult:
    """인증 결과를 담는 데이터 클래스."""

    access_token: str
    raw_refresh_token: str
    user: User


class AuthService:
    """인증 비즈니스 로직 서비스."""

    @staticmethod
    async def authenticate(email: str, password: str, timestamp: str) -> AuthResult:
        """이메일과 비밀번호로 사용자를 인증하고 토큰을 발급합니다.

        타이밍 공격 방지를 위해 사용자가 존재하지 않아도 bcrypt 비교를 수행합니다.

        Args:
            email: 사용자 이메일.
            password: 사용자 비밀번호.
            timestamp: 요청 타임스탬프.

        Returns:
            AuthResult: access_token, raw_refresh_token, user를 포함하는 결과.

        Raises:
            HTTPException 401: 인증 실패 시.
            HTTPException 403: 계정 정지 시.
        """
        user = await user_models.get_user_by_email(email)

        # 소셜 전용 계정(password=NULL): 타이밍 공격 방지 후 안내 메시지 반환
        if user and user.password is None:
            await asyncio.to_thread(verify_password, password, _TIMING_ATTACK_DUMMY_HASH)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "social_only_account",
                    "message": "소셜 로그인으로 가입된 계정입니다. 소셜 로그인을 이용해주세요.",
                    "timestamp": timestamp,
                },
            )

        password_valid = await asyncio.to_thread(
            verify_password,
            password,
            (user.password or _TIMING_ATTACK_DUMMY_HASH) if user else _TIMING_ATTACK_DUMMY_HASH,
        )

        if not user or not password_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": "unauthorized",
                    "timestamp": timestamp,
                },
            )

        # 정지된 사용자 로그인 차단
        if user.is_suspended:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "account_suspended",
                    "message": "계정이 정지되었습니다.",
                    "suspended_until": user.suspended_until.strftime("%Y-%m-%dT%H:%M:%SZ")
                    if user.suspended_until
                    else None,
                    "suspended_reason": user.suspended_reason,
                    "timestamp": timestamp,
                },
            )

        access_token = create_access_token(user_id=user.id)

        raw_refresh = create_refresh_token()
        expires_at = datetime.now(UTC) + timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS)
        await token_models.create_refresh_token(user.id, raw_refresh, expires_at)

        return AuthResult(
            access_token=access_token,
            raw_refresh_token=raw_refresh,
            user=user,
        )

    @staticmethod
    async def refresh_access_token(refresh_token_value: str, timestamp: str) -> AuthResult:
        """리프레시 토큰을 검증하고 회전(rotate)하여 새 토큰 쌍을 발급합니다.

        토큰 회전: DELETE + INSERT를 단일 트랜잭션으로 묶어 원자성 보장.

        Args:
            refresh_token_value: 현재 리프레시 토큰 값.
            timestamp: 요청 타임스탬프.

        Returns:
            AuthResult: 새 access_token, raw_refresh_token, user를 포함하는 결과.

        Raises:
            HTTPException 401: 토큰이 유효하지 않거나 사용자가 존재하지 않는 경우.
            HTTPException 403: 계정 정지 시.

        Note:
            토큰이 유효하지 않은 경우 None을 반환하지 않고 예외를 발생시킵니다.
            컨트롤러에서 쿠키 삭제가 필요한 경우를 구분하기 위해,
            쿠키 삭제가 필요한 실패 케이스에서 HTTPException을 발생시킵니다.
        """
        # 만료된 토큰이면 내부에서 삭제 후 None 반환
        token_record = await token_models.get_refresh_token(refresh_token_value)
        if not token_record:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "refresh_token_invalid", "timestamp": timestamp},
            )

        user = await user_models.get_user_by_id(token_record["user_id"])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "unauthorized", "timestamp": timestamp},
            )

        # 정지된 사용자 토큰 갱신 차단
        if user.is_suspended:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "account_suspended",
                    "message": "계정이 정지되었습니다.",
                    "suspended_until": user.suspended_until.strftime("%Y-%m-%dT%H:%M:%SZ")
                    if user.suspended_until
                    else None,
                    "suspended_reason": user.suspended_reason,
                    "timestamp": timestamp,
                },
            )

        # 토큰 원자적 회전: SELECT FOR UPDATE + DELETE + INSERT를 단일 트랜잭션으로 묶어
        # 동시 갱신 요청이 모두 성공하는 팬아웃(fan-out)을 방지
        new_access_token = create_access_token(user_id=user.id)
        new_raw_refresh = create_refresh_token()
        new_expires_at = datetime.now(UTC) + timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS)
        rotated = await token_models.atomic_rotate_refresh_token(
            old_token_hash=hash_refresh_token(refresh_token_value),
            user_id=user.id,
            new_token_hash=hash_refresh_token(new_raw_refresh),
            new_expires_at=new_expires_at,
        )
        if not rotated:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "refresh_token_invalid", "timestamp": timestamp},
            )

        return AuthResult(
            access_token=new_access_token,
            raw_refresh_token=new_raw_refresh,
            user=user,
        )

    @staticmethod
    async def logout(refresh_token_value: str | None) -> None:
        """리프레시 토큰을 삭제하여 로그아웃 처리합니다.

        Args:
            refresh_token_value: 삭제할 리프레시 토큰 값. None이면 무시.
        """
        if refresh_token_value:
            await token_models.delete_refresh_token(refresh_token_value)
