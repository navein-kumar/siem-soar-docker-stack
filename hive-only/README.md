# TheHive Only - Docker Deployment

Lightweight incident response stack with TheHive 5 only — no Cortex, no MISP.
For clients who need incident logging and case management without threat intelligence or analysis engines.

## Architecture

| Service | Image | Port | Purpose |
|---|---|---|---|
| TheHive | strangebee/thehive:5.2 | 8444 (HTTPS) | Incident response platform |
| Elasticsearch | elasticsearch:7.17.15 | internal | Search backend |
| Cassandra | cassandra:4.1 | internal | TheHive database |
| MinIO | minio/minio:latest | internal | S3 file storage |
| Nginx | nginx:alpine | 8444 | SSL reverse proxy |

## Prerequisites

- Docker and Docker Compose
- Minimum 4GB RAM (recommended 6GB+)
- `vm.max_map_count=262144` for Elasticsearch

```bash
sudo sysctl -w vm.max_map_count=262144
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf
```

## Deployment

```bash
# 1. Create data directories
chmod +x setup-folders.sh
sudo bash setup-folders.sh

# 2. Generate self-signed SSL certs (if not already present)
mkdir -p config/nginx/ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout config/nginx/ssl/selfsigned.key \
  -out config/nginx/ssl/selfsigned.crt \
  -subj "/CN=thehive"

# 3. Start the stack
docker-compose up -d

# 4. Verify
docker-compose ps
```

## Access

| Service | URL | Default Credentials |
|---|---|---|
| TheHive | `https://<IP>:8444` | admin@thehive.local / secret |

> Uses self-signed SSL certificate via nginx reverse proxy.

## Memory Usage

| Service | Memory Limit |
|---|---|
| Cassandra | 2GB (heap: 1GB) |
| Elasticsearch | 2GB (JVM: 512MB) |
| TheHive | 2GB (JVM: 1GB) |
| MinIO | ~256MB |
| **Total** | **~6GB** |

## Data Persistence

All data in `./data/` using bind mounts:

```
data/
├── cassandra/          # TheHive database
├── elasticsearch/      # Search indices
├── minio/              # S3 file storage
└── thehive/            # TheHive data, files, logs
```

## Integration with Wazuh

This stack works with the Wazuh SIEM stack:
- **Wazuh** sends alerts to **TheHive** for incident tracking
- **N8N** orchestrates SOAR workflows between Wazuh and TheHive
