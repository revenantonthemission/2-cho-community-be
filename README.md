# 2-cho-community-be
AWS AI School 2기 3주차 과제: 커뮤니티 백엔드 서버

## 요약 (Summary)

커뮤니티 포럼 "아무 말 대잔치"를 구축합니다. FastAPI를 기반으로 하는 비동기 백엔드와 Vanilla JavaScript 프론트엔드로 구성된 모노레포 구조이며, JWT 기반 인증(Access Token + Refresh Token)과 MySQL 데이터베이스를 사용합니다. 게시글 CRUD, 댓글, 좋아요, 회원 관리 기능을 제공합니다.

## 배경 (Background)

AWS AI School 2기의 개인 프로젝트로 커뮤니티 서비스를 개발해야 합니다. 수강생들이 자유롭게 소통할 수 있는 공간이 필요하며, 실무에서 자주 사용되는 기술 스택(FastAPI, MySQL, Vanilla JS)을 학습하고 적용하는 것이 목표입니다.

기존에 별도의 커뮤니티 플랫폼이 없어 수강생 간 교류가 제한적이었습니다. 이 서비스를 통해 학습 경험을 공유하고, 질문/답변을 주고받으며, 프로젝트 협업의 기회를 마련하고자 합니다.

## 목표 (Goals)

- 회원가입, 로그인, 로그아웃, 회원 탈퇴 기능을 제공한다.
- 게시글 작성, 조회, 수정, 삭제(CRUD) 기능을 제공한다.
- 댓글 작성, 수정, 삭제 기능을 제공한다.
- 게시글 좋아요/좋아요 취소 기능을 제공한다.
- 프로필 이미지 및 닉네임 수정 기능을 제공한다.
- 무한 스크롤 기반의 게시글 목록을 제공한다.
- 모바일/데스크탑 반응형 UI를 제공한다.

## 목표가 아닌 것 (Non-Goals)

- 실시간 알림 기능 (WebSocket)
- 게시글 검색 기능
- 대댓글(nested comments) 기능
- 소셜 로그인 (OAuth)
- 이메일 인증 및 비밀번호 찾기
- 관리자 대시보드
- 게시글 카테고리 또는 태그 기능

## 계획 (Plan)

### 1. 시스템 아키텍처

```mermaid
flowchart TD
    subgraph Client["Client (Browser)"]
        FE["Vanilla JS MPA<br/>정적 파일: HTML/CSS/JS<br/>개발: npm serve :8080 | 프로덕션: S3 + CloudFront"]
    end

    Client -->|"HTTP (JSON/FormData)<br/>Bearer Token + HttpOnly Cookie"| Backend

    subgraph Backend["FastAPI Backend (Port 8000)"]
        direction LR
        Routers --> Controllers --> Services --> Models --> Pool["aiomysql Pool"]
    end

    note["Middleware: CORS → Logging → Timing → RateLimit"]

    Backend -->|"Async Connection Pool"| DB

    subgraph DB["MySQL Database"]
        Tables["user, refresh_token, post, comment,<br/>post_like, image, post_view_log"]
    end
```

### 2. 데이터베이스 설계

#### ERD

```mermaid
erDiagram
    user ||--o{ refresh_token : "has tokens"
    user ||--o{ post : "creates"
    user ||--o{ comment : "writes"
    user ||--o{ post_like : "likes"
    user ||--o{ image : "uploads"
    user ||--o{ post_view_log : "views"
    post ||--o{ comment : "has"
    post ||--o{ post_like : "receives"
    post ||--o{ post_view_log : "tracks"

    user {
        int id PK
        varchar email UK
        varchar password_hash
        varchar nickname UK
        varchar profile_image
        datetime deleted_at
        datetime created_at
    }

    refresh_token {
        int id PK
        int user_id FK
        varchar token_hash UK
        datetime expires_at
        datetime created_at
    }

    post {
        int id PK
        int author_id FK
        varchar title
        text content
        varchar image_url
        int view_count
        datetime deleted_at
        datetime created_at
    }

    comment {
        int id PK
        int post_id FK
        int author_id FK
        text content
        datetime deleted_at
        datetime created_at
    }

    post_like {
        int id PK
        int post_id FK
        int user_id FK
        datetime created_at
    }

    image {
        int id PK
        varchar image_url
        enum type
        int uploader_id FK
        datetime uploaded_at
    }

    post_view_log {
        int id PK
        int user_id FK
        int post_id FK
        date view_date
        datetime created_at
    }
```

#### 주요 설계 결정

- **Soft Delete**: `user`, `post`, `comment` 테이블에 `deleted_at` 컬럼 사용. 물리적 삭제 대신 논리적 삭제로 데이터 보존.
- **JWT 기반 인증**: Access Token(30분, HS256) + Refresh Token(7일, opaque random). Access Token은 프론트엔드 in-memory 저장, Refresh Token은 HttpOnly 쿠키로 전달하고 SHA-256 해시로 DB 저장. JWT payload에는 `sub`(user_id)만 포함하여 PII 노출 방지. 토큰 회전(rotation)으로 Refresh Token 탈취 시 자동 무효화.
- **인덱스 전략**:
  - `idx_refresh_token_hash`: Refresh Token 해시 조회
  - `idx_post_created_deleted`: 최신순 게시글 목록 조회
  - `idx_comment_post_deleted`: 게시글별 댓글 목록 조회

### 3. API 설계

#### 인증 API (`/v1/auth`)

| Method | Endpoint | 설명 | 인증 |
| ------ | -------- | ---- | ---- |
| POST | `/v1/auth/session` | 로그인 (Access Token + Refresh Token 발급) | X |
| DELETE | `/v1/auth/session` | 로그아웃 (Refresh Token 무효화) | O |
| POST | `/v1/auth/token/refresh` | 토큰 갱신 (Refresh Token → 새 Access Token) | X (쿠키) |
| GET | `/v1/auth/me` | 현재 사용자 정보 | O |

#### 사용자 API (`/v1/users`)

| Method | Endpoint | 설명 | 인증 |
| ------ | -------- | ---- | ---- |
| POST | `/v1/users` | 회원가입 | X |
| GET | `/v1/users/{user_id}` | 사용자 프로필 조회 | X |
| PATCH | `/v1/users/me` | 프로필 수정 (본인) | O |
| DELETE | `/v1/users/me` | 회원 탈퇴 (본인) | O |
| PUT | `/v1/users/me/password` | 비밀번호 변경 | O |
| POST | `/v1/users/profile/image` | 프로필 이미지 업로드 | O |

#### 게시글 API (`/v1/posts`)

| Method | Endpoint | 설명 | 인증 |
| ------ | -------- | ---- | ---- |
| GET | `/v1/posts` | 게시글 목록 (페이지네이션) | X |
| POST | `/v1/posts` | 게시글 작성 | O |
| GET | `/v1/posts/{post_id}` | 게시글 상세 조회 | X |
| PATCH | `/v1/posts/{post_id}` | 게시글 수정 | O (작성자) |
| DELETE | `/v1/posts/{post_id}` | 게시글 삭제 | O (작성자) |
| POST | `/v1/posts/{post_id}/likes` | 좋아요 | O |
| DELETE | `/v1/posts/{post_id}/likes` | 좋아요 취소 | O |
| POST | `/v1/posts/{post_id}/comments` | 댓글 작성 | O |
| PUT | `/v1/posts/{post_id}/comments/{comment_id}` | 댓글 수정 | O (작성자) |
| DELETE | `/v1/posts/{post_id}/comments/{comment_id}` | 댓글 삭제 | O (작성자) |
| POST | `/v1/posts/image` | 게시글 이미지 업로드 | O |

#### 응답 형식

```json
{
  "code": 200,
  "message": "성공",
  "data": { },
  "errors": null,
  "timestamp": "2024-01-01T00:00:00Z"
}
```

#### 에러 코드

| HTTP Status | 설명 |
| ----------- | ---- |
| 400 | 잘못된 요청 (유효성 검사 실패) |
| 401 | 인증 필요 (토큰 만료/미로그인) |
| 403 | 권한 없음 (타인의 게시글 수정 시도 등) |
| 404 | 리소스 없음 |
| 409 | 충돌 (이메일/닉네임 중복) |
| 500 | 서버 오류 |

### 4. 인증 흐름

```mermaid
sequenceDiagram
    participant Client
    participant Server as FastAPI Server
    participant MySQL

    rect rgb(240, 248, 255)
        Note over Client,MySQL: 로그인 절차
        Client->>Server: POST /v1/auth/session<br/>{email, password}
        Server->>MySQL: SELECT user WHERE email
        MySQL-->>Server: user data
        Server->>Server: bcrypt.verify(password)
        Server->>Server: JWT Access Token 생성 (30분)
        Server->>Server: Refresh Token 생성 (opaque random)
        Server->>MySQL: INSERT refresh_token (SHA-256 hash)
        MySQL-->>Server: token stored
        Server-->>Client: {access_token} + Set-Cookie: refresh_token (HttpOnly)
    end

    rect rgb(255, 248, 240)
        Note over Client,MySQL: 인증된 요청
        Client->>Server: GET /v1/posts<br/>Authorization: Bearer {access_token}
        Server->>Server: JWT 디코딩 + 검증 (stateless)
        Server->>MySQL: SELECT user WHERE id = sub
        MySQL-->>Server: user data
        Server-->>Client: 200 OK + posts data
    end

    rect rgb(240, 255, 240)
        Note over Client,MySQL: 토큰 갱신 (Access Token 만료 시)
        Client->>Server: POST /v1/auth/token/refresh<br/>Cookie: refresh_token
        Server->>MySQL: SELECT refresh_token WHERE hash
        MySQL-->>Server: token record
        Server->>Server: 새 Access Token + Refresh Token 생성
        Server->>MySQL: DELETE old + INSERT new (atomic rotation)
        Server-->>Client: {new_access_token} + Set-Cookie: new_refresh_token
    end
```

### 5. 프론트엔드 아키텍처

#### 디렉토리 구조

```text
2-cho-community-fe/
├── html/                    # 8개 정적 HTML 페이지
│   ├── post_list.html       # 메인 피드
│   ├── post_detail.html     # 게시글 상세
│   ├── post_write.html      # 게시글 작성
│   ├── post_edit.html       # 게시글 수정
│   ├── user_login.html      # 로그인
│   ├── user_signup.html     # 회원가입
│   ├── user_password.html   # 비밀번호 변경
│   └── user_edit.html       # 프로필 수정
│
├── js/
│   ├── app/                 # 페이지별 진입점
│   ├── controllers/         # 비즈니스 로직
│   ├── models/              # API 통신 계층
│   ├── views/               # DOM 렌더링
│   ├── services/            # ApiService (HTTP 클라이언트)
│   ├── utils/               # Logger, Validators, Formatters
│   ├── config.js            # API_BASE_URL
│   └── constants.js         # 엔드포인트, 메시지, 라우트
│
└── css/
    ├── style.css            # 마스터 import
    ├── base.css             # 리셋, 타이포그래피
    ├── layout.css           # 헤더, 컨테이너
    ├── modules/             # 재사용 컴포넌트 (버튼, 폼, 카드, 모달, 토스트)
    └── pages/               # 페이지별 스타일
```

#### MVC 패턴

- **Model**: API 호출 담당. `AuthModel`, `PostModel`, `UserModel`, `CommentModel`
- **View**: DOM 렌더링. 정적 메서드로 HTML 생성 및 이벤트 바인딩
- **Controller**: 비즈니스 로직. Model과 View 조정, 상태 관리

#### 주요 패턴

- **정적 메서드**: 모든 클래스가 static 메서드만 사용
- **IntersectionObserver**: 무한 스크롤 구현
- **Custom Event**: `auth:session-expired` 이벤트로 401 처리 (silent refresh 실패 시 발생)
- **XSS 방지**: `escapeHtml()` 유틸리티로 사용자 입력 이스케이프

### 6. 보안 고려사항

| 항목 | 구현 방식 |
| ---- | --------- |
| 비밀번호 해싱 | bcrypt (cost factor 기본값) |
| JWT 인증 | Access Token(30분, in-memory) + Refresh Token(7일, HttpOnly Cookie, SHA-256 해시 DB 저장) |
| CORS | 허용 출처 명시적 설정 (localhost:8080) |
| SQL Injection | Parameterized queries (aiomysql) |
| XSS | 프론트엔드에서 escapeHtml() 적용 |
| Timing Attack | 로그인 시 존재하지 않는 사용자도 bcrypt 검증 수행 |

### 7. 비밀번호 정책

- 길이: 8-20자
- 필수 포함: 대문자, 소문자, 숫자, 특수문자

## 이외 고려 사항들 (Other Considerations)

- **JWT 인증**: Access Token(HS256, 30분) + Refresh Token(opaque random, 7일) 이중 토큰 전략 사용. Access Token은 프론트엔드 in-memory(JS 변수)에 저장하여 XSS 노출 최소화, Refresh Token은 HttpOnly 쿠키로 전달하고 SHA-256 해시로 DB에 저장. 토큰 회전(rotation)을 통해 Refresh Token 탈취 시 자동 무효화. CSRF 미들웨어는 제거됨 (Bearer 토큰이 CSRF 방어 역할).
- **ORM vs Raw SQL**: SQLAlchemy 등 ORM 사용을 고려했으나, 학습 목적으로 raw SQL을 직접 작성하여 쿼리 최적화 경험을 쌓기로 결정.
- **Vanilla JS**: React, Vue 등 프레임워크 대신 Vanilla JS를 선택. 프레임워크 학습 비용 없이 JavaScript 기본기를 다지는 것이 목표.
- **이미지 저장소**: 프로덕션에서는 EFS(`/mnt/uploads`)에 저장. 로컬 개발 시에도 로컬 파일시스템 사용.
- **Soft Delete**: 물리적 삭제 대신 `deleted_at` 컬럼 사용. 데이터 복구 가능성 확보 및 FK 무결성 유지.

## 마일스톤 (Milestones)

| 단계 | 기간 | 내용 |
| ---- | ---- | ---- |
| 1단계 | 1주차 | DB 스키마 설계, 백엔드 프로젝트 셋업, 인증 API 구현 |
| 2단계 | 2주차 | 게시글/댓글/좋아요 API 구현, 이미지 업로드 |
| 3단계 | 3주차 | 프론트엔드 구현 (HTML/CSS/JS), API 연동 |
| 4단계 | 4주차 | E2E 테스트 작성, QA, 버그 수정 |
| 5단계 | 5주차 | 문서화, 코드 리뷰, 최종 배포 |

## Changelog

### 2026-02 (Feb)

- **02-28: 보안 취약점 5건 수정 (Critical)**
  - Path Traversal 방지: `delete_file()`에 `Path.resolve()` + 경계 검사 추가
  - SSRF 방지: `image_url` 필드에 `/uploads/` 프리픽스 강제 (외부 URL 차단)
  - Lambda 시크릿: 평문 환경변수 → SSM Parameter Store SecureString 조회 (`_resolve_ssm_secrets()`)

- **02-27: GitHub Actions CD 파이프라인 구축**
  - `deploy-backend.yml`: `workflow_dispatch` → Docker build → ECR push (SHA + latest) → Lambda update
  - OIDC 인증 (GitHub → AWS IAM Role), 환경 선택 (dev/staging/prod)
  - `--provenance=false` 필수, `aws lambda wait function-updated`로 배포 완료 대기

- **02-26: AWS 인프라 Terraform 구축 및 배포**
  - 14개 Terraform 모듈 구성 및 dev 환경 전체 배포
  - CloudFront CDN + HTTPS + Clean URL (CloudFront Functions)
  - Lambda 컨테이너 (Python 3.13/AL2023), EFS, RDS, API Gateway, EC2 bastion
  - 앱 코드에서 AWS 하드코딩 제거, 로컬 개발 환경 정리

- **02-25: JWT 인증 전환 + 보안 강화**
  - 세션 기반 → JWT (Access Token 30분 + Refresh Token 7일, 토큰 회전)
  - JWT payload 최소화: PII 제거, `sub`(user_id)만 유지
  - ProxyHeadersMiddleware 보안 수정, GitHub Actions CI 구축

- **02-09 ~ 12: CSRF 보호 + 코드 품질 + 프론트엔드 환경 개선**
  - Double Submit Cookie 패턴 CSRF 방어 (JWT 전환 후 제거)
  - 크리티컬 버그 수정: `update_post()` params 순서, 트랜잭션 원자성
  - SQL Injection 방어: 동적 쿼리 whitelist 검증
  - 프론트엔드 npm serve 마이그레이션 (Port 8080)

- **02-02 ~ 05: 아키텍처 리팩토링**
  - Service Layer 도입 (`post_service`, `user_service`)
  - Rate Limiter 미들웨어 (IP 기반 브루트포스 방지)
  - 단위 테스트 도입 (커버리지 85%), DB 격리 수준 READ COMMITTED
  - 코드 리뷰 기반 보안/코드 품질 전면 개선

### 2026-01 (Jan)

- **01-28 ~ 30: 데이터베이스 연동 + 보안 강화**
  - MySQL + aiomysql 커넥션 풀, 트랜잭션 적용
  - bcrypt 비밀번호 해싱, 세션 보안 강화
  - 조회수/무한 스크롤/이미지 업로드 버그 수정
  - 좋아요/댓글 모델 분리, 코드 중복 제거

- **01-19 ~ 26: 게시글 API + 프론트엔드 연결**
  - 게시글 CRUD, 좋아요, 댓글 API 완성
  - CORS 설정, 프론트엔드 서버 연결
  - Pydantic 스키마, 미들웨어(로깅/타이밍/예외처리) 도입

- **01-12 ~ 17: 초기 구현**
  - router-controller-model 아키텍처 구현
  - 회원가입/로그인/로그아웃 (세션 기반)
  - 회원 CRUD API (프로필, 비밀번호 변경, 탈퇴)
