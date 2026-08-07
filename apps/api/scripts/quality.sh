#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "==> ruff check"
ruff check .

echo "==> ruff format --check"
ruff format --check .

echo "==> pytest"
pytest

echo "==> mypy (optional)"
mypy config apps

echo "All quality checks passed."
