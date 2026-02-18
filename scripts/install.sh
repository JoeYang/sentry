#!/usr/bin/env bash
set -euo pipefail

# Must run as root
if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: This script must be run as root" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
INSTALL_DIR="/opt/sentry"
CONFIG_DIR="/etc/sentry"
LOG_DIR="/var/log/sentry"

echo "=== Sentry Installation ==="

# Step 1: Create system user
echo "[1/6] Creating sentry system user..."
if ! id -u sentry &>/dev/null; then
    useradd --system --no-create-home --shell /usr/sbin/nologin sentry
fi

# Step 2: Create directories
echo "[2/6] Creating directories..."
mkdir -p "$INSTALL_DIR" "$CONFIG_DIR" "$LOG_DIR"
chown sentry:sentry "$LOG_DIR"

# Step 3: Install application source
echo "[3/6] Installing application..."
cp -r "$PROJECT_DIR/sentry/" "$INSTALL_DIR/sentry/"
cp "$PROJECT_DIR/requirements.txt" "$INSTALL_DIR/"
cp "$PROJECT_DIR/requirements_lock.txt" "$INSTALL_DIR/"

# Step 4: Create venv and install dependencies
echo "[4/6] Setting up Python virtual environment..."
python3 -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/.venv/bin/pip" install -r "$INSTALL_DIR/requirements_lock.txt"

# Step 5: Install config
echo "[5/6] Installing configuration..."
if [ ! -f "$CONFIG_DIR/config.yaml" ]; then
    cp "$PROJECT_DIR/config.yaml" "$CONFIG_DIR/config.yaml"
    # Update paths for production
    sed -i 's|audit_log_path:.*|audit_log_path: "/var/log/sentry/audit.jsonl"|' "$CONFIG_DIR/config.yaml"
    sed -i 's|app_log_path:.*|app_log_path: "/var/log/sentry/sentry.log"|' "$CONFIG_DIR/config.yaml"
else
    echo "  Config already exists, not overwriting"
fi
chown -R sentry:sentry "$CONFIG_DIR"

# Step 6: Install systemd service
echo "[6/6] Installing systemd service..."
cat > /etc/systemd/system/sentry.service << 'EOF'
[Unit]
Description=Sentry Linux Monitoring Agent
After=network.target docker.service
Wants=docker.service

[Service]
Type=simple
User=sentry
Group=sentry
WorkingDirectory=/opt/sentry
ExecStart=/opt/sentry/.venv/bin/python -m sentry.main --config /etc/sentry/config.yaml
Restart=on-failure
RestartSec=5

# Security hardening
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
ReadOnlyPaths=/
ReadWritePaths=/var/log/sentry /tmp
PrivateTmp=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
MemoryDenyWriteExecute=yes

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=sentry

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
echo "=== Installation complete ==="
echo "Start with: systemctl start sentry"
echo "Enable at boot: systemctl enable sentry"
