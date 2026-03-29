"""TheHive 5 API client — fetches all data needed for Incident Management report."""

import ssl, asyncio
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import config

IST = timezone(timedelta(hours=5, minutes=30))

def _ssl_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

def _headers():
    return {
        "Authorization": f"Bearer {config.THEHIVE_API_KEY}",
        "Content-Type": "application/json"
    }

async def _query(session, pipeline):
    import aiohttp
    ssl_ctx = _ssl_ctx()
    async with session.post(
        f"{config.THEHIVE_URL}/api/v1/query",
        headers=_headers(),
        json={"query": pipeline},
        ssl=ssl_ctx
    ) as r:
        data = await r.json()
        return data if isinstance(data, list) else []

async def fetch_all(period="7d"):
    import aiohttp
    async with aiohttp.ClientSession() as session:
        alerts_raw, cases_raw = await asyncio.gather(
            _query(session, [{"_name": "listAlert"}]),
            _query(session, [{"_name": "listCase"}]),
        )

        # Fetch observables for all cases
        obs_raw = []
        for case in cases_raw[:50]:
            case_id = case.get("_id", "")
            if case_id:
                o = await _query(session, [
                    {"_name": "getCase", "idOrName": case_id},
                    {"_name": "observables"}
                ])
                obs_raw.extend(o)

    return _process(alerts_raw, cases_raw, obs_raw, period)

def _ts_to_dt(ts):
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).astimezone(IST)
    except:
        return None

def _age_hours(ts):
    if not ts:
        return 0
    try:
        created = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        return (datetime.now(timezone.utc) - created).total_seconds() / 3600
    except:
        return 0

def _process(alerts_raw, cases_raw, obs_raw, period="7d"):
    now = datetime.now(IST)

    # ── Period filter ────────────────────────────────────────
    _period_h = {"24h": 24, "7d": 168, "30d": 720, "90d": 2160}
    cutoff_ms = int((now - timedelta(hours=_period_h.get(period, 168))).timestamp() * 1000)
    alerts_raw = [a for a in alerts_raw if a.get("_createdAt", 0) >= cutoff_ms]
    cases_raw  = [c for c in cases_raw  if c.get("_createdAt", 0) >= cutoff_ms]

    # ── Timeline bucket config (adaptive to period) ──────────
    if period == "24h":
        _tl_labels = [(now - timedelta(hours=i)).strftime("%H:00") for i in range(23, -1, -1)]
        def _tl_key(dt): return dt.strftime("%H:00")
    elif period == "30d":
        _tl_labels = [(now - timedelta(days=i)).strftime("%m/%d") for i in range(29, -1, -1)]
        def _tl_key(dt): return dt.strftime("%m/%d")
    else:  # 7d default
        _tl_labels = [(now - timedelta(days=i)).strftime("%m/%d") for i in range(6, -1, -1)]
        def _tl_key(dt): return dt.strftime("%m/%d")

    # ── Alerts ──────────────────────────────────────────────
    total_alerts = len(alerts_raw)
    sev_counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    status_counts = defaultdict(int)
    alert_sources = defaultdict(int)
    alert_tags = defaultdict(int)
    alert_by_bucket = defaultdict(int)
    alert_title_counts = defaultdict(int)

    SEV_MAP = {4: "Critical", 3: "High", 2: "Medium", 1: "Low"}

    for a in alerts_raw:
        sev = SEV_MAP.get(a.get("severity", 1), "Low")
        sev_counts[sev] += 1
        status_counts[a.get("status", "Unknown")] += 1
        alert_sources[a.get("source", "unknown")] += 1
        alert_title_counts[a.get("title", "Unknown")[:60]] += 1
        for tag in a.get("tags", []):
            alert_tags[tag] += 1
        ts = _ts_to_dt(a.get("_createdAt"))
        if ts:
            alert_by_bucket[_tl_key(ts)] += 1

    top_alert_titles = sorted(alert_title_counts.items(), key=lambda x: -x[1])[:10]
    top_tags = sorted(alert_tags.items(), key=lambda x: -x[1])[:12]

    alert_timeline = [{"label": lbl, "value": alert_by_bucket.get(lbl, 0)} for lbl in _tl_labels]

    # ── Cases ───────────────────────────────────────────────
    total_cases = len(cases_raw)
    case_sev = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    case_status = defaultdict(int)
    case_assignees = defaultdict(int)
    mttr_hours = []
    open_cases = []
    closed_cases = []
    case_by_bucket = defaultdict(int)

    for c in cases_raw:
        sev = SEV_MAP.get(c.get("severity", 1), "Low")
        case_sev[sev] += 1
        stage = c.get("stage", c.get("status", "New"))
        case_status[stage] += 1

        assignee = c.get("assignee", "Unassigned") or "Unassigned"
        case_assignees[assignee] += 1

        ts = _ts_to_dt(c.get("_createdAt"))
        if ts:
            case_by_bucket[_tl_key(ts)] += 1

        age = _age_hours(c.get("_createdAt"))
        resolution = c.get("resolutionStatus", "")

        if stage in ("Resolved", "TruePositive", "FalsePositive", "Duplicated", "Other", "Indeterminate", "Closed", "Archived"):
            closed_cases.append(c)
            # MTTR: created → updated
            updated = c.get("_updatedAt") or c.get("endDate")
            if updated and c.get("_createdAt"):
                hrs = (updated - c["_createdAt"]) / 3600000
                if 0 < hrs < 8760:
                    mttr_hours.append(hrs)
        else:
            open_cases.append({
                "id": c.get("_id", ""),
                "number": c.get("number", ""),
                "title": c.get("title", "N/A")[:55],
                "severity": sev,
                "assignee": assignee,
                "status": stage,
                "age_h": round(age, 1),
                "tags": c.get("tags", [])[:4],
                "tlp": c.get("tlp", 2),
            })

    open_cases.sort(key=lambda x: -x["age_h"])

    mttr_avg = round(sum(mttr_hours) / len(mttr_hours), 2) if mttr_hours else 0
    if mttr_hours:
        _total_min = round(mttr_avg * 60)
        mttr_display = f"{_total_min // 60}h {_total_min % 60}m" if _total_min >= 60 else f"{_total_min}m"
    else:
        mttr_display = "N/A"

    # Resolution breakdown
    res_counts = defaultdict(int)
    for c in closed_cases:
        stage = c.get("stage", c.get("status", "Closed"))
        res_counts[stage] += 1

    # Closed cases list for display (top 15, most recently closed first)
    closed_cases_list = []
    for c in sorted(closed_cases, key=lambda x: x.get("_updatedAt") or 0, reverse=True)[:15]:
        sev = SEV_MAP.get(c.get("severity", 1), "Low")
        stage = c.get("stage", c.get("status", "Closed"))
        assignee = c.get("assignee", "Unassigned") or "Unassigned"
        updated_ms = c.get("_updatedAt") or c.get("endDate")
        closed_at = _ts_to_dt(updated_ms).strftime("%m/%d %H:%M") if updated_ms and _ts_to_dt(updated_ms) else "N/A"
        closed_cases_list.append({
            "number": c.get("number", ""),
            "title": c.get("title", "N/A")[:55],
            "severity": sev,
            "assignee": assignee,
            "resolution": stage,
            "closed_at": closed_at,
        })

    # SLA breaches
    sla_24h = sum(1 for c in open_cases if c["age_h"] > 24)
    sla_72h = sum(1 for c in open_cases if c["age_h"] > 72)

    # ── Observables ─────────────────────────────────────────
    obs_by_type = defaultdict(list)
    for o in obs_raw:
        dtype = o.get("dataType", "other")
        data = o.get("data", "")
        if data:
            obs_by_type[dtype].append(data)

    top_ips = _top_values(obs_by_type.get("ip", []), 10)
    top_hostnames = _top_values(obs_by_type.get("hostname", []), 8)
    top_domains = _top_values(obs_by_type.get("domain", []), 8)
    top_hashes = _top_values(obs_by_type.get("hash", []), 5)

    obs_summary = {t: len(v) for t, v in obs_by_type.items()}

    # ── MITRE ───────────────────────────────────────────────
    mitre_counts = defaultdict(int)
    for a in alerts_raw:
        for tag in a.get("tags", []):
            # MITRE tags from Wazuh start with capital or are technique names
            if any(c.isupper() for c in tag[:2]):
                mitre_counts[tag] += 1
    top_mitre = sorted(mitre_counts.items(), key=lambda x: -x[1])[:10]

    # ── Summary metrics ─────────────────────────────────────
    false_positive = res_counts.get("FalsePositive", 0)
    true_positive = res_counts.get("TruePositive", 0)
    tp_rate = round(true_positive / max(len(closed_cases), 1) * 100)

    return {
        # Meta
        "generated_at": now.strftime("%d %B %Y, %H:%M IST"),
        "period": {"24h": "Last 24 Hours", "7d": "Last 7 Days", "30d": "Last 30 Days", "90d": "Last 90 Days"}.get(period, "Last 7 Days"),
        "period_key": period,

        # Alert stats
        "total_alerts": total_alerts,
        "alert_sev": sev_counts,
        "alert_status": dict(status_counts),
        "alert_sources": dict(alert_sources),
        "top_alert_titles": top_alert_titles,
        "top_tags": top_tags,
        "alert_timeline": alert_timeline,

        # Case stats
        "total_cases": total_cases,
        "open_cases_count": len(open_cases),
        "closed_cases_count": len(closed_cases),
        "case_sev": case_sev,
        "case_status": dict(case_status),
        "case_assignees": dict(case_assignees),
        "resolution_counts": dict(res_counts),
        "open_cases": open_cases[:20],
        "closed_cases": closed_cases_list,
        "mttr_avg": mttr_avg,
        "mttr_display": mttr_display,
        "sla_24h": sla_24h,
        "sla_72h": sla_72h,
        "tp_rate": tp_rate,

        # Observables
        "obs_summary": obs_summary,
        "top_ips": top_ips,
        "top_hostnames": top_hostnames,
        "top_domains": top_domains,
        "top_hashes": top_hashes,

        # MITRE
        "top_mitre": top_mitre,

        # Case timeline
        "case_timeline": [{"label": lbl, "value": case_by_bucket.get(lbl, 0)} for lbl in _tl_labels],
    }

def _top_values(lst, n):
    counts = defaultdict(int)
    for v in lst:
        counts[str(v)[:40]] += 1
    return sorted(counts.items(), key=lambda x: -x[1])[:n]
