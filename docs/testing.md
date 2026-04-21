# 테스트 가이드

## 구조

```
tests/
  unit/                 단위 테스트 (DB 모킹)
  integration/          통합 테스트 (Redis 필요)
  smoke/                스모크 테스트 (배포 환경 대상)
  conftest.py           공유 fixture (DB 풀, 테스트 유저, httpx client)
```

## 실행

```bash
uv run pytest                              # 전체 (커버리지 임계값 60%)
uv run pytest tests/unit/ -v               # 단위만
uv run pytest tests/integration/ -v        # 통합 (Redis 필요)
uv run pytest tests/smoke/ --base-url=URL  # 스모크 (배포 환경)
```

## 테스트 라우터
- `TESTING=true` + `DEBUG=true` 둘 다 필요
- 하나만으로는 테스트 전용 엔드포인트 활성화 안 됨

## CI
- `python-app.yml` — pytest만 실행 (MySQL 서비스 컨테이너)
- 정적 분석(ruff, mypy)은 pre-commit에서만 실행 — CI에서는 안 함

## 커버리지
- 대상: `modules/` + `core/`
- 임계값: 60%
