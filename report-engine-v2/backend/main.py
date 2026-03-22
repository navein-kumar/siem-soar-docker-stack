"""Report Engine API - FastAPI backend"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List, Any
import json, os
import config, database, opensearch_client
from pdf_generator import generate_report, generate_quick_report
from inventory_report import generate_inventory_report

app = FastAPI(title="Codesec Report Engine", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

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
    return FileResponse(filepath, media_type="application/pdf", filename=report["filename"])

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
async def gen_inventory(tid: Optional[str] = None):
    result, err = await generate_inventory_report(tid)
    if err:
        raise HTTPException(500, err)
    return {"download_url": f"/api/reports/{result['id']}/download", **result}

@app.post("/api/generate/{tid}")
async def gen_report(tid: str, period: Optional[str] = "24h"):
    result, err = await generate_report(tid, period)
    if err:
        raise HTTPException(400, err)
    return {"download_url": f"/api/reports/{result['id']}/download", **result}

# --- HEALTH ---
@app.get("/api/health")
def health():
    try:
        client = opensearch_client.get_client()
        info = client.info()
        return {"status": "ok", "opensearch": info["version"]["number"], "cluster": info["cluster_name"]}
    except Exception as e:
        return {"status": "error", "message": str(e)}
