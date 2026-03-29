#!/bin/bash
# Create data directories for Wazuh multi-node Docker setup

set -e

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="$BASE_DIR/data"

echo "Creating data directories in $DATA_DIR ..."

# Wazuh manager subdirs (master + worker)
for NODE in master worker; do
  mkdir -p \
    "$DATA_DIR/$NODE/ossec/api/configuration" \
    "$DATA_DIR/$NODE/ossec/etc" \
    "$DATA_DIR/$NODE/ossec/logs" \
    "$DATA_DIR/$NODE/ossec/queue" \
    "$DATA_DIR/$NODE/ossec/var/multigroups" \
    "$DATA_DIR/$NODE/ossec/integrations" \
    "$DATA_DIR/$NODE/ossec/active-response/bin" \
    "$DATA_DIR/$NODE/ossec/agentless" \
    "$DATA_DIR/$NODE/ossec/wodles" \
    "$DATA_DIR/$NODE/filebeat/etc" \
    "$DATA_DIR/$NODE/filebeat/var"
done

# Indexer data dir (single indexer)
mkdir -p "$DATA_DIR/indexer1"

# Dashboard dirs
mkdir -p "$DATA_DIR/dashboard/config" "$DATA_DIR/dashboard/custom"

# N8N + Redis data dirs
mkdir -p "$DATA_DIR/n8n" "$DATA_DIR/redis"

# Wazuh manager runs as uid 101 (wazuh user)
chown -R 101:101 "$DATA_DIR/master"
chown -R 101:101 "$DATA_DIR/worker"

# Indexer runs as uid 1000 (wazuh-indexer user)
chown -R 1000:1000 "$DATA_DIR/indexer1"

# Dashboard runs as uid 1000
chown -R 1000:1000 "$DATA_DIR/dashboard"

# N8N runs as uid 1000 (node user)
chown -R 1000:1000 "$DATA_DIR/n8n"

chmod -R 750 "$DATA_DIR"

echo "Done. Folders ready."
