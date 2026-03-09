# Changelog

## 2026-03 (Mar)

- **03-09: EventBridge 배치 작업 전환 — 수평 확장 대응**
  - `main.py`의 인프로세스 배치 작업(토큰 정리, 피드 점수 재계산) 제거 → EventBridge 스케줄 기반으로 전환
  - 내부 API 인증: `X-Internal-Key` 헤더 기반 `require_internal` / `require_admin_or_internal` 이중 인증
  - 새 엔드포인트: `POST /v1/admin/cleanup/tokens` (만료 Refresh Token + 이메일 인증 토큰 일괄 삭제)
  - `POST /v1/admin/feed/recompute` 관리자 전용 → 관리자 + 내부 키 이중 인증으로 변경
  - `INTERNAL_API_KEY` SSM Parameter Store 통합 (`_resolve_ssm_secrets()` 확장)
  - 테스트: 8 cases (내부 키 인증 + 엔드포인트)

- **03-09: 분산 Rate Limiter — DynamoDB 백엔드**
  - Protocol 패턴으로 Rate Limiter 백엔드 추상화 (`RateLimiterProtocol`)
  - DynamoDB Fixed Window Counter 구현 (fail-open, 원자적 카운터)
  - 팩토리 패턴: `RATE_LIMIT_BACKEND` 환경변수로 `memory`/`dynamodb` 선택
  - 기존 인메모리 Rate Limiter를 `MemoryRateLimiter`로 분리 (로컬 개발용 유지)
  - 테스트: 15 cases (메모리 9 + DynamoDB 6)

- **03-09: 추천 피드(For You Feed) — 개인화 정렬**
... rest of the file ...
