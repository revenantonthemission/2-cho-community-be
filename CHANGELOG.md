# Changelog

## 2026-03 (Mar)

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
