#!/usr/bin/env python3
"""
Build OpenSearch Dashboard saved objects (NDJSON) for Wazuh SIEM.
Enterprise-grade Vega visualizations + 3 dashboards (Daily/Weekly/Monthly).
"""
import json, uuid

INDEX_PATTERN_ID = "wazuh-alerts-*"
objects = []

def make_id(name):
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"codesec.wazuh.v2.{name}"))

def vis(title, vis_type, vis_state, search_source=None):
    vid = make_id(title)
    if search_source is None:
        search_source = {"query": {"language": "kuery", "query": ""}, "filter": []}
    if vis_type != "vega":
        search_source["index"] = INDEX_PATTERN_ID
    obj = {
        "type": "visualization", "id": vid,
        "attributes": {
            "title": title, "visState": json.dumps(vis_state), "uiStateJSON": "{}",
            "description": "", "kibanaSavedObjectMeta": {"searchSourceJSON": json.dumps(search_source)}
        },
        "references": [{"id": INDEX_PATTERN_ID, "name": "kibanaSavedObjectMeta.searchSourceJSON.index", "type": "index-pattern"}]
    }
    objects.append(obj)
    return vid

def vega_vis(title, spec):
    """Create a Vega visualization with proper $schema handling"""
    vid = make_id(title)
    spec_str = json.dumps(spec)
    obj = {
        "type": "visualization", "id": vid,
        "attributes": {
            "title": title,
            "visState": json.dumps({"title": title, "type": "vega", "aggs": [], "params": {"spec": spec_str}}),
            "uiStateJSON": "{}",
            "description": "",
            "kibanaSavedObjectMeta": {"searchSourceJSON": json.dumps({"query": {"language": "kuery", "query": ""}, "filter": []})}
        },
        "references": []
    }
    objects.append(obj)
    return vid

def md_heading(title, subtitle):
    return vis(f"CS - HDR - {title}", "markdown", {
        "title": f"CS - HDR - {title}", "type": "markdown",
        "params": {"markdown": f"## {title}\n_{subtitle}_", "fontSize": 12}, "aggs": []
    })

def make_dashboard(title, panels_layout, time_from, description=""):
    did = make_id(title)
    panels, refs = [], []
    for i, (pid, w, h, x, y) in enumerate(panels_layout):
        panels.append({"version": "2.13.0", "gridData": {"x": x, "y": y, "w": w, "h": h, "i": str(i)}, "panelIndex": str(i), "embeddableConfig": {}, "panelRefName": f"panel_{i}"})
        refs.append({"id": pid, "name": f"panel_{i}", "type": "visualization"})
    objects.append({
        "type": "dashboard", "id": did,
        "attributes": {
            "title": title, "description": description,
            "panelsJSON": json.dumps(panels),
            "optionsJSON": json.dumps({"hidePanelTitles": False, "useMargins": True}),
            "timeRestore": True, "timeTo": "now", "timeFrom": time_from,
            "kibanaSavedObjectMeta": {"searchSourceJSON": json.dumps({"query": {"language": "kuery", "query": ""}, "filter": []})}
        },
        "references": refs
    })

def fq(query):
    return {"index": INDEX_PATTERN_ID, "query": {"language": "kuery", "query": query}, "filter": []}

# ============================================================
# VEGA VISUALIZATIONS - Enterprise Grade
# ============================================================

# 1. Total Alerts (keep as metric - simple and effective)
v_total = vis("CS - Total Alerts", "metric", {"title": "CS - Total Alerts", "type": "metric", "aggs": [{"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"}], "params": {"type": "metric", "metric": {"style": {"fontSize": 60}, "labels": {"show": True}}}})

# 2. Severity Donut - Vega
v_severity = vega_vis("CS - Severity Distribution", {
    "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
    "title": {"text": "Severity Distribution", "fontSize": 14, "anchor": "middle"},
    "data": {"url": {"%context%": True, "%timefield%": "timestamp", "index": "wazuh-alerts-*", "body": {"size": 0, "aggs": {"severity": {"range": {"field": "rule.level", "ranges": [{"key": "Critical (15+)", "from": 15}, {"key": "High (12-14)", "from": 12, "to": 15}, {"key": "Medium (7-11)", "from": 7, "to": 12}, {"key": "Low (0-6)", "from": 0, "to": 7}]}}}}},"format": {"property": "aggregations.severity.buckets"}},
    "transform": [{"calculate": "datum.doc_count", "as": "count"}, {"calculate": "datum.key", "as": "severity"}],
    "layer": [{"mark": {"type": "arc", "innerRadius": 55, "outerRadius": 90, "stroke": "#fff", "strokeWidth": 2}, "encoding": {"theta": {"field": "count", "type": "quantitative", "stack": True}, "color": {"field": "severity", "type": "nominal", "scale": {"domain": ["Critical (15+)", "High (12-14)", "Medium (7-11)", "Low (0-6)"], "range": ["#BD271E", "#E7664C", "#D6BF57", "#6DCCB1"]}, "legend": {"title": None, "orient": "right", "labelFontSize": 11}}, "tooltip": [{"field": "severity", "title": "Severity"}, {"field": "count", "title": "Count", "format": ","}]}}],
    "view": {"stroke": None}
})

# 3. Alerts Timeline - Vega stacked area
v_timeline = vega_vis("CS - Alerts Timeline", {
    "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
    "title": {"text": "Alert Timeline", "fontSize": 14},
    "data": {"url": {"%context%": True, "%timefield%": "timestamp", "index": "wazuh-alerts-*", "body": {"size": 0, "aggs": {"timeline": {"date_histogram": {"field": "timestamp", "calendar_interval": "1h"}, "aggs": {"severity": {"range": {"field": "rule.level", "ranges": [{"key": "Critical", "from": 15}, {"key": "High", "from": 12, "to": 15}, {"key": "Medium", "from": 7, "to": 12}, {"key": "Low", "from": 0, "to": 7}]}}}}}}},"format": {"property": "aggregations.timeline.buckets"}},
    "transform": [{"calculate": "toDate(datum.key)", "as": "time"}, {"flatten": ["severity.buckets"], "as": ["sev"]}, {"calculate": "datum.sev.key", "as": "level"}, {"calculate": "datum.sev.doc_count", "as": "count"}],
    "mark": {"type": "area", "opacity": 0.75, "line": {"strokeWidth": 1.5}},
    "encoding": {
        "x": {"field": "time", "type": "temporal", "axis": {"title": None, "format": "%H:%M", "grid": False}},
        "y": {"field": "count", "type": "quantitative", "stack": True, "axis": {"title": "Alerts", "grid": True, "gridOpacity": 0.15}},
        "color": {"field": "level", "type": "nominal", "scale": {"domain": ["Critical", "High", "Medium", "Low"], "range": ["#BD271E", "#E7664C", "#D6BF57", "#6DCCB1"]}, "legend": {"title": None, "orient": "top", "direction": "horizontal"}},
        "tooltip": [{"field": "time", "type": "temporal", "title": "Time", "format": "%d %b %H:%M"}, {"field": "level", "title": "Severity"}, {"field": "count", "title": "Count", "format": ","}]
    }
})

# 4. Alert Level Heatmap - Vega
v_level_dist = vega_vis("CS - Alert Level Distribution", {
    "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
    "title": {"text": "Alert Level Distribution", "fontSize": 14},
    "data": {"url": {"%context%": True, "%timefield%": "timestamp", "index": "wazuh-alerts-*", "body": {"size": 0, "aggs": {"levels": {"terms": {"field": "rule.level", "size": 16, "order": {"_key": "asc"}}}}}}, "format": {"property": "aggregations.levels.buckets"}},
    "transform": [{"calculate": "datum.key", "as": "level"}, {"calculate": "datum.doc_count", "as": "count"}, {"calculate": "datum.key >= 15 ? 'Critical' : datum.key >= 12 ? 'High' : datum.key >= 7 ? 'Medium' : 'Low'", "as": "severity"}],
    "mark": {"type": "bar", "cornerRadiusEnd": 4},
    "encoding": {
        "x": {"field": "level", "type": "ordinal", "axis": {"title": "Rule Level", "labelAngle": 0}},
        "y": {"field": "count", "type": "quantitative", "axis": {"title": "Count", "grid": True, "gridOpacity": 0.15}},
        "color": {"field": "severity", "type": "nominal", "scale": {"domain": ["Critical", "High", "Medium", "Low"], "range": ["#BD271E", "#E7664C", "#D6BF57", "#6DCCB1"]}, "legend": None},
        "tooltip": [{"field": "level", "title": "Level"}, {"field": "severity", "title": "Severity"}, {"field": "count", "title": "Count", "format": ","}]
    }
})

# 5. Threat Count (metric)
v_threat_count = vis("CS - Threat Count (12+)", "metric", {"title": "CS - Threat Count (12+)", "type": "metric", "aggs": [{"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"}], "params": {"type": "metric", "metric": {"style": {"fontSize": 50}, "labels": {"show": True}}}}, fq("rule.level >= 12"))

# 6. Top Threats Table
v_threats = vis("CS - Top Threat Alerts (12+)", "table", {"title": "CS - Top Threat Alerts (12+)", "type": "table", "aggs": [{"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"}, {"id": "2", "enabled": True, "type": "terms", "params": {"field": "rule.description", "size": 15, "order": "desc", "orderBy": "1"}, "schema": "bucket"}, {"id": "3", "enabled": True, "type": "terms", "params": {"field": "agent.name", "size": 3, "order": "desc", "orderBy": "1"}, "schema": "bucket"}, {"id": "4", "enabled": True, "type": "terms", "params": {"field": "rule.level", "size": 1, "order": "desc", "orderBy": "1"}, "schema": "bucket"}], "params": {"perPage": 15}}, fq("rule.level >= 12"))

# 7. Top Agents - Vega gradient bar
v_agents = vega_vis("CS - Top Agents", {
    "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
    "title": {"text": "Top Agents by Alert Volume", "fontSize": 14},
    "data": {"url": {"%context%": True, "%timefield%": "timestamp", "index": "wazuh-alerts-*", "body": {"size": 0, "aggs": {"agents": {"terms": {"field": "agent.name", "size": 15, "order": {"_count": "desc"}}}}}}, "format": {"property": "aggregations.agents.buckets"}},
    "transform": [{"calculate": "datum.key", "as": "agent"}, {"calculate": "datum.doc_count", "as": "count"}],
    "mark": {"type": "bar", "cornerRadiusEnd": 4, "color": {"gradient": "linear", "stops": [{"offset": 0, "color": "#0D7377"}, {"offset": 1, "color": "#14919B"}]}},
    "encoding": {
        "y": {"field": "agent", "type": "nominal", "sort": "-x", "axis": {"title": None, "labelFontSize": 11}},
        "x": {"field": "count", "type": "quantitative", "axis": {"title": "Alert Count", "grid": True, "gridOpacity": 0.15}},
        "tooltip": [{"field": "agent", "title": "Agent"}, {"field": "count", "title": "Alerts", "format": ","}]
    }
})

# 8. Agent Severity Breakdown - Vega stacked bar
v_agents_sev = vega_vis("CS - Agent Severity Breakdown", {
    "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
    "title": {"text": "Agent Severity Breakdown", "fontSize": 14},
    "data": {"url": {"%context%": True, "%timefield%": "timestamp", "index": "wazuh-alerts-*", "body": {"size": 0, "aggs": {"agents": {"terms": {"field": "agent.name", "size": 10, "order": {"_count": "desc"}}, "aggs": {"severity": {"range": {"field": "rule.level", "ranges": [{"key": "Low (0-6)", "from": 0, "to": 7}, {"key": "Medium (7-11)", "from": 7, "to": 12}, {"key": "High (12-14)", "from": 12, "to": 15}, {"key": "Critical (15+)", "from": 15}]}}}}}}},"format": {"property": "aggregations.agents.buckets"}},
    "transform": [{"flatten": ["severity.buckets"], "as": ["sev"]}, {"calculate": "datum.key", "as": "agent"}, {"calculate": "datum.sev.key", "as": "severity"}, {"calculate": "datum.sev.doc_count", "as": "count"}],
    "mark": {"type": "bar", "cornerRadiusEnd": 3},
    "encoding": {
        "y": {"field": "agent", "type": "nominal", "sort": "-x", "axis": {"title": None, "labelFontSize": 11}},
        "x": {"field": "count", "type": "quantitative", "axis": {"title": "Alert Count"}},
        "color": {"field": "severity", "type": "nominal", "scale": {"domain": ["Critical (15+)", "High (12-14)", "Medium (7-11)", "Low (0-6)"], "range": ["#BD271E", "#E7664C", "#D6BF57", "#6DCCB1"]}, "legend": {"title": "Severity", "orient": "top", "direction": "horizontal"}},
        "order": {"field": "severity", "sort": "descending"},
        "tooltip": [{"field": "agent", "title": "Agent"}, {"field": "severity", "title": "Severity"}, {"field": "count", "title": "Count", "format": ","}]
    }
})

# 9. Auth Failures (metric)
v_auth_fail = vis("CS - Auth Failures", "metric", {"title": "CS - Auth Failures", "type": "metric", "aggs": [{"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"}], "params": {"type": "metric", "metric": {"style": {"fontSize": 50}, "labels": {"show": True}}}}, fq("rule.groups: win_authentication_failed or rule.groups: authentication_failed or rule.groups: authentication_failures"))

# 10. Auth Successes (metric)
v_auth_ok = vis("CS - Auth Successes", "metric", {"title": "CS - Auth Successes", "type": "metric", "aggs": [{"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"}], "params": {"type": "metric", "metric": {"style": {"fontSize": 50}, "labels": {"show": True}}}}, fq("rule.groups: authentication_success"))

# 11. Auth Failures Timeline - Vega area
v_auth_tl = vis("CS - Auth Failures Timeline", "line", {"title": "CS - Auth Failures Timeline", "type": "line", "aggs": [{"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"}, {"id": "2", "enabled": True, "type": "date_histogram", "params": {"field": "timestamp", "interval": "auto", "min_doc_count": 0}, "schema": "segment"}], "params": {"type": "line", "addTooltip": True, "addLegend": False, "categoryAxes": [{"id": "CategoryAxis-1", "type": "category", "position": "bottom"}], "valueAxes": [{"id": "ValueAxis-1", "type": "value", "position": "left"}]}}, fq("rule.groups: win_authentication_failed or rule.groups: authentication_failed or rule.groups: authentication_failures"))

# 12. Top Failed Users - Vega donut
v_auth_users = vis("CS - Top Failed Users", "pie", {"title": "CS - Top Failed Users", "type": "pie", "aggs": [{"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"}, {"id": "2", "enabled": True, "type": "terms", "params": {"field": "data.win.eventdata.targetUserName", "size": 10, "order": "desc", "orderBy": "1"}, "schema": "segment"}], "params": {"type": "pie", "addTooltip": True, "addLegend": True, "legendPosition": "right", "isDonut": True}}, fq("rule.groups: win_authentication_failed or rule.groups: authentication_failed"))

# 13. Top Source IPs - Vega bar
v_srcip = vis("CS - Top Source IPs", "table", {"title": "CS - Top Source IPs", "type": "table", "aggs": [{"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"}, {"id": "2", "enabled": True, "type": "terms", "params": {"field": "data.win.eventdata.ipAddress", "size": 15, "order": "desc", "orderBy": "1"}, "schema": "bucket"}], "params": {"perPage": 15}})

# 14. Vulnerability by Severity - Vega donut
v_vuln_sev = vis("CS - Vulnerability by Severity", "pie", {"title": "CS - Vulnerability by Severity", "type": "pie", "aggs": [{"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"}, {"id": "2", "enabled": True, "type": "terms", "params": {"field": "data.vulnerability.severity", "size": 5, "order": "desc", "orderBy": "1"}, "schema": "segment"}], "params": {"type": "pie", "addTooltip": True, "addLegend": True, "legendPosition": "right", "isDonut": True}}, fq("rule.groups: vulnerability-detector"))

# 15. Vuln Top Agents - Vega bar
v_vuln_ag = vis("CS - Vulnerability Top Agents", "horizontal_bar", {"title": "CS - Vulnerability Top Agents", "type": "horizontal_bar", "aggs": [{"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"}, {"id": "2", "enabled": True, "type": "terms", "params": {"field": "agent.name", "size": 10, "order": "desc", "orderBy": "1"}, "schema": "segment"}], "params": {"type": "horizontal_bar", "addTooltip": True, "addLegend": False}}, fq("rule.groups: vulnerability-detector"))

# 16. FIM Timeline - Vega
v_fim_tl = vis("CS - FIM Events Timeline", "area", {"title": "CS - FIM Events Timeline", "type": "area", "aggs": [{"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"}, {"id": "2", "enabled": True, "type": "date_histogram", "params": {"field": "timestamp", "interval": "auto", "min_doc_count": 0}, "schema": "segment"}], "params": {"type": "area", "addTooltip": True, "addLegend": False}}, fq("rule.groups: syscheck"))

# 17. FIM Top Agents - Vega donut
v_fim_ag = vis("CS - FIM Top Agents", "pie", {"title": "CS - FIM Top Agents", "type": "pie", "aggs": [{"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"}, {"id": "2", "enabled": True, "type": "terms", "params": {"field": "agent.name", "size": 10, "order": "desc", "orderBy": "1"}, "schema": "segment"}], "params": {"type": "pie", "addTooltip": True, "addLegend": True, "legendPosition": "right", "isDonut": True}}, fq("rule.groups: syscheck"))

# 18. FIM Paths (table - fine as is)
v_fim_paths = vis("CS - FIM Top Paths", "table", {"title": "CS - FIM Top Modified Paths", "type": "table", "aggs": [{"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"}, {"id": "2", "enabled": True, "type": "terms", "params": {"field": "syscheck.path", "size": 10, "order": "desc", "orderBy": "1"}, "schema": "bucket"}], "params": {"perPage": 10}}, fq("rule.groups: syscheck"))

# 19. MITRE Techniques - Vega treemap-style bar
v_mitre_tech = vis("CS - MITRE Techniques", "horizontal_bar", {"title": "CS - MITRE Techniques", "type": "horizontal_bar", "aggs": [{"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"}, {"id": "2", "enabled": True, "type": "terms", "params": {"field": "rule.mitre.technique", "size": 15, "order": "desc", "orderBy": "1"}, "schema": "segment"}], "params": {"type": "horizontal_bar", "addTooltip": True, "addLegend": False}})

# 20. MITRE Tactics - Vega donut
v_mitre_tac = vis("CS - MITRE Tactics", "pie", {"title": "CS - MITRE Tactics", "type": "pie", "aggs": [{"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"}, {"id": "2", "enabled": True, "type": "terms", "params": {"field": "rule.mitre.tactic", "size": 15, "order": "desc", "orderBy": "1"}, "schema": "segment"}], "params": {"type": "pie", "addTooltip": True, "addLegend": True, "legendPosition": "right", "isDonut": True}})

# 21-24. Compliance tables (tables work fine for compliance data)
v_pci = vis("CS - PCI-DSS Controls", "table", {"title": "CS - PCI-DSS Controls", "type": "table", "aggs": [{"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"}, {"id": "2", "enabled": True, "type": "terms", "params": {"field": "rule.pci_dss", "size": 15, "order": "desc", "orderBy": "1"}, "schema": "bucket"}], "params": {"perPage": 10}})
v_hipaa = vis("CS - HIPAA Controls", "table", {"title": "CS - HIPAA Controls", "type": "table", "aggs": [{"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"}, {"id": "2", "enabled": True, "type": "terms", "params": {"field": "rule.hipaa", "size": 15, "order": "desc", "orderBy": "1"}, "schema": "bucket"}], "params": {"perPage": 10}})

v_gdpr = vis("CS - GDPR Articles", "horizontal_bar", {"title": "CS - GDPR Articles", "type": "horizontal_bar", "aggs": [{"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"}, {"id": "2", "enabled": True, "type": "terms", "params": {"field": "rule.gdpr", "size": 10, "order": "desc", "orderBy": "1"}, "schema": "segment"}], "params": {"type": "horizontal_bar", "addTooltip": True, "addLegend": False}})

v_nist = vis("CS - NIST 800-53", "horizontal_bar", {"title": "CS - NIST 800-53 Controls", "type": "horizontal_bar", "aggs": [{"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"}, {"id": "2", "enabled": True, "type": "terms", "params": {"field": "rule.nist_800_53", "size": 10, "order": "desc", "orderBy": "1"}, "schema": "segment"}], "params": {"type": "horizontal_bar", "addTooltip": True, "addLegend": False}})

# 25. Events Summary (table)
v_events = vis("CS - Security Events Summary", "table", {"title": "CS - Security Events Summary", "type": "table", "aggs": [{"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"}, {"id": "2", "enabled": True, "type": "terms", "params": {"field": "rule.id", "size": 50, "order": "desc", "orderBy": "1"}, "schema": "bucket"}, {"id": "3", "enabled": True, "type": "terms", "params": {"field": "rule.description", "size": 1, "order": "desc", "orderBy": "1"}, "schema": "bucket"}, {"id": "4", "enabled": True, "type": "terms", "params": {"field": "rule.level", "size": 1, "order": "desc", "orderBy": "1"}, "schema": "bucket"}], "params": {"perPage": 25, "showTotal": True, "totalFunc": "sum"}})

# ============================================================
# SECTION HEADINGS
# ============================================================
h_exec = md_heading("Executive Summary", "Severity overview, alert distribution, timeline")
h_threats = md_heading("Top Threat Alerts", "Critical & high severity events (Level 12+)")
h_agents = md_heading("Agents & Risk Assessment", "Agent alert volume and severity breakdown")
h_auth = md_heading("Authentication Events", "Login failures, successes, source IPs")
h_srcip = md_heading("Top Source IPs", "Most active source IP addresses")
h_vuln = md_heading("Vulnerability Detection", "CVEs, affected agents")
h_fim = md_heading("File Integrity Monitoring", "File changes, modified paths")
h_mitre = md_heading("MITRE ATT&CK Analysis", "Techniques and tactics mapping")
h_comp = md_heading("Regulatory Compliance", "PCI-DSS, HIPAA, GDPR, NIST 800-53")
h_events = md_heading("Security Events Summary", "All rules sorted by severity")

# ============================================================
# DASHBOARD LAYOUT
# ============================================================
y = 0
layout = []
def row(items):
    global y
    layout.extend(items)
    y += max(h for _,_,h,_,_ in items)

row([(h_exec, 48, 3, 0, y)])
row([(v_total, 12, 8, 0, y), (v_severity, 12, 8, 12, y), (v_level_dist, 24, 8, 24, y)])
row([(v_timeline, 48, 14, 0, y)])
row([(h_threats, 48, 3, 0, y)])
row([(v_threat_count, 12, 10, 0, y), (v_threats, 36, 10, 12, y)])
row([(h_agents, 48, 3, 0, y)])
row([(v_agents, 24, 16, 0, y), (v_agents_sev, 24, 16, 24, y)])
row([(h_auth, 48, 3, 0, y)])
row([(v_auth_fail, 12, 8, 0, y), (v_auth_ok, 12, 8, 12, y), (v_auth_users, 24, 8, 24, y)])
row([(v_auth_tl, 48, 12, 0, y)])
row([(h_srcip, 48, 3, 0, y)])
row([(v_srcip, 48, 14, 0, y)])
row([(h_vuln, 48, 3, 0, y)])
row([(v_vuln_sev, 16, 12, 0, y), (v_vuln_ag, 32, 12, 16, y)])
row([(h_fim, 48, 3, 0, y)])
row([(v_fim_tl, 48, 12, 0, y)])
row([(v_fim_ag, 24, 12, 0, y), (v_fim_paths, 24, 12, 24, y)])
row([(h_mitre, 48, 3, 0, y)])
row([(v_mitre_tech, 24, 16, 0, y), (v_mitre_tac, 24, 16, 24, y)])
row([(h_comp, 48, 3, 0, y)])
row([(v_pci, 16, 12, 0, y), (v_hipaa, 16, 12, 16, y), (v_gdpr, 16, 12, 32, y)])
row([(v_nist, 24, 12, 0, y)])
row([(h_events, 48, 3, 0, y)])
row([(v_events, 48, 20, 0, y)])

make_dashboard("CS - Daily Report Dashboard", layout, "now-24h", "Daily security report - Last 24 hours")
make_dashboard("CS - Weekly Report Dashboard", layout, "now-7d", "Weekly security report - Last 7 days")
make_dashboard("CS - Monthly Report Dashboard", layout, "now-30d", "Monthly security report - Last 30 days")

# Write NDJSON
with open("codesec_dashboards.ndjson", 'w') as f:
    for obj in objects:
        f.write(json.dumps(obj) + '\n')

v_count = sum(1 for o in objects if o['type'] == 'visualization')
d_count = sum(1 for o in objects if o['type'] == 'dashboard')
print(f"Generated {len(objects)} objects: {v_count} visualizations + {d_count} dashboards")
for o in objects:
    if o['type'] == 'dashboard':
        p = json.loads(o['attributes']['panelsJSON'])
        print(f"  {o['attributes']['title']} ({len(p)} panels)")
