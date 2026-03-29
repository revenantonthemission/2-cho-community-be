"""diff 엔진 단위 테스트."""

from modules.wiki.diff_engine import compute_diff


def test_no_changes():
    """동일 내용은 모든 라인이 equal이다."""
    result = compute_diff("hello\nworld", "hello\nworld")
    assert all(c["type"] == "equal" for c in result)
    assert len(result) == 2


def test_insertion():
    """새 라인 추가 시 insert 타입이 포함된다."""
    result = compute_diff("line1\nline3", "line1\nline2\nline3")
    types = [c["type"] for c in result]
    assert "insert" in types


def test_deletion():
    """라인 삭제 시 delete 타입이 포함된다."""
    result = compute_diff("line1\nline2\nline3", "line1\nline3")
    types = [c["type"] for c in result]
    assert "delete" in types


def test_replacement():
    """라인 변경 시 delete와 insert가 모두 포함된다."""
    result = compute_diff("old line", "new line")
    types = [c["type"] for c in result]
    assert "delete" in types and "insert" in types


def test_empty_to_content():
    """빈 문자열에서 내용 추가."""
    result = compute_diff("", "new content")
    assert any(c["type"] == "insert" for c in result)


def test_content_to_empty():
    """내용에서 빈 문자열로."""
    result = compute_diff("old content", "")
    assert any(c["type"] == "delete" for c in result)


def test_line_numbers_correct():
    """라인 번호가 1부터 시작하고 올바르게 매핑된다."""
    result = compute_diff("a\nb\nc", "a\nb\nc")
    for i, change in enumerate(result):
        assert change["old_line"] == i + 1
        assert change["new_line"] == i + 1
