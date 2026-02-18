#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VERSION="0.1.0"
DIST_DIR="$PROJECT_DIR/dist"
STAGING_DIR="$DIST_DIR/sentry-$VERSION"

echo "=== Packaging Sentry $VERSION ==="

# Clean previous build
rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR/scripts"

# Copy Python package (exclude __pycache__, .pyc)
echo "[1/5] Copying Python source..."
rsync -a \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    "$PROJECT_DIR/sentry/" "$STAGING_DIR/sentry/"

# Copy requirements
echo "[2/5] Copying requirements..."
cp "$PROJECT_DIR/requirements.txt" "$STAGING_DIR/"
cp "$PROJECT_DIR/requirements_lock.txt" "$STAGING_DIR/"

# Copy default config
echo "[3/5] Copying default config..."
cp "$PROJECT_DIR/config.yaml" "$STAGING_DIR/"

# Copy install script
echo "[4/5] Copying install script..."
cp "$PROJECT_DIR/scripts/install.sh" "$STAGING_DIR/scripts/"

# Create tarball
echo "[5/5] Creating tarball..."
tar -czf "$DIST_DIR/sentry-$VERSION.tar.gz" -C "$DIST_DIR" "sentry-$VERSION"

# Clean staging directory
rm -rf "$STAGING_DIR"

echo "=== Package created: dist/sentry-$VERSION.tar.gz ==="
