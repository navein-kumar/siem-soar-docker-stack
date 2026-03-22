"""V2 Inventory Report — Enhanced enterprise styling.
Imports data collection from v1, only overrides rendering."""

import os
import json
from datetime import datetime

from inventory_report import collect_inventory_data, _query
from pdf_generator import _fc, _html_to_pdf, IST
from pdf_generator_v2 import (
    CSS_V2, PALETTE_V2, _icon, _footer, _stat_card,
    svg_donut_v2, svg_hbars_v2, svg_vbars_v2, svg_gauge,
    _stbl_v2
)
import config, database


def _render_cover_inv(d, template_cfg=None):
    """Render inventory cover page with v2 styling."""
    now = datetime.now(IST)
    cco = "#0f172a"
    cac = "#0891b2"
    client_name = "Codesecure Solutions"
    client_address = "Chennai, Tamil Nadu, India"
    client_logo = "https://codesecure.in/images/codesec-logo1.png"

    if template_cfg:
        cco = template_cfg.get("cover_color", cco)
        cac = template_cfg.get("cover_accent", cac)
        client_name = template_cfg.get("description", client_name) or client_name
        client_address = template_cfg.get("client_address", client_address) or client_address
        client_logo = template_cfg.get("logo_url", client_logo) or client_logo

    logo = ''
    if client_logo:
        logo = (
            f'<div style="margin-bottom:40px;display:inline-flex;'
            f'align-items:center;background:rgba(255,255,255,0.95);'
            f'padding:16px 24px;border-radius:10px;'
            f'box-shadow:0 4px 16px rgba(0,0,0,0.2)">'
            f'<img src="{client_logo}" '
            f'style="height:42px;display:block" '
            f'onerror="this.style.display=\'none\'"/>'
            f'</div>'
        )

    return f'''<div class="page" style="padding:0;overflow:hidden;background:{cco}">
  <div style="position:absolute;top:-100px;right:-100px;width:500px;height:500px;
    border-radius:50%;background:linear-gradient(135deg,{cac},#14b8a6);opacity:0.12"></div>
  <div style="position:absolute;bottom:-150px;left:-100px;width:450px;height:450px;
    border-radius:50%;background:linear-gradient(135deg,#14b8a6,{cac});opacity:0.08"></div>
  <div style="height:5px;background:linear-gradient(90deg,{cac},#14b8a6,#2dd4bf)"></div>
  <div style="position:absolute;top:0;left:0;right:0;bottom:0;
    background-image:radial-gradient(circle,rgba(255,255,255,0.03) 1px,transparent 1px);
    background-size:20px 20px"></div>

  <div style="position:relative;z-index:1;padding:60px 50px 40px">
    {logo}
    <div style="margin-bottom:50px">
      <div style="font-size:13px;color:{cac};text-transform:uppercase;
        letter-spacing:5px;font-weight:600;margin-bottom:16px">Asset Report</div>
      <h1 style="font-size:48px;font-weight:800;color:#fff;
        line-height:1.05;margin-bottom:0">IT Asset &amp; Inventory</h1>
      <h1 style="font-size:48px;font-weight:800;color:{cac};
        line-height:1.05;margin-bottom:18px">Management Report</h1>
      <div style="width:60px;height:4px;background:linear-gradient(90deg,{cac},#14b8a6);
        border-radius:2px"></div>
    </div>

    <p style="font-size:13px;color:rgba(255,255,255,0.4);
      letter-spacing:1px;margin-bottom:40px">
      Comprehensive Infrastructure Inventory Analysis
    </p>

    <div style="display:flex;gap:0;margin-bottom:40px;
      background:rgba(0,0,0,0.25);border-radius:10px;overflow:hidden;
      border:1px solid rgba(255,255,255,0.06)">
      <div style="flex:1;padding:20px 24px;border-left:3px solid {cac}">
        <div style="font-size:8px;text-transform:uppercase;letter-spacing:2px;
          color:rgba(255,255,255,0.35);margin-bottom:8px">Prepared For</div>
        <div style="font-size:15px;font-weight:700;color:#fff;
          margin-bottom:4px">{client_name}</div>
        <div style="font-size:10px;color:rgba(255,255,255,0.45);
          line-height:1.4">{client_address}</div>
      </div>
      <div style="flex:1;padding:20px 24px;
        border-left:1px solid rgba(255,255,255,0.06)">
        <div style="font-size:8px;text-transform:uppercase;letter-spacing:2px;
          color:rgba(255,255,255,0.35);margin-bottom:8px">Generated</div>
        <div style="font-size:11px;font-weight:600;color:#fff;
          margin-bottom:4px">{now.strftime("%d/%m/%Y")}</div>
        <div style="font-size:11px;color:rgba(255,255,255,0.45)">
          {now.strftime("%I:%M %p").lower()} IST</div>
      </div>
      <div style="flex:1;padding:20px 24px;
        border-left:1px solid rgba(255,255,255,0.06)">
        <div style="font-size:8px;text-transform:uppercase;letter-spacing:2px;
          color:rgba(255,255,255,0.35);margin-bottom:8px">Scope</div>
        <div style="font-size:11px;font-weight:600;color:#fff;
          margin-bottom:4px">{_fc(d["total_endpoints"])} Endpoints</div>
        <div style="font-size:11px;color:rgba(255,255,255,0.45)">
          {_fc(d["total_packages"])} Packages</div>
      </div>
    </div>
  </div>

  <div style="position:absolute;bottom:0;left:0;right:0;height:4px;
    background:linear-gradient(90deg,{cac},#14b8a6,#2dd4bf)"></div>
</div>'''


def _render_asset_overview(d):
    """Render asset overview page."""
    windows_count = sum(
        o["count"] for o in d["os_platform"]
        if o["name"].lower() == "windows"
    )
    linux_count = sum(
        o["count"] for o in d["os_platform"]
        if o["name"].lower() in (
            "linux", "ubuntu", "centos", "rhel",
            "debian", "fedora", "amazon", "suse"
        )
    )
    mac_count = sum(
        o["count"] for o in d["os_platform"]
        if o["name"].lower() in ("darwin", "macos", "macosx")
    )

    # OS donut
    os_donut = ''
    os_legend = ''
    if d["os_distribution"]:
        donut_data = [
            {"value": o["count"], "color": PALETTE_V2[i % 24]}
            for i, o in enumerate(d["os_distribution"])
        ]
        os_donut = svg_donut_v2(donut_data, 180, 180, 70, 45)
        for i, o in enumerate(d["os_distribution"]):
            os_legend += (
                f'<div style="display:flex;align-items:center;margin:4px 0">'
                f'<div style="width:12px;height:12px;border-radius:4px;'
                f'background:{PALETTE_V2[i % 24]};margin-right:8px"></div>'
                f'<div style="font-size:8px">'
                f'<strong>{o["name"][:25]}</strong>: {_fc(o["count"])}'
                f'</div></div>'
            )

    # Hardware table
    hw_rows = ''
    for i, h in enumerate(d.get("hardware_agents", [])):
        bg = '#fff' if i % 2 == 0 else '#f8fafc'
        if h["memory_pct"] < 60:
            mem_color = '#22c55e'
        elif h["memory_pct"] < 80:
            mem_color = '#f97316'
        else:
            mem_color = '#ef4444'
        hw_rows += (
            f'<tr style="background:{bg}">'
            f'<td style="padding:5px 8px;border-bottom:1px solid #e2e8f0;'
            f'font-size:8px;font-weight:600">{h["name"]}</td>'
            f'<td style="padding:5px 8px;border-bottom:1px solid #e2e8f0;'
            f'text-align:center;font-size:8px">{h["cpu_cores"]}</td>'
            f'<td style="padding:5px 8px;border-bottom:1px solid #e2e8f0;'
            f'text-align:center;font-size:8px">{h["memory_gb"]} GB</td>'
            f'<td style="padding:5px 8px;border-bottom:1px solid #e2e8f0;'
            f'text-align:center">'
            f'<div style="display:inline-flex;align-items:center;gap:4px">'
            f'<div style="background:#e2e8f0;border-radius:8px;height:10px;'
            f'width:60px;overflow:hidden">'
            f'<div style="background:linear-gradient(90deg,{mem_color},{mem_color}bb);'
            f'height:100%;width:{h["memory_pct"]}%;border-radius:8px"></div></div>'
            f'<span style="font-size:7px;font-weight:700;'
            f'color:{mem_color}">{h["memory_pct"]}%</span>'
            f'</div></td></tr>'
        )

    # Memory gauge
    gauge = svg_gauge(
        int(d["avg_memory_usage"]), 100, 140, 90, "Avg Memory"
    )

    return f'''<div class="page">
  <div class="hdr">
    <h2>Asset Overview</h2>
    <p>Endpoint inventory and hardware specifications</p>
  </div>

  <div style="display:flex;gap:8px;margin-bottom:12px">
    {_stat_card("Total Endpoints", d["total_endpoints"], "#2563eb",
                icon_name="globe", gradient=False)}
    {_stat_card("Windows", windows_count, "#22c55e",
                icon_name="shield", gradient=False)}
    {_stat_card("Linux", linux_count, "#f97316",
                icon_name="target", gradient=False)}
    <div style="flex:1;text-align:center;padding:10px 6px;
      border-radius:10px;background:#f8fafc;border:1px solid #e2e8f0">
      {gauge}
    </div>
  </div>

  <div style="display:flex;gap:12px;margin-bottom:12px">
    <div class="card" style="flex:1">
      <div class="stitle">
        <span class="dot" style="background:#2563eb"></span>
        OS Distribution
      </div>
      <div style="display:flex;align-items:center;justify-content:center;gap:16px">
        {os_donut}
        <div>{os_legend}</div>
      </div>
    </div>
    <div class="card" style="flex:1">
      <div class="stitle">
        <span class="dot" style="background:#059669"></span>CPU Types
      </div>
      {_stbl_v2(d["cpu_types"], "name", "CPU", "Endpoints", "#059669")}
    </div>
  </div>

  <div class="card">
    <div class="stitle">
      <span class="dot" style="background:#f97316"></span>
      Hardware Specifications per Agent
    </div>
    <div class="rtable">
      <table><thead><tr>
        <th>Agent</th>
        <th style="text-align:center">CPU Cores</th>
        <th style="text-align:center">Total RAM</th>
        <th style="text-align:center">Memory Usage</th>
      </tr></thead>
      <tbody>{hw_rows}</tbody></table>
    </div>
  </div>

  {_footer("Asset Overview")}
</div>'''


def _render_software(d):
    """Render software inventory page."""
    pkg_items = [
        {"value": p["count"], "label": p["name"], "color": PALETTE_V2[i % 24]}
        for i, p in enumerate(d["pkg_by_type"])
    ]
    pkg_bars = svg_hbars_v2(pkg_items, 250) if pkg_items else ""

    return f'''<div class="page">
  <div class="hdr" style="background:linear-gradient(135deg,#4f46e5,#312e81)">
    <h2>Software Inventory</h2>
    <p>{_fc(d["total_packages"])} packages across {_fc(d["total_endpoints"])} endpoints</p>
  </div>

  <div style="display:flex;gap:8px;margin-bottom:12px">
    {_stat_card("Total Packages", d["total_packages"], "#2563eb",
                icon_name="file", gradient=False)}
    {_stat_card("Package Types", len(d["pkg_by_type"]), "#059669",
                icon_name="chart", gradient=False)}
    {_stat_card("Vendors", len(d["pkg_by_vendor"]), "#d97706",
                icon_name="users", gradient=False)}
  </div>

  <div style="display:flex;gap:12px;margin-bottom:12px">
    <div class="card" style="flex:1">
      <div class="stitle">
        <span class="dot" style="background:#2563eb"></span>Packages by Type
      </div>
      <div style="text-align:center">{pkg_bars}</div>
    </div>
    <div class="card" style="flex:1">
      <div class="stitle">
        <span class="dot" style="background:#d97706"></span>Top Vendors
      </div>
      {_stbl_v2(d["pkg_by_vendor"][:10], "name", "Vendor", "Packages", "#d97706", font="7px")}
    </div>
  </div>

  <div style="display:flex;gap:12px;margin-bottom:12px">
    <div class="card" style="flex:1">
      <div class="stitle">
        <span class="dot" style="background:#7c3aed"></span>Packages per Agent
      </div>
      {_stbl_v2(d["pkg_by_agent"], "name", "Agent", "Packages", "#7c3aed")}
    </div>
    <div class="card" style="flex:1">
      <div class="stitle">
        <span class="dot" style="background:#059669"></span>Top Installed Packages
      </div>
      {_stbl_v2(d["top_packages"], "name", "Package", "Agents", "#059669", font="7px")}
    </div>
  </div>

  {_footer("Software Inventory")}
</div>'''


def _render_processes_ports(d):
    """Render processes & ports page."""
    proc_items = [
        {"value": p["count"], "label": p["name"], "color": PALETTE_V2[i % 24]}
        for i, p in enumerate(d["top_processes"][:10])
    ]
    proc_bars = svg_hbars_v2(proc_items, 480) if proc_items else ""

    return f'''<div class="page">
  <div class="hdr" style="background:linear-gradient(135deg,#0891b2,#164e63)">
    <h2>Running Processes &amp; Network Ports</h2>
    <p>{_fc(d["total_processes"])} processes, {_fc(d["total_ports"])} open ports</p>
  </div>

  <div style="display:flex;gap:8px;margin-bottom:12px">
    {_stat_card("Processes", d["total_processes"], "#2563eb",
                icon_name="target", gradient=False)}
    {_stat_card("Open Ports", d["total_ports"], "#059669",
                icon_name="globe", gradient=False)}
    {_stat_card("Services", d["total_services"], "#d97706",
                icon_name="shield", gradient=False)}
    {_stat_card("Protocols", len(d["port_by_transport"]), "#7c3aed",
                icon_name="chart", gradient=False)}
  </div>

  <div class="card">
    <div class="stitle">
      <span class="dot" style="background:#2563eb"></span>Top Running Processes
    </div>
    <div style="text-align:center">{proc_bars}</div>
  </div>

  <div style="display:flex;gap:12px;margin-bottom:12px">
    <div class="card" style="flex:1">
      <div class="stitle">
        <span class="dot" style="background:#d97706"></span>Top Listening Ports
      </div>
      {_stbl_v2(d["top_ports"][:10], "name", "Port", "Listeners", "#d97706")}
    </div>
    <div class="card" style="flex:1">
      <div class="stitle">
        <span class="dot" style="background:#059669"></span>Listening Processes
      </div>
      {_stbl_v2(d["port_services"][:10], "name", "Process", "Ports", "#059669")}
    </div>
  </div>

  {_footer("Processes & Ports")}
</div>'''


def _render_services_users(d):
    """Render services & user accounts page."""
    svc_items = [
        {
            "value": s["count"], "label": s["name"],
            "color": (
                "#22c55e" if "RUNNING" in s["name"].upper()
                else "#ef4444" if "STOPPED" in s["name"].upper()
                else "#2563eb"
            )
        }
        for s in d["svc_by_state"]
    ]
    svc_bars = svg_hbars_v2(svc_items, 250) if svc_items else ""

    return f'''<div class="page">
  <div class="hdr">
    <h2>Services &amp; User Accounts</h2>
    <p>{_fc(d["total_services"])} services, {_fc(d["total_users"])} user accounts</p>
  </div>

  <div style="display:flex;gap:12px;margin-bottom:12px">
    <div class="card" style="flex:1">
      <div class="stitle">
        <span class="dot" style="background:#059669"></span>Service States
      </div>
      <div style="text-align:center">{svc_bars}</div>
    </div>
    <div class="card" style="flex:1">
      <div class="stitle">
        <span class="dot" style="background:#2563eb"></span>Service Types
      </div>
      {_stbl_v2(d["svc_by_type"], "name", "Type", "Count", "#2563eb")}
    </div>
  </div>

  <div style="display:flex;gap:8px;margin-bottom:12px">
    {_stat_card("Total Users", d["total_users"], "#2563eb",
                icon_name="users", gradient=False)}
    {_stat_card("Active", d["users_logged_in"], "#22c55e",
                icon_name="unlock", gradient=False)}
    {_stat_card("Inactive", d["users_disabled"], "#ef4444",
                icon_name="lock", gradient=False)}
  </div>

  <div style="display:flex;gap:12px;margin-bottom:12px">
    <div class="card" style="flex:1">
      <div class="stitle">
        <span class="dot" style="background:#7c3aed"></span>User Types
      </div>
      {_stbl_v2(d["user_by_type"], "name", "Type", "Count", "#7c3aed")}
    </div>
    <div class="card" style="flex:1">
      <div class="stitle">
        <span class="dot" style="background:#d97706"></span>Users per Agent
      </div>
      {_stbl_v2(d["users_by_agent"], "name", "Agent", "Users", "#d97706")}
    </div>
  </div>

  {_footer("Services & Users")}
</div>'''


def _render_browser_ext(d):
    """Render browser extensions page."""
    return f'''<div class="page">
  <div class="hdr" style="background:linear-gradient(135deg,#e11d48,#881337)">
    <h2>Browser Extensions</h2>
    <p>{_fc(d["total_extensions"])} extensions across endpoints</p>
  </div>

  <div style="display:flex;gap:8px;margin-bottom:12px">
    {_stat_card("Total", d["total_extensions"], "#2563eb",
                icon_name="globe", gradient=False)}
    {_stat_card("Enabled", d["ext_enabled"], "#22c55e",
                icon_name="check", gradient=False)}
    {_stat_card("Disabled", d["ext_disabled"], "#ef4444",
                icon_name="lock", gradient=False)}
  </div>

  <div style="display:flex;gap:12px;margin-bottom:12px">
    <div class="card" style="flex:1">
      <div class="stitle">
        <span class="dot" style="background:#2563eb"></span>By Browser
      </div>
      {_stbl_v2(d["ext_by_browser"], "name", "Browser", "Extensions", "#2563eb")}
    </div>
    <div class="card" style="flex:1">
      <div class="stitle">
        <span class="dot" style="background:#d97706"></span>Top Extensions
      </div>
      {_stbl_v2(d["top_extensions"][:10], "name", "Extension", "Agents", "#d97706", font="7px")}
    </div>
  </div>

  {_footer("Browser Extensions")}
</div>'''


def _render_network(d):
    """Render network interfaces & addresses page."""
    return f'''<div class="page">
  <div class="hdr" style="background:linear-gradient(135deg,#059669,#064e3b)">
    <h2>Network Interfaces &amp; Addresses</h2>
    <p>{_fc(d["total_interfaces"])} interfaces, {d["unique_ips"]} unique IPs</p>
  </div>

  <div style="display:flex;gap:8px;margin-bottom:12px">
    {_stat_card("Interfaces", d["total_interfaces"], "#2563eb",
                icon_name="globe", gradient=False)}
    {_stat_card("Addresses", d["total_networks"], "#059669",
                icon_name="target", gradient=False)}
    {_stat_card("Unique IPs", d["unique_ips"], "#d97706",
                icon_name="chart", gradient=False)}
  </div>

  <div style="display:flex;gap:12px;margin-bottom:12px">
    <div class="card" style="flex:1">
      <div class="stitle">
        <span class="dot" style="background:#2563eb"></span>Top Interfaces
      </div>
      {_stbl_v2(d["top_interfaces"], "name", "Interface", "Count", "#2563eb")}
    </div>
    <div class="card" style="flex:1">
      <div class="stitle">
        <span class="dot" style="background:#059669"></span>Network Type
      </div>
      {_stbl_v2(d["net_by_type"], "name", "Type", "Count", "#059669")}
    </div>
  </div>

  <div class="card">
    <div class="stitle">
      <span class="dot" style="background:#7c3aed"></span>Network IP Addresses
    </div>
    {_stbl_v2(d["top_network_ips"][:15], "name", "IP Address", "Interfaces", "#7c3aed", font="7.5px")}
  </div>

  {_footer("Network")}
</div>'''


def _render_users_groups(d):
    """Render user accounts & groups page."""
    return f'''<div class="page">
  <div class="hdr">
    <h2>User Accounts &amp; Groups</h2>
    <p>{_fc(d["total_users"])} user accounts, {len(d["user_groups"])} groups</p>
  </div>

  <div style="display:flex;gap:8px;margin-bottom:12px">
    {_stat_card("Total Users", d["total_users"], "#2563eb",
                icon_name="users", gradient=False)}
    {_stat_card("Active", d["users_logged_in"], "#22c55e",
                icon_name="unlock", gradient=False)}
    {_stat_card("Inactive", d["users_disabled"], "#ef4444",
                icon_name="lock", gradient=False)}
    {_stat_card("Groups", len(d["user_groups"]), "#d97706",
                icon_name="target", gradient=False)}
  </div>

  <div style="display:flex;gap:12px;margin-bottom:12px">
    <div class="card" style="flex:1">
      <div class="stitle">
        <span class="dot" style="background:#2563eb"></span>Top Users
      </div>
      {_stbl_v2(d["top_usernames"][:10], "name", "Username", "Agents", "#2563eb")}
    </div>
    <div class="card" style="flex:1">
      <div class="stitle">
        <span class="dot" style="background:#059669"></span>User Groups
      </div>
      {_stbl_v2(d["user_groups"][:10], "name", "Group", "Members", "#059669")}
    </div>
  </div>

  <div style="display:flex;gap:12px;margin-bottom:12px">
    <div class="card" style="flex:1">
      <div class="stitle">
        <span class="dot" style="background:#7c3aed"></span>User Shells
      </div>
      {_stbl_v2(d["user_shells"], "name", "Shell", "Users", "#7c3aed", font="7px")}
    </div>
    <div class="card" style="flex:1">
      <div class="stitle">
        <span class="dot" style="background:#d97706"></span>Users per Agent
      </div>
      {_stbl_v2(d["users_by_agent"], "name", "Agent", "Users", "#d97706")}
    </div>
  </div>

  {_footer("Users & Groups")}
</div>'''


def _render_hotfixes_v2(d):
    """Render Windows hotfixes page."""
    if d.get("total_hotfixes", 0) == 0:
        return ''

    return f'''<div class="page">
  <div class="hdr">
    <h2>Windows Hotfixes</h2>
    <p>{_fc(d["total_hotfixes"])} hotfixes installed across Windows endpoints</p>
  </div>

  <div style="display:flex;gap:12px;margin-bottom:12px">
    <div class="card" style="flex:1">
      <div class="stitle">
        <span class="dot" style="background:#2563eb"></span>
        Top Hotfixes (KB Articles)
      </div>
      {_stbl_v2(d["top_hotfixes"], "name", "Hotfix", "Agents", "#2563eb")}
    </div>
    <div class="card" style="flex:1">
      <div class="stitle">
        <span class="dot" style="background:#d97706"></span>
        Hotfixes per Agent
      </div>
      {_stbl_v2(d["hotfix_by_agent"], "name", "Agent", "Hotfixes", "#d97706")}
    </div>
  </div>

  {_footer("Hotfixes")}
</div>'''


def _render_vulnerability_posture(d):
    """Render vulnerability posture page."""
    vuln_colors = {
        "Critical": "#BD271E", "High": "#E7664C",
        "Medium": "#D6BF57", "Low": "#6DCCB1"
    }

    vuln_donut = ''
    vuln_legend = ''
    if d["vuln_by_severity"]:
        donut_data = [
            {"value": v["count"], "color": vuln_colors.get(v["name"], "#94a3b8")}
            for v in d["vuln_by_severity"]
        ]
        vuln_donut = svg_donut_v2(donut_data, 180, 180, 70, 45)
        for v in d["vuln_by_severity"]:
            vc = vuln_colors.get(v["name"], "#94a3b8")
            vuln_legend += (
                f'<div style="display:flex;align-items:center;margin:4px 0">'
                f'<div style="width:12px;height:12px;border-radius:4px;'
                f'background:{vc};margin-right:8px"></div>'
                f'<div style="font-size:9px">'
                f'<strong>{v["name"]}</strong>: {_fc(v["count"])}'
                f'</div></div>'
            )

    # CVSS gauge
    gauge = svg_gauge(
        int(d["vuln_avg_score"] * 10), 100, 140, 90,
        f'CVSS {d["vuln_avg_score"]}'
    )

    return f'''<div class="page">
  <div class="hdr" style="background:linear-gradient(135deg,#BD271E,#7f1d1d)">
    <h2>Vulnerability Posture</h2>
    <p>{_fc(d["total_vulns"])} vulnerabilities detected &bull;
      Average CVSS: {d["vuln_avg_score"]}</p>
  </div>

  <div style="display:flex;gap:12px;margin-bottom:12px">
    <div class="card" style="flex:1">
      <div class="stitle">
        <span class="dot" style="background:#BD271E"></span>
        Vulnerability by Severity
      </div>
      <div style="display:flex;align-items:center;justify-content:center;gap:16px">
        {vuln_donut}
        <div>{vuln_legend}</div>
      </div>
    </div>
    <div style="flex:0 0 160px;text-align:center;padding:20px 8px;
      border-radius:10px;background:#f8fafc;border:1px solid #e2e8f0">
      {gauge}
    </div>
  </div>

  <div style="display:flex;gap:12px;margin-bottom:12px">
    <div class="card" style="flex:1">
      <div class="stitle">
        <span class="dot" style="background:#ef4444"></span>Top CVEs
      </div>
      {_stbl_v2(d["vuln_top_cves"], "name", "CVE ID", "Affected", "#ef4444", font="7px")}
    </div>
    <div class="card" style="flex:1">
      <div class="stitle">
        <span class="dot" style="background:#d97706"></span>Vulnerable Packages
      </div>
      {_stbl_v2(d["vuln_top_packages"], "name", "Package", "Vulns", "#d97706", font="7px")}
    </div>
  </div>

  <div class="card">
    <div class="stitle">
      <span class="dot" style="background:#2563eb"></span>Most Affected Agents
    </div>
    {_stbl_v2(d["vuln_by_agent"], "name", "Agent", "Vulns", "#2563eb")}
  </div>

  {_footer("Vulnerability Posture")}
</div>'''


# ── Main Render ──────────────────────────────────────────────────

def render_inventory_html_v2(d, template_cfg=None):
    """Render v2 inventory HTML report."""
    pages = []
    pages.append(_render_cover_inv(d, template_cfg))
    pages.append(_render_asset_overview(d))
    pages.append(_render_software(d))
    pages.append(_render_processes_ports(d))
    pages.append(_render_services_users(d))
    pages.append(_render_browser_ext(d))
    pages.append(_render_network(d))
    pages.append(_render_users_groups(d))

    hotfixes = _render_hotfixes_v2(d)
    if hotfixes:
        pages.append(hotfixes)

    pages.append(_render_vulnerability_posture(d))

    return (
        f'<!DOCTYPE html><html><head>'
        f'<meta charset="UTF-8">'
        f'<title>IT Asset Inventory Report</title>'
        f'<style>{CSS_V2}</style>'
        f'</head><body>'
        f'{"".join(pages)}'
        f'</body></html>'
    )


# ── Public API ───────────────────────────────────────────────────

async def generate_inventory_report_v2(template_id=None):
    """Generate v2-styled inventory PDF report."""
    try:
        template_cfg = None
        if template_id:
            template_cfg = database.get_template(template_id)

        data = collect_inventory_data()
        html = render_inventory_html_v2(data, template_cfg)

        pdf_bytes, err = await _html_to_pdf(html)
        if err:
            return None, err

        fname = (
            f"inventory_report_v2_"
            f"{datetime.now(IST).strftime('%Y%m%d_%H%M')}.pdf"
        )
        fpath = os.path.join(config.REPORTS_DIR, fname)
        os.makedirs(config.REPORTS_DIR, exist_ok=True)
        with open(fpath, "wb") as f:
            f.write(pdf_bytes)

        rid = database.save_report(
            template_id, fname,
            "Current Snapshot", "Current Snapshot",
            len(pdf_bytes)
        )
        return {"id": rid, "filename": fname, "size": len(pdf_bytes)}, None

    except Exception as e:
        import traceback
        return None, f"{str(e)}\n{traceback.format_exc()}"
