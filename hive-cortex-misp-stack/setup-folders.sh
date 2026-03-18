#!/bin/bash
# Create data directories for TheHive + Cortex + MISP stack

set -e

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="$BASE_DIR/data"

echo "Creating data directories in $DATA_DIR ..."

# Cassandra
mkdir -p "$DATA_DIR/cassandra/data" "$DATA_DIR/cassandra/logs"

# Elasticsearch
mkdir -p "$DATA_DIR/elasticsearch/data" "$DATA_DIR/elasticsearch/logs"

# MinIO
mkdir -p "$DATA_DIR/minio"

# TheHive
mkdir -p "$DATA_DIR/thehive/data" "$DATA_DIR/thehive/files" "$DATA_DIR/thehive/index" "$DATA_DIR/thehive/logs"

# Cortex
mkdir -p "$DATA_DIR/cortex/logs"

# MISP Redis
mkdir -p "$DATA_DIR/misp-redis"

# MISP MariaDB
mkdir -p "$DATA_DIR/misp-db"

# MISP Core
mkdir -p "$DATA_DIR/misp-core/configs" "$DATA_DIR/misp-core/logs" "$DATA_DIR/misp-core/files" "$DATA_DIR/misp-core/ssl" "$DATA_DIR/misp-core/gnupg"

# Elasticsearch runs as uid 1000
chown -R 1000:1000 "$DATA_DIR/elasticsearch"

# TheHive runs as uid 1000 (thehive user)
chown -R 1000:1000 "$DATA_DIR/thehive"

# MinIO runs as uid 1000
chown -R 1000:1000 "$DATA_DIR/minio"

# Cortex runs as uid 1000
chown -R 1000:1000 "$DATA_DIR/cortex"

# MISP core runs as www-data (uid 33)
chown -R 33:33 "$DATA_DIR/misp-core"

# MariaDB runs as mysql (uid 999)
chown -R 999:999 "$DATA_DIR/misp-db"

chmod -R 750 "$DATA_DIR"

# Cortex needs docker socket access
echo "NOTE: Run 'chmod 666 /var/run/docker.sock' if Cortex analyzers fail"

echo "Done. Folders ready."
