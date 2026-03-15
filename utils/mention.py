"""mention: @멘션 파싱 유틸리티."""

import re

MENTION_PATTERN = re.compile(r"@([a-zA-Z0-9_]{3,10})")


def extract_mentions(content: str) -> list[str]:
    """댓글 content에서 @닉네임 목록을 추출합니다.

    Args:
        content: 댓글 본문 텍스트.

    Returns:
        중복 제거된 닉네임 목록 (순서 보존).
    """
    if not content:
        return []
    return list(dict.fromkeys(MENTION_PATTERN.findall(content)))
