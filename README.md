# 2-cho-community-be
AWS AI School 2기 3주차 과제: 커뮤니티 백엔드 서버

## changelog
- 2026-01-14: 세션 기반의 간단한 로그인/로그아웃 기능 구현
    - 세션 ID 생성 및 관리
    - 로그인/로그아웃 API 구현
    - 세션 데이터 저장 및 검증
- 2026-01-12: API 설계 후 기본 구조 구현
    - router-controller-model 구조 구현
    - 인증 컨트롤러와 라우터 추가(`/v1/auth`)
    - 사용자 컨트롤러와 라우터 추가(`/v1/users`)
    - 사용자 데이터 모델과 관련 함수 추가(`models/user_models.py`)
    - 회원가입 기능 추가(`user_controller.py`)
    - 라우터 구조 개선 (`/v1`)
    - `pyproject.toml` 패키지 관련 이슈 해결
    - CORS 미들웨어 추가
- 2026-01-06: router-controller-model 구조 구현