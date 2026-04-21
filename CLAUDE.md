# Backend — CLAUDE.md

Camp Linux 백엔드. FastAPI + MySQL + aiomysql 비동기 REST API.

## Commands

```bash
# 개발 서버
source .venv/bin/activate
uvicorn main:app --reload --port 8000

# 테스트
uv run pytest                              # 전체 (커버리지 임계값 60%)
uv run pytest tests/unit/ -v               # 단위 테스트
uv run pytest tests/integration/ -v        # 통합 테스트
uv run pytest tests/smoke/ --base-url=URL  # 스모크 테스트

# 린팅 + 타입 체크
uv run ruff check .
uv run ruff format --check .
uv run mypy .
bash scripts/lint.sh                       # 통합 품질 검사

# 의존성
uv pip install -e ".[dev]"
uv lock                                    # pyproject.toml 변경 후 필수
```

## 모듈러 모놀리스 구조

```
main.py (진입점)
  ↓
core/         (공유 인프라: middleware, dependencies, utils, database)
  ↓
modules/<domain>/  (router → controller → service → models → schemas)
  ↓
MySQL (38 tables, soft delete)
```

### 10개 도메인 모듈

| 모듈 | 역할 |
|------|------|
| `modules/auth/` | 인증 — JWT, OAuth, 이메일 인증 |
| `modules/user/` | 사용자 — 프로필, 팔로우, 차단, 활동 |
| `modules/post/` | 게시글 — 댓글, 좋아요, 북마크, 투표, 피드 |
| `modules/dm/` | 쪽지 — 대화, 메시지, 읽음 처리 |
| `modules/notification/` | 알림 — CRUD, 유형별 설정 |
| `modules/admin/` | 관리자 — 신고 처리, 정지, 대시보드 |
| `modules/content/` | 콘텐츠 — 카테고리, 태그, 이용약관, 임시저장 |
| `modules/wiki/` | 위키 — 페이지 CRUD, 태그, 리비전/diff/롤백 |
| `modules/package/` | 패키지 — 등록, 리뷰 |
| `modules/reputation/` | 평판 — 이벤트, 뱃지, 신뢰 레벨, 일일 방문 |

### Import 규칙

- 도메인 내부: `from modules.<domain>.models import ...`
- 공유 인프라: `from core.database import get_db_pool`
- 공유 스키마: `from schemas.common import create_response`
- 도메인 간 직접 import 최소화 — `core/`를 통해 공유

## 테스트

- **프레임워크**: pytest + pytest-asyncio + pytest-cov
- **구조**: `tests/unit/`, `tests/integration/`, `tests/smoke/`
- **테스트 라우터 활성화**: `TESTING=true` + `DEBUG=true` 둘 다 필요
- **커버리지**: `modules/` + `core/` 대상, 임계값 60%
- **CI**: `python-app.yml` — pytest만 실행 (ruff/mypy는 pre-commit)

## 주요 Gotchas

- **`uv run` 필수**: `ruff`/`mypy`/`pytest`는 `.venv/bin/`에만 설치. `uv run ruff check .` 형태로 실행
- **Trailing slash redirect**: `/v1/posts` → 307 → `/v1/posts/`. URL 끝에 `/` 명시 또는 `follow_redirects=True`
- **동적 라우트 순서**: `/{slug}` 같은 catch-all을 고정 경로보다 뒤에 등록
- **Soft delete**: `user`, `post`, `comment`, `dm_message` 조회 시 `WHERE deleted_at IS NULL`
- **비밀 비교**: `hmac.compare_digest()` 필수 (`==` 금지)
- **`validate_pagination()`**: `core/utils/pagination.py` — 페이지네이션 검증 통합 헬퍼
- **`create_notifications_bulk()`**: `modules/notification/models.py` — 벌크 INSERT (N+1 방지)
- **스키마 변경**: `migrations/versions/` (Alembic) + `core/database/schema.sql` (Docker init) 동시 업데이트
- **`REQUIRE_EMAIL_VERIFICATION=false`**: 로컬에서 이메일 인증 없이 글 작성 가능
- **Pre-commit**: `pre-commit` (ruff + format + mypy)
- **`uv.lock` 동기화**: `pyproject.toml` 변경 후 반드시 `uv lock`
- **uv Python 3.13 hang**: `uv run --python 3.14`로 재생성
- **mypy 설정**: 모든 패키지 디렉토리에 `__init__.py` 필수
- **CI Python 버전 Prod 매칭**: CI와 Prod의 Python 버전이 다르면 "CI 통과, Prod 실패". `python-app.yml`의 `python-version`을 Prod 이미지와 동일하게 유지 (현재 3.13)
- **BE CI는 테스트 전용**: 정적 분석(ruff, mypy)은 pre-commit hook에서만. CI(`python-app.yml`)는 pytest만 실행
- **이메일 발송 로컬 테스트**: MailHog(`localhost:1025`) 또는 Gmail SMTP
- **테스트 라우터 이중 게이트**: `TESTING=true` + `DEBUG=true` 둘 다 필요. 하나만으로는 테스트 엔드포인트 활성화 안 됨
- **`get_users_by_nicknames()`**: `modules/user/models.py` — 멘션 닉네임 배치 조회 (N+1 방지)
- **Secret scanner 오탐**: `core/utils/error_codes.py`의 `INVALID_PASSWORD`/`SAME_PASSWORD` StrEnum 상수가 비밀번호로 감지. `git add`/`git commit` 차단 시 수동 실행
- **ruff per-file-ignores 경로 동기화**: 파일 이동 시 `pyproject.toml` `[tool.ruff.lint.per-file-ignores]`의 glob 패턴도 갱신 필수
- **K8s 프로브 분리**: `/livez` (liveness, DB 무관) + `/readyz` (readiness, DB 503) + `/health` (하위 호환). liveness에 DB 체크 포함하면 Pod 재시작 루프
- **OAuth 토큰 쿠키 전달**: 소셜 로그인 access token은 60초 non-HttpOnly 쿠키(`access_token_temp`)로 전달. FE에서 읽고 삭제
- **부하 테스트 사전 준비**: 계정 시딩 시 `email_verified = 1` 필수 (미설정 시 POST 403). `locustfile.py`의 게시글 작성에 `category_id` 필드 포함
