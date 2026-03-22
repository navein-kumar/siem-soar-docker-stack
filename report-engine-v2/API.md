# Report Engine v2 — API Documentation

Base URL: `http://your-server:8447`

---

## Health & Connection

### Check OpenSearch Connection
```
GET /api/health
```
```json
{"status": "ok", "opensearch": "7.10.2", "cluster": "wazuh-cluster"}
```

### Discover Index Fields
```
GET /api/fields?index=wazuh-alerts-*
```

---

## Templates

### List All Templates
```
GET /api/templates
```

### Create Template
```
POST /api/templates
Content-Type: application/json

{
  "name": "My Report",
  "description": "Company Name",
  "cover_title": "Security Report",
  "cover_subtitle": "Daily Analysis",
  "cover_color": "#1B2A4A",
  "cover_accent": "#0D7377",
  "logo_url": "https://example.com/logo.png",
  "client_address": "City, Country",
  "sections": ["executive_summary", "top_threats", "agents_risk"]
}
```

### Get / Update / Delete Template
```
GET    /api/templates/{tid}
PUT    /api/templates/{tid}
DELETE /api/templates/{tid}
```

### Clone Template
```
POST /api/templates/{tid}/clone
```

### Bulk Update Company Details (All Templates)
```
PUT /api/templates/bulk/company
Content-Type: application/json

{
  "description": "Your Company Name",
  "client_address": "City, State, Country",
  "logo_url": "https://example.com/logo.png"
}
```
Response:
```json
{"message": "Updated 11 templates", "fields_updated": ["description", "client_address", "logo_url"]}
```

**Available fields for bulk update:**
- `description` — Company name shown on cover page
- `client_address` — Address shown on cover page
- `logo_url` — Logo URL shown on cover page
- `cover_color` — Theme color (hex)
- `cover_accent` — Accent color (hex)

---

## Report Generation

### Available Sections
| Section | Description |
|---------|-------------|
| executive_summary | Overview, severity cards, donut chart, timeline, heatmap |
| top_threats | Top rules by count with treemap + bar chart |
| agents_risk | Agent list with risk gauge + severity breakdown |
| authentication | Login success/failure, top users, auth timeline |
| source_ips | Top source IPs with geo info |
| vulnerability | CVE list, severity distribution |
| fim | File integrity changes, top paths |
| mitre | ATT&CK tactics/techniques with radar chart |
| compliance | PCI-DSS, GDPR, HIPAA, NIST, TSC frameworks |
| security_events | All rules sorted by severity (top 50) |

### Generate v2 PDF (Enhanced)
```
POST /api/generate/v2/{template_id}?period=24h
```
Periods: `24h`, `7d`, `30d`, `90d`

Response:
```json
{
  "id": "abc123",
  "filename": "report_v2_Daily_Security_Report_20260322_1741.pdf",
  "size": 1154145,
  "download_url": "/api/reports/abc123/download"
}
```

### Generate Quick Report (No Template)
```
POST /api/generate/v2/quick?period=24h
```

### Generate Inventory PDF
```
POST /api/generate/v2/inventory
```

### Generate v1 PDF (Classic)
```
POST /api/generate/{template_id}?period=24h
POST /api/generate/quick?period=24h
POST /api/generate/inventory
```

---

## PDF Preview (HTML in Browser)

```
GET /api/preview/v2/{template_id}?period=24h
GET /api/preview/v2/quick?period=24h
GET /api/preview/v2/inventory
```

---

## Excel Exports (Async)

### Security Events Excel
```
POST /api/export/security?period=24h
```
Response:
```json
{"job_id": "xyz789", "status": "queued"}
```

### Authentication Events Excel
```
POST /api/export/auth?period=24h
```

### Vulnerability Excel
```
POST /api/export/vulnerability?period=24h
```

### Inventory Excel
```
POST /api/generate/inventory/excel/async
```

### Poll Job Status
```
GET /api/jobs/{job_id}
```
Response:
```json
{"job_id": "xyz789", "status": "completed", "progress": 100, "download_url": "/api/jobs/xyz789/download"}
```
Statuses: `queued` → `processing` → `completed` / `failed`

### Download Completed Excel
```
GET /api/jobs/{job_id}/download
```

---

## Report Archive

### List Reports
```
GET /api/reports?limit=50
```

### Download Report
```
GET /api/reports/{rid}/download
```

### Delete Single Report
```
DELETE /api/reports/{rid}
```

### Purge ALL Reports (cleanup)
```
DELETE /api/reports/purge/all
```
Response:
```json
{"message": "Purged 15 files, freed 22.5 MB", "files_deleted": 15, "freed_mb": 22.5}
```

---

## Query Builder

### Run Query
```
POST /api/query
Content-Type: application/json

{
  "filters": [
    {"field": "rule.level", "operator": "gte", "value": "12"}
  ],
  "time_from": "now-24h",
  "time_to": "now",
  "size": 100
}
```

### Run Aggregation
```
POST /api/aggregate
Content-Type: application/json

{
  "filters": [],
  "time_from": "now-24h",
  "time_to": "now",
  "group_by": "rule.level",
  "size": 20
}
```

---

## Widgets

### List / Create / Delete
```
GET    /api/widgets
POST   /api/widgets
DELETE /api/widgets/{wid}
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| OPENSEARCH_URL | https://wazuh.indexer:9200 | OpenSearch endpoint |
| OPENSEARCH_USER | admin | Username |
| OPENSEARCH_PASS | SecretPassword@123 | Password |
| OPENSEARCH_INDEX | wazuh-alerts-* | Alert index pattern |
| GOTENBERG_URL | http://gotenberg:3000 | Gotenberg PDF service |
| CLEANUP_SCHEDULE | off | Auto-cleanup: `daily`, `weekly`, `off` |
| REPORTS_DIR | /app/reports | Report file storage path |
| DB_PATH | /app/data/report_engine.db | SQLite database path |

---

## Docker Deployment

### Production (Docker Hub)
```bash
docker-compose pull && docker-compose up -d
```

### First-time Setup
```bash
# Update company details across all templates
curl -X PUT "http://localhost:8447/api/templates/bulk/company" \
  -H "Content-Type: application/json" \
  -d '{"description":"Your Company","client_address":"City, Country","logo_url":"https://..."}'
```

### Local Development
```bash
docker-compose -f docker-compose.local.yml up -d --build
```
