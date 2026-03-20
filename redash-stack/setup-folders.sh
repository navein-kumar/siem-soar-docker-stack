#!/bin/bash
set -e
BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="$BASE_DIR/data"

echo "Creating Redash data directories..."
mkdir -p "$DATA_DIR/postgres" "$DATA_DIR/redis"
chmod -R 750 "$DATA_DIR"
echo "Done."
