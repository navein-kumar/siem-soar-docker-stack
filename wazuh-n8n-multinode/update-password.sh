#!/bin/bash
# Post-deploy script: Apply admin password to Wazuh indexer security config
# Run AFTER: docker compose up -d (wait ~30s for indexer to be ready)
#
# Usage: bash update-password.sh
#
# This applies the bcrypt hash from internal_users.yml to the running indexer.
# Only needs to run once after fresh deployment or password change.

set -e

echo "============================================"
echo "  Wazuh Indexer Password Update (Multinode)"
echo "============================================"

# Wait for indexer to be ready
INDEXER="wazuh1.indexer"
CONTAINER=$(docker compose ps 2>/dev/null | grep -i 'indexer' | head -1 | awk '{print $1}')

if [ -z "$CONTAINER" ]; then
  echo "ERROR: No indexer container found. Is docker compose up?"
  exit 1
fi
echo "Found indexer container: $CONTAINER"

echo ""
echo "[1/3] Waiting for indexer to be ready..."
for i in $(seq 1 30); do
  if docker exec "$CONTAINER" curl -sk -u admin:SecretPassword@123 https://localhost:9200 >/dev/null 2>&1; then
    echo "  Indexer is ready (new password already works)!"
    echo "  Password already applied. Nothing to do."
    exit 0
  fi
  if docker exec "$CONTAINER" curl -sk -u admin:SecretPassword https://localhost:9200 >/dev/null 2>&1; then
    echo "  Indexer is ready (old password still active)."
    break
  fi
  echo "  Waiting... ($i/30)"
  sleep 5
done

echo ""
echo "[2/3] Applying security config to indexer..."

# Set environment variables for securityadmin
docker exec "$CONTAINER" bash -c '
  export JAVA_HOME=/usr/share/wazuh-indexer/jdk
  CONFIG_DIR=/usr/share/wazuh-indexer
  CACERT=$CONFIG_DIR/certs/root-ca.pem
  CERT=$CONFIG_DIR/certs/admin.pem
  KEY=$CONFIG_DIR/certs/admin-key.pem

  echo "  Running securityadmin.sh..."
  bash $CONFIG_DIR/plugins/opensearch-security/tools/securityadmin.sh \
    -cd $CONFIG_DIR/opensearch-security/ \
    -nhnv \
    -cacert $CACERT \
    -cert $CERT \
    -key $KEY \
    -p 9200 \
    -icl
'

echo ""
echo "[3/3] Verifying new password..."
if docker exec "$CONTAINER" curl -sk -u admin:SecretPassword@123 https://localhost:9200 >/dev/null 2>&1; then
  echo "  SUCCESS: Admin password updated to SecretPassword@123"
else
  echo "  WARNING: Password verification failed. Check logs."
  exit 1
fi

echo ""
echo "============================================"
echo "  Password update complete!"
echo "  admin / SecretPassword@123"
echo "============================================"
echo ""
echo "NOTE: Restart manager and dashboard to use new password:"
echo "  docker compose restart wazuh.master wazuh.worker wazuh.dashboard"
