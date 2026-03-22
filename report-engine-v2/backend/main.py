"""Report Engine API - FastAPI backend"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List, Any
import json, os, uuid, threading
import config, database, opensearch_client
from pdf_generator import generate_report, generate_quick_report
from pdf_generator_v2 import generate_report_v2, generate_quick_report_v2
from inventory_report import generate_inventory_report
from inventory_excel import generate_inventory_excel
from security_excel import export_security_events, export_auth_events, export_vulnerability
from comparison import compare_periods

app = FastAPI(title="Codesec Report Engine", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Async job tracker
jobs = {}  # {job_id: {status, progress, message, result, error}}

@app.on_event("startup")
def startup():
    database.init_db()
    os.makedirs(config.REPORTS_DIR, exist_ok=True)

# --- FIELD DISCOVERY ---
@app.get("/api/fields")
def get_fields(index: Optional[str] = None):
    try:
        fields = opensearch_client.discover_fields(index)
        return {"fields": fields, "total": len(fields)}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/fields/{field}/values")
def get_field_values(field: str, size: int = 20):
    try:
        values = opensearch_client.get_field_values(field, size=size)
        return {"field": field, "values": values}
    except Exception as e:
        raise HTTPException(500, str(e))

# --- QUERY ENGINE ---
class QueryRequest(BaseModel):
    query: Optional[dict] = None
    time_from: Optional[str] = "now-24h"
    time_to: Optional[str] = "now"

class AggRequest(BaseModel):
    query: Optional[dict] = None
    time_from: Optional[str] = "now-24h"
    time_to: Optional[str] = "now"
    group_by: str
    metric: str = "count"
    metric_field: Optional[str] = None
    size: int = 10

@app.post("/api/query")
def run_query(req: QueryRequest):
    try:
        must = []
        if req.query:
            must.append(req.query)
        must.append({"range": {"timestamp": {"gte": req.time_from, "lte": req.time_to}}})
        result = opensearch_client.run_query({"bool": {"must": must}})
        return {"total": result["hits"]["total"]["value"], "took_ms": result["took"]}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/aggregate")
def run_aggregation(req: AggRequest):
    try:
        must = []
        if req.query:
            must.append(req.query)
        must.append({"range": {"timestamp": {"gte": req.time_from, "lte": req.time_to}}})
        query_dsl = {"bool": {"must": must}}

        if req.group_by == "_date_histogram":
            aggs = {"result": {"date_histogram": {"field": "timestamp", "calendar_interval": "1h"}}}
        else:
            aggs = {"result": {"terms": {"field": req.group_by, "size": req.size, "order": {"_count": "desc"}}}}

        result = opensearch_client.run_aggregation(query_dsl, aggs)
        buckets = result["aggregations"]["result"]["buckets"]
        data = [{"label": str(b.get("key_as_string", b["key"])), "value": b["doc_count"]} for b in buckets]
        return {"data": data, "total": result["hits"]["total"]["value"], "took_ms": result["took"]}
    except Exception as e:
        raise HTTPException(500, str(e))

# --- TEMPLATES ---
class TemplateData(BaseModel):
    name: str
    description: Optional[str] = ""
    cover_title: Optional[str] = "Security Report"
    cover_subtitle: Optional[str] = ""
    cover_color: Optional[str] = "#1B2A4A"
    cover_accent: Optional[str] = "#0D7377"
    logo_url: Optional[str] = ""
    client_address: Optional[str] = ""
    sections: Optional[List[Any]] = []

@app.get("/api/templates")
def list_templates():
    return {"templates": database.get_templates()}

@app.post("/api/templates")
def create_template(t: TemplateData):
    return {"id": database.create_template(t.dict())}

@app.get("/api/templates/{tid}")
def get_template(tid: str):
    t = database.get_template(tid)
    if not t:
        raise HTTPException(404, "Not found")
    return t

@app.put("/api/templates/{tid}")
def update_template(tid: str, t: TemplateData):
    database.update_template(tid, t.dict())
    return {"message": "Updated"}

@app.delete("/api/templates/{tid}")
def delete_template(tid: str):
    database.delete_template(tid)
    return {"message": "Deleted"}

@app.post("/api/templates/{tid}/clone")
def clone_template(tid: str):
    new_id = database.clone_template(tid)
    if not new_id:
        raise HTTPException(404, "Not found")
    return {"id": new_id}

# --- WIDGETS ---
class WidgetData(BaseModel):
    name: str
    description: Optional[str] = ""
    query_dsl: Optional[dict] = {}
    agg_config: Optional[dict] = {}
    chart_type: Optional[str] = "table"

@app.get("/api/widgets")
def list_widgets():
    return {"widgets": database.get_widgets()}

@app.post("/api/widgets")
def create_widget(w: WidgetData):
    return {"id": database.save_widget(w.dict())}

@app.delete("/api/widgets/{wid}")
def delete_widget(wid: str):
    db = database.get_db()
    db.execute("DELETE FROM saved_widgets WHERE id=?", (wid,))
    db.commit()
    db.close()
    return {"message": "Deleted"}

# --- REPORTS ---
@app.get("/api/reports")
def list_reports(limit: int = 50):
    return {"reports": database.get_reports(limit)}

@app.get("/api/reports/{rid}/download")
def download_report(rid: str):
    reports = database.get_reports(100)
    report = next((r for r in reports if r["id"] == rid), None)
    if not report:
        raise HTTPException(404, "Not found")
    filepath = os.path.join(config.REPORTS_DIR, report["filename"])
    if not os.path.exists(filepath):
        raise HTTPException(404, "File not found")
    mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if report["filename"].endswith(".xlsx") else "application/pdf"
    return FileResponse(filepath, media_type=mime, filename=report["filename"])

@app.delete("/api/reports/{rid}")
def delete_report(rid: str):
    reports = database.get_reports(100)
    report = next((r for r in reports if r["id"] == rid), None)
    if not report:
        raise HTTPException(404, "Not found")
    # Delete file
    filepath = os.path.join(config.REPORTS_DIR, report["filename"])
    if os.path.exists(filepath):
        os.remove(filepath)
    # Delete DB record
    db = database.get_db()
    db.execute("DELETE FROM reports WHERE id=?", (rid,))
    db.commit()
    db.close()
    return {"message": "Deleted"}

# --- GENERATE ---
@app.post("/api/generate/quick")
async def gen_quick(period: Optional[str] = "24h"):
    result, err = await generate_quick_report(period)
    if err:
        raise HTTPException(500, err)
    return {"download_url": f"/api/reports/{result['id']}/download", **result}

@app.post("/api/generate/inventory")
async def gen_inventory(tid: Optional[str] = None, agent: Optional[str] = None):
    result, err = await generate_inventory_report(tid)
    if err:
        raise HTTPException(500, err)
    return {"download_url": f"/api/reports/{result['id']}/download", **result}

@app.post("/api/generate/inventory/excel")
def gen_inventory_excel_sync(agent: Optional[str] = None):
    """Synchronous Excel export - for small datasets"""
    try:
        result = generate_inventory_excel(agent)
        return FileResponse(result["filepath"], media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename=result["filename"])
    except Exception as e:
        raise HTTPException(500, str(e))

# --- ASYNC JOB SYSTEM ---
def _run_job(job_id, export_fn, label, *args):
    """Generic background worker for any export function"""
    try:
        jobs[job_id]["status"] = "processing"
        jobs[job_id]["progress"] = 10
        jobs[job_id]["message"] = f"Starting {label}..."
        result = export_fn(*args, progress_cb=lambda p, m: _update_job(job_id, p, m))
        rid = database.save_report(None, result["filename"], label, args[0] if args else "All", result["size"])
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["progress"] = 100
        jobs[job_id]["message"] = "Ready for download"
        jobs[job_id]["result"] = {"id": rid, "filename": result["filename"], "filepath": result["filepath"], "size": result["size"]}
    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["message"] = f"Error: {str(e)}"

def _start_job(export_fn, label, *args):
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {"status": "queued", "progress": 0, "message": "Starting...", "result": None, "error": None}
    t = threading.Thread(target=_run_job, args=(job_id, export_fn, label, *args), daemon=True)
    t.start()
    return {"job_id": job_id, "status": "queued"}

def _update_job(job_id, progress, message):
    if job_id in jobs:
        jobs[job_id]["progress"] = progress
        jobs[job_id]["message"] = message

# Inventory Excel
@app.post("/api/generate/inventory/excel/async")
def gen_inventory_excel_async(agent: Optional[str] = None):
    return _start_job(lambda a, progress_cb=None: generate_inventory_excel(a, progress_callback=progress_cb), "Inventory Excel", agent)

# Security Events Excel
@app.post("/api/export/security")
def export_security_excel(period: Optional[str] = "24h", agent: Optional[str] = None):
    return _start_job(lambda p, a, progress_cb=None: export_security_events(p, a, progress_cb), "Security Events Excel", period, agent)

# Auth Events Excel
@app.post("/api/export/auth")
def export_auth_excel(period: Optional[str] = "24h", agent: Optional[str] = None):
    return _start_job(lambda p, a, progress_cb=None: export_auth_events(p, a, progress_cb), "Auth Events Excel", period, agent)

# Vulnerability Excel
@app.post("/api/export/vulnerability")
def export_vuln_excel(agent: Optional[str] = None):
    return _start_job(lambda a, progress_cb=None: export_vulnerability(a, progress_cb), "Vulnerability Excel", agent)

@app.get("/api/jobs/{job_id}")
def get_job_status(job_id: str):
    """Get async job status and progress"""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    job = jobs[job_id]
    resp = {"job_id": job_id, "status": job["status"], "progress": job["progress"], "message": job["message"]}
    if job["status"] == "completed" and job["result"]:
        resp["download_url"] = f"/api/jobs/{job_id}/download"
        resp["filename"] = job["result"]["filename"]
        resp["size"] = job["result"]["size"]
    if job["error"]:
        resp["error"] = job["error"]
    return resp

@app.get("/api/jobs/{job_id}/download")
def download_job_result(job_id: str):
    """Download completed job file"""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    job = jobs[job_id]
    if job["status"] != "completed" or not job["result"]:
        raise HTTPException(400, "Job not ready")
    return FileResponse(job["result"]["filepath"],
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=job["result"]["filename"])

@app.get("/api/agents")
def list_agents():
    """Get list of all agents for dropdown"""
    try:
        client = opensearch_client.get_client()
        idx_prefix = config.OPENSEARCH_INDEX.split('-')[0]
        r = client.search(index=f"{idx_prefix}-states-inventory-system-*", body={"size": 0, "aggs": {"agents": {"terms": {"field": "agent.name", "size": 100}}}})
        agents = [b["key"] for b in r["aggregations"]["agents"]["buckets"]]
        return {"agents": agents}
    except Exception as e:
        return {"agents": [], "error": str(e)}

# --- V2 ENHANCED REPORTS ---
@app.post("/api/generate/v2/quick")
async def gen_quick_v2(period: Optional[str] = "24h"):
    result, err = await generate_quick_report_v2(period)
    if err:
        raise HTTPException(500, err)
    return {"download_url": f"/api/reports/{result['id']}/download", **result}

@app.post("/api/generate/v2/{tid}")
async def gen_report_v2(tid: str, period: Optional[str] = "24h"):
    result, err = await generate_report_v2(tid, period)
    if err:
        raise HTTPException(400, err)
    return {"download_url": f"/api/reports/{result['id']}/download", **result}

@app.post("/api/generate/{tid}")
async def gen_report(tid: str, period: Optional[str] = "24h"):
    result, err = await generate_report(tid, period)
    if err:
        raise HTTPException(400, err)
    return {"download_url": f"/api/reports/{result['id']}/download", **result}

# --- PDF PREVIEW (renders HTML in browser, no PDF download) ---
def _center_preview(html):
    """Wrap report HTML with centering styles for browser preview"""
    return html.replace(
        '<body>',
        '<body style="background:#e5e7eb;display:flex;flex-direction:column;align-items:center;padding:20px 0">'
    ).replace(
        '.page{page-break-after:always;width:210mm;min-height:297mm;',
        '.page{page-break-after:always;width:210mm;min-height:297mm;margin:0 auto 20px;box-shadow:0 4px 20px rgba(0,0,0,0.15);'
    )

def _center_preview_v2(html):
    """Wrap v2 report HTML with centering styles for browser preview"""
    inject_style = (
        'body { background:#e5e7eb !important; '
        'display:flex; flex-direction:column; align-items:center; padding:20px 0; } '
        '.page { margin:0 auto 20px !important; '
        'box-shadow:0 4px 24px rgba(0,0,0,0.18) !important; }'
    )
    return html.replace('</style>', f'{inject_style}</style>')

@app.get("/api/preview/quick")
async def preview_quick(period: Optional[str] = "24h"):
    from fastapi.responses import HTMLResponse
    try:
        import pdf_generator
        query = pdf_generator.build_query(period)
        client = opensearch_client.get_client()
        raw = client.search(index=config.OPENSEARCH_INDEX, body=query)
        data = pdf_generator.process_data(raw, period=period)
        html = _center_preview(pdf_generator.render_html(data))
        return HTMLResponse(content=html)
    except Exception as e:
        return HTMLResponse(content=f"<html><body><h2>Preview Error</h2><pre>{str(e)}</pre></body></html>")

@app.get("/api/preview/inventory")
async def preview_inventory():
    from fastapi.responses import HTMLResponse
    try:
        from inventory_report import collect_inventory_data, render_inventory_html
        data = collect_inventory_data()
        html = _center_preview(render_inventory_html(data))
        return HTMLResponse(content=html)
    except Exception as e:
        return HTMLResponse(content=f"<html><body><h2>Preview Error</h2><pre>{str(e)}</pre></body></html>")

@app.get("/api/preview/v2/quick")
async def preview_quick_v2(period: Optional[str] = "24h"):
    from fastapi.responses import HTMLResponse
    try:
        import pdf_generator_v2
        from pdf_generator import build_query, process_data
        query = build_query(period)
        client = opensearch_client.get_client()
        raw = client.search(index=config.OPENSEARCH_INDEX, body=query)
        data = process_data(raw, period=period)
        html = _center_preview_v2(pdf_generator_v2.render_html_v2(data))
        return HTMLResponse(content=html)
    except Exception as e:
        return HTMLResponse(content=f"<html><body><h2>Preview Error</h2><pre>{str(e)}</pre></body></html>")

@app.get("/api/preview/v2/{tid}")
async def preview_report_v2(tid: str, period: Optional[str] = "24h"):
    from fastapi.responses import HTMLResponse
    template = database.get_template(tid)
    if not template:
        raise HTTPException(404, "Template not found")
    try:
        import pdf_generator_v2
        from pdf_generator import build_query, process_data
        query = build_query(period)
        client = opensearch_client.get_client()
        raw = client.search(index=config.OPENSEARCH_INDEX, body=query)
        data = process_data(raw, template, period)
        sections = json.loads(template["sections"]) if isinstance(template["sections"], str) else template["sections"]
        html = _center_preview_v2(pdf_generator_v2.render_html_v2(data, sections))
        return HTMLResponse(content=html)
    except Exception as e:
        return HTMLResponse(content=f"<html><body><h2>Preview Error</h2><pre>{str(e)}</pre></body></html>")

@app.get("/api/preview/{tid}")
async def preview_report(tid: str, period: Optional[str] = "24h"):
    from fastapi.responses import HTMLResponse
    template = database.get_template(tid)
    if not template:
        raise HTTPException(404, "Template not found")
    try:
        import pdf_generator
        query = pdf_generator.build_query(period)
        client = opensearch_client.get_client()
        raw = client.search(index=config.OPENSEARCH_INDEX, body=query)
        data = pdf_generator.process_data(raw, template, period)
        sections = json.loads(template["sections"]) if isinstance(template["sections"], str) else template["sections"]
        html = _center_preview(pdf_generator.render_html(data, sections))
        return HTMLResponse(content=html)
    except Exception as e:
        return HTMLResponse(content=f"<html><body><h2>Preview Error</h2><pre>{str(e)}</pre></body></html>")

# --- COMPARISON ---
@app.get("/api/compare")
def compare(period_a: str = "now-24h", period_b: str = "now-48h/now-24h", agent: Optional[str] = None):
    try:
        return compare_periods(period_a, period_b, agent)
    except Exception as e:
        raise HTTPException(500, str(e))

# --- HEALTH ---
@app.get("/api/health")
def health():
    try:
        client = opensearch_client.get_client()
        info = client.info()
        return {"status": "ok", "opensearch": info["version"]["number"], "cluster": info["cluster_name"]}
    except Exception as e:
        return {"status": "error", "message": str(e)}
