"""평판 시스템 Pydantic 스키마."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ReputationEventResponse(BaseModel):
    id: int
    event_type: str
    points: int
    source_type: str | None
    source_id: int | None
    is_backfill: bool
    created_at: datetime


class BadgeResponse(BaseModel):
    badge_id: int
    name: str
    description: str
    icon: str
    category: str
    earned_at: datetime | None = None


class BadgeDefinitionResponse(BaseModel):
    id: int
    name: str
    description: str
    icon: str
    category: str
    trigger_type: str
    trigger_threshold: int
    points_awarded: int


class TrustLevelResponse(BaseModel):
    level: int
    name: str
    min_reputation: int
    description: str
