"""PDF Report Generator - Exact port of N8N workflow HTML template to Python.
Produces identical output to 3_Daily_Report_v3.json workflow."""

import json, os, math, aiohttp
from datetime import datetime, timedelta, timezone
import config, database, opensearch_client

IST = timezone(timedelta(hours=5, minutes=30))
PALETTE = ['#2ecc71','#3498db','#9b59b6','#e67e22','#1abc9c','#e74c3c','#f39c12','#2980b9','#8e44ad','#16a085','#e91e63','#00bcd4','#8bc34a','#ff5722','#607d8b']

def _fc(n):
    return f"{n:,}"

def _sc(level):
    if level >= 15: return "#BD271E"
    if level >= 12: return "#E7664C"
    if level >= 7: return "#D6BF57"
    return "#6DCCB1"

def _rc(risk):
    return {"Critical":"#BD271E","High":"#E7664C","Medium":"#D6BF57","Low":"#6DCCB1"}.get(risk, "#6DCCB1")

def svg_donut(data, w, h, r, r2):
    cx, cy = w/2, h/2
    total = sum(x["value"] for x in data) or 1
    cum = -90
    paths = ""
    for x in data:
        if x["value"] <= 0: continue
        pct = x["value"] / total
        ang = pct * 360
        s = cum * math.pi / 180
        e = (cum + ang) * math.pi / 180
        cum += ang
        la = 1 if ang > 180 else 0
        x1, y1 = cx + r * math.cos(s), cy + r * math.sin(s)
        x2, y2 = cx + r * math.cos(e), cy + r * math.sin(e)
        x3, y3 = cx + r2 * math.cos(e), cy + r2 * math.sin(e)
        x4, y4 = cx + r2 * math.cos(s), cy + r2 * math.sin(s)
        paths += f'<path d="M{x1:.1f},{y1:.1f} A{r},{r} 0 {la},1 {x2:.1f},{y2:.1f} L{x3:.1f},{y3:.1f} A{r2},{r2} 0 {la},0 {x4:.1f},{y4:.1f}Z" fill="{x["color"]}"/>'
    return f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}">{paths}<text x="{cx}" y="{cy-6}" text-anchor="middle" font-size="18" font-weight="800" fill="#2c3e50">{_fc(total)}</text><text x="{cx}" y="{cy+10}" text-anchor="middle" font-size="9" fill="#95a5a6">Total Alerts</text></svg>'

def svg_vbars(items, w, h):
    pt, pb, pl, pr = 15, 40, 5, 5
    cW, cH = w - pl - pr, h - pt - pb
    mx = max((i["value"] for i in items), default=1) or 1
    bW = min(int(cW / max(len(items),1)) - 2, 22)
    gap = (cW - bW * len(items)) / (len(items) + 1) if items else 0
    s = ""
    for idx, it in enumerate(items):
        bH = max((it["value"] / mx) * cH, 2)
        x = pl + gap + (bW + gap) * idx
        y = pt + cH - bH
        val = it["value"]
        val_str = f"{val/1000000:.1f}M" if val >= 1000000 else (f"{val//1000}k" if val >= 1000 else str(val))
        s += f'<rect x="{x:.1f}" y="{y:.1f}" width="{bW}" height="{bH:.1f}" fill="{it.get("color","#3498db")}" rx="2"/>'
        s += f'<text x="{x+bW/2:.1f}" y="{pt+cH+12}" text-anchor="middle" font-size="5.5" fill="#7f8c8d" transform="rotate(50,{x+bW/2:.1f},{pt+cH+12})">{it.get("label","")}</text>'
        s += f'<text x="{x+bW/2:.1f}" y="{y-4:.1f}" text-anchor="middle" font-size="5.5" fill="#555">{val_str}</text>'
    s += f'<line x1="{pl}" y1="{pt+cH}" x2="{w-pr}" y2="{pt+cH}" stroke="#ecf0f1" stroke-width="1"/>'
    return f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}">{s}</svg>'

def svg_hbars(items, w, h):
    pt, pb, pl, pr = 5, 5, 110, 55
    cW = w - pl - pr
    bH = min(int((h - pt - pb) / max(len(items),1)) - 3, 16)
    mx = max((i["value"] for i in items), default=1) or 1
    s = ""
    for idx, it in enumerate(items):
        bw = max((it["value"] / mx) * cW, 3)
        y = pt + (bH + 3) * idx
        label = it.get("label", "")[:16]
        s += f'<text x="{pl-5}" y="{y+bH/2+3:.1f}" text-anchor="end" font-size="7" fill="#2c3e50">{label}</text>'
        s += f'<rect x="{pl}" y="{y}" width="{bw:.1f}" height="{bH}" fill="{it.get("color","#3498db")}" rx="3"/>'
        s += f'<text x="{pl+bw+4:.1f}" y="{y+bH/2+3:.1f}" font-size="7" font-weight="700" fill="#2c3e50">{_fc(it["value"])}</text>'
    return f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}">{s}</svg>'

def build_query(period="24h"):
    base = os.path.dirname(__file__)
    qfile = {"7d": "opensearch_query_weekly.json", "30d": "opensearch_query_monthly.json"}.get(period, "opensearch_query.json")
    qpath = os.path.join(base, qfile)
    if not os.path.exists(qpath):
        qpath = os.path.join(base, "opensearch_query.json")
    with open(qpath) as f:
        q = json.load(f)

    time_from = f"now-{period}"
    prev_map = {"24h": "48h", "7d": "14d", "30d": "60d", "90d": "180d"}
    prev_outer = prev_map.get(period, "48h")

    # Update time ranges based on period
    q["query"]["range"]["timestamp"]["gte"] = f"now-{prev_outer}"
    # Find the main agg key (today/this_week/this_month)
    main_key = "today"
    for k in ("today", "this_week", "this_month"):
        if k in q["aggs"]:
            main_key = k
            break
    q["aggs"][main_key]["filter"]["range"]["timestamp"]["gte"] = time_from

    # Update prev period
    for k in ("prev_day_total", "prev_week_total", "prev_month_total"):
        if k in q["aggs"]:
            q["aggs"][k]["filter"]["range"]["timestamp"]["gte"] = f"now-{prev_outer}"
            q["aggs"][k]["filter"]["range"]["timestamp"]["lt"] = time_from
    for k in ("prev_day_by_level", "prev_week_by_level", "prev_month_by_level"):
        if k in q["aggs"]:
            q["aggs"][k]["filter"]["range"]["timestamp"]["gte"] = f"now-{prev_outer}"
            q["aggs"][k]["filter"]["range"]["timestamp"]["lt"] = time_from
    return q

def process_data(raw, template_cfg=None, period="24h"):
    # Find main aggregation key
    main_key = "today"
    for k in ("today", "this_week", "this_month"):
        if k in raw["aggregations"]:
            main_key = k
            break
    aggs = raw["aggregations"][main_key]
    total = aggs["doc_count"]

    # Find prev period total
    prev_total = 0
    prev_lvl = []
    for k in ("prev_day_total", "prev_week_total", "prev_month_total"):
        if k in raw["aggregations"]:
            prev_total = raw["aggregations"][k].get("doc_count", 0)
            break
    for k in ("prev_day_by_level", "prev_week_by_level", "prev_month_by_level"):
        if k in raw["aggregations"]:
            prev_lvl = raw["aggregations"][k].get("levels", {}).get("buckets", [])
            break
    now = datetime.now(IST)
    days = {"24h": 1, "7d": 7, "30d": 30, "90d": 90}.get(period, 1)
    from_date = (now - timedelta(days=days)).strftime("%d %b %Y %I:%M %p")
    to_date = now.strftime("%d %b %Y %I:%M %p")

    def _sev_count(buckets):
        s = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
        sm = {"critical": "Critical", "high": "High", "medium": "Medium", "low": "Low"}
        for b in buckets:
            k = b["key"]
            if isinstance(k, str):
                mapped = sm.get(k.lower().split(" ")[0], "Low")
                s[mapped] += b["doc_count"]
            else:
                if k >= 15: s["Critical"] += b["doc_count"]
                elif k >= 12: s["High"] += b["doc_count"]
                elif k >= 7: s["Medium"] += b["doc_count"]
                else: s["Low"] += b["doc_count"]
        return s

    sc = _sev_count(aggs.get("alerts_by_level", {}).get("buckets", []))
    ps = _sev_count(prev_lvl)

    top_rules = sorted([{"rule_id": b["key"], "description": (b.get("rule_desc",{}).get("buckets",[{}])[0].get("key","N/A") if b.get("rule_desc",{}).get("buckets") else "N/A"), "level": (b.get("rule_level", b.get("by_level",{})).get("buckets",[{}])[0].get("key",0) if b.get("rule_level", b.get("by_level",{})).get("buckets") else 0), "count": b["doc_count"]} for b in aggs.get("top_rules",{}).get("buckets",[])], key=lambda x: (-x["level"], -x["count"]))

    def _classify_level(key, doc_count, target):
        """Handle both integer keys (terms agg) and string keys (range agg)"""
        if isinstance(key, str):
            k = key.lower()
            if k == "critical" or k.startswith("critical"): target["critical"] += doc_count
            elif k == "high" or k.startswith("high"): target["high"] += doc_count
            elif k == "medium" or k.startswith("medium"): target["medium"] += doc_count
            else: target["low"] += doc_count
        else:
            if key >= 15: target["critical"] += doc_count
            elif key >= 12: target["high"] += doc_count
            elif key >= 7: target["medium"] += doc_count
            else: target["low"] += doc_count

    top_agents = []
    for b in aggs.get("top_agents",{}).get("buckets",[]):
        a = {"name": b["key"], "count": b["doc_count"], "critical": 0, "high": 0, "medium": 0, "low": 0}
        for lb in b.get("by_level",{}).get("buckets",[]):
            _classify_level(lb["key"], lb["doc_count"], a)
        top_agents.append(a)

    mitre_tech = [{"technique": b["key"], "count": b["doc_count"]} for b in aggs.get("mitre_techniques",{}).get("buckets",[])]
    mitre_tac = [{"tactic": b["key"], "count": b["doc_count"]} for b in aggs.get("mitre_tactics",{}).get("buckets",[])]

    timeline = []
    for b in aggs.get("alerts_over_time",{}).get("buckets",[]):
        try:
            dt = datetime.fromisoformat(b["key_as_string"].replace("Z","+00:00")).astimezone(IST)
        except Exception:
            dt = datetime.fromtimestamp(b["key"]/1000, tz=IST)
        timeline.append({"hour": dt.strftime("%H:%M"), "count": b["doc_count"]})

    def _mu(*srcs):
        m = {}
        for s in srcs:
            for b in s:
                if b["key"] not in ("-",""):
                    m[b["key"]] = max(m.get(b["key"],0), b["doc_count"])
        return sorted([{"user":k,"count":v} for k,v in m.items()], key=lambda x:-x["count"])[:5]

    def _mi(*srcs):
        m = {}
        for s in srcs:
            for b in s:
                if b["key"] not in ("-",""):
                    m[b["key"]] = max(m.get(b["key"],0), b["doc_count"])
        return sorted([{"ip":k,"count":v} for k,v in m.items()], key=lambda x:-x["count"])[:5]

    af = aggs.get("auth_fail",{})
    asuc = aggs.get("auth_success",{})
    vuln = aggs.get("vuln",{})
    fim = aggs.get("fim",{})

    comp = {}
    for fw in ("pci","hipaa","gdpr","nist","tsc"):
        fd = aggs.get(f"compliance_{fw}",{})
        comp[fw] = {"total": fd.get("doc_count",0), "controls": [{"control":b["key"],"count":b["doc_count"]} for b in fd.get("controls",{}).get("buckets",[])]}

    ip_map = {}
    for b in aggs.get("top_srcip",{}).get("buckets",[]):
        ip_map[b["key"]] = ip_map.get(b["key"],0) + b["doc_count"]
    for b in aggs.get("top_srcip_linux",{}).get("buckets",[]):
        ip_map[b["key"]] = ip_map.get(b["key"],0) + b["doc_count"]
    top_srcips = sorted([{"ip":k,"count":v} for k,v in ip_map.items() if k not in ("127.0.0.1","::1")], key=lambda x:-x["count"])[:10]

    inc_agg = aggs.get("incidents",{})
    incidents = []
    for b in inc_agg.get("by_rule",{}).get("buckets",[]):
        hits = b.get("latest",{}).get("hits",{}).get("hits",[])
        if not hits: continue
        h = hits[0]["_source"]
        desc_b = b.get("rule_desc",{}).get("buckets",[])
        agents_b = b.get("agents",{}).get("buckets",[])
        srcip = "N/A"
        if h.get("data"):
            srcip = h["data"].get("srcip") or (h["data"].get("win",{}).get("eventdata",{}).get("ipAddress")) or "N/A"
        try:
            ls = datetime.fromisoformat(h["timestamp"].replace("Z","+00:00")).astimezone(IST).strftime("%d/%m/%Y, %H:%M:%S")
        except Exception:
            ls = "N/A"
        incidents.append({"level": round(b.get("max_level",{}).get("value",0)), "description": desc_b[0]["key"] if desc_b else h.get("rule",{}).get("description","N/A"), "rule_id": b["key"], "count": b["doc_count"], "agents": ", ".join(a["key"] for a in agents_b), "last_seen": ls})

    agent_risk = []
    for a in top_agents:
        t = a["count"] or 1
        score = min(100, round((a["critical"]/t)*400 + (a["high"]/t)*200 + (a["medium"]/t)*30))
        if a["critical"] > 0: risk, note = "Critical", f'{a["critical"]} critical alerts - investigate immediately'
        elif a["high"] > 10: risk, note = "High", f'{a["high"]} high severity alerts - review required'
        elif score >= 30: risk, note = "Medium", "Elevated alert volume - monitor closely"
        else: risk, note = "Low", "Normal activity - routine monitoring"
        agent_risk.append({**a, "score": score, "risk": risk, "note": note})
    agent_risk.sort(key=lambda x: -x["score"])

    recs = []
    if sc["Critical"] > 0: recs.append({"icon":"!!","color":"#BD271E","text":f'{sc["Critical"]} critical alerts detected. Investigate immediately.'})
    if sc["High"] > 50: recs.append({"icon":"!","color":"#E7664C","text":f'High volume of high-severity alerts ({_fc(sc["High"])}). Review and tune.'})
    if af.get("doc_count",0) > 100: recs.append({"icon":"X","color":"#e74c3c","text":f'{_fc(af["doc_count"])} authentication failures. Review sources and consider blocking.'})
    if vuln.get("doc_count",0) > 0: recs.append({"icon":"V","color":"#e67e22","text":f'{_fc(vuln["doc_count"])} vulnerability alerts. Prioritize patching.'})
    if top_agents and top_agents[0]["count"] > total * 0.3: recs.append({"icon":"A","color":"#3498db","text":f'Agent {top_agents[0]["name"]} generates {round(top_agents[0]["count"]/total*100)}% of alerts.'})
    if not recs: recs.append({"icon":"OK","color":"#2ecc71","text":"No critical recommendations. Continue monitoring."})

    ct = "Security Threat Analysis Report"
    cs = "Daily Security Alert Analysis"
    cc, ca = "#1B2A4A", "#0D7377"
    cn, caddr = "Codesecure Solutions", "Chennai, Tamil Nadu, India"
    cl = "https://codesecure.in/images/codesec-logo1.png"
    pl = {"24h":"Last 24 Hours","7d":"Last 7 Days","30d":"Last 30 Days"}.get(period, period)
    if template_cfg:
        ct = template_cfg.get("cover_title", ct)
        cs = template_cfg.get("cover_subtitle", cs)
        cc = template_cfg.get("cover_color", cc)
        ca = template_cfg.get("cover_accent", ca)
        cn = template_cfg.get("description", cn) or cn
        cl = template_cfg.get("logo_url", cl) or cl

    # Weekly/Monthly daily trend data
    daily_trend = []
    for b in aggs.get("alerts_over_time", {}).get("buckets", []):
        day_label = b.get("key_as_string", "")
        by_lv = b.get("by_level", {}).get("buckets", [])
        low = high = med = crit = 0
        for lb in by_lv:
            if isinstance(lb.get("key"), str):
                if lb["key"] == "low": low = lb["doc_count"]
                elif lb["key"] == "medium": med = lb["doc_count"]
                elif lb["key"] == "high": high = lb["doc_count"]
                elif lb["key"] == "critical": crit = lb["doc_count"]
            else:
                low += lb.get("doc_count", 0)  # fallback
        daily_trend.append({"day": day_label, "total": b["doc_count"], "low": low, "medium": med, "high": high, "critical": crit})

    auth_fail_daily = [{"day": b.get("key_as_string", ""), "count": b.get("count", {}).get("doc_count", b.get("doc_count", 0))} for b in aggs.get("auth_fail_daily", {}).get("buckets", [])]
    fim_daily = [{"day": b.get("key_as_string", ""), "count": b.get("count", {}).get("doc_count", b.get("doc_count", 0))} for b in aggs.get("fim_daily", {}).get("buckets", [])]

    return {"client_name":cn,"client_address":caddr,"client_logo":cl,"cover_title":ct,"cover_subtitle":cs,"cover_color":cc,"cover_accent":ca,"total_alerts":total,"severity_counts":sc,"prev_total":prev_total,"prev_severity":ps,"top_rules":top_rules,"top_agents":top_agents,"agent_risk":agent_risk,"mitre_techniques":mitre_tech,"mitre_tactics":mitre_tac,"timeline":timeline,"auth_fail_count":af.get("doc_count",0),"auth_fail_users":_mu(af.get("by_win_user",{}).get("buckets",[]),af.get("by_dstuser",{}).get("buckets",[]),af.get("by_srcuser",{}).get("buckets",[])),"auth_fail_ips":_mi(af.get("by_win_ip",{}).get("buckets",[]),af.get("by_srcip",{}).get("buckets",[])),"auth_fail_events":[{"desc":b["key"],"count":b["doc_count"]} for b in af.get("top_rules",{}).get("buckets",[])],"auth_success_count":asuc.get("doc_count",0),"auth_success_users":_mu(asuc.get("by_win_user",{}).get("buckets",[]),asuc.get("by_dstuser",{}).get("buckets",[]),asuc.get("by_srcuser",{}).get("buckets",[])),"auth_success_events":[{"desc":b["key"],"count":b["doc_count"]} for b in asuc.get("top_rules",{}).get("buckets",[])],"vuln_total":vuln.get("doc_count",0),"vuln_by_sev":[{"severity":b["key"],"count":b["doc_count"]} for b in vuln.get("by_sev",{}).get("buckets",[]) if b["key"] not in ("-","")],"vuln_top_cve":[{"cve":b["key"],"count":b["doc_count"]} for b in vuln.get("top_cve",{}).get("buckets",[])],"vuln_top_agent":[{"agent":b["key"],"count":b["doc_count"]} for b in vuln.get("top_agent",{}).get("buckets",[])],"vuln_top_pkg":[{"pkg":b["key"],"count":b["doc_count"]} for b in vuln.get("top_pkg",{}).get("buckets",[])],"fim_total":fim.get("doc_count",0),"fim_events":[{"event":b["key"],"count":b["doc_count"]} for b in fim.get("by_event",{}).get("buckets",[])],"fim_agents":[{"agent":b["key"],"count":b["doc_count"]} for b in fim.get("by_agent",{}).get("buckets",[])],"fim_paths":[{"path":b["key"],"count":b["doc_count"]} for b in fim.get("by_path",{}).get("buckets",[])],"compliance":comp,"top_srcips":top_srcips,"incidents":incidents,"incident_count":inc_agg.get("doc_count",0),"level12_count":aggs.get("level12",{}).get("doc_count",0),"recommendations":recs,"from_date":from_date,"to_date":to_date,"ist_date":now.strftime("%d/%m/%Y"),"ist_time":now.strftime("%I:%M %p").lower(),"period":period,"period_label":pl,"daily_trend":daily_trend,"auth_fail_daily":auth_fail_daily,"fim_daily":fim_daily}

def _stbl(items, key, hdr, chdr, color, font="8px"):
    if not items: return '<div style="text-align:center;color:#95a5a6;font-size:9px;padding:20px">No data</div>'
    rows = "".join(f'<tr style="background:{"#fff" if i%2==0 else "#f8f9fb"}"><td style="padding:4px 8px;border-bottom:1px solid #ecf0f1;font-size:{font}">{item[key]}</td><td style="padding:4px 8px;border-bottom:1px solid #ecf0f1;text-align:right;font-weight:700;font-size:8px;color:{color}">{_fc(item["count"])}</td></tr>' for i, item in enumerate(items))
    return f'<table><thead><tr><th>{hdr}</th><th style="text-align:right;padding-right:10px">{chdr}</th></tr></thead><tbody>{rows}</tbody></table>'

def render_html(d, sections=None):
    # If no sections specified, render all
    ALL = ["executive_summary","top_threats","agents_risk","authentication","source_ips","vulnerability","fim","mitre","compliance","security_events"]
    if not sections:
        sections = ALL
    def has(s): return s in sections
    sc = d["severity_counts"]
    sev_def = [{"key":"Critical","color":"#BD271E","range":"Level 15+"},{"key":"High","color":"#E7664C","range":"Level 12-14"},{"key":"Medium","color":"#D6BF57","range":"Level 7-11"},{"key":"Low","color":"#6DCCB1","range":"Level 0-6"}]
    donut = svg_donut([{"value":sc[s["key"]],"color":s["color"]} for s in sev_def], 180, 180, 70, 45)
    donut_leg = "".join(f'<div style="display:flex;align-items:center;margin:4px 0"><div style="width:14px;height:14px;border-radius:3px;background:{s["color"]};margin-right:8px"></div><div><div style="font-size:10px;font-weight:700">{s["key"]}</div><div style="font-size:8px;color:#95a5a6">{s["range"]}: {_fc(sc[s["key"]])}</div></div></div>' for s in sev_def)
    is_daily = d.get("period") == "24h"
    if is_daily:
        tl_svg = svg_vbars([{"value":t["count"],"label":t["hour"],"color":"#3498db"} for t in d["timeline"]], 500, 150) if d["timeline"] else '<div style="text-align:center;color:#95a5a6;padding:20px">No timeline data</div>'
        tl_label = "Alerts Timeline (24h)"
    else:
        # Daily trend bars for weekly/monthly
        trend = d.get("daily_trend", [])
        if trend:
            chart_w = 680 if d.get("period") == "30d" else 500
            tl_svg = svg_vbars([{"value":t["total"],"label":t["day"],"color":"#3498db"} for t in trend], chart_w, 160)
        else:
            tl_svg = '<div style="text-align:center;color:#95a5a6;padding:20px">No timeline data</div>'
        tl_label = "Daily Alert Trend"

    # Auth fail daily trend (weekly/monthly only)
    auth_daily_svg = ""
    if not is_daily and d.get("auth_fail_daily"):
        auth_daily_svg = f'<div class="card"><div class="stitle"><span class="dot" style="background:#e74c3c"></span>Auth Failures - Daily Trend</div><div style="text-align:center">{svg_vbars([{"value":t["count"],"label":t["day"],"color":"#e74c3c"} for t in d["auth_fail_daily"]], 500, 100)}</div></div>'

    # FIM daily trend (weekly/monthly only)
    fim_daily_svg = ""
    if not is_daily and d.get("fim_daily"):
        fim_daily_svg = f'<div class="card"><div class="stitle"><span class="dot" style="background:#9b59b6"></span>File Changes - Daily Trend</div><div style="text-align:center">{svg_vbars([{"value":t["count"],"label":t["day"],"color":"#9b59b6"} for t in d["fim_daily"]], 500, 100)}</div></div>'

    ag_items = [{"value":a["count"],"label":a["name"],"color":PALETTE[i%15]} for i,a in enumerate(d["top_agents"])]
    ag_svg = svg_hbars(ag_items, 500, max(len(ag_items)*19+10,80)) if ag_items else ""
    tech_svg = svg_hbars([{"value":m["count"],"label":m["technique"],"color":PALETTE[i%15]} for i,m in enumerate(d["mitre_techniques"])], 500, max(len(d["mitre_techniques"])*19+10,80)) if d["mitre_techniques"] else '<div style="text-align:center;color:#95a5a6;padding:20px">No MITRE data</div>'
    tac_svg = svg_hbars([{"value":m["count"],"label":m["tactic"],"color":PALETTE[i%15]} for i,m in enumerate(d["mitre_tactics"])], 500, max(len(d["mitre_tactics"])*19+10,80)) if d["mitre_tactics"] else ""
    stat_cards = "".join(f'<div style="flex:1;text-align:center;padding:14px 6px;border-radius:8px;border:1px solid #ecf0f1;background:#fafbfc"><div style="font-size:10px;font-weight:600;color:#69707D;margin-bottom:6px">{s["key"]} severity</div><div style="font-size:26px;font-weight:800;color:{s["color"]}">{_fc(sc[s["key"]])}</div><div style="font-size:8px;color:#98A2B3;margin-top:3px">{s["range"]}</div></div>' for s in sev_def)

    ps = d["prev_severity"]
    dod = ""
    for k in ("Critical","High","Medium","Low"):
        tv, pv = sc[k], ps[k]
        diff = tv - pv
        pct = f"{(diff/pv*100):.1f}" if pv > 0 else "N/A"
        ar = "\u25B2" if diff>0 else ("\u25BC" if diff<0 else "\u25CF")
        cl = "#e74c3c" if diff>0 else ("#2ecc71" if diff<0 else "#95a5a6")
        dod += f'<div style="flex:1;text-align:center;padding:8px;border-radius:6px;background:#fafbfc;border:1px solid #ecf0f1"><div style="font-size:8px;color:#69707D;margin-bottom:3px">{k}</div><div style="font-size:12px;font-weight:700;color:{cl}">{ar} {pct}{"%" if pct!="N/A" else ""}</div><div style="font-size:7px;color:#95a5a6;margin-top:2px">{_fc(pv)} &rarr; {_fc(tv)}</div></div>'
    td = d["total_alerts"] - d["prev_total"]
    tp = f"{(td/d['prev_total']*100):.1f}" if d["prev_total"]>0 else "N/A"
    ta = "\u25B2" if td>0 else ("\u25BC" if td<0 else "\u25CF")
    tc = "#e74c3c" if td>0 else ("#2ecc71" if td<0 else "#95a5a6")
    dod += f'<div style="flex:1;text-align:center;padding:8px;border-radius:6px;background:#fafbfc;border:1px solid #ecf0f1"><div style="font-size:8px;color:#69707D;margin-bottom:3px">Total</div><div style="font-size:12px;font-weight:700;color:{tc}">{ta} {tp}{"%" if tp!="N/A" else ""}</div><div style="font-size:7px;color:#95a5a6;margin-top:2px">{_fc(d["prev_total"])} &rarr; {_fc(d["total_alerts"])}</div></div>'

    sr = sorted(d["top_rules"], key=lambda x:(-x["level"],-x["count"]))
    pp = 40
    def mkr(r,i,off):
        sn=off+i+1; lc=_sc(r["level"]); bg="#fff" if i%2==0 else "#f8f9fb"; desc=r["description"][:90]+("..." if len(r["description"])>90 else "")
        return f'<tr style="background:{bg};border-left:3px solid {lc}"><td style="padding:3px 6px;border-bottom:1px solid #ecf0f1;text-align:center;font-weight:600;color:#95a5a6;font-size:7px">{sn}</td><td style="padding:3px 6px;border-bottom:1px solid #ecf0f1;text-align:center;font-weight:700;color:#2c3e50;font-size:8px">{r["rule_id"]}</td><td style="padding:3px 6px;border-bottom:1px solid #ecf0f1;font-size:7.5px;color:#34495e">{desc}</td><td style="padding:5px 8px;border-bottom:1px solid #ecf0f1;text-align:center"><span style="background:{lc};color:#fff;padding:2px 8px;border-radius:10px;font-size:7px;font-weight:700">{r["level"]}</span></td><td style="padding:3px 6px;border-bottom:1px solid #ecf0f1;text-align:right;font-weight:700;color:#2c3e50;font-size:8px">{_fc(r["count"])}</td></tr>'
    rp1 = "".join(mkr(r,i,0) for i,r in enumerate(sr[:pp]))
    rp2 = "".join(mkr(r,i,pp) for i,r in enumerate(sr[pp:pp*2]))

    logo = f'<div style="margin-bottom:40px;display:inline-flex;align-items:center;justify-content:center;background:#fff;padding:16px;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.15)"><img src="{d["client_logo"]}" style="height:40px;display:block" onerror="this.style.display=\'none\'"/></div>' if d.get("client_logo") else ""
    cco, cac = d.get("cover_color","#1B2A4A"), d.get("cover_accent","#0D7377")
    ctp = d.get("cover_title","Security Threat Analysis Report").rsplit(" ",2)
    t1 = " ".join(ctp[:-2]) if len(ctp)>=3 else ctp[0]
    t2 = " ".join(ctp[-2:]) if len(ctp)>=3 else (" ".join(ctp[1:]) if len(ctp)>1 else "Report")
    pla = d.get("period_label","Last 24 Hours")

    # Threats section
    if d["incident_count"] > 0 and d["incidents"]:
        thr_rows = "".join(f'<tr style="background:{"#fff" if i%2==0 else "#f8f9fb"}"><td style="padding:5px 8px;border-bottom:1px solid #ecf0f1;text-align:center"><span style="background:{"#BD271E" if inc["level"]>=15 else "#E7664C"};color:#fff;padding:2px 6px;border-radius:4px;font-size:8px;font-weight:700">{inc["level"]}</span></td><td style="padding:5px 8px;border-bottom:1px solid #ecf0f1;font-size:8px">{inc["description"]}</td><td style="padding:5px 8px;border-bottom:1px solid #ecf0f1;text-align:center;font-size:9px;font-weight:700;color:#BD271E">{_fc(inc["count"])}</td><td style="padding:5px 8px;border-bottom:1px solid #ecf0f1;font-size:8px">{inc["agents"]}</td><td style="padding:5px 8px;border-bottom:1px solid #ecf0f1;font-size:7px">{inc["last_seen"]}</td></tr>' for i,inc in enumerate(d["incidents"]))
        threats_html = f'<div style="background:#fdf2f2;border:2px solid #BD271E;border-radius:8px;padding:14px;margin-bottom:14px"><div style="display:flex;align-items:center;gap:8px;margin-bottom:8px"><div style="width:28px;height:28px;background:#BD271E;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:14px;color:#fff;font-weight:800">!</div><div style="font-size:12px;font-weight:700;color:#BD271E">HIGH SEVERITY THREATS DETECTED</div></div><div style="font-size:9px;color:#69707D">Events with severity level 12+ may indicate active threats or critical changes.</div></div><table><thead><tr><th style="width:35px">Level</th><th>Description</th><th style="width:50px;text-align:center">Count</th><th style="width:120px">Affected Agents</th><th style="width:100px">Last Seen (IST)</th></tr></thead><tbody>{thr_rows}</tbody></table>'
    else:
        threats_html = '<div style="text-align:center;padding:60px 20px"><div style="width:64px;height:64px;background:#f0fdf4;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;margin-bottom:16px"><svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#2ecc71" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg></div><div style="font-size:16px;font-weight:700;color:#1a1a2e;margin-bottom:6px">No Top Threats Found</div><div style="font-size:10px;color:#69707D;max-width:400px;margin:0 auto">No alerts with severity level 12 or above were detected.</div></div>'

    # Agent risk table
    ar_rows = "".join(f'<tr style="background:{"#fff" if i%2==0 else "#f8f9fb"};border-left:3px solid {_rc(a["risk"])}"><td style="padding:4px 6px;border-bottom:1px solid #ecf0f1;font-size:8px;font-weight:600">{a["name"]}</td><td style="padding:4px 6px;border-bottom:1px solid #ecf0f1;text-align:center;font-size:8px">{_fc(a["count"])}</td><td style="padding:4px 6px;border-bottom:1px solid #ecf0f1;text-align:center;font-size:8px;font-weight:700;color:#BD271E">{a["critical"] or "-"}</td><td style="padding:4px 6px;border-bottom:1px solid #ecf0f1;text-align:center;font-size:8px;font-weight:700;color:#E7664C">{a["high"] or "-"}</td><td style="padding:4px 6px;border-bottom:1px solid #ecf0f1;text-align:center;font-size:8px;color:#D6BF57">{_fc(a["medium"]) if a["medium"]>0 else "-"}</td><td style="padding:4px 6px;border-bottom:1px solid #ecf0f1;text-align:center"><div style="background:#ecf0f1;border-radius:8px;height:12px;overflow:hidden;width:50px;display:inline-block"><div style="background:{_rc(a["risk"])};height:100%;width:{a["score"]}%;border-radius:8px"></div></div><span style="font-size:7px;font-weight:700;color:{_rc(a["risk"])};margin-left:3px">{a["score"]}</span></td><td style="padding:4px 6px;border-bottom:1px solid #ecf0f1;text-align:center"><span style="background:{_rc(a["risk"])};color:#fff;padding:1px 6px;border-radius:8px;font-size:6.5px;font-weight:700">{a["risk"]}</span></td><td style="padding:4px 6px;border-bottom:1px solid #ecf0f1;font-size:7px;color:#69707D;font-style:italic">{a["note"]}</td></tr>' for i,a in enumerate(d["agent_risk"]))

    recs_html = "".join(f'<div style="display:flex;align-items:flex-start;margin-bottom:8px;padding:8px 12px;border-radius:6px;background:#fafbfc;border-left:3px solid {r["color"]}"><div style="width:24px;height:24px;border-radius:50%;background:{r["color"]};color:#fff;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700;flex-shrink:0;margin-right:10px">{r["icon"]}</div><div style="font-size:9px;line-height:1.5;color:#34495e">{r["text"]}</div></div>' for r in d["recommendations"])

    # Source IPs
    if d["top_srcips"]:
        mx_ip = d["top_srcips"][0]["count"]
        int_tag = '<span style="background:#e8f4fd;color:#3498db;padding:1px 5px;border-radius:3px;font-size:7px;font-weight:600">INTERNAL</span>'
        ext_tag = '<span style="background:#fdf2f2;color:#e74c3c;padding:1px 5px;border-radius:3px;font-size:7px;font-weight:600">EXTERNAL</span>'
        ip_rows = ""
        for i, ip in enumerate(d["top_srcips"]):
            bg = "#fff" if i%2==0 else "#f8f9fb"
            is_priv = ip["ip"].startswith(("192.168.","10.","172.","fe80"))
            tag = int_tag if is_priv else ext_tag
            bar_c = "#3498db" if is_priv else "#e74c3c"
            pct = round(ip["count"]/mx_ip*100)
            ip_rows += f'<tr style="background:{bg}"><td style="padding:5px 8px;border-bottom:1px solid #ecf0f1;font-size:8px;text-align:center;font-weight:700;color:#95a5a6">{i+1}</td><td style="padding:5px 8px;border-bottom:1px solid #ecf0f1;font-size:9px;font-family:monospace;font-weight:600">{ip["ip"]} {tag}</td><td style="padding:5px 8px;border-bottom:1px solid #ecf0f1;text-align:right;font-weight:700;font-size:9px">{_fc(ip["count"])}</td><td style="padding:5px 8px;border-bottom:1px solid #ecf0f1"><div style="background:#ecf0f1;border-radius:4px;height:14px;overflow:hidden"><div style="background:{bar_c};height:100%;width:{pct}%;border-radius:4px;min-width:2px"></div></div></td></tr>'
        srcip_html = f'<table><thead><tr><th style="width:30px">#</th><th>IP Address</th><th style="text-align:right;width:80px">Events</th><th style="width:200px">Activity</th></tr></thead><tbody>{ip_rows}</tbody></table><div style="margin-top:10px;display:flex;gap:16px;font-size:8px;color:#69707D"><div><span style="display:inline-block;width:10px;height:10px;background:#3498db;border-radius:2px;vertical-align:middle;margin-right:4px"></span>Internal</div><div><span style="display:inline-block;width:10px;height:10px;background:#e74c3c;border-radius:2px;vertical-align:middle;margin-right:4px"></span>External</div></div>'
    else:
        srcip_html = '<div style="text-align:center;color:#95a5a6;font-size:9px;padding:20px">No source IP data</div>'

    # Vulnerability
    vsev = ""
    if d["vuln_total"] > 0 and d["vuln_by_sev"]:
        vc_map = {"Critical":"#BD271E","High":"#E7664C","Medium":"#D6BF57","Low":"#6DCCB1"}
        vsev_items = ""
        for v in d["vuln_by_sev"]:
            vc = vc_map.get(v["severity"], "#95a5a6")
            vsev_items += f'<div style="flex:1;text-align:center;padding:12px;border-radius:8px;border:1px solid #ecf0f1;background:#fafbfc"><div style="font-size:22px;font-weight:800;color:{vc}">{_fc(v["count"])}</div><div style="font-size:9px;color:#69707D;margin-top:3px">{v["severity"]}</div></div>'
        vsev = f'<div style="display:flex;gap:8px;margin-bottom:14px">{vsev_items}</div>'

    # FIM event cards
    fim_cards = f'<div style="flex:1;text-align:center;padding:16px;border-radius:8px;background:#f0f4ff;border:1px solid #b3c6ff"><div style="font-size:28px;font-weight:800;color:#3498db">{_fc(d["fim_total"])}</div><div style="font-size:9px;color:#69707D;margin-top:4px">Total FIM Events</div></div>'
    for e in d["fim_events"]:
        ec = {"deleted":"#e74c3c","added":"#2ecc71","modified":"#e67e22"}.get(e["event"],"#3498db")
        fim_cards += f'<div style="flex:1;text-align:center;padding:16px;border-radius:8px;border:1px solid #ecf0f1;background:#fafbfc"><div style="font-size:28px;font-weight:800;color:{ec}">{_fc(e["count"])}</div><div style="font-size:9px;color:#69707D;margin-top:4px">{e["event"].capitalize()}</div></div>'

    # Compliance
    c = d.get("compliance",{})
    fw_info = [("pci","PCI-DSS","#3498db","#f0f4ff","#b3c6ff"),("hipaa","HIPAA","#2ecc71","#f0fdf4","#a3cfbb"),("gdpr","GDPR","#e67e22","#fef9f0","#f5d6a3"),("nist","NIST 800-53","#9b59b6","#fdf2f2","#f5c6cb"),("tsc","TSC","#8e44ad","#f5f0ff","#d5c6f5")]
    comp_cards = "".join(f'<div style="flex:1;min-width:100px;text-align:center;padding:12px;border-radius:8px;background:{bg};border:1px solid {bd}"><div style="font-size:22px;font-weight:800;color:{cl}">{_fc(c.get(k,{}).get("total",0))}</div><div style="font-size:8px;color:#69707D;margin-top:3px;font-weight:600">{nm}</div></div>' for k,nm,cl,bg,bd in fw_info)

    def fw_tbl(k,nm,cl,col="Control"):
        ctrls = c.get(k,{}).get("controls",[])
        if not ctrls: return f'<div style="text-align:center;color:#95a5a6;font-size:9px;padding:12px">No {nm} data</div>'
        rows = "".join(f'<tr style="background:{"#fff" if i%2==0 else "#f8f9fb"}"><td style="padding:3px 8px;border-bottom:1px solid #ecf0f1;font-size:8px;font-family:monospace">{ct["control"]}</td><td style="padding:3px 8px;border-bottom:1px solid #ecf0f1;text-align:right;font-weight:700;font-size:8px">{_fc(ct["count"])}</td></tr>' for i,ct in enumerate(ctrls))
        return f'<table><thead><tr><th>{col}</th><th style="text-align:right">Alerts</th></tr></thead><tbody>{rows}</tbody></table>'

    tsc_sec = f'<div class="card"><div class="stitle"><span class="dot" style="background:#8e44ad"></span>TSC (Trust Services Criteria)</div>{fw_tbl("tsc","TSC","#8e44ad","Criteria")}</div>' if c.get("tsc",{}).get("total",0)>0 else ""

    css = '@page{size:A4 portrait;margin:0}*{margin:0;padding:0;box-sizing:border-box}body{font-family:"Segoe UI",Arial,sans-serif;font-size:9px;color:#2c3e50;background:#fff}.page{page-break-after:always;width:210mm;min-height:297mm;padding:20px 24px 40px;position:relative}.page:last-child{page-break-after:auto}.card{background:#fff;border-radius:10px;box-shadow:0 1px 6px rgba(0,0,0,0.05);padding:14px;margin-bottom:12px;border:1px solid #ecf0f1}.stitle{font-size:12px;font-weight:700;color:#2c3e50;margin:0 0 10px;padding:6px 0;border-bottom:2px solid #3498db;display:flex;align-items:center}.stitle .dot{width:8px;height:8px;border-radius:50%;background:#3498db;margin-right:8px;flex-shrink:0}.hdr{background:linear-gradient(135deg,#1a1a2e,#16213e,#0f3460);color:#fff;padding:12px 20px;border-radius:8px;margin-bottom:14px}.hdr h2{font-size:15px;font-weight:700;margin-bottom:2px}.hdr p{font-size:8px;opacity:0.8}table{width:100%;border-collapse:collapse;font-size:8px}tr{page-break-inside:avoid;break-inside:avoid}td{word-wrap:break-word;overflow-wrap:break-word;max-width:300px}thead{display:table-header-group}tbody{display:table-row-group}thead th{background:linear-gradient(135deg,#1a1a2e,#16213e);color:#fff;padding:6px 8px;text-align:left;font-size:7.5px;text-transform:uppercase;letter-spacing:0.5px}'

    the_head = '<thead><tr><th style="width:25px;text-align:center">#</th><th style="width:50px;text-align:center">Rule ID</th><th>Description</th><th style="width:42px;text-align:center">Level</th><th style="width:65px;text-align:right;padding-right:10px">Count</th></tr></thead>'

    ta0 = d["top_agents"][0] if d["top_agents"] else {"name":"N/A","count":0}

    # Build pages list - only include sections that are in the template
    pages = []

    # Cover page (always)
    pages.append(f'<div class="page" style="padding:0;overflow:hidden;position:relative;background:{cco}"><div style="position:absolute;top:-100px;right:-100px;width:450px;height:450px;border-radius:50%;background:linear-gradient(135deg,{cac},#14919B);opacity:0.15"></div><div style="position:absolute;bottom:-150px;left:-100px;width:400px;height:400px;border-radius:50%;background:linear-gradient(135deg,#14919B,{cac});opacity:0.1"></div><div style="height:5px;background:linear-gradient(90deg,{cac},#14919B,#32DBC6)"></div><div style="position:relative;z-index:1;padding:60px 50px 40px">{logo}<div style="margin-bottom:50px"><div style="font-size:14px;color:{cac};text-transform:uppercase;letter-spacing:4px;font-weight:600;margin-bottom:14px">Security Report</div><h1 style="font-size:48px;font-weight:800;color:#fff;line-height:1.05;margin-bottom:0">{t1}</h1><h1 style="font-size:48px;font-weight:800;color:{cac};line-height:1.05;margin-bottom:16px">{t2}</h1><div style="width:50px;height:4px;background:{cac};border-radius:2px"></div></div><p style="font-size:13px;color:rgba(255,255,255,0.45);letter-spacing:1px;margin-bottom:40px">{d.get("cover_subtitle","")} &bull; {pla}</p><div style="display:flex;gap:0;margin-bottom:40px;background:rgba(0,0,0,0.2);border-radius:8px;overflow:hidden"><div style="flex:1;padding:18px 22px;border-left:3px solid {cac}"><div style="font-size:8px;text-transform:uppercase;letter-spacing:2px;color:rgba(255,255,255,0.4);margin-bottom:8px">Prepared For</div><div style="font-size:15px;font-weight:700;color:#fff;margin-bottom:4px">{d["client_name"]}</div><div style="font-size:10px;color:rgba(255,255,255,0.5);line-height:1.4">{d["client_address"]}</div></div><div style="flex:1;padding:18px 22px;border-left:1px solid rgba(255,255,255,0.08)"><div style="font-size:8px;text-transform:uppercase;letter-spacing:2px;color:rgba(255,255,255,0.4);margin-bottom:8px">Period</div><div style="font-size:11px;font-weight:600;color:#fff;margin-bottom:4px">{d["from_date"]}</div><div style="font-size:11px;font-weight:600;color:#fff">{d["to_date"]}</div></div><div style="flex:1;padding:18px 22px;border-left:1px solid rgba(255,255,255,0.08)"><div style="font-size:8px;text-transform:uppercase;letter-spacing:2px;color:rgba(255,255,255,0.4);margin-bottom:8px">Generated</div><div style="font-size:11px;font-weight:600;color:#fff;margin-bottom:4px">{d["ist_date"]}</div><div style="font-size:11px;color:rgba(255,255,255,0.5)">{d["ist_time"]} IST</div></div></div></div></div>')

    if has("executive_summary"):
        pages.append(f'<div class="page"><div class="hdr"><h2>Executive Summary</h2><p>{pla} alert overview</p></div><div class="card" style="background:#f8f9fb;border-left:4px solid #3498db;margin-bottom:14px"><div style="font-size:9px;line-height:1.6;color:#34495e">During the reporting period <strong>{d["from_date"]}</strong> to <strong>{d["to_date"]}</strong>, a total of <strong>{_fc(d["total_alerts"])}</strong> security alerts were recorded. Of these, <strong style="color:#BD271E">{_fc(sc["Critical"])} critical</strong> and <strong style="color:#E7664C">{_fc(sc["High"])} high</strong> severity alerts (level 12+: {_fc(d["level12_count"])}) require attention. There were <strong style="color:#e74c3c">{_fc(d["auth_fail_count"])} authentication failures</strong> and <strong style="color:#2ecc71">{_fc(d["auth_success_count"])} successful logons</strong>. {"Vulnerability detection identified <strong>" + _fc(d["vuln_total"]) + " vulnerability events</strong>." if d["vuln_total"]>0 else "No vulnerability events detected."} Top agent: <strong>{ta0["name"]}</strong> with {_fc(ta0["count"])} alerts. MITRE ATT&amp;CK: <strong>{len(d["mitre_techniques"])} techniques</strong> across <strong>{len(d["mitre_tactics"])} tactics</strong>.</div></div><div class="card" style="margin-bottom:14px;padding:10px 16px"><div class="stitle" style="margin-bottom:8px"><span class="dot" style="background:#9b59b6"></span>Period Comparison</div><div style="display:flex;gap:10px;font-size:9px">{dod}</div></div><div style="display:flex;gap:8px;margin-bottom:14px">{stat_cards}</div><div class="card"><div class="stitle"><span class="dot"></span>Severity Distribution</div><div style="display:flex;align-items:center;justify-content:center;gap:24px">{donut}<div>{donut_leg}</div></div></div><div class="card"><div class="stitle"><span class="dot"></span>{tl_label}</div><div style="text-align:center">{tl_svg}</div></div></div>')

    if has("top_threats"):
        pages.append(f'<div class="page"><div class="hdr" style="background:linear-gradient(135deg,#BD271E,#920000)"><h2 style="color:#fff">Top Threat Alerts</h2><p style="color:rgba(255,255,255,0.8)">{str(d["incident_count"])+" critical/high severity events" if d["incident_count"]>0 else "No high severity threats detected"}</p></div>{threats_html}</div>')

    if has("agents_risk"):
        pages.append(f'<div class="page"><div class="hdr"><h2>Agents &amp; Risk Assessment</h2><p>Agent overview, severity breakdown, risk scoring and recommendations</p></div><div class="card"><div class="stitle"><span class="dot" style="background:#2ecc71"></span>Top {len(d["top_agents"])} Agents (Alert Volume)</div><div style="text-align:center">{ag_svg}</div></div><div class="card"><div class="stitle"><span class="dot" style="background:#e74c3c"></span>Agent Risk Scores</div><table><thead><tr><th>Agent</th><th style="text-align:center">Total</th><th style="text-align:center;color:#BD271E">Crit</th><th style="text-align:center;color:#E7664C">High</th><th style="text-align:center;color:#D6BF57">Med</th><th style="text-align:center">Score</th><th style="text-align:center">Risk</th><th>Action</th></tr></thead><tbody>{ar_rows}</tbody></table></div><div class="card"><div class="stitle"><span class="dot" style="background:#f39c12"></span>Recommendations</div>{recs_html}</div></div>')

    if has("authentication"):
        pages.append(f'<div class="page"><div class="hdr"><h2>Authentication Events</h2><p>Login success and failure analysis</p></div><div style="display:flex;gap:10px;margin-bottom:14px"><div style="flex:1;text-align:center;padding:16px;border-radius:8px;background:#fdf2f2;border:1px solid #f5c6cb"><div style="font-size:28px;font-weight:800;color:#e74c3c">{_fc(d["auth_fail_count"])}</div><div style="font-size:9px;color:#69707D;margin-top:4px">Authentication Failures</div></div><div style="flex:1;text-align:center;padding:16px;border-radius:8px;background:#f0fdf4;border:1px solid #a3cfbb"><div style="font-size:28px;font-weight:800;color:#2ecc71">{_fc(d["auth_success_count"])}</div><div style="font-size:9px;color:#69707D;margin-top:4px">Successful Logons</div></div><div style="flex:1;text-align:center;padding:16px;border-radius:8px;background:#f0f4ff;border:1px solid #b3c6ff"><div style="font-size:28px;font-weight:800;color:#3498db">{_fc(d["auth_fail_count"]+d["auth_success_count"])}</div><div style="font-size:9px;color:#69707D;margin-top:4px">Total Auth Events</div></div></div><div style="display:flex;gap:12px;margin-bottom:12px"><div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#e74c3c"></span>Top Failed Login Users</div>{_stbl(d["auth_fail_users"],"user","User","Failures","#e74c3c")}</div><div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#e67e22"></span>Top Source IPs (Failed)</div>{_stbl(d["auth_fail_ips"],"ip","IP Address","Attempts","#e67e22")}</div></div><div class="card"><div class="stitle"><span class="dot" style="background:#2ecc71"></span>Successful Logon Users</div>{_stbl(d["auth_success_users"],"user","User","Logons","#2ecc71")}</div><div style="display:flex;gap:12px;margin-bottom:12px"><div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#e74c3c"></span>Top Failed Login Events</div>{_stbl(d["auth_fail_events"],"desc","Rule Description","Count","#e74c3c",font="7.5px")}</div><div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#2ecc71"></span>Top Success Login Events</div>{_stbl(d["auth_success_events"],"desc","Rule Description","Count","#2ecc71",font="7.5px")}</div></div>{auth_daily_svg}</div>')

    if has("source_ips"):
        pages.append(f'<div class="page"><div class="hdr"><h2>Top Source IPs</h2><p>Most active source IP addresses</p></div>{srcip_html}</div>')

    if has("vulnerability"):
        pages.append(f'<div class="page"><div class="hdr"><h2>Vulnerability Detection</h2><p>Vulnerability alerts (rule.groups: vulnerability-detector)</p></div>{vsev}<div style="display:flex;gap:12px;margin-bottom:12px"><div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#e74c3c"></span>Top CVEs</div>{_stbl(d["vuln_top_cve"],"cve","CVE ID","Count","#e74c3c")}</div><div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#3498db"></span>Affected Agents</div>{_stbl(d["vuln_top_agent"],"agent","Agent","Vulns","#3498db")}</div></div><div class="card"><div class="stitle"><span class="dot" style="background:#9b59b6"></span>Affected Packages</div>{_stbl(d["vuln_top_pkg"],"pkg","Package","Count","#9b59b6")}</div></div>')

    if has("fim"):
        pages.append(f'<div class="page"><div class="hdr"><h2>File Integrity Monitoring</h2><p>File changes detected (rule.groups: syscheck)</p></div><div style="display:flex;gap:10px;margin-bottom:14px">{fim_cards}</div><div style="display:flex;gap:12px;margin-bottom:12px"><div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#3498db"></span>Top Agents (FIM)</div>{_stbl(d["fim_agents"],"agent","Agent","Changes","#3498db")}</div><div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#e67e22"></span>Top Modified Paths</div>{_stbl(d["fim_paths"],"path","File Path","Count","#e67e22",font="7px")}</div></div>{fim_daily_svg}</div>')

    if has("mitre"):
        pages.append(f'<div class="page"><div class="hdr"><h2>MITRE ATT&amp;CK Analysis</h2><p>Techniques and tactics detected</p></div><div class="card"><div class="stitle"><span class="dot" style="background:#e74c3c"></span>Top Techniques</div><div style="text-align:center">{tech_svg}</div></div><div class="card"><div class="stitle"><span class="dot" style="background:#e67e22"></span>Top Tactics</div><div style="text-align:center">{tac_svg}</div></div></div>')

    if has("compliance"):
        pages.append(f'<div class="page"><div class="hdr"><h2>Regulatory Compliance Mapping</h2><p>Alerts mapped to compliance frameworks</p></div><div style="display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap">{comp_cards}</div><div style="display:flex;gap:10px;margin-bottom:10px"><div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#3498db"></span>PCI-DSS Controls</div>{fw_tbl("pci","PCI-DSS","#3498db")}</div><div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#2ecc71"></span>HIPAA Controls</div>{fw_tbl("hipaa","HIPAA","#2ecc71")}</div></div><div style="display:flex;gap:10px;margin-bottom:10px"><div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#e67e22"></span>GDPR Articles</div>{fw_tbl("gdpr","GDPR","#e67e22","Article")}</div><div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#9b59b6"></span>NIST 800-53 Controls</div>{fw_tbl("nist","NIST 800-53","#9b59b6")}</div></div>{tsc_sec}</div>')

    if has("security_events"):
        pages.append(f'<div style="page-break-before:always" class="page"><div class="hdr"><h2>Security Events Summary</h2><p>All rules sorted by severity &bull; {len(sr)} unique rules</p></div><div class="card" style="padding:0;overflow:hidden"><table>{the_head}<tbody>{rp1}</tbody></table></div></div>')
        if rp2:
            pages.append(f'<div style="page-break-before:always" class="page"><div class="card" style="padding:0;overflow:hidden"><table>{the_head}<tbody>{rp2}</tbody></table></div></div>')

    # Render custom widget sections
    for sec_id in sections:
        if sec_id.startswith("widget_"):
            wid = sec_id.replace("widget_", "")
            widget_html = _render_widget_section(wid, d)
            if widget_html:
                pages.append(widget_html)

    return f'<!DOCTYPE html><html><head><meta charset="UTF-8"><title>{d["cover_title"]}</title><style>{css}</style></head><body>{"".join(pages)}</body></html>'


def _render_widget_section(widget_id, d):
    """Render a custom widget as a report page"""
    try:
        widgets = database.get_widgets()
        w = next((x for x in widgets if x["id"] == widget_id), None)
        if not w:
            return None

        cfg = json.loads(w["agg_config"]) if isinstance(w["agg_config"], str) else w["agg_config"]
        query_dsl = json.loads(w["query_dsl"]) if isinstance(w["query_dsl"], str) else w["query_dsl"]

        field = cfg.get("field", "rule.level")
        size = cfg.get("size", 10)
        color = cfg.get("color", "#0D7377")
        chart_type = cfg.get("chart_type", "bar")
        time_from = cfg.get("time_from", f"now-{d.get('period','24h')}")

        # Run aggregation
        must = [{"range": {"timestamp": {"gte": time_from, "lte": "now"}}}]
        if query_dsl and isinstance(query_dsl, dict) and query_dsl.get("bool"):
            must.extend(query_dsl["bool"].get("must", []))

        aggs = {"result": {"terms": {"field": field, "size": size, "order": {"_count": "desc"}}}}
        result = opensearch_client.run_aggregation({"bool": {"must": must}}, aggs)
        buckets = result["aggregations"]["result"]["buckets"]

        if not buckets:
            return f'<div class="page"><div class="hdr"><h2>{w["name"]}</h2><p>{w.get("description","Custom analysis")}</p></div><div style="text-align:center;color:#95a5a6;padding:40px">No data for this widget</div></div>'

        items = [{"value": b["doc_count"], "label": str(b["key"]), "color": color} for b in buckets]

        # Render chart based on type
        if chart_type in ("horizontalBar", "bar"):
            if chart_type == "horizontalBar":
                chart_svg = svg_hbars(items, 500, max(len(items) * 19 + 10, 80))
            else:
                chart_svg = svg_vbars(items, 500, 180)
        elif chart_type in ("doughnut", "pie"):
            chart_svg = svg_donut([{"value": i["value"], "color": PALETTE[idx % 15]} for idx, i in enumerate(items)], 200, 200, 80, 50)
        else:
            chart_svg = svg_vbars(items, 500, 180)

        # Also build a data table
        rows = "".join(f'<tr style="background:{"#fff" if i%2==0 else "#f8f9fb"}"><td style="padding:4px 8px;border-bottom:1px solid #ecf0f1;font-size:8px">{it["label"]}</td><td style="padding:4px 8px;border-bottom:1px solid #ecf0f1;text-align:right;font-weight:700;font-size:8px;color:{color}">{_fc(it["value"])}</td></tr>' for i, it in enumerate(items))
        table_html = f'<table><thead><tr><th>{field}</th><th style="text-align:right">Count</th></tr></thead><tbody>{rows}</tbody></table>'

        return f'''<div class="page">
  <div class="hdr" style="background:linear-gradient(135deg,{color},#1a1a2e)"><h2 style="color:#fff">{w["name"]}</h2><p style="color:rgba(255,255,255,0.7)">{w.get("description","Custom analysis")} &bull; {_fc(result["hits"]["total"]["value"])} total events</p></div>
  <div class="card"><div class="stitle"><span class="dot" style="background:{color}"></span>{w["name"]}</div><div style="text-align:center">{chart_svg}</div></div>
  <div class="card"><div class="stitle"><span class="dot" style="background:{color}"></span>Data Table</div>{table_html}</div>
</div>'''
    except Exception as e:
        return f'<div class="page"><div class="hdr"><h2>Widget Error</h2></div><div class="card"><p style="color:#e74c3c">{str(e)}</p></div></div>'

async def _html_to_pdf(html):
    url = f"{config.GOTENBERG_URL}/forms/chromium/convert/html"
    data = aiohttp.FormData()
    data.add_field("files", html.encode(), filename="index.html", content_type="text/html")
    data.add_field("preferCssPageSize", "true")
    data.add_field("printBackground", "true")
    data.add_field("marginTop", "0")
    data.add_field("marginBottom", "0.6")
    data.add_field("marginLeft", "0")
    data.add_field("marginRight", "0")
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data) as resp:
            if resp.status == 200: return await resp.read(), None
            else: return None, f"Gotenberg error: {resp.status}"

async def generate_report(template_id, period="24h"):
    template = database.get_template(template_id)
    if not template: return None, "Template not found"
    try:
        query = build_query(period)
        client = opensearch_client.get_client()
        raw = client.search(index=config.OPENSEARCH_INDEX, body=query)
        data = process_data(raw, template, period)
        # Get sections from template
        secs = template.get("sections", [])
        if isinstance(secs, str):
            import json as _j
            secs = _j.loads(secs)
        html = render_html(data, secs if secs else None)
        pdf_bytes, err = await _html_to_pdf(html)
        if err: return None, err
        fname = f"report_{template['name'].replace(' ','_')}_{datetime.now(IST).strftime('%Y%m%d_%H%M')}.pdf"
        fpath = os.path.join(config.REPORTS_DIR, fname)
        os.makedirs(config.REPORTS_DIR, exist_ok=True)
        with open(fpath, "wb") as f: f.write(pdf_bytes)
        rid = database.save_report(template_id, fname, data["from_date"], data["to_date"], len(pdf_bytes))
        return {"id": rid, "filename": fname, "size": len(pdf_bytes)}, None
    except Exception as e: return None, str(e)

async def generate_quick_report(period="24h"):
    try:
        query = build_query(period)
        client = opensearch_client.get_client()
        raw = client.search(index=config.OPENSEARCH_INDEX, body=query)
        data = process_data(raw, period=period)
        html = render_html(data)
        pdf_bytes, err = await _html_to_pdf(html)
        if err: return None, err
        fname = f"quick_report_{datetime.now(IST).strftime('%Y%m%d_%H%M')}.pdf"
        fpath = os.path.join(config.REPORTS_DIR, fname)
        os.makedirs(config.REPORTS_DIR, exist_ok=True)
        with open(fpath, "wb") as f: f.write(pdf_bytes)
        rid = database.save_report(None, fname, data["from_date"], data["to_date"], len(pdf_bytes))
        return {"id": rid, "filename": fname, "size": len(pdf_bytes)}, None
    except Exception as e: return None, str(e)
