"""위키 리비전 diff 엔진 (difflib 기반)."""

import difflib


def compute_diff(old_content: str, new_content: str) -> list[dict]:
    """두 텍스트 간 라인 단위 diff를 구조화된 리스트로 반환."""
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)

    changes: list[dict] = []
    matcher = difflib.SequenceMatcher(None, old_lines, new_lines)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for idx, line in enumerate(old_lines[i1:i2]):
                changes.append(
                    {
                        "type": "equal",
                        "content": line.rstrip("\n"),
                        "old_line": i1 + idx + 1,
                        "new_line": j1 + idx + 1,
                    }
                )
        elif tag == "delete":
            for idx, line in enumerate(old_lines[i1:i2]):
                changes.append(
                    {
                        "type": "delete",
                        "content": line.rstrip("\n"),
                        "old_line": i1 + idx + 1,
                    }
                )
        elif tag == "insert":
            for idx, line in enumerate(new_lines[j1:j2]):
                changes.append(
                    {
                        "type": "insert",
                        "content": line.rstrip("\n"),
                        "new_line": j1 + idx + 1,
                    }
                )
        elif tag == "replace":
            for idx, line in enumerate(old_lines[i1:i2]):
                changes.append(
                    {
                        "type": "delete",
                        "content": line.rstrip("\n"),
                        "old_line": i1 + idx + 1,
                    }
                )
            for idx, line in enumerate(new_lines[j1:j2]):
                changes.append(
                    {
                        "type": "insert",
                        "content": line.rstrip("\n"),
                        "new_line": j1 + idx + 1,
                    }
                )

    return changes
