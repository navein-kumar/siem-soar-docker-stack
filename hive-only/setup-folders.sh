#!/bin/bash
# Create data directories for TheHive-only stack

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

# Elasticsearch runs as uid 1000
chown -R 1000:1000 "$DATA_DIR/elasticsearch"

# TheHive runs as uid 1000 (thehive user)
chown -R 1000:1000 "$DATA_DIR/thehive"

# MinIO runs as uid 1000
chown -R 1000:1000 "$DATA_DIR/minio"

chmod -R 750 "$DATA_DIR"

echo "Done. Folders ready."
