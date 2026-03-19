#!/bin/bash
# Create data directories for Wazuh single-node + N8N Docker setup

set -e

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="$BASE_DIR/data"

echo "Creating data directories in $DATA_DIR ..."

# Wazuh manager subdirs
mkdir -p \
  "$DATA_DIR/manager/ossec/api/configuration" \
  "$DATA_DIR/manager/ossec/etc" \
  "$DATA_DIR/manager/ossec/logs" \
  "$DATA_DIR/manager/ossec/queue" \
  "$DATA_DIR/manager/ossec/var/multigroups" \
  "$DATA_DIR/manager/ossec/integrations" \
  "$DATA_DIR/manager/ossec/active-response/bin" \
  "$DATA_DIR/manager/ossec/agentless" \
  "$DATA_DIR/manager/ossec/wodles" \
  "$DATA_DIR/manager/filebeat/etc" \
  "$DATA_DIR/manager/filebeat/var"

# Indexer data dir
mkdir -p "$DATA_DIR/indexer"

# Dashboard dirs
mkdir -p "$DATA_DIR/dashboard/config" "$DATA_DIR/dashboard/custom"

# N8N + Redis
mkdir -p "$DATA_DIR/n8n" "$DATA_DIR/redis"

# Indexer runs as uid 1000
chown -R 1000:1000 "$DATA_DIR/indexer"

# Dashboard runs as uid 1000
chown -R 1000:1000 "$DATA_DIR/dashboard"

# N8N runs as uid 1000 (node user)
chown -R 1000:1000 "$DATA_DIR/n8n"

chmod -R 750 "$DATA_DIR"

echo "Done. Folders ready."
