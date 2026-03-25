# Changelog

## 2026-03 (Mar)

- feat: Alembic 마이그레이션 관리 도입 — 버전 관리 + 롤백, K8s PreSync Job 자동 실행
- chore: 레거시 migration_*.sql 10개 파일 삭제 (Alembic으로 대체)

- feat: 게시글 구독 (Topic Tracking) — watching/normal/muted 3단계, 댓글 시 자동 구독, reply 알림
- feat: Q&A 답변 채택 (Solved Answer) — 게시글 작성자가 루트 댓글 채택, 해결됨 배지
- feat: 이메일 다이제스트 — 비활성 사용자 대상 daily/weekly 요약 발송, HTML 이메일
- feat: 알림 설정에 reply_enabled, digest_frequency 추가
- feat: send_email() HTML 지원 (multipart/alternative)

- **03-17: 위키 FAQ/지식베이스 시스템**
  - `wiki_page`, `wiki_page_tag` 테이블 추가 (31개 테이블)
  - 위키 CRUD API (`/v1/wiki`), 태그 연동, 슬러그 기반 조회, 조회수

- **03-16: 패키지 리뷰 시스템**
  - 패키지 등록/조회: 이름, 카테고리, 패키지 매니저, 홈페이지 URL
  - 패키지 리뷰: 1유저 1패키지 1리뷰, 평점(1~5), 제목, 내용
  - 평균 평점 집계 + 리뷰 수 (서브쿼리 패턴)

- **03-16: Camp Linux 리브랜딩**
  - 사이트 이름 "아무 말 대잔치" → "Camp Linux" 전환
  - 카테고리 4개 → 6개 (배포판, Q&A, 뉴스/소식, 프로젝트/쇼케이스, 팁/가이드, 공지사항)
  - `user.distro` 컬럼 추가 (배포판 플레어/뱃지 시스템)
  - 터미널 감성 테마 (차콜 + 오렌지/골드)
  - 코드 하이라이팅 강화 (14개 언어, 터미널 스타일)

- **03-16: Lambda 호환성 완전 제거 — K8s 전용 전환**
  - `ws_handler/` (Lambda WebSocket 핸들러) 삭제
  - `Dockerfile`(Lambda) 삭제, `Dockerfile.k8s` → `Dockerfile` 리네임
  - `deploy-backend.yml`, `rollback-backend.yml` (Lambda 배포/롤백 워크플로우) 삭제
  - `main.py`: Mangum import, `AWS_LAMBDA_EXEC` 조건 분기 전체 제거
  - `core/config.py`: SSM 시크릿 리졸버, `WS_DYNAMODB_TABLE`/`WS_API_GW_ENDPOINT` 삭제, `WS_BACKEND` 기본값 `redis`
  - `utils/websocket_pusher.py`: DynamoDB/API GW 경로 삭제, Redis + 로컬 DEBUG 경로만 유지
  - `pyproject.toml`: `mangum` 의존성 제거

- **03-16: 소셜 로그인 (GitHub OAuth)**
  - `social_account` 테이블 + OAuth 프로바이더 팩토리 (GitHub/카카오/네이버 구조, GitHub만 활성)
  - `GET /v1/auth/social/{provider}/authorize` — OAuth 인가 URL 반환
  - `GET /v1/auth/social/{provider}/callback` — 콜백 처리 (기존 계정 연결 또는 신규 가입 리다이렉트)
  - `POST /v1/auth/social/complete-signup` — 닉네임 설정 후 가입 완료
  - 소셜 전용 계정(`password=NULL`)의 이메일 로그인 시 안내 메시지
  - `user.nickname_set` 컬럼 추가 (소셜 가입 사용자는 `0`)
  - 환경변수: `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `GITHUB_REDIRECT_URI`
  - Rate Limit: `/v1/auth/social/` 경로 설정 추가
  - 테스트: OAuth 콜백 통합 14개 + 모델/가입 단위 테스트

- **03-16: 게시글 임시저장 API**
  - `post_draft` 테이블 (사용자당 1개, UPSERT)
  - `GET/PUT/DELETE /v1/drafts/` — 기기 간 동기화 지원

- **03-16: 알림 유형별 on/off 설정 API**
  - `notification_setting` 테이블 (5개 타입별 boolean)
  - `GET/PATCH /v1/notifications/settings`
  - `create_notification()`에서 음소거 체크 — muted 시 INSERT 스킵

- **03-15: DynamoDB Rate Limiter 제거**
  - Lambda 환경 폐기로 `rate_limiter_dynamodb.py` 삭제 (-99줄)
  - Rate Limiter 백엔드: `memory`(로컬) + `redis`(K8s 프로덕션) 2중 구조로 단순화
  - 커버리지 82.53% → 84.03%

- **03-15: 이미지 업로드 시 자동 리사이징**
  - Pillow 의존성 추가, `utils/image_resize.py` 신규
  - 프로필 이미지: 최대 400x400, 게시글 이미지: 최대 폭 1200px, GIF 제외
  - local/S3 양쪽 스토리지에 동일 적용

- **03-15: 이용약관 동의 기록**
  - `user.terms_agreed_at` 컬럼 추가 (마이그레이션: `migration_terms_agreed.sql`)
  - 회원가입 시 `terms_agreed` 필드 필수 (`CreateUserRequest` 검증)
  - 시드/테스트 페이로드 동기화 (conftest, seed_data, load_tests 등 5곳)

- **03-15: @멘션 정규식 수정 및 수정 시 알림**
  - `@(\S+)` → `@([a-zA-Z0-9_]{3,10})` — 후행 구두점 오탐 방지, 닉네임 규칙 일치
  - 댓글/게시글 수정 시 새로 추가된 멘션에 대해서만 알림 (차집합 패턴)

- **03-15: 댓글 인기순 정렬**
  - `ALLOWED_COMMENT_SORT_OPTIONS`에 `popular` 추가
  - `likes_count DESC, created_at DESC` 기준 루트 댓글 정렬 (대댓글은 시간순 유지)

- **03-12: 투표 변경/취소 API + 팔로워·팔로잉 공개 목록 API**
  - `PUT /v1/posts/{post_id}/poll/vote` — 투표 변경 (다른 옵션으로 UPDATE, 원자적 처리)
  - `DELETE /v1/posts/{post_id}/poll/vote` — 투표 취소 (만료 전만 가능)
  - `GET /v1/users/{user_id}/following` — 특정 사용자의 팔로잉 목록 (공개, 페이지네이션)
  - `GET /v1/users/{user_id}/followers` — 특정 사용자의 팔로워 목록 (공개, 인증 불필요)
  - 테스트: 투표 변경/취소 11개 + 팔로잉/팔로워 공개 목록 6개 + 상호 팔로우 1개 추가 (총 242개)

- **03-12: 테스트 속도 최적화**
  - `TESTING=true` 환경에서 bcrypt rounds 12 → 4 (해싱 ~250배 빠름, 프로덕션 영향 없음)

- **03-12: E2E 테스트 전용 API (`/v1/test/*`)**
  - `TESTING=true` 환경 변수 게이트: 프로덕션에서 엔드포인트 미존재
  - 이메일 인증 바이패스, 역할 변경, 사용자 정지/해제, DB 정리 5개 엔드포인트
  - 프론트엔드 E2E 헬퍼에 래퍼 함수 추가, `test.fixme()` 테스트 활성화

- **03-11: QA 테스트 코드 전면 재구성**
  - 기존 35개 플랫 테스트 파일(~250 케이스) → 10개 도메인별 디렉토리 구조(231 케이스)로 클린 리라이트
  - 도메인: auth, users, posts, comments, engagement, feed, dm, notifications, admin, security
  - 공통 conftest.py 헬퍼 함수 통일 (`create_verified_user()`, `create_admin_user()`, `create_test_post()`, `create_test_comment()`)
  - 기존 빈 테스트 파일 8개(for_you_feed, rate_limiter 등)를 실제 테스트로 구현

- **03-11: 대규모 시드 데이터 스크립트 (`seed_data_large.py`)**
  - 5만 유저(3-tier), 25만 게시글, 75만 댓글 등 총 ~300만 행 생성
  - 성장 곡선 시간 분포 (최근 50%), 인기 편중 분포 (멱법칙 태그, 상위 5% 좋아요 40%)
  - asyncio.gather 병렬 처리 + 5,000행 배치 INSERT로 ~5-10분 내 시딩
  - CLI 기반 독립 실행: `--dry-run`, `--clean`, `--recompute-url` 지원

- **03-10: DM 기능 개선**
  - 메시지 삭제 API 추가 (`DELETE /v1/dms/{id}/messages/{msg_id}`, soft delete)
  - 삭제된 메시지 플레이스홀더 표시, 대화 목록 프리뷰 반영, unread count 제외
  - `GET /v1/dms/{id}` 응답에 `other_user` 객체 추가
  - 읽음 확인 WebSocket 푸시 (`message_read` 이벤트)
  - WebSocket Lambda: 타이핑 인디케이터 중계 (`typing_start`/`typing_stop`)

- **03-10: 코드 리뷰 기반 코드 수정**
  - `hmac.compare_digest()` 적용: 내부 API 키 비교 시 타이밍 공격 방지
  - Rate Limit 설정 키 동기화: GET 엔드포인트(`verify-email`, `resend-verification`) 설정 키 수정
  - 투표 검증 강화: `option_belongs_to_poll()` 검증 추가 (다른 투표의 옵션으로 투표 방지)
  - `PATCH /v1/users/me` 인증 강화: `get_current_user` → `require_verified_email`
  - 모든 DELETE 작업에 `transactional()` 일관 적용
  - 팔로워 알림에 `actor_nickname` 파라미터 전달 (N+1 DB 쿼리 제거)

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
... rest of the file ...
