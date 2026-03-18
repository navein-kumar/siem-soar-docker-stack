# SIEM + SOAR + CTI - Docker Stack

Complete security operations stack running on Docker.

```
wazuh-n8n-stack/              Wazuh SIEM + N8N SOAR
hive-cortex-misp-stack/       TheHive IR + Cortex + MISP CTI
```

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

### 2. Deploy Wazuh + N8N

```bash
cd wazuh-n8n-stack

# Create folders
chmod +x setup-folders.sh
sudo bash setup-folders.sh

# Generate Wazuh SSL certs
docker-compose -f generate-indexer-certs.yml run --rm generator

# Start
docker-compose up -d
```

### 3. Deploy TheHive + Cortex + MISP

```bash
cd ../hive-cortex-misp-stack

# Create folders
chmod +x setup-folders.sh
sudo bash setup-folders.sh

# Start
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

## Memory Requirements

| Stack | Service | RAM |
|---|---|---|
| **Wazuh** | Indexer x3 | 3 GB |
| | Master + Worker | 1 GB |
| | Dashboard | 512 MB |
| | N8N + Redis | 512 MB |
| **CTI** | Cassandra | 2 GB |
| | Elasticsearch | 2 GB |
| | TheHive | 2 GB |
| | Cortex | 1 GB |
| | MISP + MariaDB | 1 GB |
| | **Total** | **~13 GB** |

> Recommended: 16 GB RAM minimum for running both stacks.

## Stack Details

- [Wazuh + N8N Stack](wazuh-n8n-stack/) - SIEM with multi-node indexer cluster, agent load balancer, and N8N SOAR
- [TheHive + Cortex + MISP Stack](hive-cortex-misp-stack/) - Incident response, analysis engine, and threat intelligence
