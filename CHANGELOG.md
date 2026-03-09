# Changelog

## 2026-03 (Mar)

- **03-09: EventBridge 배치 작업 전환 — 수평 확장 대응**
  - `main.py`의 인프로세스 배치 작업(토큰 정리, 피드 점수 재계산) 제거 → EventBridge 스케줄 기반으로 전환
  - 내부 API 인증: `X-Internal-Key` 헤더 기반 `require_internal` / `require_admin_or_internal` 이중 인증
  - 새 엔드포인트: `POST /v1/admin/cleanup/tokens` (만료 Refresh Token + 이메일 인증 토큰 일괄 삭제)
  - `POST /v1/admin/feed/recompute` 관리자 전용 → 관리자 + 내부 키 이중 인증으로 변경
  - `INTERNAL_API_KEY` SSM Parameter Store 통합 (`_resolve_ssm_secrets()` 확장)
  - 테스트: 8 cases (내부 키 인증 + 엔드포인트)

- **03-09: 분산 Rate Limiter (DynamoDB)**
  - Rate Limiter를 프로토콜 기반으로 리팩토링 (`RateLimiterProtocol` → `MemoryRateLimiter` / `DynamoDBRateLimiter`)
  - DynamoDB Fixed Window Counter: 수평 확장된 Lambda 인스턴스 간 rate limit 상태 공유
  - fail-open 정책: DynamoDB 장애 시 요청 허용 (가용성 우선)
  - 팩토리 패턴: `RATE_LIMIT_BACKEND` 설정으로 백엔드 선택 (`memory` / `dynamodb`)
  - 테스트: 15 cases (메모리 9 + DynamoDB 6)

- **03-09: 추천 피드(For You Feed) — 개인화 정렬**
  - 사용자 친화도 기반 개인화 추천: 7개 신호(좋아요/북마크/댓글 태그, 조회 카테고리, 팔로우/좋아요/북마크 작성자)
  - 아키텍처: `affinity_models.py`(SQL) → `affinity_scorer.py`(순수 Python) → `feed_service.py`(배치)
  - DB: `user_post_score` 테이블, 30분 주기 배치 갱신 (Lambda: 관리자 엔드포인트로 외부 트리거)
  - `GET /v1/posts/?sort=for_you` + `POST /v1/admin/feed/recompute` (관리자 전용)
  - 콜드 스타트 폴백, 다양성 필터 (작성자당 최대 3개), 기존 필터와 자유 조합
  - 테스트: 22 cases, 전체 303 passed

- **03-09: 팔로잉 피드 + 연관 게시글 추천**
  - 팔로잉 피드: `GET /v1/posts?following=true` — 팔로우한 사용자의 게시글만 필터링
  - 연관 게시글: `GET /v1/posts/{id}/related?limit=5` — 태그 매칭 + 카테고리 + hot score 기반 추천
  - 팔로우 Rate Limit 보강: `POST/DELETE /v1/users/{id}/follow` (10 req/60s)
  - 연관 게시글 Rate Limit: `GET /v1/posts/{id}/related` (30 req/60s)

- **03-08: DM 쪽지 시스템**
  - DB: `dm_conversation` + `dm_message` 테이블, 참가자 MIN/MAX 정규화, UNIQUE 제약
  - API: 대화 목록/생성/삭제, 메시지 전송/조회, 읽음 처리, 읽지 않은 수
  - WebSocket `type: "dm"` 실시간 푸시 통합, 차단 사용자 간 대화 403
  - 테스트: 14개, 전체 270 passed, 87% coverage

- **03-08: 실시간 알림 (WebSocket) — 백엔드**
  - WebSocket Lambda 핸들러: `websocket/` 패키지 (`handler.py`, `dynamo.py`, `auth.py`)
  - WebSocket Pusher: `utils/websocket_pusher.py` — DynamoDB 조회 → API GW Management API 전송 (best-effort)
  - 알림 생성 시 실시간 푸시 통합: `notification_models.create_notification()` → `push_to_user()`
  - 로컬 개발 WebSocket: `routers/websocket_router.py` (DEBUG 전용, 인메모리 연결 관리)
  - 테스트: 22개 (handler + pusher), 전체 256 passed, 86% coverage

- **03-06: 투표(Poll) 시스템**
  - DB: `poll`, `poll_option`, `poll_vote` 테이블, `migration_polls.sql` 마이그레이션
  - 게시글 생성 시 투표 동시 생성 (`CreatePostRequest.poll` 필드, 옵션 2~10개, 만료일 선택)
  - 투표 참여 API: `POST /v1/posts/{id}/poll/vote` (중복 투표 409, 만료 400)
  - 게시글 상세에 투표 데이터 포함 (옵션별 득표수, 총 투표수, 내 투표, 만료 여부)
  - 테스트: 9개 테스트

- **03-06: 관리자 대시보드**
  - 대시보드 요약 API: `GET /v1/admin/dashboard` (총 사용자/게시글/댓글, 오늘 가입자)
  - 일별 통계 API: 30일간 가입자/게시글/댓글 수 추이
  - 사용자 관리 API: `GET /v1/admin/users` (검색, 페이지네이션)
  - 테스트: 5개 테스트

- **03-06: 팔로우/팔로잉 시스템**
  - DB: `user_follow` 테이블, `notification.type` ENUM에 `follow` 추가
  - 팔로우/언팔로우 API: `POST/DELETE /v1/users/{id}/follow` (자기 자신/중복 방지)
  - 내 팔로워/팔로잉 목록: `GET /v1/users/me/followers`, `/me/following`
  - 프로필에 팔로워/팔로잉 수 + 팔로우 여부 표시
  - 팔로우한 사용자의 새 게시글 작성 시 팔로워에게 알림 발송
  - 테스트: 12개 테스트

- **03-06: 태그 시스템**
  - DB: `tag`(이름 UNIQUE) + `post_tag`(다대다) 테이블, `migration_tags.sql` 마이그레이션
  - API: 게시글 생성/수정에 `tags[]` 배열 추가 (최대 5개, 소문자 정규화, 자동 생성)
  - 태그 검색: `GET /v1/tags?search=키워드` (상위 10개, post_count 포함)
  - 태그 필터: `GET /v1/posts?tag=태그명` (해당 태그가 달린 게시글 필터링)
  - 테스트: 12개 테스트 (CRUD, 정규화, 검색, 필터링, 제한)

- **03-06: 읽은 게시글 표시**
  - `post_view_log` 테이블 재활용, `get_read_post_ids()` 벌크 조회 (N+1 방지)
  - 게시글 목록 응답에 `is_read: bool` 필드 추가 (비로그인 시 항상 false)
  - 테스트: 3개 테스트 (미읽음, 조회 후 읽음, 비로그인)

- **03-05: @멘션 알림**
  - 댓글 @닉네임 파싱 → 사용자 조회 → 멘션 알림 생성
  - `notification.type` ENUM에 `mention` 추가
  - 자기 자신/중복 알림 방지 (`already_notified` set)
  - 테스트: 11개 테스트

- **03-04: 계정 정지 시스템 (관리자 전용)**
  - DB: `user.suspended_until` TIMESTAMP + `suspended_reason` VARCHAR(500), `idx_user_suspended` 인덱스
  - 인증 차단: `_validate_token()`(403), `login()`(403), `refresh_token()`(403) 3중 체크. 자동 만료 (배치 작업 불필요)
  - 관리자 API: `POST /v1/admin/users/{id}/suspend` (1~365일 기간 정지), `DELETE /v1/admin/users/{id}/suspend` (정지 해제)
  - 신고 연동: `ResolveReportRequest.suspend_days` 옵션으로 신고 처리 시 작성자 동시 정지. 비원자적 트랜잭션 — 정지 실패 시 로깅
  - 테스트: 17개 테스트 (인증 차단, 만료 허용, 신고 연동, 입력 검증, 비정지 사용자 해제 방지)

- **03-03: Blue/Green Deployment (Lambda Alias 기반)**
  - CD 파이프라인: `--publish`로 Lambda 버전 발행 → `/health` 직접 호출 health check → `live` alias 전환
  - 롤백 워크플로우: `rollback-backend.yml` 신규 — 수동 트리거로 이전 Lambda 버전 즉시 전환
  - 보안 강화: 입력값 sanitization (env var 패턴), 동시 배포 방지 (`concurrency`), `create-alias` 폴백

- **03-02: 북마크, 댓글 좋아요, 공유, 다중 이미지, 사용자 차단, 인기 게시글**
  - 북마크: `post_bookmark` 테이블, 게시글 북마크 추가/해제 API, 내 북마크 목록, 상세 `bookmarks_count`+`is_bookmarked`
  - 댓글 좋아요: `comment_like` 테이블, 댓글별 좋아요/취소 API, 트리에 `likes_count`+`is_liked`, 벌크 조회로 N+1 방지
  - 사용자 차단: `user_block` 테이블, 차단/해제 API, 게시글 SQL 필터(`NOT IN`), 댓글 Python 후처리 필터
  - 다중 이미지: `post_image` 테이블(`sort_order`), 최대 5개, `image_urls`↔`image_url` 하위 호환, 마이그레이션 스크립트
  - 인기 게시글: `hot` 정렬 옵션, `(likes*3+comments*2+views*0.5)/POW(hours+2,1.5)` 가중치 수식

- **03-02: 관리자 역할, 신고 시스템, 카테고리, 게시글 고정**
  - 관리자 역할: `user.role` ENUM 컬럼, `require_admin` 의존성, 관리자 게시글/댓글 삭제 권한
  - 카테고리: `category` 테이블 (4종 시드), `post.category_id` FK, 카테고리별 게시글 필터링
  - 신고: `report` 테이블 (UNIQUE 중복 방지), 자기 콘텐츠 신고 방지, 관리자 처리(resolved→삭제/dismissed→유지)
  - 게시글 고정: `post.is_pinned` 플래그, 관리자 전용 PIN/UNPIN API, 목록 상단 표시

- **03-02: 이메일 인증, 알림, 내 활동, 사용자 프로필**
  - 이메일 인증: `email_verification` 테이블, 토큰 기반 인증 흐름, `require_verified_email` 가드 (게시글/댓글 쓰기)
  - 알림 시스템: `notification` 테이블, 좋아요/댓글 트리거, CRUD API, 읽음 처리
  - 내 활동: 내가 쓴 글/댓글/좋아요한 글 조회 API (`/v1/users/me/posts|comments|likes`)
  - 사용자 프로필: 공개 프로필 조회 (이메일 제외), `author_id` 필터로 게시글 목록 조회

- **03-02: 검색, 정렬, 대댓글 기능**
  - 게시글 검색: FULLTEXT INDEX(ngram parser)로 제목+내용 한국어 검색, 특수문자 이스케이프, BOOLEAN MODE
  - 게시글 정렬: 최신순/좋아요순/조회수순/댓글순 4종, `ALLOWED_SORT_OPTIONS` 화이트리스트로 SQL 주입 방지
  - 대댓글(1단계): `comment.parent_id` 자기참조 FK, 앱 레벨 O(n) 트리 구성, 삭제된 부모 플레이스홀더 표시

- **03-01: Locust 부하 테스트 구축**
  - 3종 사용자 시나리오: ReaderUser(60%), WriterUser(20%), ActiveUser(20%)
  - 계정 풀(`queue.Queue` 싱글턴)로 동시 사용자 간 계정 1:1 바인딩, Refresh Token 충돌 방지
  - Rate Limit 준수 설계: 로그인 1회/세션, WriterUser 대기 8-20초, 429 시 `gevent.sleep(65s)` 재시도
  - AWS 배포 환경 대상 (API Gateway → Lambda → RDS), 동시 50-200명 규모
  - `seed_accounts.py`: API/DB 이중 모드 계정 시딩 (회원가입 API 또는 직접 DB 접속)

## 2026-02 (Feb)

- **02-28: 계정 찾기 기능 (이메일 찾기 + 비밀번호 재설정)**
  - 이메일 찾기: 닉네임으로 마스킹된 이메일 조회 (`POST /v1/users/find-email`)
  - 비밀번호 재설정: 임시 비밀번호 생성 후 이메일 발송 (`POST /v1/users/reset-password`)
  - 이메일 발송 이중 지원: SES(프로덕션) + SMTP(로컬 개발), `asyncio.to_thread()`로 비동기 처리
  - 보안: 정보 열거 방지(존재 여부 무관 동일 응답), 타이밍 공격 방지(더미 bcrypt), Rate Limiting(5/5분, 3/5분)

- **02-28: 코드 리뷰 기반 보안 강화 + 버그 수정**
  - 보안 취약점: Path Traversal(`Path.is_relative_to()`), SSRF(`/uploads/` 프리픽스 강제), 이미지 URL 검증 공통 헬퍼(`_image_validators.py`)
  - 토큰·시크릿: `SELECT ... FOR UPDATE`(replay attack 방지), Lambda 시크릿 SSM SecureString 전환(`get_parameters` 배치 API)
  - 안정성: `transactional()` 일관성 통일, Rate limiter 키 동기화, IntegrityError 처리 개선

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

## 2026-01 (Jan)

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
