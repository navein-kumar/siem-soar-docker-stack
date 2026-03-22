# Codesecure Report Engine v1.0

Web-based security report builder for Wazuh SIEM. Create, customize, and generate PDF/Excel reports with visual query builder.

## Quick Start

```bash
# 1. Clone
git clone https://github.com/navein-kumar/siem-soar-docker-stack.git
cd siem-soar-docker-stack/report-engine-v2

# 2. Configure OpenSearch connection
# Edit docker-compose.yml environment variables:
#   OPENSEARCH_URL, OPENSEARCH_USER, OPENSEARCH_PASS

# 3. Deploy
docker-compose up -d

# Access at http://your-server:8447
```

## Architecture

```
Browser :8447 → Nginx → FastAPI :8000 → OpenSearch
                                      → Gotenberg (PDF)
                                      → SQLite (config)
```

## File Structure

```
report-engine-v2/
├── docker-compose.yml           # Stack: backend + gotenberg + nginx
├── backend/
│   ├── Dockerfile               # Python 3.11 slim
│   ├── requirements.txt         # Dependencies
│   ├── config.py                # Environment config
│   ├── main.py                  # FastAPI routes (all API endpoints)
│   ├── database.py              # SQLite CRUD (templates, widgets, reports)
│   ├── opensearch_client.py     # OpenSearch connection + field discovery
│   ├── pdf_generator.py         # Security report PDF (daily/weekly/monthly)
│   ├── inventory_report.py      # IT Asset Inventory PDF
│   ├── inventory_excel.py       # Inventory Excel export (scroll API)
│   └── opensearch_query*.json   # OpenSearch aggregation templates
├── frontend/
│   ├── index.html               # HTML structure only
│   ├── css/styles.css           # All styles
│   └── js/
│       ├── app.js               # Init, tabs, globals
│       ├── query.js             # Query builder, filters, charts
│       ├── templates.js         # Template editor, sections
│       ├── reports.js           # Report generation, archive
│       ├── widgets.js           # Widget gallery
│       └── utils.js             # Toast, helpers
└── nginx/nginx.conf             # Reverse proxy config
```

## Features

- **Query Builder** — Visual filter builder with field autocomplete from OpenSearch
- **Chart Types** — Bar, horizontal bar, donut, pie, line, polar area, radar, gradient area, table
- **10 Pre-built Templates** — Daily, Weekly, Monthly, Incident, Compliance, MITRE, Auth, Vuln, FIM, Inventory
- **Template Editor** — Drag sections, customize cover page, colors, logo, period
- **PDF Generation** — Enterprise-grade reports via Gotenberg (matches N8N workflow quality)
- **Excel Export** — Full inventory data export with scroll API (unlimited rows)
- **Async Jobs** — Background generation with progress tracking
- **Report Archive** — Download, delete, bulk delete

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/health | OpenSearch connection check |
| GET | /api/fields | Field discovery from index mapping |
| GET | /api/fields/{field}/values | Top values for autocomplete |
| POST | /api/query | Run filtered query |
| POST | /api/aggregate | Aggregation with chart-ready output |
| GET/POST/PUT/DELETE | /api/templates | Template CRUD |
| GET/POST/DELETE | /api/widgets | Widget CRUD |
| GET/DELETE | /api/reports | Report archive |
| POST | /api/generate/quick | Quick PDF report |
| POST | /api/generate/inventory | Inventory PDF |
| POST | /api/generate/inventory/excel/async | Async Excel export |
| GET | /api/jobs/{id} | Job status polling |
| POST | /api/generate/{tid} | Template-based PDF |
| GET | /api/agents | List all agents |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| OPENSEARCH_URL | https://wazuh.indexer:9200 | OpenSearch endpoint |
| OPENSEARCH_USER | admin | OpenSearch username |
| OPENSEARCH_PASS | SecretPassword@123 | OpenSearch password |
| OPENSEARCH_INDEX | wazuh-alerts-* | Alert index pattern |
| GOTENBERG_URL | http://gotenberg:3000 | Gotenberg PDF service |
| EXCEL_MAX_ROWS | 200000 | Max rows per Excel sheet |
| REQUEST_TIMEOUT | 600 | Nginx proxy timeout (seconds) |

## Editing Guide

| To change... | Edit this file |
|--------------|----------------|
| API endpoints | `backend/main.py` |
| PDF report layout | `backend/pdf_generator.py` |
| Inventory report | `backend/inventory_report.py` |
| Excel columns | `backend/inventory_excel.py` |
| OpenSearch queries | `backend/opensearch_query*.json` |
| UI layout/HTML | `frontend/index.html` |
| Styles | `frontend/css/styles.css` |
| Query builder logic | `frontend/js/query.js` |
| Template editor | `frontend/js/templates.js` |
| Chart rendering | `frontend/js/query.js` (renderChart function) |
| Widget gallery | `frontend/js/widgets.js` |
