#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo "=== Sentry Build Pipeline ==="

# Step 1: Python venv
echo "[1/4] Setting up Python virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install --quiet -r requirements.txt
pip freeze > requirements_lock.txt
echo "  Lock file generated: requirements_lock.txt"

# Step 2: Docker/Ollama
echo "[2/4] Starting Ollama LLM backend..."
if command -v docker &> /dev/null && docker compose version &> /dev/null; then
    docker compose up -d
    echo "  Waiting for Ollama to be healthy..."
    timeout 120 bash -c 'until curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; do sleep 2; done'
    echo "  Pulling qwen2.5-coder:7b model..."
    docker compose exec ollama ollama pull qwen2.5-coder:7b
else
    echo "  WARNING: Docker not available, skipping Ollama setup"
fi

# Step 3: Bazel build
echo "[3/4] Running Bazel build..."
bazel build //...

echo "[4/4] Build complete!"
