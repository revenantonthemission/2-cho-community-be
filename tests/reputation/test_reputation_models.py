"""Reputation 도메인 — 모델 함수 단위 테스트."""

import pytest
from httpx import AsyncClient

from modules.reputation import models as rep_models
from tests.conftest import create_verified_user

# ---------------------------------------------------------------------------
# 평판 이벤트 삽입 + 조회
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_insert_and_get_reputation_event(client: AsyncClient, fake):
    """이벤트 삽입 후 히스토리 조회 시 해당 이벤트가 포함되어야 한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    user_id = user["user_id"]

    # Act
    event_id = await rep_models.insert_reputation_event(
        user_id=user_id,
        event_type="post_created",
        points=5,
        source_type="post",
        source_id=1,
    )

    # Assert
    assert event_id > 0

    history = await rep_models.get_reputation_history(user_id)
    assert len(history) >= 1
    found = next((e for e in history if e["id"] == event_id), None)
    assert found is not None
    assert found["event_type"] == "post_created"
    assert found["points"] == 5


@pytest.mark.asyncio
async def test_get_reputation_history_count(client: AsyncClient, fake):
    """이벤트 삽입 후 count 함수가 올바른 값을 반환해야 한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    user_id = user["user_id"]

    # Act
    await rep_models.insert_reputation_event(user_id, "post_created", 5)
    await rep_models.insert_reputation_event(user_id, "comment_created", 2)

    # Assert
    count = await rep_models.get_reputation_history_count(user_id)
    assert count == 2


@pytest.mark.asyncio
async def test_find_original_event_returns_most_recent(client: AsyncClient, fake):
    """find_original_event가 가장 최근 양의 포인트 이벤트를 반환해야 한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    user_id = user["user_id"]

    await rep_models.insert_reputation_event(user_id, "post_liked", 10, source_type="post", source_id=42)

    # Act
    result = await rep_models.find_original_event(user_id, "post_liked", "post", 42)

    # Assert
    assert result is not None
    assert result["event_type"] == "post_liked"
    assert result["points"] == 10
    assert result["source_id"] == 42


# ---------------------------------------------------------------------------
# 평판 점수 업데이트 + 조회
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_and_get_reputation_score(client: AsyncClient, fake):
    """평판 점수 delta 적용 후 조회 시 변경값이 반영되어야 한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    user_id = user["user_id"]

    # Act
    await rep_models.update_user_reputation(user_id, 50)
    score = await rep_models.get_user_reputation_score(user_id)

    # Assert
    assert score == 50


@pytest.mark.asyncio
async def test_update_reputation_negative_delta(client: AsyncClient, fake):
    """음수 delta 적용 시 점수가 감소해야 한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    user_id = user["user_id"]

    await rep_models.update_user_reputation(user_id, 100)

    # Act
    await rep_models.update_user_reputation(user_id, -30)
    score = await rep_models.get_user_reputation_score(user_id)

    # Assert
    assert score == 70


@pytest.mark.asyncio
async def test_get_user_trust_level_default(client: AsyncClient, fake):
    """신규 사용자의 신뢰 등급은 기본값(0)이어야 한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    user_id = user["user_id"]

    # Act
    level = await rep_models.get_user_trust_level(user_id)

    # Assert
    assert level == 0


@pytest.mark.asyncio
async def test_update_user_trust_level_returns_true_when_changed(client: AsyncClient, fake):
    """신뢰 등급 변경 시 True를 반환해야 한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    user_id = user["user_id"]

    # Act
    changed = await rep_models.update_user_trust_level(user_id, 1)

    # Assert
    assert changed is True
    level = await rep_models.get_user_trust_level(user_id)
    assert level == 1


@pytest.mark.asyncio
async def test_update_user_trust_level_returns_false_when_same(client: AsyncClient, fake):
    """동일한 신뢰 등급으로 업데이트 시 False를 반환해야 한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    user_id = user["user_id"]
    await rep_models.update_user_trust_level(user_id, 2)

    # Act
    changed = await rep_models.update_user_trust_level(user_id, 2)

    # Assert
    assert changed is False


# ---------------------------------------------------------------------------
# 신뢰 등급 정의
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_trust_level_definitions(client: AsyncClient, fake):
    """신뢰 등급 정의가 5개 존재해야 한다."""
    # Act
    levels = await rep_models.get_trust_level_definitions()

    # Assert
    assert len(levels) == 5
    assert levels[0]["level"] == 0
    assert levels[-1]["level"] == 4


@pytest.mark.asyncio
async def test_get_appropriate_trust_level(client: AsyncClient, fake):
    """평판 점수에 맞는 신뢰 등급을 반환해야 한다."""
    # Act & Assert
    assert await rep_models.get_appropriate_trust_level(0) == 0
    assert await rep_models.get_appropriate_trust_level(49) == 0
    assert await rep_models.get_appropriate_trust_level(50) == 1
    assert await rep_models.get_appropriate_trust_level(200) == 2
    assert await rep_models.get_appropriate_trust_level(1000) == 3
    assert await rep_models.get_appropriate_trust_level(5000) == 4


# ---------------------------------------------------------------------------
# 배지 정의 + 수여
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_all_badge_definitions_count(client: AsyncClient, fake):
    """배지 정의가 27개 존재해야 한다."""
    # Act
    badges = await rep_models.get_all_badge_definitions()

    # Assert
    assert len(badges) == 27


@pytest.mark.asyncio
async def test_get_badge_definitions_by_trigger(client: AsyncClient, fake):
    """trigger_type 조회 시 해당 트리거의 배지만 반환되어야 한다."""
    # Act
    badges = await rep_models.get_badge_definitions_by_trigger("post_count")

    # Assert
    assert len(badges) >= 1
    for badge in badges:
        assert badge["trigger_type"] == "post_count"


@pytest.mark.asyncio
async def test_award_badge_success(client: AsyncClient, fake):
    """배지 수여 시 True를 반환하고 사용자 배지 목록에 포함되어야 한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    user_id = user["user_id"]

    badges = await rep_models.get_all_badge_definitions()
    assert badges, "배지 정의가 존재해야 합니다"
    badge_id = badges[0]["id"]

    # Act
    result = await rep_models.award_badge(user_id, badge_id)

    # Assert
    assert result is True
    user_badges = await rep_models.get_user_badges(user_id)
    assert any(ub["badge_id"] == badge_id for ub in user_badges)


@pytest.mark.asyncio
async def test_award_badge_duplicate_returns_false(client: AsyncClient, fake):
    """이미 획득한 배지를 다시 수여하면 False를 반환해야 한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    user_id = user["user_id"]

    badges = await rep_models.get_all_badge_definitions()
    badge_id = badges[0]["id"]
    await rep_models.award_badge(user_id, badge_id)

    # Act
    result = await rep_models.award_badge(user_id, badge_id)

    # Assert
    assert result is False


@pytest.mark.asyncio
async def test_get_user_badge_count(client: AsyncClient, fake):
    """수여한 배지 수와 badge_count가 일치해야 한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    user_id = user["user_id"]

    badges = await rep_models.get_all_badge_definitions()
    await rep_models.award_badge(user_id, badges[0]["id"])
    await rep_models.award_badge(user_id, badges[1]["id"])

    # Act
    count = await rep_models.get_user_badge_count(user_id)

    # Assert
    assert count == 2


# ---------------------------------------------------------------------------
# 일일 방문 기록 + 연속 방문일
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_daily_visit_first_time(client: AsyncClient, fake):
    """첫 방문 기록 시 True를 반환해야 한다.

    Note: create_verified_user가 로그인 시 이미 daily visit을 기록하므로,
    동일 날짜에 재호출하면 False가 반환된다. 로그인 시 자동 기록이 정상 동작하는지 확인.
    """
    # Arrange
    user = await create_verified_user(client, fake)
    user_id = user["user_id"]

    # Act — 로그인 시 이미 기록되었으므로 중복 호출은 False
    result = await rep_models.record_daily_visit(user_id)

    # Assert — 로그인 훅이 이미 기록했으므로 False
    assert result is False


@pytest.mark.asyncio
async def test_record_daily_visit_duplicate_returns_false(client: AsyncClient, fake):
    """같은 날 중복 방문 기록 시 False를 반환해야 한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    user_id = user["user_id"]
    await rep_models.record_daily_visit(user_id)

    # Act
    result = await rep_models.record_daily_visit(user_id)

    # Assert
    assert result is False


@pytest.mark.asyncio
async def test_get_consecutive_visit_days_after_single_visit(client: AsyncClient, fake):
    """오늘 하루만 방문한 경우 연속 방문일은 1이어야 한다."""
    # Arrange
    user = await create_verified_user(client, fake)
    user_id = user["user_id"]
    await rep_models.record_daily_visit(user_id)

    # Act
    streak = await rep_models.get_consecutive_visit_days(user_id)

    # Assert
    assert streak == 1


@pytest.mark.asyncio
async def test_get_consecutive_visit_days_no_visits(client: AsyncClient, fake):
    """로그인 후 연속 방문일은 1이어야 한다.

    Note: create_verified_user가 로그인 시 daily visit을 자동 기록하므로,
    방문 기록 없는 상태를 테스트할 수 없다. 로그인 후 기본 streak = 1 확인.
    """
    # Arrange
    user = await create_verified_user(client, fake)
    user_id = user["user_id"]

    # Act
    streak = await rep_models.get_consecutive_visit_days(user_id)

    # Assert — 로그인 시 오늘 방문이 기록되어 streak = 1
    assert streak == 1
