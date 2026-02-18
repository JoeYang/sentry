#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo "=== Sentry Test Suite ==="

# Unit tests (exclude integration)
echo "[1/2] Running unit tests..."
bazel test //... --test_tag_filters=-integration --test_output=errors

# Integration tests (only if Ollama is running)
echo "[2/2] Checking for Ollama (integration tests)..."
if curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "  Ollama detected, running integration tests..."
    bazel test //tests/integration:test_pipeline --test_output=errors
else
    echo "  Ollama not running, skipping integration tests"
fi

echo "=== Tests complete ==="
