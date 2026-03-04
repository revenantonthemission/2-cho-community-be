# Phase 2: 사용자 활동 & 알림 설계 문서

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 내 활동 페이지, 알림 시스템, 이메일 인증, 타 사용자 프로필 4개 기능을 추가하여 커뮤니티 서비스의 사용자 경험을 강화한다.

**Architecture:** 기존 FastAPI(Router→Controller→Model) + Vanilla JS MVC 패턴 유지. 알림은 폴링 방식(30초), 이메일 인증은 토큰 기반, 내 활동은 기존 테이블 WHERE 조건 활용.

**Tech Stack:** FastAPI, aiomysql, Vanilla JS, MySQL ENUM, SHA-256 토큰

---

## 1. DB 스키마 변경

### 1-1. notification 테이블

```sql
CREATE TABLE notification (
    notification_id  BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id          BIGINT NOT NULL,
    type             ENUM('comment','like') NOT NULL,
    post_id          BIGINT NOT NULL,
    comment_id       BIGINT NULL,
    actor_id         BIGINT NOT NULL,
    is_read          TINYINT(1) NOT NULL DEFAULT 0,
    created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_notification_user_unread (user_id, is_read, created_at DESC),
    FOREIGN KEY (user_id) REFERENCES user(user_id),
    FOREIGN KEY (post_id) REFERENCES post(post_id),
    FOREIGN KEY (actor_id) REFERENCES user(user_id)
);
```

- 복합 인덱스 `(user_id, is_read, created_at DESC)` → 읽지 않은 알림 카운트 + 최신순 조회 커버
- `actor_id`로 "OOO님이 댓글을 남겼습니다" 메시지 구성
- 자기 행동에는 알림 미생성 (`actor_id != user_id`)
- Soft delete 불필요 — 삭제 시 물리 삭제

### 1-2. email_verification 테이블

```sql
CREATE TABLE email_verification (
    verification_id  BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id          BIGINT NOT NULL UNIQUE,
    token            VARCHAR(64) NOT NULL UNIQUE,
    expires_at       DATETIME NOT NULL,
    created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_email_verification_token (token),
    INDEX idx_email_verification_expires (expires_at),
    FOREIGN KEY (user_id) REFERENCES user(user_id)
);
```

- `user_id UNIQUE`: 사용자당 토큰 1개 (재발송 시 교체)
- SHA-256 해시 저장 (Refresh Token과 동일 패턴)

### 1-3. user 테이블 변경

```sql
ALTER TABLE user ADD COLUMN email_verified TINYINT(1) NOT NULL DEFAULT 0 AFTER email;
```

### 1-4. 내 활동 / 타 사용자 프로필용 인덱스

```sql
CREATE INDEX idx_comment_author ON comment(author_id, created_at DESC);
CREATE INDEX idx_post_like_user ON post_like(user_id, created_at DESC);
```

---

## 2. 이메일 인증 흐름

### 2-1. 회원가입 → 인증 메일 발송

1. 사용자 회원가입 (`POST /v1/users/`)
2. user 레코드 생성 (`email_verified = 0`)
3. `email_verification` 토큰 생성 (랜덤 → SHA-256 해시 DB 저장)
4. 인증 메일 발송 (기존 `utils/email.py` 활용)
   - 링크: `https://{frontend_url}/verify-email.html?token={raw_token}`
5. 응답: 201 + "인증 메일을 발송했습니다"

### 2-2. 인증 링크 클릭

1. 프론트엔드 `verify-email.html` → URL에서 token 추출
2. `POST /v1/auth/verify-email { token }`
3. 백엔드: SHA-256(token) 매칭 + expires_at 확인
4. 성공 → `user.email_verified = 1` (transactional) + email_verification 행 삭제
5. 실패 → 400 "유효하지 않거나 만료된 인증 링크입니다"

### 2-3. 인증 메일 재발송

- `POST /v1/auth/resend-verification` (로그인 필요)
- 이미 인증 시 400, 미인증 시 기존 토큰 REPLACE + 새 메일 발송

### 2-4. 쓰기 기능 제한

- **차단**: 글쓰기, 댓글, 좋아요
- **허용**: 로그인, 조회, 프로필 수정, 비밀번호 변경
- **구현**: `dependencies/auth.py`에 `require_verified_email` 의존성 추가
- **토큰 만료**: 24시간, `_periodic_token_cleanup()`에 정리 로직 추가

---

## 3. 알림 시스템

### 3-1. 알림 생성 트리거

| 이벤트 | 트리거 위치 | 수신자 |
|--------|-----------|--------|
| 댓글 작성 | `comment_controller.create_comment()` | 게시글 작성자 |
| 대댓글 작성 | `comment_controller.create_comment()` (parent_id) | 부모 댓글 작성자 |
| 좋아요 | `like_controller.toggle_like()` (추가 시만) | 게시글 작성자 |

- 자기 행동 → 알림 미생성
- 알림 생성 실패 → 원래 요청에 영향 없음 (try/except + 로깅)

### 3-2. 알림 API

```
GET    /v1/notifications?offset=0&limit=20    # 알림 목록
GET    /v1/notifications/unread-count          # 읽지 않은 수
PATCH  /v1/notifications/{id}/read             # 단건 읽음
PATCH  /v1/notifications/read-all              # 전체 읽음
DELETE /v1/notifications/{id}                  # 단건 삭제
```

### 3-3. 폴링

- `HeaderController`에서 30초 간격 `GET /v1/notifications/unread-count`
- 로그인 시만 폴링, 로그아웃 시 `clearInterval`
- 헤더 알림 아이콘에 뱃지 표시 (0이면 숨김)

### 3-4. 알림 클릭

1. `PATCH /v1/notifications/{id}/read` (읽음 처리)
2. 해당 게시글 상세 페이지로 이동

---

## 4. 내 활동 페이지

### 4-1. API

```
GET /v1/users/me/posts?offset=0&limit=10      # 내가 쓴 글
GET /v1/users/me/comments?offset=0&limit=10   # 내가 쓴 댓글
GET /v1/users/me/likes?offset=0&limit=10      # 좋아요한 글
```

### 4-2. 프론트엔드

`my-activity.html` — 탭 UI (내 글 / 내 댓글 / 좋아요한 글) + 무한 스크롤

### 4-3. 모델 계층

- 프론트: `ActivityModel.js` (3개 API 호출)
- 백엔드: `activity_models.py` (기존 쿼리에 author_id/user_id 조건)
- 서비스 계층 불필요 (단순 조회)

---

## 5. 타 사용자 프로필

### 5-1. API

- 기존 `GET /v1/users/{user_id}` 활용 (공개 정보만 반환)
- 게시글 목록: `GET /v1/posts/?author_id={user_id}` (필터 파라미터 추가)

### 5-2. 프론트엔드

`user-profile.html?id={user_id}` — 프로필 정보 + 해당 사용자 게시글 목록

- 진입: 닉네임 클릭 (게시글 목록, 상세, 댓글)
- 자기 프로필 → 기존 `user_edit.html`로 리다이렉트

---

## 6. 프론트엔드 UI 변경

### 6-1. 새 HTML 페이지

| 페이지 | 파일 | 진입 경로 |
|--------|------|----------|
| 이메일 인증 | `verify-email.html` | 인증 메일 링크 |
| 알림 목록 | `notifications.html` | 헤더 알림 아이콘 |
| 내 활동 | `my-activity.html` | 헤더 메뉴 |
| 타 사용자 프로필 | `user-profile.html` | 닉네임 클릭 |

### 6-2. 헤더 변경

- 알림 아이콘 + 읽지 않은 수 뱃지 (로그인 시만)
- 프로필 드롭다운에 "내 활동" 링크

### 6-3. 이메일 미인증 안내

- 글쓰기/댓글/좋아요 시도 시 안내 메시지 + 재발송 버튼
- `GET /v1/auth/me` 응답에 `email_verified` 필드 추가

### 6-4. 닉네임 클릭 영역

- 게시글 목록, 상세, 댓글의 닉네임 → 클릭 가능
- `user-profile.html?id={user_id}`로 이동
- 스타일: `cursor: pointer; color: #7C4DFF;`

### 6-5. 새 JS 파일

```
js/app/          verifyEmail.js, notifications.js, myActivity.js, userProfile.js
js/controllers/  VerifyEmailController.js, NotificationController.js, MyActivityController.js, UserProfileController.js
js/models/       NotificationModel.js, ActivityModel.js
js/views/        NotificationView.js, ActivityView.js, UserProfileView.js
```

### 6-6. constants.js / config.js

- `NAV_PATHS`에 새 경로 4개
- `API_ENDPOINTS`에 알림/인증 엔드포인트
