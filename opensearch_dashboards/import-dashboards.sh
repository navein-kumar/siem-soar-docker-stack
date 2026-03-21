#!/bin/bash
# Import pre-built dashboards into OpenSearch Dashboard
# Run AFTER docker compose is up and dashboard is ready
#
# Usage: bash import-dashboards.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NDJSON_FILE="$SCRIPT_DIR/codesec_dashboards.ndjson"

echo "============================================="
echo "  Import OpenSearch Dashboards"
echo "============================================="

if [ ! -f "$NDJSON_FILE" ]; then
  echo "ERROR: $NDJSON_FILE not found"
  exit 1
fi

# Find dashboard container
CONTAINER=$(docker compose ps 2>/dev/null | grep -i 'dashboard' | awk '{print $1}' | head -1)
if [ -z "$CONTAINER" ]; then
  CONTAINER=$(docker ps --format '{{.Names}}' | grep -i 'wazuh.*dashboard' | head -1)
fi

if [ -z "$CONTAINER" ]; then
  echo "ERROR: No dashboard container found"
  exit 1
fi
echo "Dashboard container: $CONTAINER"

# Copy NDJSON into container
docker cp "$NDJSON_FILE" "$CONTAINER:/tmp/dashboards.ndjson"

# Import via saved objects API
echo ""
echo "Importing dashboards..."
RESULT=$(docker exec "$CONTAINER" curl -sk -u "admin:SecretPassword@123" \
  -X POST "https://localhost:5601/api/saved_objects/_import?overwrite=true" \
  -H "osd-xsrf: true" \
  --form file=@/tmp/dashboards.ndjson 2>/dev/null)

# Check result
SUCCESS=$(echo "$RESULT" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('success',False))" 2>/dev/null)
COUNT=$(echo "$RESULT" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('successCount',0))" 2>/dev/null)

if [ "$SUCCESS" = "True" ]; then
  echo "  SUCCESS: Imported $COUNT objects"
else
  echo "  Result: $RESULT"
fi

# Cleanup
docker exec "$CONTAINER" rm -f /tmp/dashboards.ndjson 2>/dev/null

echo ""
echo "============================================="
echo "  Dashboards imported!"
echo "  Open: https://<server>:5601"
echo "  Go to: Dashboard > CS - Security Overview"
echo "============================================="
