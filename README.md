# 2-cho-community-be
AWS AI School 2기 3주차 과제: 커뮤니티 백엔드 서버

## changelog
- 2026-01-15: 회원 관련 API 프로토타입 구현 완료
    - 회원정보 변경: `PATCH /v1/users/me` 엔드포인트 추가
        - 닉네임 및 이메일 변경 기능 구현
        - 변경 시 중복 검사 및 형식 검사 추가
        - 세션 정보 자동 업데이트
    - 비밀번호 변경: `PUT /v1/users/me/password` 엔드포인트 추가
        - 현재 비밀번호 확인
        - 새 비밀번호와 새 비밀번호 확인이 일치하는지 확인
        - 새 비밀번호가 정책에 부합하는지 확인
        - 세션 정보 자동 업데이트
    - 회원 탈퇴: `DELETE /v1/users/me` 엔드포인트 추가
        - 탈퇴 요청 시 비활성화 후 삭제 시간 기록
        - 비밀번호 입력 및 직접 동의 절차 추가
    - 패키지 구조 개선
        - `models`, `routers`, `controllers`를 확실하게 패키지로 구성하기 위해 `__init__.py` 파일 추가
        - `__init__.py` 파일에 패키지 내의 모듈들을 import하도록 수정
- 2026-01-14: 세션 기반의 간단한 로그인/로그아웃 기능 구현
    - 세션 ID 생성 및 관리를 위해 `SessionMiddleware` 추가
    - 회원가입/로그인/로그아웃 API 구현
    - 사용자 모델을 데이터 클래스로 변환
    - 기본 프로필 이미지 추가(/assets)
    - 프로필 조회 기능을 ID 기반에서 닉네임 기반으로 전환
    - 라우터 정의를 `main.py`에서 라우터 모듈 내부로 이전
    - `.env` 파일 추가, 민감한 데이터 이전.
- 2026-01-12: API 설계 후 기본 구조 구현
    - router-controller-model 구조 구현
    - 인증 컨트롤러와 라우터 추가(/v1/auth)
    - 사용자 컨트롤러와 라우터 추가(/v1/users)
    - 사용자 데이터 모델과 관련 함수 추가(`models/user_models.py`)
    - 회원가입 기능 추가(`controllers/user_controller.py`)
    - 라우터 구조 개선 (/v1)
    - `pyproject.toml` 패키지 관련 이슈 해결
    - CORS 미들웨어 추가
- 2026-01-06: router-controller-model 구조 구현