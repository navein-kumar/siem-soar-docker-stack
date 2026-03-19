# SIEM + SOAR + CTI - Docker Stack

Complete security operations stack running on Docker.

```
wazuh-n8n-multinode/          Wazuh SIEM (multi-node) + N8N SOAR    [Enterprise]
wazuh-n8n-singlenode/         Wazuh SIEM (single-node) + N8N SOAR   [Small clients]
hive-cortex-misp-stack/       TheHive IR + Cortex + MISP CTI
```

## Which Wazuh Stack?

| Stack | Indexers | Manager | RAM | Use case |
|---|---|---|---|---|
| **[wazuh-n8n-multinode](wazuh-n8n-multinode/)** | 3 (HA cluster) | Master + Worker | ~5 GB | Enterprise, 100+ agents, fault tolerance |
| **[wazuh-n8n-singlenode](wazuh-n8n-singlenode/)** | 1 | 1 Manager | ~2 GB | Small clients, <50 agents, dev/testing |

Both include N8N SOAR with Redis, SSL reverse proxy, and webhook integration.

## Port Map

| Port | Service | Protocol |
|---|---|---|
| 443 | Wazuh Dashboard | HTTPS |
| 8443 | N8N (GUI) | HTTPS |
| 8444 | TheHive | HTTPS |
| 8445 | Cortex | HTTPS |
| 8446 | MISP | HTTPS |
| 5678 | N8N (Webhooks) | HTTP |
| 1514 | Wazuh Agent (TCP) | TCP |
| 514 | Syslog (UDP) | UDP |
| 1515 | Wazuh Registration | TCP |
| 55000 | Wazuh API | HTTPS |

## Quick Deploy

### 1. Clone

```bash
git clone https://github.com/navein-kumar/siem-soar-docker-stack.git
cd siem-soar-docker-stack
```

### 2a. Deploy Wazuh Multi-Node (Enterprise)

```bash
cd wazuh-n8n-multinode

chmod +x setup-folders.sh
sudo bash setup-folders.sh

docker-compose -f generate-indexer-certs.yml run --rm generator
docker-compose up -d
```

### 2b. Deploy Wazuh Single-Node (Small Client)

```bash
cd wazuh-n8n-singlenode

chmod +x setup-folders.sh
sudo bash setup-folders.sh

docker-compose -f generate-indexer-certs.yml run --rm generator
docker-compose up -d
```

### 3. Deploy TheHive + Cortex + MISP (Optional)

```bash
cd ../hive-cortex-misp-stack

chmod +x setup-folders.sh
sudo bash setup-folders.sh

docker-compose up -d
```

### 4. Verify

```bash
# Wazuh stack
curl -sk https://localhost:443 -w '%{http_code}\n' -o /dev/null     # Wazuh Dashboard
curl -sk https://localhost:8443/healthz                               # N8N

# CTI stack
curl -sk https://localhost:8444 -w '%{http_code}\n' -o /dev/null     # TheHive
curl -sk https://localhost:8445 -w '%{http_code}\n' -o /dev/null     # Cortex
curl -sk https://localhost:8446 -w '%{http_code}\n' -o /dev/null     # MISP
```

## Default Credentials

| Service | Username | Password |
|---|---|---|
| Wazuh Dashboard | admin | SecretPassword |
| Wazuh API | wazuh-wui | MyS3cr37P450r.*- |
| TheHive | admin@thehive.local | secret |
| MISP | admin@admin.test | admin |
| Cortex | (setup on first login) | - |
| N8N | (setup on first login) | - |

> Change all default passwords after first login.

## Architecture

### Multi-Node (Enterprise)

```
                    Internet / Agents
                          |
              +-----------+-----------+
              |                       |
         [Nginx LB]            [Nginx SSL]
         1514 / 514            8443 (N8N GUI)
              |
    +---------+---------+
    |                   |
[Wazuh Master]    [Wazuh Worker]
    |
[Wazuh Indexer x3]  -->  [Wazuh Dashboard :443]
    |
    +--- alerts ---> [N8N :5678 webhook] ---> [Cortex :8445]
                                                   |
                     [TheHive :8444] <-------------+
                          |
                     [MISP :8446]  (threat intel feeds)
```

### Single-Node (Small Client)

```
              Internet / Agents
                    |
              [Wazuh Manager]
              1514 / 514 / 1515
                    |
              [Wazuh Indexer]  -->  [Wazuh Dashboard :443]
                    |
                    +--- alerts ---> [N8N :5678 webhook]
                                          |
                                    [Nginx SSL :8443]
```

## Memory Requirements

| Stack | Component | Multi-Node | Single-Node |
|---|---|---|---|
| **Wazuh** | Indexer | 3 GB (x3) | 1 GB (x1) |
| | Manager | 1 GB (master+worker) | 512 MB |
| | Dashboard | 512 MB | 512 MB |
| | N8N + Redis | 512 MB | 512 MB |
| **CTI** | Cassandra | 2 GB | 2 GB |
| | Elasticsearch | 2 GB | 2 GB |
| | TheHive | 2 GB | 2 GB |
| | Cortex | 1 GB | 1 GB |
| | MISP + MariaDB | 1 GB | 1 GB |
| | **Total** | **~13 GB** | **~11 GB** |

> Multi-Node: 16 GB RAM minimum | Single-Node: 12 GB RAM minimum

## Stack Details

- [Wazuh Multi-Node + N8N](wazuh-n8n-multinode/) - Multi-node indexer cluster, agent load balancer, N8N SOAR
- [Wazuh Single-Node + N8N](wazuh-n8n-singlenode/) - Single indexer, single manager, N8N SOAR
- [TheHive + Cortex + MISP](hive-cortex-misp-stack/) - Incident response, analysis engine, threat intelligence
