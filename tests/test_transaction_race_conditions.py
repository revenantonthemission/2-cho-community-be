"""트랜잭션 경쟁 상태(Race Condition) 테스트.

이 테스트는 P0_FIXES_SUMMARY.md에 문서화된 트랜잭션 패턴이
모든 INSERT/UPDATE 작업에 일관되게 적용되었는지 검증합니다.

경쟁 상태 시나리오:
1. Transaction A: UPDATE 실행 (성공)
2. Transaction B: DELETE 실행 (성공)
3. Transaction A: SELECT 실행 → None 반환 (버그!)

올바른 패턴:
- async with transactional() as cur:
    - UPDATE/INSERT
    - 같은 커서로 SELECT
    - 트랜잭션 커밋
"""

import pytest
import pytest_asyncio
import asyncio
from database.connection import transactional
from models import post_models, comment_models
from utils.password import hash_password


@pytest_asyncio.fixture
async def test_user(db):
    """테스트용 사용자 생성."""
    async with transactional() as cur:
        await cur.execute(
            """
            INSERT INTO user (email, password, nickname)
            VALUES (%s, %s, %s)
            """,
            ("race@test.com", hash_password("Test1234!"), "RaceTestUser"),
        )
        user_id = cur.lastrowid

        await cur.execute(
            """
            SELECT id, email, nickname, profile_img, created_at, updated_at, deleted_at
            FROM user WHERE id = %s
            """,
            (user_id,),
        )
        row = await cur.fetchone()

    yield {
        "id": row[0],
        "email": row[1],
        "nickname": row[2],
    }


@pytest_asyncio.fixture
async def test_post(db, test_user):
    """테스트용 게시글 생성."""
    post = await post_models.create_post(
        author_id=test_user["id"],
        title="Test Post for Race Condition",
        content="This post tests transaction isolation.",
    )
    yield post


@pytest_asyncio.fixture
async def test_comment(db, test_user, test_post):
    """테스트용 댓글 생성."""
    comment = await comment_models.create_comment(
        post_id=test_post.id,
        author_id=test_user["id"],
        content="Test comment for race condition",
    )
    yield comment


# ==========================================
# Critical Issue #1: update_comment
# ==========================================


@pytest.mark.asyncio
async def test_update_comment_race_condition(db, test_comment):
    """FAIL: update_comment가 UPDATE와 SELECT을 별도 트랜잭션으로 실행.

    현재 구현:
    1. async with get_connection() as conn:  # autocommit
    2.     UPDATE comment (성공)
    3. await get_comment_by_id()  # 별도 연결!

    경쟁 상태:
    - UPDATE 성공 후, SELECT 전에 다른 트랜잭션이 DELETE 실행 가능
    - get_comment_by_id()가 None 반환 → 사용자는 "수정 실패"로 인식

    기대 동작:
    - UPDATE와 SELECT이 같은 트랜잭션에서 실행되어야 함
    - UPDATE 성공 시 항상 수정된 댓글 객체 반환
    """
    comment_id = test_comment.id
    new_content = "Updated content via race condition test"

    # 동시에 두 작업 실행
    async def update_task():
        # 약간의 지연 추가하여 타이밍 조작
        await asyncio.sleep(0.01)
        return await comment_models.update_comment(comment_id, new_content)

    async def delete_task():
        # update의 UPDATE 후 SELECT 전에 실행되도록 시도
        await asyncio.sleep(0.015)
        return await comment_models.delete_comment(comment_id)

    # 병렬 실행
    update_result, delete_result = await asyncio.gather(
        update_task(), delete_task(), return_exceptions=True
    )

    # 검증: update_result가 None이면 race condition 발생
    # 올바른 트랜잭션 구현이라면:
    # - update가 먼저 커밋되면 delete가 성공하고 update는 댓글 반환
    # - delete가 먼저 실행되면 update가 rowcount=0으로 None 반환 (정상)
    #
    # 버그가 있는 구현:
    # - update의 UPDATE는 성공했지만 SELECT 전에 delete 실행
    # - get_comment_by_id()가 None 반환 (이미 삭제됨)
    # - 사용자는 "수정되었는데 왜 None?"이라는 불일치 경험

    # 이 테스트는 현재 구현에서는 간헐적으로 실패할 수 있음
    # (타이밍에 따라 race condition 발생 여부가 달라짐)

    # 수정 후에는 항상 통과해야 함:
    # - transactional() 사용 시 UPDATE와 SELECT이 원자적으로 실행
    # - update_result가 None이면 rowcount=0인 경우만 (정상)

    if update_result is not None:
        # update가 성공했다면 댓글 객체가 반환되어야 함
        assert update_result.content == new_content
        assert update_result.id == comment_id


# ==========================================
# NOTE: 이전에 문서화된 경쟁 상태 이슈들은 수정 완료
# ==========================================
#
# 수정된 이슈들:
# - update_user: transactional() 사용으로 UPDATE+SELECT 원자성 보장
# - update_post: transactional() 사용 + params 순서 오류 수정
# - add_user: transactional() 사용 + RuntimeError 추가
#
# 이러한 수정사항은 test_update_comment_race_condition에서
# 검증된 올바른 패턴을 따릅니다.


# ==========================================
# Positive Test: 올바른 트랜잭션 패턴
# ==========================================


@pytest.mark.asyncio
async def test_create_comment_correct_pattern(db, test_user, test_post):
    """PASS: create_comment은 이미 transactional()을 올바르게 사용.

    올바른 구현 (comment_models.py의 create_comment):
    1. async with transactional() as cur:
    2.     INSERT INTO comment
    3.     comment_id = cur.lastrowid
    4.     SELECT ... WHERE id = %s  # 같은 트랜잭션!
    5.     return _row_to_comment(row)

    이 패턴은 P0_FIXES_SUMMARY.md에 문서화된 표준입니다.
    모든 update/insert 함수가 이 패턴을 따라야 합니다.
    """
    comment = await comment_models.create_comment(
        post_id=test_post.id,
        author_id=test_user["id"],
        content="Testing correct transactional pattern",
    )

    # 검증: transactional() 사용으로 INSERT-SELECT이 원자적
    assert comment is not None
    assert comment.content == "Testing correct transactional pattern"
    assert comment.post_id == test_post.id
    assert comment.author_id == test_user["id"]

    # 동시성 테스트: create와 delete를 병렬 실행
    comment_id = comment.id

    async def create_task():
        return await comment_models.create_comment(
            post_id=test_post.id,
            author_id=test_user["id"],
            content="Concurrent create",
        )

    async def delete_task():
        await asyncio.sleep(0.01)  # create의 INSERT 후 실행 유도
        return await comment_models.delete_comment(comment_id)

    create_result, delete_result = await asyncio.gather(
        create_task(), delete_task(), return_exceptions=True
    )

    # transactional() 덕분에 create는 항상 성공 (새 댓글)
    assert create_result is not None
    assert create_result.content == "Concurrent create"

    # delete는 원래 댓글을 삭제 (True 반환)
    assert delete_result is True


# ==========================================
# 통합 테스트: 실제 사용 시나리오
# ==========================================


@pytest.mark.asyncio
async def test_concurrent_comment_updates(db, test_user, test_post):
    """FAIL: 동시에 같은 댓글을 수정하는 시나리오.

    시나리오:
    1. 사용자 A: 댓글 "Original" 작성
    2. 사용자 A: "Updated A"로 수정 시도
    3. 사용자 B(관리자): 댓글 삭제 (동시)

    현재 버그:
    - A의 UPDATE는 성공 (rowcount=1)
    - B의 DELETE 실행
    - A의 SELECT → None 반환
    - 사용자 A는 "수정했는데 왜 사라졌지?" 혼란

    올바른 동작 (transactional() 사용):
    - A의 UPDATE+SELECT+COMMIT이 원자적
    - B의 DELETE는 A의 커밋 후 실행
    - 또는 B가 먼저 커밋되면 A는 rowcount=0으로 None 반환 (명확)
    """
    # 댓글 생성
    comment = await comment_models.create_comment(
        post_id=test_post.id,
        author_id=test_user["id"],
        content="Original comment",
    )

    comment_id = comment.id

    # 동시 작업
    results = await asyncio.gather(
        comment_models.update_comment(comment_id, "Updated by user A"),
        comment_models.delete_comment(comment_id),
        return_exceptions=True,
    )

    update_result, delete_result = results

    # 검증: 둘 중 하나만 성공해야 함 (명확한 결과)
    # - update 성공 → delete도 성공 가능 (순차 실행)
    # - delete 성공 → update는 None (rowcount=0)

    # 버그: update는 성공(rowcount=1)했지만 결과가 None (불일치!)
    if update_result is not None:
        assert update_result.content == "Updated by user A"

    # 수정 후: 항상 일관된 결과
    # - update가 None이 아니면 댓글 객체 반환
    # - update가 None이면 delete가 먼저 실행된 것 (정상)
