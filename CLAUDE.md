# Backend — CLAUDE.md

FastAPI 백엔드 (Python 3.11+, aiomysql, Port 8000). 상세 아키텍처는 `README.md` 참조.

## Commands

```bash
source .venv/bin/activate
uvicorn main:app --reload --port 8000       # 개발 서버
pytest                                       # 전체 테스트
pytest tests/test_qa_full.py::test_name      # 단일 테스트
pytest --cov                                 # 커버리지
ruff check .                                 # 린팅
ruff check . --fix                           # 자동 수정
mypy .                                       # 타입 체크
```

## Architecture (Router → Controller → Model)

- `routers/`: API 엔드포인트 (`/v1/auth`, `/v1/auth/social`, `/v1/users`, `/v1/posts`, `/v1/terms`, `/v1/categories`, `/v1/tags`, `/v1/reports`, `/v1/admin/reports`, `/v1/dms`, `/v1/drafts`, `/v1/notifications`, `/v1/packages`)
- `controllers/`: 비즈니스 로직
- `services/`: 컨트롤러-모델 간 조율 (`user_service`, `post_service`, `report_service`, `dm_service`)
- `models/`: DB 쿼리 (raw SQL with aiomysql)
- `schemas/`: Pydantic 요청/응답 모델
- `dependencies/`: 인증, 컨텍스트 주입
- `middleware/`: 로깅, 타이밍, Rate Limiting, 전역 예외 처리
- `utils/`: 비밀번호 해싱, JWT(`jwt_utils.py`), 파일 업로드, HTTP 에러 헬퍼, 포매터, 이메일(`email.py`), 임시 비밀번호(`temp_password.py`)

## 보안 규칙 (필수)

- **XSS 방지**: `createElement()` 또는 `textContent` 사용 (innerHTML 금지)
- **비밀 문자열 비교**: `==` 사용 금지. `hmac.compare_digest()` 필수
- **정보 열거 방지**: 이메일/비밀번호 찾기에서 존재 여부 무관하게 동일 응답. 미존재 시에도 bcrypt 해싱 수행 (타이밍 공격 방지)
- **Path Traversal 방지**: `utils/storage.py`의 `delete_file()`에서 `Path.resolve()` + `is_relative_to()` 사용
- **이미지 URL 검증**: `schemas/_image_validators.py` 공통 헬퍼. 새 이미지 URL 필드 추가 시 반드시 사용
- **`DEBUG` 기본값 `False` 필수**: `True`일 때 500 응답에 `str(exc)` 포함 → 프로덕션 정보 유출
- **이미지 URL 검증 변경 시**: `schemas/_image_validators.py` 수정 후 post_schemas.py, user_schemas.py 양쪽의 validator 확인. 새 이미지 필드 추가 시 반드시 동일 헬퍼 사용

## 인증 & 권한

- **JWT**: Access Token 30분(in-memory) + Refresh Token 7일(HttpOnly 쿠키, SHA-256 해시 DB 저장). payload는 `sub`(user_id)만 — PII 미포함
- **인증 가드**: `get_current_user`(읽기), `require_verified_email`(쓰기), `require_admin`(관리자), `require_internal`(내부 키), `require_admin_or_internal`(이중 인증)
- **`get_optional_user()` 전파**: 401만 None 변환, 403 이상은 전파. `_validate_token()`에 에러 추가 시 except 분기 확인 필수
- **계정 정지**: `suspended_until` + `suspended_reason`. `_validate_token()`/`login()`/`refresh_token()` 3중 403 차단

## 백엔드 규칙

- **Soft Delete**: `user`, `post`, `comment`, `dm_message` 조회 시 반드시 `WHERE deleted_at IS NULL`
- **Assert vs Raise**: `assert`=내부 불변성, `raise HTTPException`=사용자 입력 에러
- **PATCH API 필드 의미**: `None`=변경 없음, `[]`(빈 배열)도 변경 없음
- **datetime 포맷팅**: 모든 모델 datetime은 `format_datetime()` (`utils/formatters.py`)로 ISO 8601 변환
- **게시글 정렬**: `ALLOWED_SORT_OPTIONS` 화이트리스트로 SQL 주입 방지. 유효하지 않으면 `latest` 폴백
- **IntegrityError 전파**: like/bookmark/follow/poll/report에서 중복 시 `IntegrityError`는 `transactional()` 밖 controller에서 409로 변환
- **대댓글**: 1단계만 허용 (대댓글의 대댓글은 400). 삭제된 부모는 대댓글 있으면 플레이스홀더, 없으면 숨김
- **사용자 차단 필터**: 게시글=SQL `NOT IN`, 댓글=Python 후처리 (삭제 부모 플레이스홀더 보존)
- **알림**: `create_notification()`에서 자기 자신 알림 미생성. `actor_nickname` 파라미터로 DB 조회 생략 가능
- **알림 설정 체크 주체**: `is_notification_muted(user_id, type)`의 `user_id`는 알림 수신자. actor(발신자)가 아님. 좋아요를 누른 사람의 설정이 아닌 게시글 작성자의 설정을 체크
- **추천 피드**: `user_post_score` materialized → `LEFT JOIN + COALESCE` 폴백. `user_has_scores()` False면 `latest` 폴백. `_apply_diversity_cap()` 작성자당 최대 3개
- **WebSocket 푸시**: `websocket_pusher.py`가 Redis Pub/Sub(`WS_BACKEND=redis`)로 best-effort 푸시 (transactional 밖). 로컬은 `DEBUG=True` 시 인메모리 연결 사용
- **멘션 정규식 동기화**: `utils/mention.py`의 `MENTION_PATTERN`은 `schemas/user_schemas.py`의 `_NICKNAME_PATTERN`과 동일 문자셋 사용 필수. FE `js/utils/mention.js`도 동기화
- **user 테이블 INSERT-only 컬럼**: 조회 불필요한 컬럼 추가 시 `USER_SELECT_FIELDS`/`_row_to_user()`/`User` dataclass 변경 없이 INSERT SQL만 수정 가능 (인덱스 시프트 회피)
- **이미지 리사이징**: `utils/image_resize.py` — 프로필 최대 400x400, 게시글 최대 폭 1200px. GIF는 애니메이션 보존을 위해 리사이징 제외
- **API 응답 키 규칙**: 카운트 필드는 복수형 (`likes_count`, `views_count` 등). 단수형(`like_count`) 금지. 목록 응답은 `data.{entity_plural}` 형태
- **API 응답 경로 주의**: `create_response(data={"url": ...})` → FE에서 `response.data.data.url`. `extractUploadedImageUrl()` 참조. 새 응답 필드 추가 시 FE 접근 경로 확인 필수
- **새 라우터 추가 시**: `routers/*.py` 생성 → `main.py` 상단에 import + `app.include_router()` 등록. import를 등록 근처에 두면 ruff E402 위반
- **사용자당 1행 테이블**: `UNIQUE KEY (user_id)` + `ON DUPLICATE KEY UPDATE` UPSERT 패턴 사용 (notification_setting, post_draft 참조)
- **소셜 로그인 프로바이더 추가**: `services/social_auth/{provider}.py` 생성 + `factory.py`의 `_PROVIDERS` dict에 등록. `SocialProvider` Protocol 구현 필수
- **GitHub OAuth 이메일 비공개**: `get_user_info()`에서 `/user` 응답의 `email`이 `null`이면 `/user/emails` API에서 `primary=true && verified=true` 이메일 조회. `SocialUserInfo.email`은 `str | None`
- **소셜 로그인 쿠키 도메인**: 콜백(`127.0.0.1:8000`)이 프론트엔드로 리다이렉트하면서 `refresh_token` 쿠키 설정. `FRONTEND_URL`이 `localhost`이면 도메인 불일치로 쿠키 미전송. 반드시 `FRONTEND_URL=http://127.0.0.1:8080`으로 통일
- **`nickname_set` 컬럼**: `user` 테이블에 추가됨. 소셜 가입 사용자는 `nickname_set=0`. `USER_SELECT_FIELDS` 인덱스 4번 (nickname 뒤, password 앞). `User.password`는 `str | None` (소셜 사용자 NULL)
- **프로필 응답 중첩**: `GET /v1/users/me`, `GET /v1/users/{id}` 모두 `data.user.{field}` 구조
- **조회수 중복 방지**: `post_view_log` 테이블에 `(user_id, post_id, date)` 유니크 키. 테스트 시 다른 사용자로 조회 필요

## 트랜잭션 (중요!)

- **`transactional()` 사용 필수**: 다중 쿼리 작업(INSERT 후 SELECT 등) 시 반드시 `async with transactional() as cur:` 사용
- **모든 쓰기 작업은 `transactional()`**: `delete_post`, `delete_comment` 포함 모든 INSERT/UPDATE/DELETE에 일관 적용
- **autocommit=True 주의**: `database/connection.py`에서 풀 설정 시 autocommit=True이지만, `transactional()` 내부에서는 명시적 트랜잭션 사용
- **경쟁 상태 방지**: `like_models.py`, `comment_models.py`에서 INSERT와 SELECT을 같은 트랜잭션에서 실행해야 Phantom Read 방지
- **IntegrityError는 transactional() 밖에서 처리**: 내부에서 catch 후 `return`하면 `conn.commit()` 시도 → 2차 에러. 반드시 전파 → rollback → controller에서 처리
- **격리 수준**: READ COMMITTED (Dirty Read 방지, 성능 향상)
- **토큰 회전 원자성**: `token_models.rotate_refresh_token()`은 DELETE + INSERT를 `transactional()`로 묶음. `get_refresh_token()`은 `SELECT ... FOR UPDATE`로 행 잠금

## Rate Limiting

- **분산 Rate Limiter**: `RATE_LIMIT_BACKEND` 설정으로 `"memory"`(로컬, 기본) 또는 `"redis"`(K8s 프로덕션) 선택
- **프로토콜 기반 구조**: `RateLimiterProtocol` → `MemoryRateLimiter` / `RedisRateLimiter`. 팩토리 `_create_rate_limiter()`
- **fail-open 정책**: Redis 장애 시 요청 허용 (가용성 우선)
- **RATE_LIMIT_CONFIG 키 동기화 필수**: `_PATH_PARAM_RE`로 정규화 (`/\d+` → `/{id}`). 키 형식: `"METHOD:/v1/path/{id}/action"`. 불일치 시 브루트포스 제한 무효화
- **OPTIONS 요청 제외 필수**: CORS preflight는 rate limit 대상 아님
- **테스트 비활성화**: `TESTING=true` 환경변수
- **프로덕션**: `.env`에서 `TRUSTED_PROXIES` 설정 필요

## 데이터베이스

- **DB 스키마**: `database/schema.sql`로 전체 스키마 관리
- **테이블 수**: 29개. 추가/삭제 시 `README.md` 아키텍처 다이어그램도 업데이트
- **테이블 수 동기화 5곳**: `README.md` ERD 주석, `CLAUDE.md` 이 항목, `tests/conftest.py` docstring, `routers/test_router.py` docstring, 루트 `CLAUDE.md` Architecture 다이어그램
- **ERD 동기화 필수**: `schema.sql` 변경 시 `README.md` ERD도 갱신
- **커넥션 풀**: 5-50 크기, 연결 타임아웃 5초 (`database/connection.py`)
- **FULLTEXT 검색 ngram**: `WITH PARSER ngram` — 한국어 검색 필수. CI(MySQL 9.6) 호환
- **`comment` 테이블 컬럼명 주의**: `comment`는 `author_id`, `post_like`/`post_bookmark`/`post_view_log`는 `user_id`. JOIN 시 별칭 필수
- **user.role ENUM**: `'user'`, `'admin'`만 허용. Admin 부여는 DB 직접 설정
- **category 테이블**: 6개 시드 (배포판/Q&A/뉴스·소식/프로젝트·쇼케이스/팁·가이드/공지사항). `tests/conftest.py`의 `clear_all_data()`에서도 시드 재삽입
- **user.distro 컬럼**: 사용자 선호 배포판 (`ubuntu`, `fedora`, `arch`, `debian`, `opensuse`, `mint`, `manjaro`, `other` 또는 NULL). 프로필 뱃지/플레어 표시에 사용
- **`tests/conftest.py` `clear_all_data()` 동기화**: 새 테이블 추가 시 TRUNCATE 추가 필수 (FK 자식 → 부모 순서)
- **`user` 테이블 컬럼 추가 시**: `USER_SELECT_FIELDS` + `_row_to_user()` 인덱스 시프트 + `User` dataclass 3곳 동기화 필수
- **MySQL TIMESTAMP timezone-naive**: UTC 비교 시 `replace(tzinfo=timezone.utc)` 필요
- **`notification.post_id` NULL 허용**: 팔로우/북마크 등 게시글 없는 알림은 `post_id=NULL`. `safe_notify()`가 예외를 삼킴
- **MySQL `@variable :=` deprecated**: MySQL 9.x에서 `WITH RECURSIVE` CTE 사용
- **MySQL 버전 변경 시**: `database/Dockerfile`, `.github/workflows/python-app.yml`, README, CHANGELOG 함께 업데이트

### 쿼리 성능 최적화

- **TEXT/BLOB 컬럼 GROUP BY 금지**: 성능 급격히 저하
- **Cartesian Product 방지**: 여러 LEFT JOIN + GROUP BY → 서브쿼리로 미리 집계 후 JOIN
- **`get_posts_with_details()` 최적화**: 서브쿼리 패턴 사용. 직접 JOIN 변경 시 성능 저하 주의
- **인덱스 활용**: `idx_post_list_optimized`, `idx_post_like_post_id`, `idx_comment_list_optimized` 존재

## API Endpoints

모든 API는 `/v1/` 프리픽스. 라우터: `auth`, `auth/social`, `users`, `posts`, `categories`, `tags`, `reports`, `admin/reports`, `admin/users`, `dms`, `drafts`, `notifications`, `terms`, `packages`.

- 정렬: `?sort=latest|likes|views|comments|hot|for_you`
- 필터: `?search=`, `?category_id=`, `?tag=`, `?following=true`
- 관리자 전용: 게시글 고정, 신고 처리(`suspend_days`), 사용자 정지, 대시보드, 피드 재계산, 토큰 정리
- 내부 API: `POST /v1/admin/feed/recompute`, `POST /v1/admin/cleanup/tokens` (`X-Internal-Key` 인증)
- **E2E 테스트 API**: `/v1/test/*`는 `settings.TESTING=True`일 때만 등록. 프로덕션에서 절대 `TESTING=true` 금지

## K8s 전용 (Lambda 완전 제거 완료)

- **Lambda 코드 삭제 완료 (2026-03-16)**: Mangum, SSM resolver, DynamoDB pusher, ws_handler/, Lambda Dockerfile, deploy-backend.yml/rollback-backend.yml 모두 삭제. `AWS_LAMBDA_EXEC` 분기 없음
- **WS_BACKEND 기본값 `"redis"`**: 로컬에서 Redis 미실행 시 `DEBUG=True`이면 인메모리 폴백 사용. `.env`에 `WS_BACKEND` 설정 불필요
- **Dockerfile 리네임**: `Dockerfile.k8s` → `Dockerfile`. `deploy-k8s.yml`도 `-f Dockerfile` 참조

## Gotchas

- **`FRONTEND_URL` 도메인 통일 필수**: `localhost` ≠ `127.0.0.1` (브라우저 쿠키 정책). 소셜 로그인 콜백의 `Set-Cookie`가 `127.0.0.1`에 설정되므로 `FRONTEND_URL=http://127.0.0.1:8080` 사용. `localhost`로 설정 시 refresh token 전송 실패
- **FastAPI 라우트 순서**: 정적 경로(`/find-email`, `/reset-password`)를 동적 경로(`/{user_id}`) 전에 등록
- **DM 라우트 순서**: `/unread-count`를 `/{conversation_id}` 앞에 등록
- **DM API 응답 구조**: `POST /v1/dms` → `data.conversation.id`. `POST /v1/dms/{id}/messages` → `data.message`
- **이메일 발송 후 비밀번호 변경 순서**: `reset_password()`에서 이메일 발송 성공 후에만 비밀번호 변경
- **bcrypt는 asyncio.to_thread()**: CPU-bound 해싱을 이벤트 루프에서 직접 호출하면 블로킹
- **httpx 0.28 `delete()` 제약**: `json=` 파라미터 없음. `client.request("DELETE", url, json=...)` 사용
- **Pydantic `settings` vs `os.environ`**: `BaseSettings`는 `os.environ`에 설정하지 않음. 반드시 `settings.FIELD` 사용
- **`TESTING=true` 이메일 스킵**: 로컬 SMTP 미설정 시 TCP 타임아웃 방지
- **비밀번호 허용 특수문자**: `@, $, !, %, *, ?, &` 7개만 (8~20자, 대/소문자/숫자 포함). 닉네임 3~10자
- **`redis.asyncio` mypy 이중 타입**: `await` 시 `# type: ignore[misc]` 필요
- **Pydantic 스키마 필수 필드 추가 시**: 기존 테스트 payload 전수 검사 필수. `grep -r "json=.*title.*content" tests/`
- **회원가입 payload 동기화 5곳**: `tests/conftest.py` `_make_user_payload()`, FE `tests/e2e/fixtures/test-helpers.js` `createTestUser()`, `database/seed_data.py`, `database/seed_data_large.py`, `load_tests/seed_accounts.py`. 필수 필드 추가 시 전수 확인 필수
- **모듈 리네임 시**: mock patch 경로 `grep`으로 전체 검색 필수
- **K8s optional dependency**: `pyproject.toml`의 `[k8s]` 그룹. CI는 `[dev]` extras만 설치. `redis` 의존 테스트는 `pytest.importorskip("redis")` 선행 필수

## Seed Data

```bash
# 소규모 (프로젝트 connection.py 사용)
python database/seed_data.py --scale small --no-confirm

# 대규모 (독립 aiomysql 풀, CLI 인자)
python database/seed_data_large.py --db-user admin --db-password SECRET --dry-run
python database/seed_data_large.py --db-host 127.0.0.1 --db-port 3307 \
    --db-user admin --db-password SECRET --no-confirm
```

## Load Test (Locust)

```bash
uv pip install -e ".[load-test]"
python -m load_tests.seed_accounts --mode api --host https://api.my-community.shop
locust -f load_tests/locustfile.py --host=https://api.my-community.shop
```

- **테스트 계정 사전 시딩 필수**: `seed_accounts.py`로 대상 DB에 계정 생성 후 실행
- **회원가입 API는 Form 데이터**: `POST /v1/users/`는 `data={}` (JSON 아님)
- **`gevent.sleep()` 필수**: `time.sleep()` 사용 시 전체 워커 블록
- **`StopUser` 예외**: 로그인 실패 시 깨끗한 종료 (`from locust.exception import StopUser`)
- **계정 풀**: `queue.Queue` 1:1 바인딩. 동시 사용자 > 250이면 블록
- **Access Token 30분 만료**: 30분 초과 테스트 시 401 비율 증가 감안
