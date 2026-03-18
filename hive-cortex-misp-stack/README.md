# TheHive + Cortex + MISP - Docker Deployment

CTI (Cyber Threat Intelligence) and Incident Response stack running on Docker with SSL reverse proxy.

## Architecture

| Service | Image | Port | Purpose |
|---|---|---|---|
| TheHive | strangebee/thehive:5.2 | 8444 (HTTPS) | Incident response platform |
| Cortex | thehiveproject/cortex:3.1.1 | 8445 (HTTPS) | Analysis & response engine |
| MISP | ghcr.io/misp/misp-docker/misp-core:latest | 8446 (HTTPS) | Threat intelligence sharing |
| Elasticsearch | elasticsearch:7.17.15 | internal | Search backend (TheHive + Cortex) |
| Cassandra | cassandra:4.1 | internal | TheHive database |
| MinIO | minio/minio:latest | internal | S3 file storage for TheHive |
| MariaDB | mariadb:10.11 | internal | MISP database |
| Redis (Valkey) | valkey/valkey:7.2 | internal | MISP cache |
| MISP Modules | misp-modules:latest | internal | Enrichment modules |
| Nginx | nginx:alpine | 8444, 8445 | SSL reverse proxy for TheHive + Cortex |

## Prerequisites

- Docker and Docker Compose
- Minimum 8GB RAM (recommended 12GB+)
- `vm.max_map_count=262144` for Elasticsearch

```bash
sudo sysctl -w vm.max_map_count=262144
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf
```

## Deployment

### 1. Clone the repository

```bash
git clone https://github.com/navein-kumar/hive-cortex-misp-docker.git
cd hive-cortex-misp-docker
```

### 2. Create data directories

```bash
chmod +x setup-folders.sh
sudo bash setup-folders.sh
```

### 3. Start the stack

```bash
docker-compose up -d
```

### 4. Verify all services are running

```bash
docker-compose ps
```

## Access URLs

| Service | URL | Default Credentials |
|---|---|---|
| TheHive | `https://<IP>:8444` | admin@thehive.local / secret |
| Cortex | `https://<IP>:8445` | (setup on first login) |
| MISP | `https://<IP>:8446` | admin@admin.test / admin |

> All web services use self-signed SSL certificates via nginx reverse proxy.

## Memory Usage

| Service | Memory Limit |
|---|---|
| Cassandra | 2GB (heap: 1GB) |
| Elasticsearch | 2GB (JVM: 512MB) |
| TheHive | 2GB (JVM: 1GB) |
| Cortex | 1GB |
| MinIO | ~256MB |
| MISP Core | ~512MB |
| MariaDB | ~512MB |

## Data Persistence

All data is stored in `./data/` using bind mounts:

```
data/
├── cassandra/          # TheHive database
├── elasticsearch/      # Search indices
├── minio/              # S3 file storage
├── thehive/            # TheHive data, files, logs
├── cortex/             # Cortex logs
├── misp-core/          # MISP configs, files, logs
├── misp-db/            # MariaDB data
└── misp-redis/         # Redis persistence
```

## Integration with Wazuh + N8N

This stack is designed to work alongside [wazuh-docker-n8n-multinode](https://github.com/navein-kumar/wazuh-docker-n8n-multinode):

- **Wazuh** sends alerts to **TheHive** for incident tracking
- **Cortex** runs analyzers/responders (e.g., trigger N8N webhooks)
- **MISP** shares threat intelligence with Wazuh for IOC detection
- **N8N** orchestrates SOAR workflows between all platforms

## Stopping / Restarting

```bash
# Stop all services
docker-compose down

# Restart (data persists)
docker-compose up -d
```
