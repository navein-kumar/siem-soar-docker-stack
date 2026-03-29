"""Incident Management Report — TheHive 5 data → PDF via Gotenberg.
Uses identical CSS/page structure as pdf_generator.py for consistent look."""

from pdf_generator import _html_to_pdf, _fc, svg_hbars, svg_vbars, svg_donut, PALETTE, IST
import config, thehive_client

SEV_COLOR = {"Critical": "#BD271E", "High": "#E7664C", "Medium": "#D6BF57", "Low": "#54B399"}

# ── Exact same CSS as pdf_generator.py ──────────────────────────────────────
CSS = '@page{size:A4 portrait;margin:0}*{margin:0;padding:0;box-sizing:border-box}body{font-family:"Segoe UI",Arial,sans-serif;font-size:9px;color:#2c3e50;background:#fff}.page{page-break-after:always;width:210mm;min-height:297mm;margin:0 auto 20px;box-shadow:0 4px 20px rgba(0,0,0,0.15);padding:20px 24px 40px;position:relative}.page:last-child{page-break-after:auto}.card{background:#fff;border-radius:10px;box-shadow:0 1px 6px rgba(0,0,0,0.05);padding:14px;margin-bottom:12px;border:1px solid #ecf0f1}.stitle{font-size:12px;font-weight:700;color:#2c3e50;margin:0 0 10px;padding:6px 0;border-bottom:2px solid #3498db;display:flex;align-items:center}.stitle .dot{width:8px;height:8px;border-radius:50%;background:#3498db;margin-right:8px;flex-shrink:0}.hdr{background:linear-gradient(135deg,#1a1a2e,#16213e,#0f3460);color:#fff;padding:12px 20px;border-radius:8px;margin-bottom:14px}.hdr h2{font-size:15px;font-weight:700;margin-bottom:2px}.hdr p{font-size:8px;opacity:0.8}table{width:100%;border-collapse:collapse;font-size:8px}tr{page-break-inside:avoid;break-inside:avoid}td{word-wrap:break-word;overflow-wrap:break-word;max-width:300px}thead{display:table-header-group}tbody{display:table-row-group}thead th{background:linear-gradient(135deg,#1a1a2e,#16213e);color:#fff;padding:6px 8px;text-align:left;font-size:7.5px;text-transform:uppercase;letter-spacing:0.5px}.badge{display:inline-block;padding:2px 8px;border-radius:12px;font-size:6.5px;font-weight:700}.badge-critical{background:#fdecea;color:#BD271E;border:1px solid #f5c6c2}.badge-high{background:#fef0eb;color:#c0392b;border:1px solid #f9c5b2}.badge-medium{background:#fef9e7;color:#9a7d0a;border:1px solid #f9e79f}.badge-low{background:#eafaf1;color:#1e8449;border:1px solid #a9dfbf}.badge-new{background:#e8f4fd;color:#1a5276;border:1px solid #aed6f1}.badge-inprogress{background:#fef5e7;color:#9a6516;border:1px solid #f9d69c}.badge-closed{background:#eafaf1;color:#1e8449;border:1px solid #a9dfbf}.mitre-chip{display:inline-block;padding:2px 8px;border-radius:12px;font-size:6.5px;font-weight:700;background:#eef2ff;color:#1B2A4A;border:1px solid #c5cde8;margin:2px}.rec-item{background:#f0f7ff;border-left:3px solid #0D7377;padding:8px 10px;border-radius:0 8px 8px 0;margin-bottom:6px;font-size:8px}'

def _sev_badge(sev):
    return f'<span class="badge badge-{sev.lower()}">{sev}</span>'

def _status_badge(status):
    s = str(status).lower().replace(" ", "")
    if s in ("inprogress",): cls = "inprogress"
    elif s in ("resolved","truepositiveimported","truepositive","closed"): cls = "closed"
    else: cls = "new"
    return f'<span class="badge badge-{cls}">{status}</span>'

def _stbl(items, key, hdr, chdr, color, font="8px"):
    if not items: return '<div style="text-align:center;color:#95a5a6;font-size:9px;padding:20px">No data</div>'
    rows = "".join(f'<tr style="background:{"#fff" if i%2==0 else "#f8f9fb"}"><td style="padding:4px 8px;border-bottom:1px solid #ecf0f1;font-size:{font}">{item[key]}</td><td style="padding:4px 8px;border-bottom:1px solid #ecf0f1;text-align:right;font-weight:700;font-size:8px;color:{color}">{_fc(item["count"])}</td></tr>' for i, item in enumerate(items))
    return f'<table><thead><tr><th>{hdr}</th><th style="text-align:right;padding-right:10px">{chdr}</th></tr></thead><tbody>{rows}</tbody></table>'

def _donut(data_dict, colors):
    items = [{"label": k, "value": v, "color": c}
             for (k, v), c in zip(data_dict.items(), colors) if v > 0]
    if not items:
        return '<svg width="120" height="120"><text x="60" y="65" text-anchor="middle" font-size="9" fill="#aaa">No data</text></svg>'
    return svg_donut(items, 160, 160, 65, 38)

def _hbar(items_list, n=8):
    rows = [{"label": str(k)[:22], "value": v, "color": PALETTE[i % len(PALETTE)]}
            for i, (k, v) in enumerate(items_list[:n])]
    if not rows:
        return '<svg width="300" height="80"><text x="150" y="45" text-anchor="middle" font-size="9" fill="#aaa">No data</text></svg>'
    h = max(60, len(rows) * 19 + 10)
    return svg_hbars(rows, 300, h)


def render_html(d, company="Codesecure Solutions", logo_url="https://codesecure.in/images/codesec-logo1.png", period="7d"):
    total_a = d["total_alerts"]
    total_c = d["total_cases"]
    open_c = d["open_cases_count"]
    closed_c = d["closed_cases_count"]
    asev = d["alert_sev"]
    csev = d["case_sev"]
    tp_rate = d["tp_rate"]
    sla_24h = d["sla_24h"]
    sla_72h = d["sla_72h"]

    # ── Period label (auto-adaptive) ─────────────────────────────────────────
    period_label = d.get("period", "Last 7 Days")

    # ── Alert sources hbar ───────────────────────────────────────────────────
    sources_items = sorted(d.get("alert_sources", {}).items(), key=lambda x: -x[1])[:8]
    sources_hbar = _hbar(sources_items, 8) if sources_items else '<div style="text-align:center;color:#aaa;padding:20px;font-size:8px">No source data</div>'

    # ── Case timeline chart (same period granularity as alert timeline) ───────
    case_tl_svg = svg_vbars([{"value": t["value"], "label": t["label"], "color": "#9b59b6"} for t in d.get("case_timeline", [])], 500, 120) if d.get("case_timeline") else '<div style="text-align:center;color:#95a5a6;padding:20px">No data</div>'

    # ── Case severity hbar ───────────────────────────────────────────────────
    csev_items = [(k, d["case_sev"].get(k, 0)) for k in ["Critical", "High", "Medium", "Low"]]
    csev_hbar = _hbar([(k, v) for k, v in csev_items if v > 0], 4) if any(v for _, v in csev_items) else '<div style="text-align:center;color:#aaa;padding:20px;font-size:8px">No cases</div>'

    # ── Cover — same structure as pdf_generator.py ──────────────────────────
    cco, cac = "#1B2A4A", "#0D7377"
    logo = f'<div style="margin-bottom:40px;display:inline-flex;align-items:center;justify-content:center;background:#fff;padding:16px;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.15)"><img src="{logo_url}" style="height:40px;display:block" onerror="this.style.display=\'none\'"/></div>'

    cover = f'<div class="page" style="padding:0;overflow:hidden;position:relative;background:{cco}"><div style="position:absolute;top:-100px;right:-100px;width:450px;height:450px;border-radius:50%;background:linear-gradient(135deg,{cac},#14919B);opacity:0.15"></div><div style="position:absolute;bottom:-150px;left:-100px;width:400px;height:400px;border-radius:50%;background:linear-gradient(135deg,#14919B,{cac});opacity:0.1"></div><div style="height:5px;background:linear-gradient(90deg,{cac},#14919B,#32DBC6)"></div><div style="position:relative;z-index:1;padding:60px 50px 40px">{logo}<div style="margin-bottom:50px"><div style="font-size:14px;color:{cac};text-transform:uppercase;letter-spacing:4px;font-weight:600;margin-bottom:14px">Security Report</div><h1 style="font-size:48px;font-weight:800;color:#fff;line-height:1.05;margin-bottom:0">Incident Management</h1><h1 style="font-size:48px;font-weight:800;color:{cac};line-height:1.05;margin-bottom:16px">Report</h1><div style="width:50px;height:4px;background:{cac};border-radius:2px"></div></div><p style="font-size:13px;color:rgba(255,255,255,0.45);letter-spacing:1px;margin-bottom:40px">TheHive SOAR — Alert &amp; Case Analysis</p><div style="display:flex;gap:0;margin-bottom:40px;background:rgba(0,0,0,0.2);border-radius:8px;overflow:hidden"><div style="flex:1;padding:18px 22px;border-left:3px solid {cac}"><div style="font-size:8px;text-transform:uppercase;letter-spacing:2px;color:rgba(255,255,255,0.4);margin-bottom:8px">Prepared For</div><div style="font-size:15px;font-weight:700;color:#fff;margin-bottom:4px">{company}</div><div style="font-size:10px;color:rgba(255,255,255,0.5)">Chennai, Tamil Nadu, India</div></div><div style="flex:1;padding:18px 22px;border-left:1px solid rgba(255,255,255,0.08)"><div style="font-size:8px;text-transform:uppercase;letter-spacing:2px;color:rgba(255,255,255,0.4);margin-bottom:8px">Total Alerts</div><div style="font-size:15px;font-weight:700;color:#fff">{_fc(total_a)}</div><div style="font-size:10px;color:rgba(255,255,255,0.5)">Across {total_c} cases</div></div><div style="flex:1;padding:18px 22px;border-left:1px solid rgba(255,255,255,0.08)"><div style="font-size:8px;text-transform:uppercase;letter-spacing:2px;color:rgba(255,255,255,0.4);margin-bottom:8px">Generated</div><div style="font-size:11px;font-weight:600;color:#fff;margin-bottom:4px">{d["generated_at"]}</div><div style="font-size:11px;color:rgba(255,255,255,0.5)">{d["period"]} · MTTR: {d["mttr_display"]}</div></div></div></div></div>'

    # ── Severity stat cards (same inline style as pdf_generator) ─────────────
    sev_def = [("Critical","#BD271E","Level 4"),("High","#E7664C","Level 3"),("Medium","#D6BF57","Level 2"),("Low","#6DCCB1","Level 1")]
    alert_stat_cards = "".join(f'<div style="flex:1;text-align:center;padding:14px 6px;border-radius:8px;border:1px solid #ecf0f1;background:#fafbfc"><div style="font-size:10px;font-weight:600;color:#69707D;margin-bottom:6px">{s} severity</div><div style="font-size:26px;font-weight:800;color:{c}">{_fc(asev.get(s,0))}</div><div style="font-size:8px;color:#98A2B3;margin-top:3px">{r}</div></div>' for s,c,r in sev_def)
    case_stat_cards = "".join(f'<div style="flex:1;text-align:center;padding:14px 6px;border-radius:8px;border:1px solid #ecf0f1;background:#fafbfc"><div style="font-size:10px;font-weight:600;color:#69707D;margin-bottom:6px">{s} cases</div><div style="font-size:26px;font-weight:800;color:{c}">{_fc(csev.get(s,0))}</div><div style="font-size:8px;color:#98A2B3;margin-top:3px">{r}</div></div>' for s,c,r in sev_def)

    alert_donut_items = [{"value": asev.get(s,0), "color": c} for s,c,_ in sev_def]
    case_donut_items  = [{"value": csev.get(s,0), "color": c} for s,c,_ in sev_def]
    alert_donut = svg_donut(alert_donut_items, 180, 180, 70, 45)
    case_donut  = svg_donut(case_donut_items,  180, 180, 70, 45)
    alert_leg = "".join(f'<div style="display:flex;align-items:center;margin:4px 0"><div style="width:14px;height:14px;border-radius:3px;background:{c};margin-right:8px"></div><div><div style="font-size:10px;font-weight:700">{s}</div><div style="font-size:8px;color:#95a5a6">{r}: {_fc(asev.get(s,0))}</div></div></div>' for s,c,r in sev_def)
    case_leg  = "".join(f'<div style="display:flex;align-items:center;margin:4px 0"><div style="width:14px;height:14px;border-radius:3px;background:{c};margin-right:8px"></div><div><div style="font-size:10px;font-weight:700">{s}</div><div style="font-size:8px;color:#95a5a6">{r}: {_fc(csev.get(s,0))}</div></div></div>' for s,c,r in sev_def)

    pages = [cover]

    # ── Page 1: Executive Summary ────────────────────────────────────────────
    tl_svg = svg_vbars([{"value": t["value"], "label": t["label"], "color": "#3498db"} for t in d["alert_timeline"]], 500, 120) if d.get("alert_timeline") else '<div style="text-align:center;color:#95a5a6;padding:20px">No timeline data</div>'

    pages.append(f'<div class="page"><div class="hdr"><h2>Executive Summary</h2><p>TheHive alert &amp; case overview — {period_label}</p></div><div class="card" style="background:#f8f9fb;border-left:4px solid #3498db;margin-bottom:14px"><div style="font-size:9px;line-height:1.6;color:#34495e">In the <strong>{period_label}</strong>, a total of <strong>{_fc(total_a)}</strong> security alerts and <strong>{_fc(total_c)}</strong> cases recorded in TheHive. <strong style="color:#BD271E">{_fc(asev.get("Critical",0))} critical</strong> and <strong style="color:#E7664C">{_fc(asev.get("High",0))} high</strong> severity alerts require attention. Open cases: <strong style="color:#e67e22">{open_c}</strong>, Closed: <strong style="color:#2ecc71">{closed_c}</strong>. True positive rate: <strong>{tp_rate}%</strong>. Mean Time to Resolve: <strong>{d["mttr_display"]}</strong>. SLA breaches (&gt;72h): <strong style="color:{"#BD271E" if sla_72h > 0 else "#2ecc71"}">{sla_72h}</strong>.</div></div><div style="display:flex;gap:8px;margin-bottom:14px"><div style="flex:1;text-align:center;padding:14px 6px;border-radius:8px;border:1px solid #ecf0f1;background:#fafbfc"><div style="font-size:10px;font-weight:600;color:#69707D;margin-bottom:6px">Total Alerts</div><div style="font-size:26px;font-weight:800;color:#3498db">{_fc(total_a)}</div></div><div style="flex:1;text-align:center;padding:14px 6px;border-radius:8px;border:1px solid #ecf0f1;background:#fafbfc"><div style="font-size:10px;font-weight:600;color:#69707D;margin-bottom:6px">Total Cases</div><div style="font-size:26px;font-weight:800;color:#1B2A4A">{_fc(total_c)}</div></div><div style="flex:1;text-align:center;padding:14px 6px;border-radius:8px;border:1px solid #ecf0f1;background:#fafbfc"><div style="font-size:10px;font-weight:600;color:#69707D;margin-bottom:6px">Open Cases</div><div style="font-size:26px;font-weight:800;color:#e67e22">{open_c}</div></div><div style="flex:1;text-align:center;padding:14px 6px;border-radius:8px;border:1px solid #ecf0f1;background:#fafbfc"><div style="font-size:10px;font-weight:600;color:#69707D;margin-bottom:6px">MTTR</div><div style="font-size:26px;font-weight:800;color:#0D7377">{d["mttr_display"]}</div></div><div style="flex:1;text-align:center;padding:14px 6px;border-radius:8px;border:1px solid #ecf0f1;background:#fafbfc"><div style="font-size:10px;font-weight:600;color:#69707D;margin-bottom:6px">SLA Breaches</div><div style="font-size:26px;font-weight:800;color:{"#BD271E" if sla_72h>0 else "#2ecc71"}">{sla_72h}</div></div></div><div style="display:flex;gap:8px;margin-bottom:14px">{alert_stat_cards}</div><div class="card"><div class="stitle"><span class="dot"></span>Alert Severity Distribution</div><div style="display:flex;align-items:center;justify-content:center;gap:24px">{alert_donut}<div>{"".join(alert_leg)}</div></div></div><div class="card"><div class="stitle"><span class="dot" style="background:#9b59b6"></span>Alert Timeline — {period_label}</div><div style="text-align:center">{tl_svg}</div></div><div style="display:flex;gap:8px;margin-top:8px"><div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#e67e22"></span>Alert Sources</div><div style="text-align:center">{sources_hbar}</div></div><div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#9b59b6"></span>Cases Opened — {period_label}</div><div style="text-align:center">{case_tl_svg}</div></div></div></div>')

    # ── Page 2: Top Alerts + Cases Overview ──────────────────────────────────
    # ── Page 2: pre-compute case status chips (no backslashes in f-string expr, Py3.11) ──
    case_status_chips = "".join(
        f'<div style="flex:1;min-width:80px;text-align:center;padding:8px;border-radius:8px;background:#f8f9fb;border:1px solid #ecf0f1"><div style="font-size:16px;font-weight:800;color:#1B2A4A">{v}</div><div style="font-size:7px;color:#69707D">{k}</div></div>'
        for k, v in sorted(d.get("case_status", {}).items(), key=lambda x: -x[1]) if v > 0
    )

    alert_rows = "".join(f'<tr style="background:{"#fff" if i%2==0 else "#f8f9fb"}"><td style="padding:5px 8px;border-bottom:1px solid #ecf0f1;text-align:center;font-size:7px;color:#95a5a6">{i+1}</td><td style="padding:5px 8px;border-bottom:1px solid #ecf0f1;font-size:8px">{title}</td><td style="padding:5px 8px;border-bottom:1px solid #ecf0f1;text-align:right;font-weight:700;color:#E7664C;font-size:8px">{_fc(cnt)}</td></tr>' for i,(title,cnt) in enumerate(d["top_alert_titles"]))
    top_alerts_tbl = f'<table><thead><tr><th style="width:25px">#</th><th>Alert Title</th><th style="text-align:right;width:60px">Count</th></tr></thead><tbody>{alert_rows or "<tr><td colspan=3 style=text-align:center;color:#aaa;padding:16px>No alert data</td></tr>"}</tbody></table>'
    alert_hbar = _hbar(d["top_alert_titles"], 8)

    pages.append(f'<div class="page"><div class="hdr" style="background:linear-gradient(135deg,#BD271E,#920000)"><h2 style="color:#fff">Top Triggered Alerts — {period_label}</h2><p style="color:rgba(255,255,255,0.8)">{_fc(total_a)} total alerts · {total_c} cases · {open_c} open · {closed_c} closed</p></div><div style="display:flex;gap:12px;margin-bottom:12px"><div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#E7664C"></span>Alert Count by Title</div><div style="text-align:center">{alert_hbar}</div></div><div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#3498db"></span>Case Severity Distribution</div><div style="display:flex;align-items:center;justify-content:center;gap:16px">{case_donut}<div style="font-size:8px">{"".join(case_leg)}</div></div></div></div><div style="display:flex;gap:12px;margin-bottom:12px"><div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#BD271E"></span>Case Severity Breakdown</div><div style="text-align:center">{csev_hbar}</div></div><div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#2ecc71"></span>Case Status Summary</div><div style="display:flex;flex-wrap:wrap;gap:8px;padding:8px">{case_status_chips}</div></div></div><div class="card"><div class="stitle"><span class="dot" style="background:#E7664C"></span>Top Alert Titles</div>{top_alerts_tbl}</div></div>')

    # ── Page 3: Open Cases ────────────────────────────────────────────────────
    case_rows = ""
    for c in d["open_cases"]:
        age_str = f'{int(c["age_h"])}h'
        age_col = "#BD271E" if c["age_h"] > 72 else ("#E7664C" if c["age_h"] > 24 else "#2ecc71")
        tags_html = " ".join(f'<span class="mitre-chip">{t}</span>' for t in c["tags"][:3])
        case_rows += f'<tr style="background:{"#fff" if d["open_cases"].index(c)%2==0 else "#f8f9fb"}"><td style="padding:5px 8px;border-bottom:1px solid #ecf0f1;font-size:7px;color:#95a5a6">#{c.get("number","")}</td><td style="padding:5px 8px;border-bottom:1px solid #ecf0f1;font-size:8px">{c["title"][:60]}</td><td style="padding:5px 8px;border-bottom:1px solid #ecf0f1">{_sev_badge(c["severity"])}</td><td style="padding:5px 8px;border-bottom:1px solid #ecf0f1">{_status_badge(c["status"])}</td><td style="padding:5px 8px;border-bottom:1px solid #ecf0f1;font-size:8px">{c["assignee"]}</td><td style="padding:5px 8px;border-bottom:1px solid #ecf0f1;font-weight:700;color:{age_col};font-size:8px">{age_str}</td><td style="padding:5px 8px;border-bottom:1px solid #ecf0f1">{tags_html}</td></tr>'

    # Closed cases table rows
    closed_rows_html = ""
    for i, c in enumerate(d.get("closed_cases", [])):
        res_col = {"TruePositive": "#2ecc71", "FalsePositive": "#9b59b6", "Duplicated": "#e67e22"}.get(c["resolution"], "#95a5a6")
        closed_rows_html += f'<tr style="background:{"#fff" if i%2==0 else "#f8f9fb"}"><td style="padding:5px 8px;border-bottom:1px solid #ecf0f1;font-size:7px;color:#95a5a6">#{c.get("number","")}</td><td style="padding:5px 8px;border-bottom:1px solid #ecf0f1;font-size:8px">{c["title"][:55]}</td><td style="padding:5px 8px;border-bottom:1px solid #ecf0f1">{_sev_badge(c["severity"])}</td><td style="padding:5px 8px;border-bottom:1px solid #ecf0f1;font-size:8px">{c["assignee"]}</td><td style="padding:5px 8px;border-bottom:1px solid #ecf0f1;font-size:8px;font-weight:700;color:{res_col}">{c["resolution"]}</td><td style="padding:5px 8px;border-bottom:1px solid #ecf0f1;font-size:7px;color:#95a5a6">{c["closed_at"]}</td></tr>'

    assignee_chart = _hbar(list(d["case_assignees"].items()), 8)
    pages.append(f'<div class="page"><div class="hdr"><h2>Open Cases &amp; Case Resolution</h2><p>{open_c} open · {closed_c} closed — {period_label}</p></div><div style="display:flex;gap:8px;margin-bottom:14px">{case_stat_cards}</div><div style="display:flex;gap:12px;margin-bottom:12px"><div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#2ecc71"></span>Cases by Assignee</div><div style="text-align:center">{assignee_chart}</div></div><div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#e67e22"></span>Resolution Metrics</div><div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px"><div style="flex:1;text-align:center;padding:10px;border-radius:8px;background:#f0fdf4;border:1px solid #a3cfbb"><div style="font-size:18px;font-weight:800;color:#2ecc71">{tp_rate}%</div><div style="font-size:7px;color:#69707D">True Positive Rate</div></div><div style="flex:1;text-align:center;padding:10px;border-radius:8px;background:{"#fdf2f2" if sla_72h>0 else "#f0fdf4"};border:1px solid {"#f5c6cb" if sla_72h>0 else "#a3cfbb"}"><div style="font-size:18px;font-weight:800;color:{"#e74c3c" if sla_72h>0 else "#2ecc71"}">{sla_72h}</div><div style="font-size:7px;color:#69707D">SLA Breaches &gt;72h</div></div><div style="flex:1;text-align:center;padding:10px;border-radius:8px;background:#f0f4ff;border:1px solid #b3c6ff"><div style="font-size:18px;font-weight:800;color:#3498db">{d["mttr_display"]}</div><div style="font-size:7px;color:#69707D">Mean Time to Resolve</div></div></div></div></div><div class="card"><div class="stitle"><span class="dot" style="background:#e74c3c"></span>Open Cases Detail</div><table><thead><tr><th style="width:30px">#</th><th>Title</th><th style="width:60px">Severity</th><th style="width:70px">Status</th><th style="width:80px">Assignee</th><th style="width:35px">Age</th><th>Tags</th></tr></thead><tbody>{case_rows or "<tr><td colspan=7 style=text-align:center;color:#aaa;padding:16px>No open cases</td></tr>"}</tbody></table></div><div class="card"><div class="stitle"><span class="dot" style="background:#2ecc71"></span>Closed Cases ({closed_c})</div><table><thead><tr><th style="width:30px">#</th><th>Title</th><th style="width:60px">Severity</th><th style="width:80px">Assignee</th><th style="width:90px">Resolution</th><th style="width:70px">Closed At</th></tr></thead><tbody>{closed_rows_html or "<tr><td colspan=6 style=text-align:center;color:#aaa;padding:16px>No closed cases</td></tr>"}</tbody></table></div></div>')

    # ── Page 4: Observables / IOCs ────────────────────────────────────────────
    obs_type_rows = "".join(f'<tr style="background:{"#fff" if i%2==0 else "#f8f9fb"}"><td style="padding:4px 8px;border-bottom:1px solid #ecf0f1;font-size:8px">{t}</td><td style="padding:4px 8px;border-bottom:1px solid #ecf0f1;text-align:right;font-weight:700;font-size:8px;color:#0D7377">{_fc(cnt)}</td></tr>' for i,(t,cnt) in enumerate(sorted(d["obs_summary"].items(), key=lambda x:-x[1])))
    obs_donut = _donut(d["obs_summary"], PALETTE[:8]) if d["obs_summary"] else '<div style="text-align:center;color:#aaa;padding:30px;font-size:8px">No observables yet</div>'

    def _obs_rows(items, label, col):
        if not items: return f'<div style="text-align:center;color:#aaa;font-size:8px;padding:10px">No {label}</div>'
        r = "".join(f'<tr style="background:{"#fff" if i%2==0 else "#f8f9fb"}"><td style="padding:3px 8px;border-bottom:1px solid #ecf0f1;font-size:7px;font-family:monospace">{v[:40]}</td><td style="padding:3px 8px;border-bottom:1px solid #ecf0f1;text-align:right;font-weight:700;font-size:8px;color:{col}">{c}</td></tr>' for i,(v,c) in enumerate(items[:8]))
        return f'<table><thead><tr><th>{label}</th><th style="text-align:right;width:50px">Count</th></tr></thead><tbody>{r}</tbody></table>'

    pages.append(f'<div class="page"><div class="hdr"><h2>Observables / Indicators of Compromise</h2><p>IOCs extracted from TheHive cases</p></div><div style="display:flex;gap:12px;margin-bottom:12px"><div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#0D7377"></span>Observable Types</div><table><thead><tr><th>Type</th><th style="text-align:right">Count</th></tr></thead><tbody>{obs_type_rows or "<tr><td colspan=2 style=text-align:center;color:#aaa;padding:12px>No observables</td></tr>"}</tbody></table></div><div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#9b59b6"></span>Distribution</div><div style="text-align:center">{obs_donut}</div></div></div><div style="display:flex;gap:12px;margin-bottom:12px"><div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#e74c3c"></span>Top Source IPs</div>{_obs_rows(d["top_ips"],"IP Address","#e74c3c")}</div><div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#3498db"></span>Top Hostnames</div>{_obs_rows(d["top_hostnames"],"Hostname","#3498db")}</div></div><div style="display:flex;gap:12px"><div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#e67e22"></span>Top Domains</div>{_obs_rows(d["top_domains"],"Domain","#e67e22")}</div><div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#9b59b6"></span>File Hashes</div>{_obs_rows(d["top_hashes"],"Hash","#9b59b6")}</div></div></div>')

    # ── Page 5: MITRE + Analyst Activity + Tags + Recommendations ────────────
    mitre_chips = "".join(f'<span class="mitre-chip">{t} <strong>({c})</strong></span>' for t,c in d["top_mitre"]) or '<span style="color:#aaa;font-size:8px">No MITRE data — ensure alerts have MITRE tags</span>'
    mitre_rows = "".join(f'<tr style="background:{"#fff" if i%2==0 else "#f8f9fb"}"><td style="padding:4px 8px;border-bottom:1px solid #ecf0f1;font-size:8px">{t}</td><td style="padding:4px 8px;border-bottom:1px solid #ecf0f1;text-align:right;font-weight:700;font-size:8px;color:#E7664C">{_fc(c)}</td></tr>' for i,(t,c) in enumerate(d["top_mitre"])) or '<tr><td colspan="2" style="text-align:center;color:#aaa;padding:12px">No MITRE data</td></tr>'
    mitre_hbar = _hbar(d["top_mitre"], 10) if d["top_mitre"] else '<div style="text-align:center;color:#aaa;padding:20px;font-size:8px">No MITRE data</div>'

    analyst_rows = "".join(f'<tr style="background:{"#fff" if i%2==0 else "#f8f9fb"}"><td style="padding:4px 8px;border-bottom:1px solid #ecf0f1;font-size:8px">{analyst}</td><td style="padding:4px 8px;border-bottom:1px solid #ecf0f1;text-align:right;font-weight:700;font-size:8px">{_fc(cnt)}</td><td style="padding:4px 8px;border-bottom:1px solid #ecf0f1"><div style="background:#ecf0f1;border-radius:4px;height:8px"><div style="background:#0D7377;border-radius:4px;height:8px;width:{round(cnt/max(total_c,1)*100)}%;min-width:2px"></div></div></td></tr>' for i,(analyst,cnt) in enumerate(sorted(d["case_assignees"].items(), key=lambda x:-x[1]))) or '<tr><td colspan="3" style="text-align:center;color:#aaa;padding:12px">No analysts assigned</td></tr>'

    tag_chips = "".join(f'<span class="mitre-chip">{t} <strong>({c})</strong></span>' for t,c in d["top_tags"]) or '<span style="color:#aaa;font-size:8px">No tags</span>'

    recs = []
    if asev.get("Critical",0) > 0: recs.append({"icon":"!!","color":"#BD271E","text":f'{asev["Critical"]} critical alerts detected. Immediately escalate to Tier-2/Tier-3.'})
    if sla_72h > 0: recs.append({"icon":"SLA","color":"#E7664C","text":f'{sla_72h} case(s) exceed 72h SLA. Assign or escalate immediately.'})
    if sla_24h > 0: recs.append({"icon":"!","color":"#e67e22","text":f'{sla_24h} case(s) pending over 24h. Review and assign to available analysts.'})
    if tp_rate < 50 and closed_c > 3: recs.append({"icon":"FP","color":"#9b59b6","text":f'True positive rate is {tp_rate}%. Review alert tuning rules to reduce noise.'})
    if d["top_mitre"]: recs.append({"icon":"M","color":"#3498db","text":f'Top MITRE technique: {d["top_mitre"][0][0]}. Review detection coverage.'})
    if d["top_ips"]: recs.append({"icon":"IP","color":"#e74c3c","text":f'IP {d["top_ips"][0][0]} appeared most frequently in observables. Consider blocking.'})
    if not recs: recs.append({"icon":"OK","color":"#2ecc71","text":"No critical recommendations. Continue monitoring and periodic case reviews."})
    recs_html = "".join(f'<div style="display:flex;align-items:flex-start;margin-bottom:8px;padding:8px 12px;border-radius:6px;background:#fafbfc;border-left:3px solid {r["color"]}"><div style="width:24px;height:24px;border-radius:50%;background:{r["color"]};color:#fff;display:flex;align-items:center;justify-content:center;font-size:8px;font-weight:700;flex-shrink:0;margin-right:10px">{r["icon"]}</div><div style="font-size:9px;line-height:1.5;color:#34495e">{r["text"]}</div></div>' for r in recs)

    pages.append(f'<div class="page"><div class="hdr"><h2>MITRE ATT&amp;CK &amp; Analyst Activity</h2><p>Techniques detected and analyst workload</p></div><div style="display:flex;gap:12px;margin-bottom:12px"><div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#e74c3c"></span>MITRE Techniques</div><div style="text-align:center">{mitre_hbar}</div></div><div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#2ecc71"></span>Analyst Activity</div><table><thead><tr><th>Analyst</th><th style="text-align:right">Cases</th><th>Load</th></tr></thead><tbody>{analyst_rows}</tbody></table></div></div><div class="card"><div class="stitle"><span class="dot" style="background:#e74c3c"></span>MITRE Technique Detail</div><div style="margin-bottom:10px;line-height:2">{mitre_chips}</div><table><thead><tr><th>Technique / Tactic</th><th style="text-align:right">Count</th></tr></thead><tbody>{mitre_rows}</tbody></table></div><div class="card"><div class="stitle"><span class="dot" style="background:#9b59b6"></span>Top Tags &amp; Rule Groups</div><div style="margin-bottom:10px;line-height:2">{tag_chips}</div></div><div class="card"><div class="stitle"><span class="dot" style="background:#f39c12"></span>Recommendations</div>{recs_html}</div></div>')

    return f'<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Incident Management Report</title><style>{CSS}</style></head><body>{"".join(pages)}</body></html>'


async def generate_incident_report(period="7d"):
    data = await thehive_client.fetch_all(period)
    html = render_html(data, period=period)
    pdf_bytes, err = await _html_to_pdf(html)
    if err:
        raise RuntimeError(err)
    return pdf_bytes


async def preview_incident_report(period="7d"):
    data = await thehive_client.fetch_all(period)
    return render_html(data, period=period)
