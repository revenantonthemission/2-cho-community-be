"""feed_service: 추천 피드 배치 오케스트레이션.

신호 수집 → 점수 계산 → DB UPSERT를 주기적으로 실행합니다.
"""

import asyncio
import logging
import time

from modules.post import affinity_models
from modules.post.affinity_scorer import (
    build_profile,
    compute_combined_score,
    score_post,
)

logger = logging.getLogger(__name__)

# 동시 배치 실행 방지
_CONCURRENCY_LOCK = asyncio.Lock()

# 후보 게시글 최대 기간 (일)
_CANDIDATE_MAX_AGE_DAYS = 7

# 신호 수집 기간 (일)
_SIGNAL_LOOKBACK_DAYS = 30

# 사용자당 최대 저장 점수 수
_MAX_SCORES_PER_USER = 200


class FeedService:
    """추천 피드 점수 관리 서비스."""

    @staticmethod
    async def recompute_all_scores() -> dict:
        """전체 활성 사용자의 추천 점수를 재계산합니다.

        멱등 설계: 락으로 동시 실행 방지, UPSERT로 부분 실패 시 재실행 안전.

        Returns:
            {"users_processed": int, "scores_written": int, "elapsed_s": float}
            또는 이미 실행 중이면 {"skipped": True}.
        """
        if _CONCURRENCY_LOCK.locked():
            logger.warning("피드 배치 작업 이미 실행 중 — 건너뜀")
            return {"skipped": True}

        async with _CONCURRENCY_LOCK:
            start = time.monotonic()
            users_processed = 0

            # 1. 후보 게시글 메타 로드 (최근 N일)
            candidates = await affinity_models.get_candidate_posts_meta(
                max_age_days=_CANDIDATE_MAX_AGE_DAYS,
            )
            if not candidates:
                logger.info("추천 후보 게시글 없음")
                return {
                    "users_processed": 0,
                    "scores_written": 0,
                    "elapsed_s": 0.0,
                }

            candidate_post_ids = {c["post_id"] for c in candidates}

            # 2. 활성 사용자 목록
            user_ids = await affinity_models.get_active_user_ids(
                lookback_days=_SIGNAL_LOOKBACK_DAYS,
            )
            logger.info(
                "피드 배치 시작: 후보 %d개, 사용자 %d명",
                len(candidates),
                len(user_ids),
            )

            # 3. 사용자별 점수 계산
            for user_id in user_ids:
                try:
                    await FeedService._process_user(
                        user_id,
                        candidates,
                        candidate_post_ids,
                    )
                    users_processed += 1
                except Exception:
                    logger.warning(
                        "사용자 %s 추천 점수 계산 실패",
                        user_id,
                        exc_info=True,
                    )

                # 이벤트 루프 양보 (HTTP 요청 블로킹 방지)
                await asyncio.sleep(0)

            elapsed = time.monotonic() - start
            result = {
                "users_processed": users_processed,
                "candidates": len(candidates),
                "elapsed_s": round(elapsed, 2),
            }
            logger.info("피드 배치 완료: %s", result)
            return result

    @staticmethod
    async def _process_user(
        user_id: int,
        candidates: list[dict],
        candidate_post_ids: set[int],
    ) -> None:
        """단일 사용자의 추천 점수를 계산하고 저장합니다."""
        # 신호 수집
        signals = await affinity_models.get_user_signals(
            user_id,
            lookback_days=_SIGNAL_LOOKBACK_DAYS,
        )

        # 프로필 구축
        profile = build_profile(signals)
        if profile.is_empty:
            # 활동이 있지만 태깅/카테고리 없는 사용자 — 점수 생성 불필요
            await affinity_models.delete_stale_scores(user_id, set())
            return

        # 후보 게시글 점수 계산 (자기 게시글 제외)
        scored_rows: list[dict] = []
        for post in candidates:
            if post["author_id"] == user_id:
                continue

            affinity = score_post(
                profile,
                post_tag_ids=post["tag_ids"],
                post_category_id=post["category_id"],
                post_author_id=post["author_id"],
            )

            if affinity <= 0.0:
                continue

            combined = compute_combined_score(affinity, post["hot_score"])
            scored_rows.append(
                {
                    "post_id": post["post_id"],
                    "affinity_score": round(affinity, 6),
                    "hot_score": round(post["hot_score"], 6),
                    "combined_score": round(combined, 6),
                }
            )

        # 점수 순 정렬 후 상위 N개만 저장
        scored_rows.sort(key=lambda r: r["combined_score"], reverse=True)
        scored_rows = scored_rows[:_MAX_SCORES_PER_USER]

        # UPSERT
        if scored_rows:
            await affinity_models.upsert_user_post_scores(user_id, scored_rows)

        # 후보 목록에 없는 오래된 점수 삭제
        valid_ids = {r["post_id"] for r in scored_rows}
        await affinity_models.delete_stale_scores(user_id, valid_ids)
