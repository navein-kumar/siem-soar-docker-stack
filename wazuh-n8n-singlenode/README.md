# Wazuh Single-Node + N8N SOAR Stack

Lightweight Wazuh SIEM with single indexer node + N8N for SOAR automation. Designed for small customers.

## Architecture

| Service | Image | Port | Purpose |
|---|---|---|---|
| wazuh.manager | wazuh-manager:4.14.4 | 1514, 514/udp, 1515, 55000 | Wazuh manager (single node) |
| wazuh.indexer | wazuh-indexer:4.14.4 | (internal) | OpenSearch single node |
| wazuh.dashboard | wazuh-dashboard:4.14.4 | 443 | Wazuh web UI |
| n8n | n8n:latest | 5678 (webhook), 8443 (GUI) | SOAR automation |
| redis | redis:latest | (internal) | N8N queue |
| nginx-n8n | nginx:alpine | 8443 | SSL reverse proxy for N8N |

## Memory: ~3 GB total (vs ~7 GB for multi-node)

## Deploy

```bash
# 1. Increase max_map_count (required for OpenSearch)
sudo sysctl -w vm.max_map_count=262144

# 2. Create folders
chmod +x setup-folders.sh
sudo bash setup-folders.sh

# 3. Generate SSL certs
docker-compose -f generate-indexer-certs.yml run --rm generator

# 4. Start
docker-compose up -d

# 5. Update wazuh_manager.conf with your server IP and n8n webhook ID
#    Edit: config/wazuh_cluster/wazuh_manager.conf
#    Change: CHANGE_ME_SERVER_IP and CHANGE_ME_WEBHOOK_ID
#    Restart: docker-compose restart wazuh.manager
```

## Default Credentials

| Service | Username | Password |
|---|---|---|
| Wazuh Dashboard | admin | SecretPassword |
| Wazuh API | wazuh-wui | MyS3cr37P450r.*- |
| N8N | (setup on first login) | - |
