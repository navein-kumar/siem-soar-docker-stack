#!/bin/bash
# =============================================================
# Wazuh Config File Sync - Single File Sync via inotifywait
# Author: CodeSecure Solutions
# =============================================================

# --- Variables ---
SRC_WORKER="/root/wazuh-siem/wazuh-n8n-cluster/data/worker/ossec/etc/ossec.conf"
DST_WORKER="/root/wazuh-siem/wazuh-n8n-cluster/config/wazuh_cluster/wazuh_worker.conf"

SRC_MASTER="/root/wazuh-siem/wazuh-n8n-cluster/data/master/ossec/etc/ossec.conf"
DST_MASTER="/root/wazuh-siem/wazuh-n8n-cluster/config/wazuh_cluster/wazuh_manager.conf"

SERVICE_NAME="wazuh-conf-sync"
SCRIPT_PATH="/usr/local/bin/wazuh-conf-sync.sh"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}.service"

# --- Install prerequisite ---
if ! command -v inotifywait &>/dev/null; then
    echo "[*] Installing inotify-tools..."
    apt install inotify-tools -y
fi

# --- Write sync script ---
cat > "$SCRIPT_PATH" << EOF
#!/bin/bash

SRC_WORKER="$SRC_WORKER"
DST_WORKER="$DST_WORKER"
SRC_MASTER="$SRC_MASTER"
DST_MASTER="$DST_MASTER"

sync_files() {
    cp "\$SRC_WORKER" "\$DST_WORKER"
    cp "\$SRC_MASTER" "\$DST_MASTER"
    echo "[\$(date '+%Y-%m-%d %H:%M:%S')] Synced"
}

# Initial sync on start
sync_files

inotifywait -m "\$SRC_WORKER" "\$SRC_MASTER" -e modify,create,moved_to |
while read; do
    sync_files
done
EOF

chmod +x "$SCRIPT_PATH"

# --- Write systemd service ---
cat > "$SERVICE_PATH" << EOF
[Unit]
Description=Wazuh config file sync
After=network.target

[Service]
ExecStart=$SCRIPT_PATH
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# --- Enable and start ---
systemctl daemon-reload
systemctl reset-failed "$SERVICE_NAME" 2>/dev/null
systemctl enable --now "$SERVICE_NAME"

echo ""
systemctl status "$SERVICE_NAME" --no-pager