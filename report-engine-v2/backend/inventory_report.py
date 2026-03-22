"""Inventory Management Report Generator
Queries wazuh-states-inventory-* indices for asset, software, process, port, service, user, and vulnerability data.
"""
import json, os, math, aiohttp
from datetime import datetime, timedelta, timezone
from pdf_generator import svg_donut, svg_hbars, svg_vbars, _fc, _html_to_pdf, PALETTE, IST
import config, database, opensearch_client

def _query(index_pattern, aggs, size=0, query=None):
    """Run aggregation on inventory index"""
    client = opensearch_client.get_client()
    body = {"size": size, "aggs": aggs}
    if query:
        body["query"] = query
    return client.search(index=index_pattern, body=body)

def _stbl(items, key, hdr, chdr, color, font="8px"):
    if not items:
        return '<div style="text-align:center;color:#95a5a6;font-size:9px;padding:20px">No data</div>'
    rows = "".join(f'<tr style="background:{"#fff" if i%2==0 else "#f8f9fb"}"><td style="padding:4px 8px;border-bottom:1px solid #ecf0f1;font-size:{font}">{item[key]}</td><td style="padding:4px 8px;border-bottom:1px solid #ecf0f1;text-align:right;font-weight:700;font-size:8px;color:{color}">{_fc(item["count"])}</td></tr>' for i, item in enumerate(items))
    return f'<table><thead><tr><th>{hdr}</th><th style="text-align:right;padding-right:10px">{chdr}</th></tr></thead><tbody>{rows}</tbody></table>'

def collect_inventory_data():
    """Collect all inventory data from OpenSearch"""
    idx = "wazuh-states-inventory-*"
    vuln_idx = "wazuh-states-vulnerabilities-*"
    data = {}

    # 1. System/Hardware overview
    try:
        r = _query(f"{config.OPENSEARCH_INDEX.split('-')[0]}-states-inventory-system-*", {
            "agents": {"terms": {"field": "agent.name", "size": 50}},
            "os_name": {"terms": {"field": "host.os.name", "size": 10}},
            "os_platform": {"terms": {"field": "host.os.platform", "size": 10}},
            "arch": {"terms": {"field": "host.architecture", "size": 5}}
        })
        data["total_endpoints"] = r["hits"]["total"]["value"]
        data["os_distribution"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["os_name"]["buckets"]]
        data["os_platform"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["os_platform"]["buckets"]]
        data["architectures"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["arch"]["buckets"]]
        data["agents"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["agents"]["buckets"]]
    except:
        data["total_endpoints"] = 0
        data["os_distribution"] = []
        data["os_platform"] = []
        data["architectures"] = []
        data["agents"] = []

    # Hardware
    try:
        r = _query(f"{config.OPENSEARCH_INDEX.split('-')[0]}-states-inventory-hardware-*", {
            "cpu_names": {"terms": {"field": "host.cpu.name", "size": 10}},
            "avg_memory": {"avg": {"field": "host.memory.usage"}},
            "agents_hw": {"terms": {"field": "agent.name", "size": 50},
                "aggs": {"mem_total": {"avg": {"field": "host.memory.total"}}, "mem_used": {"avg": {"field": "host.memory.usage"}}, "cpu_cores": {"avg": {"field": "host.cpu.cores"}}}}
        })
        data["cpu_types"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["cpu_names"]["buckets"]]
        data["avg_memory_usage"] = round((r["aggregations"]["avg_memory"]["value"] or 0) * 100, 1)
        data["hardware_agents"] = []
        for b in r["aggregations"]["agents_hw"]["buckets"]:
            mem_total = b["mem_total"]["value"] or 0
            mem_pct = round((b["mem_used"]["value"] or 0) * 100, 1)
            cores = int(b["cpu_cores"]["value"] or 0)
            data["hardware_agents"].append({
                "name": b["key"], "memory_gb": round(mem_total / (1024**3), 1),
                "memory_pct": mem_pct, "cpu_cores": cores
            })
    except:
        data["cpu_types"] = []
        data["avg_memory_usage"] = 0
        data["hardware_agents"] = []

    # 2. Packages
    try:
        r = _query(f"{config.OPENSEARCH_INDEX.split('-')[0]}-states-inventory-packages-*", {
            "total": {"value_count": {"field": "package.name"}},
            "by_type": {"terms": {"field": "package.type", "size": 10}},
            "by_vendor": {"terms": {"field": "package.vendor", "size": 10}},
            "by_agent": {"terms": {"field": "agent.name", "size": 15}},
            "top_packages": {"terms": {"field": "package.name", "size": 15}}
        })
        data["total_packages"] = r["hits"]["total"]["value"]
        data["pkg_by_type"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["by_type"]["buckets"]]
        data["pkg_by_vendor"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["by_vendor"]["buckets"]]
        data["pkg_by_agent"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["by_agent"]["buckets"]]
        data["top_packages"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["top_packages"]["buckets"]]
    except:
        data["total_packages"] = 0
        data["pkg_by_type"] = []
        data["pkg_by_vendor"] = []
        data["pkg_by_agent"] = []
        data["top_packages"] = []

    # 3. Processes
    try:
        r = _query(f"{config.OPENSEARCH_INDEX.split('-')[0]}-states-inventory-processes-*", {
            "top_processes": {"terms": {"field": "process.name", "size": 15}},
            "by_agent": {"terms": {"field": "agent.name", "size": 15}}
        })
        data["total_processes"] = r["hits"]["total"]["value"]
        data["top_processes"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["top_processes"]["buckets"]]
        data["proc_by_agent"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["by_agent"]["buckets"]]
    except:
        data["total_processes"] = 0
        data["top_processes"] = []
        data["proc_by_agent"] = []

    # 4. Ports
    try:
        r = _query(f"{config.OPENSEARCH_INDEX.split('-')[0]}-states-inventory-ports-*", {
            "by_state": {"terms": {"field": "interface.state", "size": 5}},
            "by_transport": {"terms": {"field": "network.transport", "size": 5}},
            "top_ports": {"terms": {"field": "source.port", "size": 15}},
            "top_services": {"terms": {"field": "process.name", "size": 15}},
            "by_agent": {"terms": {"field": "agent.name", "size": 15}}
        })
        data["total_ports"] = r["hits"]["total"]["value"]
        data["port_by_state"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["by_state"]["buckets"]]
        data["port_by_transport"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["by_transport"]["buckets"]]
        data["top_ports"] = [{"name": str(b["key"]), "count": b["doc_count"]} for b in r["aggregations"]["top_ports"]["buckets"]]
        data["port_services"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["top_services"]["buckets"]]
        data["ports_by_agent"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["by_agent"]["buckets"]]
    except:
        data["total_ports"] = 0
        data["port_by_state"] = []
        data["port_by_transport"] = []
        data["top_ports"] = []
        data["port_services"] = []
        data["ports_by_agent"] = []

    # 5. Services
    try:
        r = _query(f"{config.OPENSEARCH_INDEX.split('-')[0]}-states-inventory-services-*", {
            "by_state": {"terms": {"field": "service.state", "size": 10}},
            "by_type": {"terms": {"field": "service.type", "size": 10}},
            "by_start_type": {"terms": {"field": "service.start_type", "size": 10}},
            "by_agent": {"terms": {"field": "agent.name", "size": 15}}
        })
        data["total_services"] = r["hits"]["total"]["value"]
        data["svc_by_state"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["by_state"]["buckets"]]
        data["svc_by_type"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["by_type"]["buckets"]]
        data["svc_by_start_type"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["by_start_type"]["buckets"]]
        data["svc_by_agent"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["by_agent"]["buckets"]]
    except:
        data["total_services"] = 0
        data["svc_by_state"] = []
        data["svc_by_type"] = []
        data["svc_by_start_type"] = []
        data["svc_by_agent"] = []

    # 6. Users
    try:
        r = _query(f"{config.OPENSEARCH_INDEX.split('-')[0]}-states-inventory-users-*", {
            "by_type": {"terms": {"field": "user.type", "size": 5}},
            "by_agent": {"terms": {"field": "agent.name", "size": 15}},
            "logged_in": {"filter": {"term": {"login.status": True}}},
            "disabled": {"filter": {"term": {"login.status": False}}}
        })
        data["total_users"] = r["hits"]["total"]["value"]
        data["user_by_type"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["by_type"]["buckets"]]
        data["users_by_agent"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["by_agent"]["buckets"]]
        data["users_logged_in"] = r["aggregations"]["logged_in"]["doc_count"]
        data["users_disabled"] = r["aggregations"]["disabled"]["doc_count"]
    except:
        data["total_users"] = 0
        data["user_by_type"] = []
        data["users_by_agent"] = []
        data["users_logged_in"] = 0
        data["users_disabled"] = 0

    # 7. Browser Extensions
    try:
        idx_prefix = config.OPENSEARCH_INDEX.split('-')[0]
        r = _query(f"{idx_prefix}-states-inventory-browser-extensions-*", {
            "by_browser": {"terms": {"field": "browser.name", "size": 10}},
            "top_extensions": {"terms": {"field": "package.name", "size": 15}},
            "by_agent": {"terms": {"field": "agent.name", "size": 15}},
            "enabled": {"filter": {"term": {"package.enabled": True}}},
            "disabled": {"filter": {"term": {"package.enabled": False}}}
        })
        data["total_extensions"] = r["hits"]["total"]["value"]
        data["ext_by_browser"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["by_browser"]["buckets"]]
        data["top_extensions"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["top_extensions"]["buckets"]]
        data["ext_by_agent"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["by_agent"]["buckets"]]
        data["ext_enabled"] = r["aggregations"]["enabled"]["doc_count"]
        data["ext_disabled"] = r["aggregations"]["disabled"]["doc_count"]
    except:
        data["total_extensions"] = 0
        data["ext_by_browser"] = []
        data["top_extensions"] = []
        data["ext_by_agent"] = []
        data["ext_enabled"] = 0
        data["ext_disabled"] = 0

    # 8. Network Interfaces & Addresses
    try:
        r = _query(f"{idx_prefix}-states-inventory-interfaces-*", {
            "by_state": {"terms": {"field": "interface.state", "size": 5}},
            "top_interfaces": {"terms": {"field": "interface.name", "size": 10}},
            "by_agent": {"terms": {"field": "agent.name", "size": 15}}
        })
        data["total_interfaces"] = r["hits"]["total"]["value"]
        data["iface_by_state"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["by_state"]["buckets"]]
        data["top_interfaces"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["top_interfaces"]["buckets"]]
        data["iface_by_agent"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["by_agent"]["buckets"]]
    except:
        data["total_interfaces"] = 0
        data["iface_by_state"] = []
        data["top_interfaces"] = []
        data["iface_by_agent"] = []

    try:
        r = _query(f"{idx_prefix}-states-inventory-networks-*", {
            "by_type": {"terms": {"field": "network.type", "size": 5}},
            "unique_ips": {"cardinality": {"field": "network.ip"}},
            "top_ips": {"terms": {"field": "network.ip", "size": 15}},
            "by_agent": {"terms": {"field": "agent.name", "size": 15}}
        })
        data["total_networks"] = r["hits"]["total"]["value"]
        data["net_by_type"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["by_type"]["buckets"]]
        data["unique_ips"] = r["aggregations"]["unique_ips"]["value"]
        data["top_network_ips"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["top_ips"]["buckets"]]
        data["net_by_agent"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["by_agent"]["buckets"]]
    except:
        data["total_networks"] = 0
        data["net_by_type"] = []
        data["unique_ips"] = 0
        data["top_network_ips"] = []
        data["net_by_agent"] = []

    # 9. User Details (groups, shells)
    try:
        r = _query(f"{idx_prefix}-states-inventory-users-*", {
            "top_users": {"terms": {"field": "user.name", "size": 15}},
            "groups": {"terms": {"field": "user.groups", "size": 15}},
            "shells": {"terms": {"field": "user.shell", "size": 10}}
        })
        data["top_usernames"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["top_users"]["buckets"]]
        data["user_groups"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["groups"]["buckets"]]
        data["user_shells"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["shells"]["buckets"]]
    except:
        data["top_usernames"] = []
        data["user_groups"] = []
        data["user_shells"] = []

    # 10. Windows Hotfixes
    try:
        r = _query(f"{idx_prefix}-states-inventory-hotfixes-*", {
            "top_hotfixes": {"terms": {"field": "package.hotfix.name", "size": 15}},
            "by_agent": {"terms": {"field": "agent.name", "size": 15}}
        })
        data["total_hotfixes"] = r["hits"]["total"]["value"]
        data["top_hotfixes"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["top_hotfixes"]["buckets"]]
        data["hotfix_by_agent"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["by_agent"]["buckets"]]
    except:
        data["total_hotfixes"] = 0
        data["top_hotfixes"] = []
        data["hotfix_by_agent"] = []

    # 11. Vulnerabilities
    try:
        r = _query(f"{config.OPENSEARCH_INDEX.split('-')[0]}-states-vulnerabilities-*", {
            "by_severity": {"terms": {"field": "vulnerability.severity", "size": 5}},
            "by_agent": {"terms": {"field": "agent.name", "size": 15}},
            "by_category": {"terms": {"field": "vulnerability.category", "size": 10}},
            "top_cves": {"terms": {"field": "vulnerability.id", "size": 10}},
            "top_packages": {"terms": {"field": "package.name", "size": 10}},
            "avg_score": {"avg": {"field": "vulnerability.score.base"}}
        })
        data["total_vulns"] = r["hits"]["total"]["value"]
        data["vuln_by_severity"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["by_severity"]["buckets"]]
        data["vuln_by_agent"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["by_agent"]["buckets"]]
        data["vuln_by_category"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["by_category"]["buckets"]]
        data["vuln_top_cves"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["top_cves"]["buckets"]]
        data["vuln_top_packages"] = [{"name": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["top_packages"]["buckets"]]
        data["vuln_avg_score"] = round(r["aggregations"]["avg_score"]["value"] or 0, 1)
    except:
        data["total_vulns"] = 0
        data["vuln_by_severity"] = []
        data["vuln_by_agent"] = []
        data["vuln_by_category"] = []
        data["vuln_top_cves"] = []
        data["vuln_top_packages"] = []
        data["vuln_avg_score"] = 0

    return data


def _render_hotfixes(d):
    if d.get("total_hotfixes", 0) == 0:
        return ""
    return '<div class="page"><div class="hdr"><h2>Windows Hotfixes</h2><p>' + _fc(d["total_hotfixes"]) + ' hotfixes installed across Windows endpoints</p></div><div style="display:flex;gap:12px;margin-bottom:12px"><div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#3498db"></span>Top Hotfixes (KB Articles)</div>' + _stbl(d["top_hotfixes"], "name", "Hotfix", "Agents", "#3498db") + '</div><div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#e67e22"></span>Hotfixes per Agent</div>' + _stbl(d["hotfix_by_agent"], "name", "Agent", "Hotfixes", "#e67e22") + '</div></div></div>'

def render_inventory_html(d, template_cfg=None):
    """Render inventory management report HTML"""
    now = datetime.now(IST)
    cover_color = "#1B2A4A"
    cover_accent = "#0D7377"
    client_name = "Codesec Technologies"
    client_logo = "https://codesecure.in/images/codesec-logo1.png"
    if template_cfg:
        cover_color = template_cfg.get("cover_color", cover_color)
        cover_accent = template_cfg.get("cover_accent", cover_accent)
        client_name = template_cfg.get("description", client_name) or client_name
        client_logo = template_cfg.get("logo_url", client_logo) or client_logo

    logo_html = f'<div style="margin-bottom:40px;display:inline-flex;align-items:center;justify-content:center;background:#fff;padding:16px;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.15)"><img src="{client_logo}" style="height:40px;display:block" onerror="this.style.display=\'none\'"/></div>' if client_logo else ""

    # Summary cards
    windows_count = sum(o["count"] for o in d["os_platform"] if o["name"].lower() == "windows")
    linux_count = sum(o["count"] for o in d["os_platform"] if o["name"].lower() in ("linux", "ubuntu", "centos", "rhel", "debian", "fedora", "amazon", "suse"))
    mac_count = sum(o["count"] for o in d["os_platform"] if o["name"].lower() in ("darwin", "macos", "macosx"))
    other_count = d["total_endpoints"] - windows_count - linux_count - mac_count

    # SVG charts
    os_donut = svg_donut([{"value": o["count"], "color": PALETTE[i % 15]} for i, o in enumerate(d["os_distribution"])], 180, 180, 70, 45) if d["os_distribution"] else ""
    os_legend = "".join(f'<div style="display:flex;align-items:center;margin:3px 0"><div style="width:12px;height:12px;border-radius:3px;background:{PALETTE[i%15]};margin-right:6px"></div><div style="font-size:8px"><strong>{o["name"][:30]}</strong>: {_fc(o["count"])}</div></div>' for i, o in enumerate(d["os_distribution"]))

    vuln_colors = {"Critical": "#BD271E", "High": "#E7664C", "Medium": "#D6BF57", "Low": "#6DCCB1"}
    vuln_donut = svg_donut([{"value": v["count"], "color": vuln_colors.get(v["name"], "#95a5a6")} for v in d["vuln_by_severity"]], 180, 180, 70, 45) if d["vuln_by_severity"] else ""
    vuln_legend = "".join(f'<div style="display:flex;align-items:center;margin:3px 0"><div style="width:12px;height:12px;border-radius:3px;background:{vuln_colors.get(v["name"],"#95a5a6")};margin-right:6px"></div><div style="font-size:8px"><strong>{v["name"]}</strong>: {_fc(v["count"])}</div></div>' for v in d["vuln_by_severity"])

    pkg_type_bars = svg_hbars([{"value": p["count"], "label": p["name"], "color": PALETTE[i%15]} for i, p in enumerate(d["pkg_by_type"])], 250, max(len(d["pkg_by_type"])*19+10, 60)) if d["pkg_by_type"] else ""
    proc_bars = svg_hbars([{"value": p["count"], "label": p["name"], "color": PALETTE[i%15]} for i, p in enumerate(d["top_processes"][:10])], 400, max(len(d["top_processes"][:10])*19+10, 60)) if d["top_processes"] else ""
    svc_state_bars = svg_hbars([{"value": s["count"], "label": s["name"], "color": "#2ecc71" if "RUNNING" in s["name"].upper() else "#e74c3c" if "STOPPED" in s["name"].upper() else "#3498db"} for s in d["svc_by_state"]], 250, max(len(d["svc_by_state"])*19+10, 60)) if d["svc_by_state"] else ""

    # Hardware table
    hw_rows = ""
    for i, h in enumerate(d.get("hardware_agents", [])):
        bg = "#fff" if i % 2 == 0 else "#f8f9fb"
        mem_color = "#2ecc71" if h["memory_pct"] < 60 else ("#e67e22" if h["memory_pct"] < 80 else "#e74c3c")
        hw_rows += f'<tr style="background:{bg}"><td style="padding:4px 8px;border-bottom:1px solid #ecf0f1;font-size:8px;font-weight:600">{h["name"]}</td><td style="padding:4px 8px;border-bottom:1px solid #ecf0f1;text-align:center;font-size:8px">{h["cpu_cores"]}</td><td style="padding:4px 8px;border-bottom:1px solid #ecf0f1;text-align:center;font-size:8px">{h["memory_gb"]} GB</td><td style="padding:4px 8px;border-bottom:1px solid #ecf0f1;text-align:center"><div style="display:inline-flex;align-items:center;gap:4px"><div style="background:#ecf0f1;border-radius:8px;height:10px;width:60px;overflow:hidden"><div style="background:{mem_color};height:100%;width:{h["memory_pct"]}%;border-radius:8px"></div></div><span style="font-size:7px;font-weight:700;color:{mem_color}">{h["memory_pct"]}%</span></div></td></tr>'

    css = '@page{size:A4 portrait;margin:0}*{margin:0;padding:0;box-sizing:border-box}body{font-family:"Segoe UI",Arial,sans-serif;font-size:9px;color:#2c3e50;background:#fff}.page{page-break-after:always;width:210mm;min-height:297mm;padding:20px 24px 40px;position:relative}.page:last-child{page-break-after:auto}.card{background:#fff;border-radius:10px;box-shadow:0 1px 6px rgba(0,0,0,0.05);padding:14px;margin-bottom:12px;border:1px solid #ecf0f1}.stitle{font-size:12px;font-weight:700;color:#2c3e50;margin:0 0 10px;padding:6px 0;border-bottom:2px solid #3498db;display:flex;align-items:center}.stitle .dot{width:8px;height:8px;border-radius:50%;background:#3498db;margin-right:8px;flex-shrink:0}.hdr{background:linear-gradient(135deg,#1a1a2e,#16213e,#0f3460);color:#fff;padding:12px 20px;border-radius:8px;margin-bottom:14px}.hdr h2{font-size:15px;font-weight:700;margin-bottom:2px}.hdr p{font-size:8px;opacity:0.8}table{width:100%;border-collapse:collapse;font-size:8px}tr{page-break-inside:avoid;break-inside:avoid}td{word-wrap:break-word;overflow-wrap:break-word;max-width:300px}thead{display:table-header-group}tbody{display:table-row-group}thead th{background:linear-gradient(135deg,#1a1a2e,#16213e);color:#fff;padding:6px 8px;text-align:left;font-size:7.5px;text-transform:uppercase;letter-spacing:0.5px}'

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>IT Asset Inventory Report</title><style>{css}</style></head><body>

<!-- COVER -->
<div class="page" style="padding:0;overflow:hidden;position:relative;background:{cover_color}">
  <div style="position:absolute;top:-100px;right:-100px;width:450px;height:450px;border-radius:50%;background:linear-gradient(135deg,{cover_accent},#14919B);opacity:0.15"></div>
  <div style="height:5px;background:linear-gradient(90deg,{cover_accent},#14919B,#32DBC6)"></div>
  <div style="position:relative;z-index:1;padding:60px 50px 40px">
    {logo_html}
    <div style="margin-bottom:50px">
      <div style="font-size:14px;color:{cover_accent};text-transform:uppercase;letter-spacing:4px;font-weight:600;margin-bottom:14px">Asset Report</div>
      <h1 style="font-size:44px;font-weight:800;color:#fff;line-height:1.05;margin-bottom:0">IT Asset &amp; Inventory</h1>
      <h1 style="font-size:44px;font-weight:800;color:{cover_accent};line-height:1.05;margin-bottom:16px">Management Report</h1>
      <div style="width:50px;height:4px;background:{cover_accent};border-radius:2px"></div>
    </div>
    <p style="font-size:13px;color:rgba(255,255,255,0.45);letter-spacing:1px;margin-bottom:40px">Comprehensive Infrastructure Inventory Analysis</p>
    <div style="display:flex;gap:0;background:rgba(0,0,0,0.2);border-radius:8px;overflow:hidden">
      <div style="flex:1;padding:18px 22px;border-left:3px solid {cover_accent}">
        <div style="font-size:8px;text-transform:uppercase;letter-spacing:2px;color:rgba(255,255,255,0.4);margin-bottom:8px">Prepared For</div>
        <div style="font-size:15px;font-weight:700;color:#fff">{client_name}</div>
      </div>
      <div style="flex:1;padding:18px 22px;border-left:1px solid rgba(255,255,255,0.08)">
        <div style="font-size:8px;text-transform:uppercase;letter-spacing:2px;color:rgba(255,255,255,0.4);margin-bottom:8px">Generated</div>
        <div style="font-size:11px;font-weight:600;color:#fff">{now.strftime("%d/%m/%Y")}</div>
        <div style="font-size:11px;color:rgba(255,255,255,0.5)">{now.strftime("%I:%M %p").lower()} IST</div>
      </div>
      <div style="flex:1;padding:18px 22px;border-left:1px solid rgba(255,255,255,0.08)">
        <div style="font-size:8px;text-transform:uppercase;letter-spacing:2px;color:rgba(255,255,255,0.4);margin-bottom:8px">Scope</div>
        <div style="font-size:11px;font-weight:600;color:#fff">{_fc(d["total_endpoints"])} Endpoints</div>
        <div style="font-size:11px;color:rgba(255,255,255,0.5)">{_fc(d["total_packages"])} Packages</div>
      </div>
    </div>
  </div>
</div>

<!-- ASSET OVERVIEW -->
<div class="page">
  <div class="hdr"><h2>Asset Overview</h2><p>Endpoint inventory and hardware specifications</p></div>
  <div style="display:flex;gap:8px;margin-bottom:14px">
    <div style="flex:1;text-align:center;padding:14px;border-radius:8px;background:#f0f4ff;border:1px solid #b3c6ff"><div style="font-size:28px;font-weight:800;color:#3498db">{_fc(d["total_endpoints"])}</div><div style="font-size:9px;color:#69707D;margin-top:4px">Total Endpoints</div></div>
    <div style="flex:1;text-align:center;padding:14px;border-radius:8px;background:#f0fdf4;border:1px solid #a3cfbb"><div style="font-size:28px;font-weight:800;color:#2ecc71">{_fc(windows_count)}</div><div style="font-size:9px;color:#69707D;margin-top:4px">Windows</div></div>
    <div style="flex:1;text-align:center;padding:14px;border-radius:8px;background:#fef9f0;border:1px solid #f5d6a3"><div style="font-size:28px;font-weight:800;color:#e67e22">{_fc(linux_count)}</div><div style="font-size:9px;color:#69707D;margin-top:4px">Linux</div></div>
    {"" if mac_count == 0 else f'<div style="flex:1;text-align:center;padding:14px;border-radius:8px;background:#f5f0ff;border:1px solid #d5c6f5"><div style="font-size:28px;font-weight:800;color:#9b59b6">{_fc(mac_count)}</div><div style="font-size:9px;color:#69707D;margin-top:4px">macOS</div></div>'}
    {"" if other_count <= 0 else f'<div style="flex:1;text-align:center;padding:14px;border-radius:8px;border:1px solid #ecf0f1"><div style="font-size:28px;font-weight:800;color:#95a5a6">{_fc(other_count)}</div><div style="font-size:9px;color:#69707D;margin-top:4px">Other</div></div>'}
    <div style="flex:1;text-align:center;padding:14px;border-radius:8px;background:#fdf2f2;border:1px solid #f5c6cb"><div style="font-size:28px;font-weight:800;color:#9b59b6">{d["avg_memory_usage"]}%</div><div style="font-size:9px;color:#69707D;margin-top:4px">Avg Memory Usage</div></div>
  </div>
  <div style="display:flex;gap:12px;margin-bottom:12px">
    <div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#3498db"></span>Operating System Distribution</div><div style="display:flex;align-items:center;justify-content:center;gap:16px">{os_donut}<div>{os_legend}</div></div></div>
    <div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#2ecc71"></span>CPU Types</div>{_stbl(d["cpu_types"], "name", "CPU", "Endpoints", "#2ecc71")}</div>
  </div>
  <div class="card"><div class="stitle"><span class="dot" style="background:#e67e22"></span>Hardware Specifications per Agent</div>
    <table><thead><tr><th>Agent</th><th style="text-align:center">CPU Cores</th><th style="text-align:center">Total RAM</th><th style="text-align:center">Memory Usage</th></tr></thead>
    <tbody>{hw_rows}</tbody></table>
  </div>
</div>

<!-- SOFTWARE INVENTORY -->
<div class="page">
  <div class="hdr"><h2>Software Inventory</h2><p>{_fc(d["total_packages"])} packages across {_fc(d["total_endpoints"])} endpoints</p></div>
  <div style="display:flex;gap:8px;margin-bottom:14px">
    <div style="flex:1;text-align:center;padding:14px;border-radius:8px;background:#f0f4ff;border:1px solid #b3c6ff"><div style="font-size:28px;font-weight:800;color:#3498db">{_fc(d["total_packages"])}</div><div style="font-size:9px;color:#69707D;margin-top:4px">Total Packages</div></div>
    <div style="flex:1;text-align:center;padding:14px;border-radius:8px;background:#f0fdf4;border:1px solid #a3cfbb"><div style="font-size:28px;font-weight:800;color:#2ecc71">{len(d["pkg_by_type"])}</div><div style="font-size:9px;color:#69707D;margin-top:4px">Package Types</div></div>
    <div style="flex:1;text-align:center;padding:14px;border-radius:8px;background:#fef9f0;border:1px solid #f5d6a3"><div style="font-size:28px;font-weight:800;color:#e67e22">{len(d["pkg_by_vendor"])}</div><div style="font-size:9px;color:#69707D;margin-top:4px">Vendors</div></div>
  </div>
  <div style="display:flex;gap:12px;margin-bottom:12px">
    <div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#3498db"></span>Packages by Type</div><div style="text-align:center">{pkg_type_bars}</div></div>
    <div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#e67e22"></span>Top Vendors</div>{_stbl(d["pkg_by_vendor"][:10], "name", "Vendor", "Packages", "#e67e22", font="7px")}</div>
  </div>
  <div style="display:flex;gap:12px;margin-bottom:12px">
    <div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#9b59b6"></span>Packages per Agent</div>{_stbl(d["pkg_by_agent"], "name", "Agent", "Packages", "#9b59b6")}</div>
    <div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#2ecc71"></span>Top Installed Packages</div>{_stbl(d["top_packages"], "name", "Package Name", "Agents", "#2ecc71", font="7px")}</div>
  </div>
</div>

<!-- PROCESSES & PORTS -->
<div class="page">
  <div class="hdr"><h2>Running Processes &amp; Network Ports</h2><p>{_fc(d["total_processes"])} processes, {_fc(d["total_ports"])} open ports</p></div>
  <div style="display:flex;gap:8px;margin-bottom:14px">
    <div style="flex:1;text-align:center;padding:14px;border-radius:8px;background:#f0f4ff;border:1px solid #b3c6ff"><div style="font-size:28px;font-weight:800;color:#3498db">{_fc(d["total_processes"])}</div><div style="font-size:9px;color:#69707D;margin-top:4px">Running Processes</div></div>
    <div style="flex:1;text-align:center;padding:14px;border-radius:8px;background:#f0fdf4;border:1px solid #a3cfbb"><div style="font-size:28px;font-weight:800;color:#2ecc71">{_fc(d["total_ports"])}</div><div style="font-size:9px;color:#69707D;margin-top:4px">Open Ports</div></div>
    <div style="flex:1;text-align:center;padding:14px;border-radius:8px;background:#fef9f0;border:1px solid #f5d6a3"><div style="font-size:28px;font-weight:800;color:#e67e22">{_fc(d["total_services"])}</div><div style="font-size:9px;color:#69707D;margin-top:4px">Services</div></div>
  </div>
  <div class="card"><div class="stitle"><span class="dot" style="background:#3498db"></span>Top Running Processes</div><div style="text-align:center">{proc_bars}</div></div>
  <div style="display:flex;gap:12px;margin-bottom:12px">
    <div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#e67e22"></span>Top Listening Ports</div>{_stbl(d["top_ports"][:10], "name", "Port", "Connections", "#e67e22")}</div>
    <div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#2ecc71"></span>Port Services</div>{_stbl(d["port_services"][:10], "name", "Process", "Ports", "#2ecc71")}</div>
  </div>
</div>

<!-- SERVICES -->
<div class="page">
  <div class="hdr"><h2>Services &amp; User Accounts</h2><p>{_fc(d["total_services"])} services, {_fc(d["total_users"])} user accounts</p></div>
  <div style="display:flex;gap:12px;margin-bottom:12px">
    <div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#2ecc71"></span>Service States</div><div style="text-align:center">{svc_state_bars}</div></div>
    <div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#3498db"></span>Service Types</div>{_stbl(d["svc_by_type"], "name", "Type", "Count", "#3498db")}</div>
  </div>
  <div style="display:flex;gap:8px;margin-bottom:14px">
    <div style="flex:1;text-align:center;padding:14px;border-radius:8px;background:#f0f4ff;border:1px solid #b3c6ff"><div style="font-size:28px;font-weight:800;color:#3498db">{_fc(d["total_users"])}</div><div style="font-size:9px;color:#69707D;margin-top:4px">Total Users</div></div>
    <div style="flex:1;text-align:center;padding:14px;border-radius:8px;background:#f0fdf4;border:1px solid #a3cfbb"><div style="font-size:28px;font-weight:800;color:#2ecc71">{_fc(d["users_logged_in"])}</div><div style="font-size:9px;color:#69707D;margin-top:4px">Active Sessions</div></div>
    <div style="flex:1;text-align:center;padding:14px;border-radius:8px;background:#fdf2f2;border:1px solid #f5c6cb"><div style="font-size:28px;font-weight:800;color:#e74c3c">{_fc(d["users_disabled"])}</div><div style="font-size:9px;color:#69707D;margin-top:4px">Inactive Accounts</div></div>
  </div>
  <div style="display:flex;gap:12px;margin-bottom:12px">
    <div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#9b59b6"></span>User Types</div>{_stbl(d["user_by_type"], "name", "Type", "Count", "#9b59b6")}</div>
    <div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#e67e22"></span>Users per Agent</div>{_stbl(d["users_by_agent"], "name", "Agent", "Users", "#e67e22")}</div>
  </div>
</div>

<!-- BROWSER EXTENSIONS -->
<div class="page">
  <div class="hdr"><h2>Browser Extensions</h2><p>{_fc(d["total_extensions"])} extensions across endpoints</p></div>
  <div style="display:flex;gap:8px;margin-bottom:14px">
    <div style="flex:1;text-align:center;padding:14px;border-radius:8px;background:#f0f4ff;border:1px solid #b3c6ff"><div style="font-size:28px;font-weight:800;color:#3498db">{_fc(d["total_extensions"])}</div><div style="font-size:9px;color:#69707D;margin-top:4px">Total Extensions</div></div>
    <div style="flex:1;text-align:center;padding:14px;border-radius:8px;background:#f0fdf4;border:1px solid #a3cfbb"><div style="font-size:28px;font-weight:800;color:#2ecc71">{_fc(d["ext_enabled"])}</div><div style="font-size:9px;color:#69707D;margin-top:4px">Enabled</div></div>
    <div style="flex:1;text-align:center;padding:14px;border-radius:8px;background:#fdf2f2;border:1px solid #f5c6cb"><div style="font-size:28px;font-weight:800;color:#e74c3c">{_fc(d["ext_disabled"])}</div><div style="font-size:9px;color:#69707D;margin-top:4px">Disabled</div></div>
  </div>
  <div style="display:flex;gap:12px;margin-bottom:12px">
    <div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#3498db"></span>By Browser</div>{_stbl(d["ext_by_browser"], "name", "Browser", "Extensions", "#3498db")}</div>
    <div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#e67e22"></span>Top Extensions</div>{_stbl(d["top_extensions"][:10], "name", "Extension Name", "Agents", "#e67e22", font="7px")}</div>
  </div>
</div>

<!-- NETWORK INTERFACES & ADDRESSES -->
<div class="page">
  <div class="hdr"><h2>Network Interfaces &amp; Addresses</h2><p>{_fc(d["total_interfaces"])} interfaces, {_fc(d["total_networks"])} network addresses, {d["unique_ips"]} unique IPs</p></div>
  <div style="display:flex;gap:8px;margin-bottom:14px">
    <div style="flex:1;text-align:center;padding:14px;border-radius:8px;background:#f0f4ff;border:1px solid #b3c6ff"><div style="font-size:28px;font-weight:800;color:#3498db">{_fc(d["total_interfaces"])}</div><div style="font-size:9px;color:#69707D;margin-top:4px">Interfaces</div></div>
    <div style="flex:1;text-align:center;padding:14px;border-radius:8px;background:#f0fdf4;border:1px solid #a3cfbb"><div style="font-size:28px;font-weight:800;color:#2ecc71">{_fc(d["total_networks"])}</div><div style="font-size:9px;color:#69707D;margin-top:4px">Network Addresses</div></div>
    <div style="flex:1;text-align:center;padding:14px;border-radius:8px;background:#fef9f0;border:1px solid #f5d6a3"><div style="font-size:28px;font-weight:800;color:#e67e22">{d["unique_ips"]}</div><div style="font-size:9px;color:#69707D;margin-top:4px">Unique IPs</div></div>
  </div>
  <div style="display:flex;gap:12px;margin-bottom:12px">
    <div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#3498db"></span>Top Interface Names</div>{_stbl(d["top_interfaces"], "name", "Interface", "Count", "#3498db")}</div>
    <div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#2ecc71"></span>Network Type</div>{_stbl(d["net_by_type"], "name", "Type", "Count", "#2ecc71")}</div>
  </div>
  <div class="card"><div class="stitle"><span class="dot" style="background:#9b59b6"></span>Network IP Addresses</div>{_stbl(d["top_network_ips"][:15], "name", "IP Address", "Interfaces", "#9b59b6", font="7.5px")}</div>
</div>

<!-- USER ACCOUNTS & GROUPS -->
<div class="page">
  <div class="hdr"><h2>User Accounts &amp; Groups</h2><p>{_fc(d["total_users"])} user accounts, {len(d["user_groups"])} groups</p></div>
  <div style="display:flex;gap:8px;margin-bottom:14px">
    <div style="flex:1;text-align:center;padding:14px;border-radius:8px;background:#f0f4ff;border:1px solid #b3c6ff"><div style="font-size:28px;font-weight:800;color:#3498db">{_fc(d["total_users"])}</div><div style="font-size:9px;color:#69707D;margin-top:4px">Total Users</div></div>
    <div style="flex:1;text-align:center;padding:14px;border-radius:8px;background:#f0fdf4;border:1px solid #a3cfbb"><div style="font-size:28px;font-weight:800;color:#2ecc71">{_fc(d["users_logged_in"])}</div><div style="font-size:9px;color:#69707D;margin-top:4px">Active Sessions</div></div>
    <div style="flex:1;text-align:center;padding:14px;border-radius:8px;background:#fdf2f2;border:1px solid #f5c6cb"><div style="font-size:28px;font-weight:800;color:#e74c3c">{_fc(d["users_disabled"])}</div><div style="font-size:9px;color:#69707D;margin-top:4px">Inactive</div></div>
    <div style="flex:1;text-align:center;padding:14px;border-radius:8px;background:#fef9f0;border:1px solid #f5d6a3"><div style="font-size:28px;font-weight:800;color:#e67e22">{len(d["user_groups"])}</div><div style="font-size:9px;color:#69707D;margin-top:4px">Groups</div></div>
  </div>
  <div style="display:flex;gap:12px;margin-bottom:12px">
    <div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#3498db"></span>Top Users</div>{_stbl(d["top_usernames"][:10], "name", "Username", "Agents", "#3498db")}</div>
    <div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#2ecc71"></span>User Groups</div>{_stbl(d["user_groups"][:10], "name", "Group", "Members", "#2ecc71")}</div>
  </div>
  <div style="display:flex;gap:12px;margin-bottom:12px">
    <div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#9b59b6"></span>User Shells</div>{_stbl(d["user_shells"], "name", "Shell", "Users", "#9b59b6", font="7px")}</div>
    <div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#e67e22"></span>Users per Agent</div>{_stbl(d["users_by_agent"], "name", "Agent", "Users", "#e67e22")}</div>
  </div>
</div>

<!-- WINDOWS HOTFIXES -->
{_render_hotfixes(d)}

<!-- VULNERABILITY POSTURE -->
<div class="page">
  <div class="hdr" style="background:linear-gradient(135deg,#BD271E,#920000)"><h2 style="color:#fff">Vulnerability Posture</h2><p style="color:rgba(255,255,255,0.8)">{_fc(d["total_vulns"])} vulnerabilities detected &bull; Average CVSS Score: {d["vuln_avg_score"]}</p></div>
  <div style="display:flex;gap:12px;margin-bottom:12px">
    <div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#BD271E"></span>Vulnerability by Severity</div><div style="display:flex;align-items:center;justify-content:center;gap:16px">{vuln_donut}<div>{vuln_legend}</div></div></div>
    <div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#e74c3c"></span>Top CVEs</div>{_stbl(d["vuln_top_cves"], "name", "CVE ID", "Affected", "#e74c3c", font="7px")}</div>
  </div>
  <div style="display:flex;gap:12px;margin-bottom:12px">
    <div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#e67e22"></span>Vulnerable Packages</div>{_stbl(d["vuln_top_packages"], "name", "Package", "Vulns", "#e67e22", font="7px")}</div>
    <div class="card" style="flex:1"><div class="stitle"><span class="dot" style="background:#3498db"></span>Most Affected Agents</div>{_stbl(d["vuln_by_agent"], "name", "Agent", "Vulns", "#3498db")}</div>
  </div>
</div>

</body></html>"""
    return html


async def generate_inventory_report(template_id=None):
    """Generate inventory management PDF report"""
    try:
        template_cfg = None
        if template_id:
            template_cfg = database.get_template(template_id)

        data = collect_inventory_data()
        html = render_inventory_html(data, template_cfg)

        pdf_bytes, err = await _html_to_pdf(html)
        if err:
            return None, err

        fname = f"inventory_report_{datetime.now(IST).strftime('%Y%m%d_%H%M')}.pdf"
        fpath = os.path.join(config.REPORTS_DIR, fname)
        os.makedirs(config.REPORTS_DIR, exist_ok=True)
        with open(fpath, "wb") as f:
            f.write(pdf_bytes)

        rid = database.save_report(template_id, fname, "Current Snapshot", "Current Snapshot", len(pdf_bytes))
        return {"id": rid, "filename": fname, "size": len(pdf_bytes)}, None
    except Exception as e:
        import traceback
        return None, f"{str(e)}\n{traceback.format_exc()}"
