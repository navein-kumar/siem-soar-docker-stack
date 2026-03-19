# Wazuh Multi-Node + N8N SOAR - Docker Deployment

## Architecture

| Service | Image | Port | Purpose |
|---|---|---|---|
| wazuh.master | wazuh-manager:4.14.3 | 1515, 514/udp, 55000 | Wazuh manager (master node) |
| wazuh.worker | wazuh-manager:4.14.3 | - | Wazuh manager (worker node) |
| wazuh1.indexer | wazuh-indexer:4.14.3 | 9200 | OpenSearch indexer node 1 |
| wazuh2.indexer | wazuh-indexer:4.14.3 | - | OpenSearch indexer node 2 |
| wazuh3.indexer | wazuh-indexer:4.14.3 | - | OpenSearch indexer node 3 |
| wazuh.dashboard | wazuh-dashboard:4.14.3 | 443 | Wazuh web dashboard |
| nginx | nginx:stable | 1514 | Load balancer for agent connections |
| n8n | n8n:latest | - | SOAR automation engine |
| redis | redis:latest | - | N8N queue backend |
| nginx-n8n | nginx:alpine | 8080 | Reverse proxy for N8N (SSL) |

## Prerequisites

- Docker & Docker Compose installed
- Minimum 8GB RAM (3GB indexers + 2GB managers + rest)
- Root access on the server

## Deployment Steps

### Step 1: Copy files to server

```bash
scp -r . user@server:/opt/wazuh
ssh user@server
cd /opt/wazuh
```

### Step 2: Set vm.max_map_count (required for OpenSearch)

```bash
sudo sysctl -w vm.max_map_count=262144
```

To make it permanent:
```bash
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf
```

### Step 3: Create data directories

```bash
chmod +x setup-folders.sh
sudo bash setup-folders.sh
```

This creates all bind-mount directories with correct ownership:
- `data/master/` and `data/worker/` - Wazuh manager data
- `data/indexer1/`, `data/indexer2/`, `data/indexer3/` - OpenSearch data
- `data/dashboard/` - Dashboard config and custom assets
- `data/n8n/` - N8N workflow data
- `data/redis/` - Redis persistence

### Step 4: Generate SSL certificates

```bash
docker compose -f generate-indexer-certs.yml run --rm generator
```

This generates all required certs into `config/wazuh_indexer_ssl_certs/`.

### Step 5: Start the stack

```bash
docker compose up -d
```

Wait ~1-2 minutes for all services to initialize (first boot takes longer).

### Step 6: Verify deployment

Check all containers are running:
```bash
docker compose ps
```

Check indexer cluster health (should be `green`):
```bash
curl -sk -u admin:SecretPassword https://localhost:9200/_cluster/health?pretty
```

Check master logs for errors:
```bash
docker compose logs --tail=30 wazuh.master
```

## Access URLs

| UI | URL | Credentials |
|---|---|---|
| Wazuh Dashboard | `https://<SERVER_IP>:443` | admin / SecretPassword |
| Wazuh API | `https://<SERVER_IP>:55000` | wazuh-wui / MyS3cr37P450r.*- |
| N8N | `https://<SERVER_IP>:8080` | (set on first login) |

## Common Operations

### Restart a single service
```bash
docker compose restart wazuh.master
```

### View logs
```bash
docker compose logs -f wazuh.master
docker compose logs -f n8n
```

### Edit Wazuh config
Config files are bind-mounted locally. Edit and restart:
```bash
vim data/master/ossec/etc/ossec.conf
docker compose restart wazuh.master
```

### Stop everything
```bash
docker compose down
```

### Full reset (destroys all data)
```bash
docker compose down
sudo rm -rf data/
sudo bash setup-folders.sh
docker compose -f generate-indexer-certs.yml run --rm generator
docker compose up -d
```

## Folder Structure

```
.
├── docker-compose.yml
├── generate-indexer-certs.yml
├── setup-folders.sh
├── README.md
├── config/
│   ├── certs.yml                    # Cert generation config
│   ├── nginx/nginx.conf             # Wazuh agent load balancer
│   ├── n8n_nginx/nginx.conf         # N8N reverse proxy
│   ├── n8n_nginx/ssl/               # N8N SSL certs
│   ├── wazuh_cluster/               # Master/worker ossec.conf
│   ├── wazuh_dashboard/             # Dashboard config
│   ├── wazuh_indexer/               # Indexer opensearch.yml
│   └── wazuh_indexer_ssl_certs/     # Generated SSL certs
└── data/                            # Created by setup-folders.sh
    ├── master/ossec/                # Master manager data
    ├── worker/ossec/                # Worker manager data
    ├── indexer1/                    # Indexer node 1 data
    ├── indexer2/                    # Indexer node 2 data
    ├── indexer3/                    # Indexer node 3 data
    ├── dashboard/                   # Dashboard data
    ├── n8n/                         # N8N workflows & credentials
    └── redis/                       # Redis persistence
```

## Troubleshooting

**Containers crash-looping?**
```bash
docker compose logs --tail=50 <service_name>
```

**Indexer cluster not forming?**
```bash
curl -sk -u admin:SecretPassword https://localhost:9200/_cat/nodes?v
```

**Agent can't connect?**
Check nginx LB is forwarding port 1514:
```bash
docker compose logs nginx
```

**N8N SSL error?**
Make sure you're using `https://` on port 8080, not 8000.
