"""SQLite database for templates, schedules, report archive"""
import sqlite3, json, os, uuid
from datetime import datetime
import config

def get_db():
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS templates (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT "",
            cover_title TEXT DEFAULT "Security Report",
            cover_subtitle TEXT DEFAULT "",
            cover_color TEXT DEFAULT "#1B2A4A",
            cover_accent TEXT DEFAULT "#0D7377",
            logo_url TEXT DEFAULT "",
            sections TEXT DEFAULT "[]",
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS saved_widgets (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT "",
            query_dsl TEXT DEFAULT "{}",
            agg_config TEXT DEFAULT "{}",
            chart_type TEXT DEFAULT "table",
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS reports (
            id TEXT PRIMARY KEY,
            template_id TEXT,
            filename TEXT,
            period_from TEXT,
            period_to TEXT,
            generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            file_size INTEGER DEFAULT 0,
            status TEXT DEFAULT "completed"
        );
        CREATE TABLE IF NOT EXISTS schedules (
            id TEXT PRIMARY KEY,
            template_id TEXT NOT NULL,
            name TEXT NOT NULL,
            cron TEXT NOT NULL,
            email TEXT DEFAULT "",
            enabled INTEGER DEFAULT 1,
            last_run TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    # Add client_address column if missing (migration)
    try:
        db.execute("ALTER TABLE templates ADD COLUMN client_address TEXT DEFAULT ''")
    except Exception:
        pass  # column already exists
    db.commit()
    db.close()

# Template CRUD
def create_template(data):
    db = get_db()
    tid = str(uuid.uuid4())[:8]
    db.execute(
        "INSERT INTO templates (id,name,description,cover_title,cover_subtitle,"
        "cover_color,cover_accent,logo_url,sections,client_address) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (tid, data["name"], data.get("description", ""),
         data.get("cover_title", "Security Report"),
         data.get("cover_subtitle", ""),
         data.get("cover_color", "#1B2A4A"),
         data.get("cover_accent", "#0D7377"),
         data.get("logo_url", ""),
         json.dumps(data.get("sections", [])),
         data.get("client_address", ""))
    )
    db.commit(); db.close()
    return tid

def get_templates():
    db = get_db()
    rows = db.execute("SELECT * FROM templates ORDER BY updated_at DESC").fetchall()
    db.close()
    return [dict(r) for r in rows]

def get_template(tid):
    db = get_db()
    row = db.execute("SELECT * FROM templates WHERE id=?", (tid,)).fetchone()
    db.close()
    return dict(row) if row else None

def update_template(tid, data):
    db = get_db()
    sets = []
    vals = []
    for k in ["name","description","cover_title","cover_subtitle","cover_color","cover_accent","logo_url","client_address"]:
        if k in data:
            sets.append(f"{k}=?")
            vals.append(data[k])
    if "sections" in data:
        sets.append("sections=?")
        vals.append(json.dumps(data["sections"]))
    sets.append("updated_at=?")
    vals.append(datetime.now().isoformat())
    vals.append(tid)
    sep = ","
    query = "UPDATE templates SET " + sep.join(sets) + " WHERE id=?"
    db.execute(query, vals)
    db.commit(); db.close()

def delete_template(tid):
    db = get_db()
    db.execute("DELETE FROM templates WHERE id=?", (tid,))
    db.commit(); db.close()

def clone_template(tid):
    t = get_template(tid)
    if not t: return None
    t["name"] = t["name"] + " (copy)"
    t["sections"] = json.loads(t["sections"]) if isinstance(t["sections"], str) else t["sections"]
    return create_template(t)

# Widget CRUD
def save_widget(data):
    db = get_db()
    wid = str(uuid.uuid4())[:8]
    db.execute("INSERT INTO saved_widgets (id,name,description,query_dsl,agg_config,chart_type) VALUES (?,?,?,?,?,?)",
        (wid, data["name"], data.get("description",""), json.dumps(data.get("query_dsl",{})),
         json.dumps(data.get("agg_config",{})), data.get("chart_type","table")))
    db.commit(); db.close()
    return wid

def get_widgets():
    db = get_db()
    rows = db.execute("SELECT * FROM saved_widgets ORDER BY created_at DESC").fetchall()
    db.close()
    return [dict(r) for r in rows]

# Report archive
def save_report(template_id, filename, period_from, period_to, file_size):
    db = get_db()
    rid = str(uuid.uuid4())[:8]
    db.execute("INSERT INTO reports (id,template_id,filename,period_from,period_to,file_size) VALUES (?,?,?,?,?,?)",
        (rid, template_id, filename, period_from, period_to, file_size))
    db.commit(); db.close()
    return rid

def get_reports(limit=50):
    db = get_db()
    rows = db.execute("SELECT r.*, t.name as template_name FROM reports r LEFT JOIN templates t ON r.template_id=t.id ORDER BY r.generated_at DESC LIMIT ?", (limit,)).fetchall()
    db.close()
    return [dict(r) for r in rows]

# Schedule CRUD
def create_schedule(data):
    db = get_db()
    sid = str(uuid.uuid4())[:8]
    db.execute("INSERT INTO schedules (id,template_id,name,cron,email,enabled) VALUES (?,?,?,?,?,?)",
        (sid, data["template_id"], data["name"], data["cron"], data.get("email",""), data.get("enabled",1)))
    db.commit(); db.close()
    return sid

def get_schedules():
    db = get_db()
    rows = db.execute("SELECT s.*, t.name as template_name FROM schedules s LEFT JOIN templates t ON s.template_id=t.id ORDER BY s.created_at DESC").fetchall()
    db.close()
    return [dict(r) for r in rows]
