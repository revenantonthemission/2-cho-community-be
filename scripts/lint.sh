#!/usr/bin/env bash
# 코드 품질 검사 스크립트
set -euo pipefail

echo "=== Ruff Check ==="
uv run ruff check .

echo ""
echo "=== Ruff Format Check ==="
uv run ruff format --check .

echo ""
echo "=== MyPy ==="
uv run mypy .

echo ""
echo "✅ All quality checks passed"
