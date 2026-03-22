"""Comparison module - compare two time periods side by side.
Returns structured data for the frontend to render."""

import config, opensearch_client

def compare_periods(period_a="now-24h", period_b="now-48h/now-24h", agent=None):
    """Compare two time periods and return delta metrics.
    period_a: current period (e.g. "now-24h")
    period_b: previous period as "from/to" (e.g. "now-48h/now-24h")
    """
    client = opensearch_client.get_client()

    # Parse period_b
    if "/" in period_b:
        b_from, b_to = period_b.split("/")
    else:
        b_from, b_to = period_b, "now"

    def _build_query(gte, lte="now"):
        must = [{"range": {"timestamp": {"gte": gte, "lte": lte}}}]
        if agent:
            must.append({"term": {"agent.name": agent}})
        return {"bool": {"must": must}}

    aggs = {
        "by_level": {"terms": {"field": "rule.level", "size": 20}},
        "agents": {"terms": {"field": "agent.name", "size": 50}},
        "top_rules": {"terms": {"field": "rule.id", "size": 20, "order": {"_count": "desc"}},
            "aggs": {"desc": {"terms": {"field": "rule.description", "size": 1}},
                     "lvl": {"max": {"field": "rule.level"}}}},
        "auth_fail": {"filter": {"terms": {"rule.groups": ["win_authentication_failed", "authentication_failed", "authentication_failures"]}}},
        "auth_success": {"filter": {"term": {"rule.groups": "authentication_success"}}},
        "mitre_tech": {"terms": {"field": "rule.mitre.technique", "size": 20}},
        "level12": {"filter": {"range": {"rule.level": {"gte": 12}}}},
    }

    # Run both queries
    body_a = {"size": 0, "track_total_hits": True, "query": _build_query(period_a), "aggs": aggs}
    body_b = {"size": 0, "track_total_hits": True, "query": _build_query(b_from, b_to), "aggs": aggs}

    r_a = client.search(index=config.OPENSEARCH_INDEX, body=body_a)
    r_b = client.search(index=config.OPENSEARCH_INDEX, body=body_b)

    def _sev(buckets):
        s = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
        for b in buckets:
            k = b["key"]
            if k >= 15: s["Critical"] += b["doc_count"]
            elif k >= 12: s["High"] += b["doc_count"]
            elif k >= 7: s["Medium"] += b["doc_count"]
            else: s["Low"] += b["doc_count"]
        return s

    def _delta(curr, prev):
        if prev == 0:
            return {"value": curr, "prev": prev, "diff": curr, "pct": "N/A", "trend": "neutral"}
        diff = curr - prev
        pct = round((diff / prev) * 100, 1)
        trend = "up" if diff > 0 else ("down" if diff < 0 else "neutral")
        return {"value": curr, "prev": prev, "diff": diff, "pct": pct, "trend": trend}

    sev_a = _sev(r_a["aggregations"]["by_level"]["buckets"])
    sev_b = _sev(r_b["aggregations"]["by_level"]["buckets"])

    # Top rules comparison
    rules_a = {b["key"]: {"desc": b["desc"]["buckets"][0]["key"] if b["desc"]["buckets"] else "N/A",
                           "level": int(b["lvl"]["value"]) if b["lvl"]["value"] else 0,
                           "count": b["doc_count"]} for b in r_a["aggregations"]["top_rules"]["buckets"]}
    rules_b = {b["key"]: b["doc_count"] for b in r_b["aggregations"]["top_rules"]["buckets"]}

    rules_compare = []
    for rid, info in rules_a.items():
        prev = rules_b.get(rid, 0)
        rules_compare.append({
            "rule_id": rid, "description": info["desc"], "level": info["level"],
            "current": info["count"], "previous": prev,
            "diff": info["count"] - prev,
            "pct": round((info["count"] - prev) / prev * 100, 1) if prev > 0 else "N/A"
        })
    rules_compare.sort(key=lambda x: (-x["level"], -x["current"]))

    # Agents comparison
    agents_a = {b["key"]: b["doc_count"] for b in r_a["aggregations"]["agents"]["buckets"]}
    agents_b = {b["key"]: b["doc_count"] for b in r_b["aggregations"]["agents"]["buckets"]}
    all_agents = sorted(set(list(agents_a.keys()) + list(agents_b.keys())))
    agents_compare = []
    for name in all_agents:
        curr = agents_a.get(name, 0)
        prev = agents_b.get(name, 0)
        agents_compare.append({
            "agent": name, "current": curr, "previous": prev,
            "diff": curr - prev,
            "pct": round((curr - prev) / prev * 100, 1) if prev > 0 else "N/A"
        })
    agents_compare.sort(key=lambda x: -x["current"])

    return {
        "summary": {
            "total": _delta(r_a["hits"]["total"]["value"], r_b["hits"]["total"]["value"]),
            "critical": _delta(sev_a["Critical"], sev_b["Critical"]),
            "high": _delta(sev_a["High"], sev_b["High"]),
            "medium": _delta(sev_a["Medium"], sev_b["Medium"]),
            "low": _delta(sev_a["Low"], sev_b["Low"]),
            "auth_fail": _delta(r_a["aggregations"]["auth_fail"]["doc_count"], r_b["aggregations"]["auth_fail"]["doc_count"]),
            "auth_success": _delta(r_a["aggregations"]["auth_success"]["doc_count"], r_b["aggregations"]["auth_success"]["doc_count"]),
            "level12": _delta(r_a["aggregations"]["level12"]["doc_count"], r_b["aggregations"]["level12"]["doc_count"]),
            "mitre_techniques": _delta(len(r_a["aggregations"]["mitre_tech"]["buckets"]), len(r_b["aggregations"]["mitre_tech"]["buckets"])),
            "agents": _delta(len(agents_a), len(agents_b)),
        },
        "severity_a": sev_a,
        "severity_b": sev_b,
        "rules": rules_compare[:20],
        "agents": agents_compare,
    }
