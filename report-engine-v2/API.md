# Report Engine v2 — Complete API Documentation

**Base URL**: `http://your-server:8447`
**Internal (Docker)**: `http://report-engine-api:8000`
**Version**: v2.0

---

## Table of Contents

1. [Health & System](#1-health--system)
2. [Templates](#2-templates)
3. [Template IDs Reference](#3-template-ids-reference)
4. [PDF Report Generation (v2 Enhanced)](#4-pdf-report-generation-v2-enhanced)
5. [PDF Report Generation (v1 Classic)](#5-pdf-report-generation-v1-classic)
6. [Excel Export (Async)](#6-excel-export-async)
7. [Async Job System](#7-async-job-system)
8. [Report Archive & Cleanup](#8-report-archive--cleanup)
9. [PDF Preview (HTML)](#9-pdf-preview-html)
10. [Query Builder](#10-query-builder)
11. [Widgets](#11-widgets)
12. [Agents](#12-agents)
13. [Period Comparison](#13-period-comparison)
14. [Environment Variables](#14-environment-variables)
15. [Docker Deployment](#15-docker-deployment)
16. [N8N Workflow Integration](#16-n8n-workflow-integration)

---

## 1. Health & System

### Check OpenSearch Connection
```
GET /api/health
```
**Response:**
```json
{
  "status": "ok",
  "opensearch": "7.10.2",
  "cluster": "wazuh-cluster"
}
```

### Discover Index Fields
```
GET /api/fields
GET /api/fields?index=wazuh-alerts-*
```
**Response:**
```json
{
  "fields": ["agent.name", "rule.level", "rule.description", ...]
}
```

### Get Field Values
```
GET /api/fields/{field}/values
```
**Example:** `GET /api/fields/agent.name/values`

---

## 2. Templates

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

### Get Single Template
```
GET /api/templates/{tid}
```

### Update Template
```
PUT /api/templates/{tid}
Content-Type: application/json
(same body as create)
```

### Delete Template
```
DELETE /api/templates/{tid}
```

### Clone Template
```
POST /api/templates/{tid}/clone
```
**Response:** `{"id": "new_template_id"}`

### Bulk Update Company Details (All Templates)
Updates company name, address, logo, colors across ALL templates in one call.
Also updates the **PDF footer** (shows "Company Name | Confidential").
```
PUT /api/templates/bulk/company
Content-Type: application/json

{
  "description": "Your Company Name",
  "client_address": "City, State, Country",
  "logo_url": "https://example.com/logo.png"
}
```
**Response:**
```json
{"message": "Updated 11 templates", "fields_updated": ["description", "client_address", "logo_url"]}
```

**Available fields for bulk update:**

| Field | Description | Example |
|-------|-------------|---------|
| `description` | Company name (cover + footer) | "RBS Wincloud" |
| `client_address` | Address on cover page | "Pune, India" |
| `logo_url` | Logo URL on cover page | "https://..." |
| `cover_color` | Theme color (hex) | "#1B2A4A" |
| `cover_accent` | Accent color (hex) | "#0D7377" |

### Available Sections

| Section Key | Description |
|------------|-------------|
| `executive_summary` | Overview, severity cards, donut chart, timeline, heatmap |
| `top_threats` | Top rules by count with treemap + bar chart |
| `agents_risk` | Agent list with risk gauge + severity breakdown |
| `authentication` | Login success/failure, top users, auth timeline |
| `source_ips` | Top source IPs with geo info |
| `vulnerability` | CVE list, severity distribution |
| `fim` | File integrity changes, top paths |
| `mitre` | ATT&CK tactics/techniques with radar chart |
| `compliance` | PCI-DSS, GDPR, HIPAA, NIST, TSC frameworks |
| `security_events` | All rules sorted by severity (top 50) |

---

## 3. Template IDs Reference

### PDF Report Templates

| # | Template ID | Name | Sections | Recommended Period |
|---|-------------|------|----------|-------------------|
| 1 | `9dda0668` | Daily Security Report | 10 sections | `24h` |
| 2 | `713b33d1` | Weekly Security Report | 10 sections | `7d` |
| 3 | `2ad281f6` | Monthly Security Report | 10 sections | `30d` |
| 4 | `f57e0167` | IT Asset Inventory Report | inventory | N/A |
| 5 | `ed54aebe` | Incident Response Report | threats + auth + IPs | `24h` |
| 6 | `1a08ac2b` | Compliance Report | exec + compliance + events | `24h` |
| 7 | `f749fcee` | Agent Health Report | agents + events | `24h` |
| 8 | `e62bea94` | MITRE ATT&CK Report | exec + mitre + threats | `24h` |
| 9 | `a949a9ab` | Authentication Audit | auth + IPs + events | `24h` |
| 10 | `c934c1a2` | Vulnerability Assessment | vuln + events | `24h` |
| 11 | `4520bcda` | File Integrity Report | FIM + events | `24h` |

### Special Report Types (No Template ID Needed)

| Type | Endpoint | Description |
|------|----------|-------------|
| Quick Report | `/api/generate/v2/quick` | All 10 sections, uses first template's company info |
| Inventory PDF | `/api/generate/v2/inventory` | IT asset inventory from system indices |

### Excel Export Types

| Type | Endpoint | Async | Description |
|------|----------|-------|-------------|
| Security Events | `POST /api/export/security?period=24h` | Yes | All alerts with rule details |
| Auth Events | `POST /api/export/auth?period=24h` | Yes | Authentication success/failure |
| Vulnerability | `POST /api/export/vulnerability` | Yes | CVE and vulnerability data |
| Inventory | `POST /api/generate/inventory/excel/async` | Yes | Full IT asset inventory |
| Inventory (sync) | `POST /api/generate/inventory/excel` | No | Small dataset direct download |

---

## 4. PDF Report Generation (v2 Enhanced)

### Generate from Template
```
POST /api/generate/v2/{template_id}?period={period}
```
**Parameters:**

| Param | Type | Required | Values |
|-------|------|----------|--------|
| `template_id` | path | Yes | See Template IDs table |
| `period` | query | No | `24h` (default), `7d`, `30d`, `90d` |

**Example:**
```bash
curl -X POST "http://localhost:8447/api/generate/v2/9dda0668?period=24h"
```

**Response:**
```json
{
  "id": "abc123",
  "filename": "report_v2_1._Daily_Security_Report_20260322_1741.pdf",
  "size": 1154145,
  "download_url": "/api/reports/abc123/download"
}
```

### Generate Quick Report (All Sections, No Template)
```
POST /api/generate/v2/quick?period=24h
```

### Generate Inventory PDF
```
POST /api/generate/v2/inventory
```

### Download Generated PDF
```
GET /api/reports/{report_id}/download
```

### Full Example: Generate + Download
```bash
# Generate
RESP=$(curl -s -X POST "http://localhost:8447/api/generate/v2/9dda0668?period=24h")
ID=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Download
curl -o daily_report.pdf "http://localhost:8447/api/reports/${ID}/download"
```

---

## 5. PDF Report Generation (v1 Classic)

Same endpoints without `/v2/`:
```
POST /api/generate/quick?period=24h
POST /api/generate/inventory
POST /api/generate/{template_id}?period=24h
```

---

## 6. Excel Export (Async)

All Excel exports are **async** — they return a `job_id` immediately, and you poll for completion.

### Security Events Excel
```
POST /api/export/security?period=24h&agent=AgentName
```
**Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `period` | query | No | `24h` (default), `7d`, `30d` |
| `agent` | query | No | Filter by agent name |

**Response:**
```json
{"job_id": "5c2486a0", "status": "queued"}
```

### Authentication Events Excel
```
POST /api/export/auth?period=24h&agent=AgentName
```

### Vulnerability Excel
```
POST /api/export/vulnerability?agent=AgentName
```

### Inventory Excel (Async)
```
POST /api/generate/inventory/excel/async?agent=AgentName
```

### Inventory Excel (Sync — Small Datasets)
```
POST /api/generate/inventory/excel?agent=AgentName
```
Returns file directly (no job polling needed).

### Full Example: Excel Export + Download
```bash
# 1. Start export
RESP=$(curl -s -X POST "http://localhost:8447/api/export/security?period=24h")
JOB=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")

# 2. Poll until completed
while true; do
  STATUS=$(curl -s "http://localhost:8447/api/jobs/${JOB}" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
  echo "Status: $STATUS"
  [ "$STATUS" = "completed" ] && break
  sleep 5
done

# 3. Download
curl -o security_events.xlsx "http://localhost:8447/api/jobs/${JOB}/download"
```

---

## 7. Async Job System

### Poll Job Status
```
GET /api/jobs/{job_id}
```
**Response (queued):**
```json
{"job_id": "5c2486a0", "status": "queued", "progress": 0, "message": "Starting..."}
```

**Response (processing):**
```json
{"job_id": "5c2486a0", "status": "processing", "progress": 50, "message": "Pulling services..."}
```

**Response (completed):**
```json
{
  "job_id": "5c2486a0",
  "status": "completed",
  "progress": 100,
  "message": "Ready for download",
  "download_url": "/api/jobs/5c2486a0/download",
  "filename": "security_events_All_Agents_Daily_202603.xlsx",
  "size": 1586511
}
```

**Response (failed):**
```json
{"job_id": "5c2486a0", "status": "failed", "progress": 0, "message": "Error: ...", "error": "..."}
```

**Job Status Flow:** `queued` → `processing` → `completed` / `failed`

### Download Completed Job
```
GET /api/jobs/{job_id}/download
```
Returns the Excel file directly.

---

## 8. Report Archive & Cleanup

### List All Archived Reports
```
GET /api/reports?limit=50
```
**Response:**
```json
{
  "reports": [
    {
      "id": "abc123",
      "filename": "report_v2_Daily_20260322.pdf",
      "template_id": "9dda0668",
      "created_at": "2026-03-22 17:41:00"
    }
  ]
}
```

### Download Report
```
GET /api/reports/{report_id}/download
```

### Delete Single Report
```
DELETE /api/reports/{report_id}
```
**Response:** `{"message": "Deleted"}`

### Purge ALL Reports (Cleanup)
Deletes all report files from disk and all DB records.
```
DELETE /api/reports/purge/all
```
**Response:**
```json
{
  "message": "Purged 15 files, freed 22.5 MB",
  "files_deleted": 15,
  "freed_mb": 22.5
}
```

### Auto-Cleanup (via Environment Variable)
Set `CLEANUP_SCHEDULE` in docker-compose:

| Value | Behavior |
|-------|----------|
| `off` | No auto-cleanup (default) |
| `daily` | Purge all reports at midnight every day |
| `weekly` | Purge all reports Sunday midnight |

---

## 9. PDF Preview (HTML)

Renders the report as HTML in the browser (no PDF download). Useful for testing.

### v2 Enhanced Preview
```
GET /api/preview/v2/quick?period=24h
GET /api/preview/v2/inventory
GET /api/preview/v2/{template_id}?period=24h
```

### v1 Classic Preview
```
GET /api/preview/quick?period=24h
GET /api/preview/inventory
GET /api/preview/{template_id}?period=24h
```

**Example:** Open in browser: `http://173.212.233.86:8447/api/preview/v2/9dda0668?period=24h`

---

## 10. Query Builder

### Run Filtered Query
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

**Operators:** `is`, `is_not`, `gte`, `lte`, `contains`, `exists`

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

**Special group_by values:**
- `_date_histogram` — hourly timeline chart
- Any field name — top N values (e.g., `agent.name`, `rule.description`)

**Response:**
```json
{
  "data": [
    {"label": "3", "value": 15234},
    {"label": "5", "value": 8912}
  ],
  "total": 24146,
  "took_ms": 45
}
```

---

## 11. Widgets

Custom saved queries for reuse in templates.

### List Widgets
```
GET /api/widgets
```

### Create Widget
```
POST /api/widgets
Content-Type: application/json

{
  "name": "Top Agents by Volume",
  "description": "agent.name (bar)",
  "query_dsl": {},
  "agg_config": {"field": "agent.name", "size": 10},
  "chart_type": "bar"
}
```

### Delete Widget
```
DELETE /api/widgets/{widget_id}
```

---

## 12. Agents

### List All Agents
```
GET /api/agents
```
**Response:**
```json
{
  "agents": ["IND-db", "IND-web", "US-app", "SG-proxy"]
}
```
Used for agent filter dropdowns in Excel exports and reports.

---

## 13. Period Comparison

### Compare Two Time Periods
```
GET /api/compare?period_a=now-24h&period_b=now-48h/now-24h&agent=AgentName
```

**Parameters:**

| Param | Description | Example |
|-------|-------------|---------|
| `period_a` | Current period | `now-24h`, `now-7d` |
| `period_b` | Previous period | `now-48h/now-24h`, `now-14d/now-7d` |
| `agent` | Filter by agent (optional) | `IND-db` |

---

## 14. Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENSEARCH_URL` | `https://wazuh.indexer:9200` | OpenSearch endpoint |
| `OPENSEARCH_USER` | `admin` | OpenSearch username |
| `OPENSEARCH_PASS` | `SecretPassword@123` | OpenSearch password |
| `OPENSEARCH_INDEX` | `wazuh-alerts-*` | Alert index pattern |
| `GOTENBERG_URL` | `http://gotenberg:3000` | Gotenberg PDF service URL |
| `CLEANUP_SCHEDULE` | `off` | Auto-cleanup: `daily`, `weekly`, `off` |
| `REPORTS_DIR` | `/app/reports` | Report file storage path |
| `DB_PATH` | `/app/data/report_engine.db` | SQLite database path |

---

## 15. Docker Deployment

### Production (Docker Hub Images)
```yaml
# docker-compose.yml
services:
  backend:
    image: navinkr431/report-engine-backend:v2.0
    environment:
      - OPENSEARCH_URL=https://your-opensearch:9200
      - OPENSEARCH_USER=admin
      - OPENSEARCH_PASS=your-password
      - OPENSEARCH_INDEX=wazuh-alerts-*
      - GOTENBERG_URL=http://gotenberg:3000
      - CLEANUP_SCHEDULE=weekly
    volumes:
      - ./data:/app/data
      - ./reports:/app/reports

  gotenberg:
    image: gotenberg/gotenberg:8

  nginx:
    image: navinkr431/report-engine-frontend:v2.0
    ports:
      - "8447:80"
```

```bash
docker-compose pull && docker-compose up -d
```

### First-Time Setup (After Deploy)
```bash
# Update company details across all 11 templates
curl -X PUT "http://localhost:8447/api/templates/bulk/company" \
  -H "Content-Type: application/json" \
  -d '{"description":"Your Company","client_address":"City, Country","logo_url":"https://..."}'
```

### Local Development (Build from Source)
```bash
docker-compose -f docker-compose.local.yml up -d --build
```

---

## 16. N8N Workflow Integration

### Workflow File
`workflow/Report_PDF_Excel_Combined.json` — 4 scheduled rows:

| Row | Schedule | Template ID | Period | Output |
|-----|----------|-------------|--------|--------|
| Daily | Every day 10 AM | `9dda0668` | `24h` | PDF + Excel email |
| Weekly | Every Monday 10 AM | `713b33d1` | `7d` | PDF + Excel email |
| Monthly | 1st of month 10 AM | `2ad281f6` | `30d` | PDF + Excel email |
| Inventory | 1st of month 10 AM | N/A | N/A | PDF + Excel email |

### Config Node Variables
```javascript
const REPORT_ENGINE_URL = 'http://172.17.0.1:8447';  // Docker host
const TEMPLATE_ID = '9dda0668';
const PERIOD = '24h';
const REPORT_EMAIL = 'naveen@codesecure.in';
const CLIENT_NAME = 'Codesecure Solutions';
const CLIENT_ADDRESS = 'Chennai, Tamil Nadu, India';
const LOGO_URL = 'https://codesecure.in/images/codesec-logo1.png';
```

### Workflow Flow
```
Schedule Trigger → Config → [Generate PDF + Start Excel] (parallel)
                           → [Download PDF + Wait → Download Excel]
                           → Merge → Combine Attachments → Send Email
```

**Note:** Use `http://172.17.0.1:8447` (Docker host) or `http://report-engine-api:8000` (same network) depending on your Docker setup.
