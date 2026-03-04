# 계정 정지 시스템 설계

## 개요

관리자가 악의적 사용자를 기간 정지할 수 있는 시스템. 신고 처리와 연동하여 콘텐츠 삭제 + 사용자 정지를 한 번에 처리 가능.

## 결정 사항

- **정지 유형**: 기간 정지만 (영구 정지 없음)
- **콘텐츠 처리**: 정지 중에도 기존 게시글/댓글 그대로 노출
- **알림 방식**: 로그인 시 차단 + 사유/해제일 메시지
- **구현 방식**: `user` 테이블에 컬럼 추가 (별도 테이블 불필요)

## 스키마 변경

```sql
ALTER TABLE user
  ADD COLUMN suspended_until TIMESTAMP NULL AFTER role,
  ADD COLUMN suspended_reason VARCHAR(500) NULL AFTER suspended_until;

CREATE INDEX idx_user_suspended ON user (suspended_until);
```

- `suspended_until = NULL` → 정상 상태
- `suspended_until > NOW()` → 정지 중
- `suspended_until <= NOW()` → 정지 자동 해제

## User dataclass 확장

```python
@dataclass(frozen=True)
class User:
    # ... 기존 필드 ...
    suspended_until: datetime | None = None
    suspended_reason: str | None = None

    @property
    def is_suspended(self) -> bool:
        if self.suspended_until is None:
            return False
        return self.suspended_until > datetime.now(timezone.utc)
```

## 인증 체인 수정

### 로그인 시 (`auth_controller.py`)
- `suspended_until > NOW()`이면 403 반환
- 응답에 사유(`suspended_reason`)와 해제일(`suspended_until`) 포함

### 토큰 검증 시 (`dependencies/auth.py`)
- `_validate_token()`에서 `is_suspended` 체크 추가
- 이미 로그인된 세션도 차단 (JWT stateless 보완)

## API 엔드포인트

### 관리자 정지 관리
```
POST   /v1/admin/users/{user_id}/suspend   — 정지 (duration_days, reason)
DELETE /v1/admin/users/{user_id}/suspend   — 정지 해제
```

- `require_admin` 의존성 사용
- 자기 자신 정지 방지
- 다른 관리자 정지 방지

### 신고 처리 연동
- `ResolveReportRequest`에 `suspend_days` 선택 필드 추가
- `resolved` 처리 시 콘텐츠 삭제 + 작성자 정지 동시 수행

## 차단 범위

정지된 사용자가 할 수 없는 것:
- 로그인 (403 + 사유/해제일)
- 글/댓글 작성, 좋아요, 북마크, 신고 등 모든 인증 필요 행위

정지된 사용자에게 유지되는 것:
- 기존 게시글/댓글 노출
- 프로필 정보 공개

## 수정 대상 파일

### 백엔드
- `database/schema.sql` — 컬럼 추가
- `database/migration_suspension.sql` — 마이그레이션 스크립트
- `models/user_models.py` — User dataclass, `_row_to_user()`, `USER_SELECT_FIELDS`
- `models/suspension_models.py` — 정지/해제 DB 함수 (신규)
- `controllers/auth_controller.py` — 로그인 시 정지 체크
- `controllers/suspension_controller.py` — 관리자 정지/해제 (신규)
- `dependencies/auth.py` — `_validate_token()` 정지 체크
- `schemas/suspension_schemas.py` — 요청/응답 스키마 (신규)
- `schemas/report_schemas.py` — `suspend_days` 필드 추가
- `services/report_service.py` — 정지 연동
- `routers/admin_router.py` 또는 `report_router.py` — 라우트 추가
- `middleware/rate_limiter.py` — 새 엔드포인트 Rate Limit 추가
- `tests/` — 테스트 추가

### 프론트엔드
- 로그인 실패 시 정지 메시지 표시 (403 응답 핸들링)
- 관리자 신고 관리 페이지에 정지 옵션 추가

### 인프라
- `database/schema.sql` 변경 반영
