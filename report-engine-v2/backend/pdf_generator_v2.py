"""PDF Report Generator V2 - Enhanced enterprise styling.
Imports data pipeline from v1, only overrides rendering layer."""

import json
import os
import math
from datetime import datetime, timedelta

import config
import database
import opensearch_client
from pdf_generator import (
    build_query, process_data, _html_to_pdf,
    _fc, _sc, _rc, PALETTE, IST
)

# ── Extended palette (24 colors) ──────────────────────────────────
PALETTE_V2 = [
    '#2563eb', '#059669', '#d97706', '#dc2626', '#7c3aed',
    '#0891b2', '#e11d48', '#4f46e5', '#16a34a', '#ea580c',
    '#0d9488', '#9333ea', '#2dd4bf', '#f59e0b', '#6366f1',
    '#10b981', '#ef4444', '#8b5cf6', '#06b6d4', '#f97316',
    '#14b8a6', '#a855f7', '#3b82f6', '#84cc16',
]

# Gradient pairs: (start, end) for each severity
SEV_GRAD = {
    'Critical': ('#BD271E', '#920000'),
    'High':     ('#E7664C', '#C0392B'),
    'Medium':   ('#D6BF57', '#B8860B'),
    'Low':      ('#6DCCB1', '#1ABC9C'),
}

# Section accent colors
SEC_ACCENT = {
    'executive_summary': '#2563eb',
    'top_threats':       '#BD271E',
    'agents_risk':       '#059669',
    'authentication':    '#dc2626',
    'source_ips':        '#d97706',
    'vulnerability':     '#7c3aed',
    'fim':               '#9333ea',
    'mitre':             '#0891b2',
    'compliance':        '#e11d48',
    'security_events':   '#1e293b',
}


# ── SVG Icons (24x24 viewBox) ────────────────────────────────────
_ICON_PATHS = {
    'shield': 'M12 2L3 7v5c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V7l-9-5z',
    'alert': 'M12 2L1 21h22L12 2zm0 4l7.53 13H4.47L12 6zm-1 5v4h2v-4h-2zm0 6v2h2v-2h-2z',
    'lock': 'M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zM12 17c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zM9 8V6c0-1.66 1.34-3 3-3s3 1.34 3 3v2H9z',
    'unlock': 'M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6h2c0-1.66 1.34-3 3-3s3 1.34 3 3v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm0 12H6V10h12v10zm-6-3c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2z',
    'bug': 'M20 8h-2.81a5.985 5.985 0 00-1.82-1.96L17 4.41 15.59 3l-2.17 2.17C12.96 5.06 12.49 5 12 5s-.96.06-1.41.17L8.41 3 7 4.41l1.62 1.63C7.88 6.55 7.26 7.22 6.81 8H4v2h2.09c-.05.33-.09.66-.09 1v1H4v2h2v1c0 .34.04.67.09 1H4v2h2.81c1.04 1.79 2.97 3 5.19 3s4.15-1.21 5.19-3H20v-2h-2.09c.05-.33.09-.66.09-1v-1h2v-2h-2v-1c0-.34-.04-.67-.09-1H20V8zm-6 8h-4v-2h4v2zm0-4h-4v-2h4v2z',
    'file': 'M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zM6 20V4h7v5h5v11H6z',
    'target': 'M12 2C6.49 2 2 6.49 2 12s4.49 10 10 10 10-4.49 10-10S17.51 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm3-8c0 1.66-1.34 3-3 3s-3-1.34-3-3 1.34-3 3-3 3 1.34 3 3z',
    'globe': 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z',
    'users': 'M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5s-3 1.34-3 3 1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z',
    'clock': 'M12 2C6.49 2 2 6.49 2 12s4.49 10 10 10 10-4.49 10-10S17.51 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67V7z',
    'check': 'M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z',
    'chart': 'M3.5 18.49l6-6.01 4 4L22 6.92l-1.41-1.41-7.09 7.97-4-4L2 16.99l1.5 1.5z',
}


def _icon(name, color='#fff', size=20):
    """Render an SVG icon by name."""
    path = _ICON_PATHS.get(name, '')
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" '
        f'fill="{color}" xmlns="http://www.w3.org/2000/svg">'
        f'<path d="{path}"/></svg>'
    )


# ── Enhanced SVG Charts ──────────────────────────────────────────

def _svg_defs_shadow():
    """Shared SVG drop shadow filter."""
    return (
        '<defs>'
        '<filter id="ds" x="-5%" y="-5%" width="115%" height="120%">'
        '<feDropShadow dx="0" dy="1" stdDeviation="2" flood-opacity="0.12"/>'
        '</filter>'
        '</defs>'
    )


def svg_donut_v2(data, w=200, h=200, r=75, r2=48):
    """Enhanced donut chart with gradients and shadow."""
    cx, cy = w / 2, h / 2
    total = sum(x["value"] for x in data) or 1

    # Build gradient defs
    defs = '<defs>'
    defs += (
        '<filter id="dshadow" x="-10%" y="-10%" width="125%" height="125%">'
        '<feDropShadow dx="0" dy="2" stdDeviation="3" flood-opacity="0.15"/>'
        '</filter>'
    )
    for i, x in enumerate(data):
        c = x["color"]
        defs += (
            f'<linearGradient id="dg{i}" x1="0%" y1="0%" x2="100%" y2="100%">'
            f'<stop offset="0%" stop-color="{c}" stop-opacity="1"/>'
            f'<stop offset="100%" stop-color="{c}" stop-opacity="0.7"/>'
            f'</linearGradient>'
        )
    defs += '</defs>'

    # Draw arcs
    paths = ''
    cum = -90
    for i, x in enumerate(data):
        if x["value"] <= 0:
            continue
        pct = x["value"] / total
        ang = pct * 360
        s = cum * math.pi / 180
        e = (cum + ang) * math.pi / 180
        cum += ang
        la = 1 if ang > 180 else 0
        x1 = cx + r * math.cos(s)
        y1 = cy + r * math.sin(s)
        x2 = cx + r * math.cos(e)
        y2 = cy + r * math.sin(e)
        x3 = cx + r2 * math.cos(e)
        y3 = cy + r2 * math.sin(e)
        x4 = cx + r2 * math.cos(s)
        y4 = cy + r2 * math.sin(s)
        paths += (
            f'<path d="M{x1:.1f},{y1:.1f} '
            f'A{r},{r} 0 {la},1 {x2:.1f},{y2:.1f} '
            f'L{x3:.1f},{y3:.1f} '
            f'A{r2},{r2} 0 {la},0 {x4:.1f},{y4:.1f}Z" '
            f'fill="url(#dg{i})" stroke="#fff" stroke-width="1.5"/>'
        )

    # Center text
    center = (
        f'<text x="{cx}" y="{cy - 6}" text-anchor="middle" '
        f'font-size="22" font-weight="800" fill="#1e293b">{_fc(total)}</text>'
        f'<text x="{cx}" y="{cy + 12}" text-anchor="middle" '
        f'font-size="9" fill="#94a3b8">Total Alerts</text>'
    )

    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        f'{defs}'
        f'<g filter="url(#dshadow)">{paths}</g>'
        f'{center}'
        f'</svg>'
    )


def svg_vbars_v2(items, w=500, h=160, show_grid=True):
    """Enhanced vertical bar chart with gradients and grid."""
    if not items:
        return '<div style="text-align:center;color:#94a3b8;padding:20px">No data</div>'

    pt, pb, pl, pr = 20, 45, 40, 10
    cW = w - pl - pr
    cH = h - pt - pb
    mx = max((i["value"] for i in items), default=1) or 1
    n = len(items)
    bW = min(int(cW / max(n, 1)) - 4, 24)
    gap = (cW - bW * n) / (n + 1) if n else 0

    # Defs
    defs = '<defs>'
    defs += (
        '<filter id="vds" x="-5%" y="-5%" width="115%" height="115%">'
        '<feDropShadow dx="0" dy="1" stdDeviation="1" flood-opacity="0.1"/>'
        '</filter>'
    )
    for idx, it in enumerate(items):
        c = it.get("color", "#2563eb")
        defs += (
            f'<linearGradient id="vg{idx}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0%" stop-color="{c}" stop-opacity="1"/>'
            f'<stop offset="100%" stop-color="{c}" stop-opacity="0.65"/>'
            f'</linearGradient>'
        )
    defs += '</defs>'

    svg = defs

    # Grid lines
    if show_grid:
        for i in range(1, 5):
            gy = pt + cH - (cH * i / 4)
            gval = int(mx * i / 4)
            gval_str = (
                f"{gval / 1000000:.1f}M" if gval >= 1000000
                else f"{gval // 1000}k" if gval >= 1000
                else str(gval)
            )
            svg += (
                f'<line x1="{pl}" y1="{gy:.0f}" x2="{w - pr}" y2="{gy:.0f}" '
                f'stroke="#e2e8f0" stroke-width="0.5" stroke-dasharray="3,3"/>'
                f'<text x="{pl - 4}" y="{gy + 3:.0f}" text-anchor="end" '
                f'font-size="6" fill="#94a3b8">{gval_str}</text>'
            )

    # Bars
    for idx, it in enumerate(items):
        bH = max((it["value"] / mx) * cH, 2)
        x = pl + gap + (bW + gap) * idx
        y = pt + cH - bH
        val = it["value"]
        val_str = (
            f"{val / 1000000:.1f}M" if val >= 1000000
            else f"{val // 1000}k" if val >= 1000
            else str(val)
        )
        label = it.get("label", "")

        svg += (
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bW}" height="{bH:.1f}" '
            f'fill="url(#vg{idx})" rx="4" filter="url(#vds)"/>'
        )
        svg += (
            f'<text x="{x + bW / 2:.1f}" y="{y - 5:.1f}" '
            f'text-anchor="middle" font-size="6" font-weight="700" '
            f'fill="#475569">{val_str}</text>'
        )
        svg += (
            f'<text x="{x + bW / 2:.1f}" y="{pt + cH + 14}" '
            f'text-anchor="middle" font-size="5.5" fill="#64748b" '
            f'transform="rotate(50,{x + bW / 2:.1f},{pt + cH + 14})">'
            f'{label}</text>'
        )

    # Bottom axis
    svg += (
        f'<line x1="{pl}" y1="{pt + cH}" x2="{w - pr}" y2="{pt + cH}" '
        f'stroke="#cbd5e1" stroke-width="1"/>'
    )

    return f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}">{svg}</svg>'


def svg_hbars_v2(items, w=500, h=None):
    """Enhanced horizontal bar chart with gradient fills and track bars."""
    if not items:
        return '<div style="text-align:center;color:#94a3b8;padding:20px">No data</div>'

    bH = 16
    gap = 4
    pt, pb, pl, pr = 5, 5, 120, 60
    if h is None:
        h = pt + pb + len(items) * (bH + gap)
    cW = w - pl - pr
    mx = max((i["value"] for i in items), default=1) or 1

    defs = '<defs>'
    for idx, it in enumerate(items):
        c = it.get("color", "#2563eb")
        defs += (
            f'<linearGradient id="hg{idx}" x1="0" y1="0" x2="1" y2="0">'
            f'<stop offset="0%" stop-color="{c}" stop-opacity="0.85"/>'
            f'<stop offset="100%" stop-color="{c}" stop-opacity="1"/>'
            f'</linearGradient>'
        )
    defs += '</defs>'

    svg = defs

    for idx, it in enumerate(items):
        bw = max((it["value"] / mx) * cW, 4)
        y = pt + (bH + gap) * idx
        label = it.get("label", "")[:18]

        # Label
        svg += (
            f'<text x="{pl - 6}" y="{y + bH / 2 + 4:.1f}" '
            f'text-anchor="end" font-size="7.5" fill="#334155">{label}</text>'
        )
        # Track bar (background)
        svg += (
            f'<rect x="{pl}" y="{y}" width="{cW}" height="{bH}" '
            f'fill="#f1f5f9" rx="5"/>'
        )
        # Active bar
        svg += (
            f'<rect x="{pl}" y="{y}" width="{bw:.1f}" height="{bH}" '
            f'fill="url(#hg{idx})" rx="5"/>'
        )
        # Value
        svg += (
            f'<text x="{pl + bw + 5:.1f}" y="{y + bH / 2 + 4:.1f}" '
            f'font-size="7.5" font-weight="700" fill="#1e293b">'
            f'{_fc(it["value"])}</text>'
        )

    return f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}">{svg}</svg>'


def svg_gauge(score, max_score=100, w=160, h=100, label="Risk"):
    """Semicircle gauge chart for risk scores."""
    cx, cy = w / 2, h - 10
    r = min(w / 2 - 10, h - 20)
    pct = min(score / max_score, 1.0)

    # Determine color
    if score >= 70:
        color = '#BD271E'
    elif score >= 40:
        color = '#E7664C'
    elif score >= 20:
        color = '#D6BF57'
    else:
        color = '#6DCCB1'

    # Background arc (180 deg)
    bg_x1 = cx - r
    bg_x2 = cx + r
    bg_path = (
        f'M{bg_x1},{cy} A{r},{r} 0 0,1 {bg_x2},{cy}'
    )

    # Foreground arc
    angle = math.pi * pct
    fg_x = cx - r * math.cos(angle)
    fg_y = cy - r * math.sin(angle)
    la = 1 if pct > 0.5 else 0
    fg_path = (
        f'M{bg_x1},{cy} A{r},{r} 0 {la},1 {fg_x:.1f},{fg_y:.1f}'
    )

    # Needle
    needle_angle = math.pi * (1 - pct)
    nx = cx + (r - 8) * math.cos(needle_angle)
    ny = cy - (r - 8) * math.sin(needle_angle)

    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        f'<defs>'
        f'<linearGradient id="gg" x1="0%" y1="0%" x2="100%" y2="0%">'
        f'<stop offset="0%" stop-color="#6DCCB1"/>'
        f'<stop offset="50%" stop-color="#D6BF57"/>'
        f'<stop offset="100%" stop-color="#BD271E"/>'
        f'</linearGradient>'
        f'</defs>'
        f'<path d="{bg_path}" fill="none" stroke="#e2e8f0" '
        f'stroke-width="10" stroke-linecap="round"/>'
        f'<path d="{fg_path}" fill="none" stroke="{color}" '
        f'stroke-width="10" stroke-linecap="round"/>'
        f'<line x1="{cx}" y1="{cy}" x2="{nx:.1f}" y2="{ny:.1f}" '
        f'stroke="#1e293b" stroke-width="2" stroke-linecap="round"/>'
        f'<circle cx="{cx}" cy="{cy}" r="4" fill="#1e293b"/>'
        f'<text x="{cx}" y="{cy - 14}" text-anchor="middle" '
        f'font-size="18" font-weight="800" fill="{color}">{score}</text>'
        f'<text x="{cx}" y="{h - 1}" text-anchor="middle" '
        f'font-size="8" fill="#64748b">{label}</text>'
        f'</svg>'
    )


def svg_sparkline(points, w=120, h=30, color='#2563eb'):
    """Inline sparkline for trend visualization."""
    if not points or len(points) < 2:
        return ''

    mx = max(points) or 1
    mn = min(points)
    rng = mx - mn or 1
    n = len(points)
    step = w / (n - 1)

    coords = []
    for i, v in enumerate(points):
        x = i * step
        y = h - 4 - ((v - mn) / rng) * (h - 8)
        coords.append(f'{x:.1f},{y:.1f}')

    polyline = ' '.join(coords)
    # Area fill
    area = f'0,{h} ' + polyline + f' {w},{h}'

    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        f'<polygon points="{area}" fill="{color}" opacity="0.1"/>'
        f'<polyline points="{polyline}" fill="none" '
        f'stroke="{color}" stroke-width="1.5" stroke-linecap="round" '
        f'stroke-linejoin="round"/>'
        f'</svg>'
    )


def svg_stacked_bars(agents, w=500, h=180):
    """Stacked bar chart showing severity breakdown per agent."""
    if not agents:
        return '<div style="text-align:center;color:#94a3b8;padding:20px">No data</div>'

    pt, pb, pl, pr = 15, 55, 5, 5
    cW = w - pl - pr
    cH = h - pt - pb
    n = len(agents)
    bW = min(int(cW / max(n, 1)) - 6, 36)
    gap = (cW - bW * n) / (n + 1) if n else 0
    mx = max((a["count"] for a in agents), default=1) or 1

    sev_colors = {
        'critical': '#BD271E',
        'high': '#E7664C',
        'medium': '#D6BF57',
        'low': '#6DCCB1',
    }

    svg = ''

    # Grid
    for i in range(1, 5):
        gy = pt + cH - (cH * i / 4)
        svg += (
            f'<line x1="{pl}" y1="{gy:.0f}" x2="{w - pr}" y2="{gy:.0f}" '
            f'stroke="#e2e8f0" stroke-width="0.5" stroke-dasharray="3,3"/>'
        )

    # Bars
    for idx, a in enumerate(agents):
        x = pl + gap + (bW + gap) * idx
        base_y = pt + cH

        for sev_key in ('low', 'medium', 'high', 'critical'):
            val = a.get(sev_key, 0)
            if val <= 0:
                continue
            seg_h = max((val / mx) * cH, 1)
            base_y -= seg_h
            svg += (
                f'<rect x="{x:.1f}" y="{base_y:.1f}" '
                f'width="{bW}" height="{seg_h:.1f}" '
                f'fill="{sev_colors[sev_key]}" rx="2"/>'
            )

        # Agent label
        name = a.get("name", "")[:12]
        svg += (
            f'<text x="{x + bW / 2:.1f}" y="{pt + cH + 14}" '
            f'text-anchor="middle" font-size="6" fill="#64748b" '
            f'transform="rotate(40,{x + bW / 2:.1f},{pt + cH + 14})">'
            f'{name}</text>'
        )

    # Bottom axis
    svg += (
        f'<line x1="{pl}" y1="{pt + cH}" x2="{w - pr}" y2="{pt + cH}" '
        f'stroke="#cbd5e1" stroke-width="1"/>'
    )

    # Legend
    lx = pl + 10
    ly = h - 10
    for sev, color in [('Critical', '#BD271E'), ('High', '#E7664C'),
                        ('Medium', '#D6BF57'), ('Low', '#6DCCB1')]:
        svg += (
            f'<rect x="{lx}" y="{ly - 6}" width="8" height="8" '
            f'fill="{color}" rx="2"/>'
            f'<text x="{lx + 11}" y="{ly + 1}" font-size="6.5" '
            f'fill="#475569">{sev}</text>'
        )
        lx += 60

    return f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}">{svg}</svg>'


# ── HEATMAP CHART ────────────────────────────────────────────────

def svg_heatmap(data, w=500, h=180):
    """Heatmap grid — rows=days, cols=hours. data=[{day,hour,count}]
    Colors: low=#e2e8f0 → medium=#3b82f6 → high=#dc2626"""
    if not data:
        return '<div style="text-align:center;color:#94a3b8;padding:20px">No heatmap data</div>'
    import math
    days = sorted(set(d["day"] for d in data))
    hours = sorted(set(d["hour"] for d in data))
    if not days or not hours:
        return '<div style="text-align:center;color:#94a3b8;padding:20px">No heatmap data</div>'
    lookup = {(d["day"], d["hour"]): d["count"] for d in data}
    mx = max(d["count"] for d in data) or 1
    cell_w = min(int((w - 80) / max(len(hours), 1)), 20)
    cell_h = min(int((h - 30) / max(len(days), 1)), 18)
    pl = 75

    svg = f'<svg width="{w}" height="{h}" style="font-family:Inter,sans-serif">'
    # Column headers (hours)
    for ci, hr in enumerate(hours):
        x = pl + ci * (cell_w + 1) + cell_w / 2
        svg += f'<text x="{x:.0f}" y="10" text-anchor="middle" font-size="6" fill="#64748b">{hr}</text>'
    # Rows
    for ri, day in enumerate(days):
        y = 18 + ri * (cell_h + 1)
        label = day if len(day) <= 10 else day[:10]
        svg += f'<text x="{pl-4}" y="{y+cell_h/2+3:.0f}" text-anchor="end" font-size="7" fill="#475569">{label}</text>'
        for ci, hr in enumerate(hours):
            x = pl + ci * (cell_w + 1)
            val = lookup.get((day, hr), 0)
            ratio = min(val / mx, 1.0)
            # Color interpolation: low=slate → medium=blue → high=red
            if ratio < 0.5:
                r2 = ratio * 2
                r_c = int(226 + (59 - 226) * r2)
                g_c = int(232 + (130 - 232) * r2)
                b_c = int(240 + (246 - 240) * r2)
            else:
                r2 = (ratio - 0.5) * 2
                r_c = int(59 + (220 - 59) * r2)
                g_c = int(130 + (38 - 130) * r2)
                b_c = int(246 + (38 - 246) * r2)
            color = f'rgb({r_c},{g_c},{b_c})'
            svg += f'<rect x="{x}" y="{y}" width="{cell_w}" height="{cell_h}" fill="{color}" rx="2"/>'
            if val > 0 and cell_w >= 14:
                fc = '#fff' if ratio > 0.4 else '#475569'
                vt = f"{val//1000}k" if val >= 1000 else str(val)
                svg += f'<text x="{x+cell_w/2:.0f}" y="{y+cell_h/2+3:.0f}" text-anchor="middle" font-size="5" fill="{fc}">{vt}</text>'
    # Legend
    ly = h - 12
    svg += f'<text x="{pl}" y="{ly}" font-size="6" fill="#94a3b8">Low</text>'
    for i in range(10):
        ratio = i / 9
        if ratio < 0.5:
            r2 = ratio * 2
            r_c = int(226 + (59 - 226) * r2)
            g_c = int(232 + (130 - 232) * r2)
            b_c = int(240 + (246 - 240) * r2)
        else:
            r2 = (ratio - 0.5) * 2
            r_c = int(59 + (220 - 59) * r2)
            g_c = int(130 + (38 - 130) * r2)
            b_c = int(246 + (38 - 246) * r2)
        svg += f'<rect x="{pl+25+i*12}" y="{ly-8}" width="10" height="8" fill="rgb({r_c},{g_c},{b_c})" rx="1"/>'
    svg += f'<text x="{pl+25+120+4}" y="{ly}" font-size="6" fill="#94a3b8">High</text>'
    svg += '</svg>'
    return svg


# ── GRADIENT AREA CHART ──────────────────────────────────────────

def svg_area_chart(points, w=500, h=140, color='#2563eb', fill_opacity=0.15):
    """Area chart with gradient fill under the line."""
    if not points or len(points) < 2:
        return '<div style="text-align:center;color:#94a3b8;padding:20px">No data</div>'
    import math
    pt, pb, pl, pr = 15, 30, 40, 10
    cW = w - pl - pr
    cH = h - pt - pb
    mx = max(p["value"] for p in points) or 1
    mn = 0
    n = len(points)

    svg = f'<svg width="{w}" height="{h}" style="font-family:Inter,sans-serif">'
    # Gradient def
    svg += f'<defs><linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="{color}" stop-opacity="{fill_opacity*3}"/><stop offset="100%" stop-color="{color}" stop-opacity="0.02"/></linearGradient></defs>'
    # Grid
    for i in range(5):
        gy = pt + cH - (cH * i / 4)
        gv = int(mn + (mx - mn) * i / 4)
        gvs = f"{gv//1000000}M" if gv >= 1000000 else (f"{gv//1000}k" if gv >= 1000 else str(gv))
        svg += f'<line x1="{pl}" y1="{gy:.1f}" x2="{w-pr}" y2="{gy:.1f}" stroke="#e2e8f0" stroke-width="0.5"/>'
        svg += f'<text x="{pl-4}" y="{gy+3:.1f}" text-anchor="end" font-size="6" fill="#94a3b8">{gvs}</text>'
    # Points
    coords = []
    for i, p in enumerate(points):
        x = pl + (cW * i / (n - 1)) if n > 1 else pl + cW / 2
        y = pt + cH - ((p["value"] - mn) / (mx - mn)) * cH if mx > mn else pt + cH / 2
        coords.append((x, y))
    # Area path
    area_path = f'M{coords[0][0]:.1f},{pt+cH}'
    for x, y in coords:
        area_path += f' L{x:.1f},{y:.1f}'
    area_path += f' L{coords[-1][0]:.1f},{pt+cH} Z'
    svg += f'<path d="{area_path}" fill="url(#areaGrad)"/>'
    # Line
    line_path = f'M{coords[0][0]:.1f},{coords[0][1]:.1f}'
    for x, y in coords[1:]:
        line_path += f' L{x:.1f},{y:.1f}'
    svg += f'<path d="{line_path}" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
    # Dots + labels
    for i, (x, y) in enumerate(coords):
        svg += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{color}" stroke="#fff" stroke-width="1.5"/>'
        label = points[i].get("label", "")
        if i % max(1, n // 8) == 0 or i == n - 1:
            svg += f'<text x="{x:.1f}" y="{pt+cH+14}" text-anchor="middle" font-size="6" fill="#94a3b8">{label}</text>'
    svg += '</svg>'
    return svg


# ── TREEMAP CHART ────────────────────────────────────────────────

def svg_treemap(items, w=500, h=200):
    """Treemap — grid layout with severity colors. Uses squarified layout."""
    if not items:
        return '<div style="text-align:center;color:#94a3b8;padding:20px">No data</div>'
    import math

    def _get_color(label):
        if 'L15' in label or 'L14' in label or 'L13' in label:
            return '#BD271E'
        elif 'L12' in label or 'L11' in label or 'L10' in label:
            return '#E7664C'
        elif 'L9' in label or 'L8' in label or 'L7' in label:
            return '#D6BF57'
        return '#6DCCB1'

    sorted_items = sorted(items, key=lambda x: -x["value"])[:12]
    n = len(sorted_items)
    if n == 0:
        return '<div style="text-align:center;color:#94a3b8;padding:20px">No data</div>'

    # Simple grid: calculate cols/rows to fill space
    legend_h = 20
    usable_h = h - legend_h - 4
    usable_w = w - 4
    cols = min(n, 4) if n <= 8 else min(n, 5)
    rows_needed = math.ceil(n / cols)
    cell_w = (usable_w - (cols - 1) * 3) / cols
    cell_h = (usable_h - (rows_needed - 1) * 3) / rows_needed

    svg = f'<svg width="{w}" height="{h}" style="font-family:Inter,sans-serif">'

    for idx, item in enumerate(sorted_items):
        col = idx % cols
        row = idx // cols
        x = 2 + col * (cell_w + 3)
        y = 2 + row * (cell_h + 3)
        color = _get_color(item.get("label", ""))

        svg += f'<rect x="{x:.0f}" y="{y:.0f}" width="{cell_w:.0f}" height="{cell_h:.0f}" fill="{color}" rx="5" opacity="0.9"/>'

        label = item.get("label", "")
        if len(label) > int(cell_w / 5):
            label = label[:int(cell_w / 5)] + ".."
        vt = f"{item['value']//1000000:.1f}M" if item["value"] >= 1000000 else (f"{item['value']//1000}k" if item["value"] >= 1000 else str(item["value"]))

        if cell_w > 40 and cell_h > 20:
            svg += f'<text x="{x+cell_w/2:.0f}" y="{y+cell_h/2-3:.0f}" text-anchor="middle" font-size="7" fill="#fff" font-weight="600">{label}</text>'
            svg += f'<text x="{x+cell_w/2:.0f}" y="{y+cell_h/2+9:.0f}" text-anchor="middle" font-size="6" fill="rgba(255,255,255,0.8)">{vt}</text>'

    # Legend
    ly = h - 8
    lx = 10
    for sev, col in [("Critical", "#BD271E"), ("High", "#E7664C"), ("Medium", "#D6BF57")]:
        svg += f'<rect x="{lx}" y="{ly-6}" width="8" height="8" fill="{col}" rx="2"/>'
        svg += f'<text x="{lx+11}" y="{ly+1}" font-size="6" fill="#475569">{sev}</text>'
        lx += 55

    svg += '</svg>'
    return svg


# ── RADAR CHART ──────────────────────────────────────────────────

def svg_radar(data, w=220, h=220, color='#2563eb'):
    """Radar/spider chart — data=[{label, value}], values normalized to max."""
    if not data or len(data) < 3:
        return '<div style="text-align:center;color:#94a3b8;padding:20px">Need 3+ data points</div>'
    import math
    cx, cy = w / 2, h / 2
    r = min(w, h) / 2 - 25
    n = len(data)
    mx = max(d["value"] for d in data) or 1

    svg = f'<svg width="{w}" height="{h}" style="font-family:Inter,sans-serif">'
    # Grid rings
    for ring in [0.25, 0.5, 0.75, 1.0]:
        pts = []
        for i in range(n):
            angle = (2 * math.pi * i / n) - math.pi / 2
            px = cx + r * ring * math.cos(angle)
            py = cy + r * ring * math.sin(angle)
            pts.append(f'{px:.1f},{py:.1f}')
        svg += f'<polygon points="{" ".join(pts)}" fill="none" stroke="#e2e8f0" stroke-width="0.5"/>'
    # Axis lines
    for i in range(n):
        angle = (2 * math.pi * i / n) - math.pi / 2
        px = cx + r * math.cos(angle)
        py = cy + r * math.sin(angle)
        svg += f'<line x1="{cx}" y1="{cy}" x2="{px:.1f}" y2="{py:.1f}" stroke="#e2e8f0" stroke-width="0.5"/>'
    # Data polygon
    pts = []
    for i, d in enumerate(data):
        ratio = d["value"] / mx
        angle = (2 * math.pi * i / n) - math.pi / 2
        px = cx + r * ratio * math.cos(angle)
        py = cy + r * ratio * math.sin(angle)
        pts.append(f'{px:.1f},{py:.1f}')
    svg += f'<polygon points="{" ".join(pts)}" fill="{color}" fill-opacity="0.2" stroke="{color}" stroke-width="2"/>'
    # Data dots + labels
    for i, d in enumerate(data):
        ratio = d["value"] / mx
        angle = (2 * math.pi * i / n) - math.pi / 2
        px = cx + r * ratio * math.cos(angle)
        py = cy + r * ratio * math.sin(angle)
        svg += f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3" fill="{color}" stroke="#fff" stroke-width="1.5"/>'
        # Label
        lx = cx + (r + 14) * math.cos(angle)
        ly = cy + (r + 14) * math.sin(angle)
        anchor = "middle"
        if math.cos(angle) > 0.3:
            anchor = "start"
        elif math.cos(angle) < -0.3:
            anchor = "end"
        label = d.get("label", "")
        if len(label) > 12:
            label = label[:12] + ".."
        svg += f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" font-size="7" fill="#475569">{label}</text>'
    svg += '</svg>'
    return svg


# ── Simple table builder ─────────────────────────────────────────

def _stbl_v2(items, key, hdr, chdr, color,
             font="8px", max_rows=0):
    """Enhanced simple table with rounded corners.
    max_rows=0 means show all, >0 truncates with '+X more'.
    """
    if not items:
        return (
            '<div style="text-align:center;color:#94a3b8;'
            'font-size:9px;padding:20px">No data</div>'
        )
    total = len(items)
    display = items[:max_rows] if max_rows > 0 else items
    rows = ''
    for i, item in enumerate(display):
        bg = '#fff' if i % 2 == 0 else '#f8fafc'
        rows += (
            f'<tr style="background:{bg}">'
            f'<td style="padding:5px 10px;'
            f'border-bottom:1px solid #e2e8f0;'
            f'font-size:{font}">{item[key]}</td>'
            f'<td style="padding:5px 10px;'
            f'border-bottom:1px solid #e2e8f0;'
            f'text-align:right;font-weight:700;'
            f'font-size:8px;color:{color}">'
            f'{_fc(item["count"])}</td>'
            f'</tr>'
        )
    extra = ''
    remaining = total - len(display)
    if remaining > 0:
        extra = (
            f'<div style="text-align:center;font-size:7px;'
            f'color:#94a3b8;padding:4px">'
            f'+{remaining} more</div>'
        )
    return (
        f'<div class="rtable">'
        f'<table><thead><tr><th>{hdr}</th>'
        f'<th style="text-align:right;padding-right:10px">'
        f'{chdr}</th>'
        f'</tr></thead><tbody>{rows}</tbody></table>'
        f'{extra}</div>'
    )


# ── CSS V2 ───────────────────────────────────────────────────────

CSS_V2 = """
@page { size: A4 portrait; margin: 0; }
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
    font-size: 9px;
    color: #1e293b;
    background: #fff;
}
.page {
    page-break-after: always;
    width: 210mm;
    min-height: 297mm;
    max-height: 297mm;
    padding: 22px 26px 50px;
    position: relative;
    overflow: hidden;
}
.page:last-child { page-break-after: auto; }

.card {
    background: linear-gradient(180deg, #ffffff, #f8fafc);
    border-radius: 12px;
    box-shadow: 0 1px 8px rgba(0,0,0,0.05);
    padding: 16px;
    margin-bottom: 14px;
    border: 1px solid #e2e8f0;
}
.stitle {
    font-size: 12px;
    font-weight: 700;
    color: #1e293b;
    margin: 0 0 12px;
    padding: 7px 0;
    border-bottom: 2px solid #2563eb;
    display: flex;
    align-items: center;
}
.stitle .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 8px;
    flex-shrink: 0;
}
.hdr {
    background: linear-gradient(135deg, #0f172a, #1e293b, #334155);
    color: #fff;
    padding: 14px 22px;
    border-radius: 10px;
    margin-bottom: 16px;
    position: relative;
    overflow: hidden;
}
.hdr::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 0;
    background-image: radial-gradient(circle at 2px 2px, rgba(255,255,255,0.04) 1px, transparent 0);
    background-size: 16px 16px;
}
.hdr h2 {
    font-size: 16px;
    font-weight: 700;
    margin-bottom: 3px;
    position: relative;
}
.hdr p {
    font-size: 8.5px;
    opacity: 0.7;
    position: relative;
}

.rtable {
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid #e2e8f0;
    margin-bottom: 4px;
}
table { width: 100%; border-collapse: collapse; font-size: 8px; }
tr { page-break-inside: avoid; break-inside: avoid; }
td { word-wrap: break-word; overflow-wrap: break-word; max-width: 300px; }
thead { display: table-header-group; }
tbody { display: table-row-group; }
thead th {
    background: linear-gradient(135deg, #0f172a, #1e293b);
    color: #fff;
    padding: 7px 10px;
    text-align: left;
    font-size: 7.5px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
tbody tr:last-child td { border-bottom: none; }
tbody tr:last-child td:first-child { border-radius: 0 0 0 10px; }
tbody tr:last-child td:last-child { border-radius: 0 0 10px 0; }

.footer {
    position: absolute;
    bottom: 14px;
    left: 26px;
    right: 26px;
    display: flex;
    justify-content: space-between;
    font-size: 7px;
    color: #94a3b8;
    border-top: 1px solid #e2e8f0;
    padding-top: 6px;
}

.stat-card {
    flex: 1;
    text-align: center;
    padding: 14px 8px;
    border-radius: 10px;
    position: relative;
    overflow: hidden;
}
.stat-card-flat {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
}
"""


# ── Build stat card ──────────────────────────────────────────────

def _stat_card(label, value, color, icon_name=None, gradient=False):
    """Build a single stat card HTML."""
    if gradient:
        g1, g2 = SEV_GRAD.get(label, (color, color))
        style = (
            f'background:linear-gradient(135deg,{g1},{g2});'
            f'color:#fff;'
        )
        val_color = '#fff'
        lbl_color = 'rgba(255,255,255,0.85)'
    else:
        style = (
            f'background:#f8fafc;'
            f'border:1px solid #e2e8f0;'
        )
        val_color = color
        lbl_color = '#64748b'

    icon_html = ''
    if icon_name:
        ic = '#fff' if gradient else color
        icon_html = (
            f'<div style="margin-bottom:6px">'
            f'{_icon(icon_name, ic, 22)}'
            f'</div>'
        )

    return (
        f'<div style="flex:1;text-align:center;padding:14px 8px;'
        f'border-radius:10px;{style}">'
        f'{icon_html}'
        f'<div style="font-size:24px;font-weight:800;'
        f'color:{val_color}">{_fc(value)}</div>'
        f'<div style="font-size:9px;font-weight:600;'
        f'color:{lbl_color};margin-top:4px">{label}</div>'
        f'</div>'
    )


# ── Page footer ──────────────────────────────────────────────────

_footer_company = "Codesecure Solutions"

def _footer(section_label=''):
    """Render page footer with dynamic company name."""
    return (
        f'<div class="footer">'
        f'<span>{_footer_company} | Confidential</span>'
        f'<span>{section_label}</span>'
        f'</div>'
    )


# ── Main Render Function ────────────────────────────────────────

def render_html_v2(d, sections=None):
    """Render enhanced HTML report with v2 styling."""
    global _footer_company
    _footer_company = d.get("client_name", "Codesecure Solutions")

    ALL = [
        "executive_summary", "top_threats", "agents_risk",
        "authentication", "source_ips", "vulnerability",
        "fim", "mitre", "compliance", "security_events"
    ]
    if not sections:
        sections = ALL

    def has(s):
        return s in sections

    sc = d["severity_counts"]
    pages = []

    # ── Cover Page ───────────────────────────────────────────
    pages.append(_render_cover(d))

    # ── Executive Summary ────────────────────────────────────
    if has("executive_summary"):
        pages.extend(_render_executive_summary(d, sc))

    # ── Top Threats ──────────────────────────────────────────
    if has("top_threats"):
        pages.append(_render_top_threats(d))

    # ── Agents & Risk ────────────────────────────────────────
    if has("agents_risk"):
        pages.extend(_render_agents_risk(d))

    # ── Authentication ───────────────────────────────────────
    if has("authentication"):
        pages.append(_render_authentication(d))

    # ── Source IPs ───────────────────────────────────────────
    if has("source_ips"):
        pages.append(_render_source_ips(d))

    # ── Vulnerability ────────────────────────────────────────
    if has("vulnerability"):
        pages.append(_render_vulnerability(d))

    # ── FIM ──────────────────────────────────────────────────
    if has("fim"):
        pages.append(_render_fim(d))

    # ── MITRE ────────────────────────────────────────────────
    if has("mitre"):
        pages.append(_render_mitre(d))

    # ── Compliance ───────────────────────────────────────────
    if has("compliance"):
        pages.extend(_render_compliance(d))

    # ── Security Events ──────────────────────────────────────
    if has("security_events"):
        pages.extend(_render_security_events(d))

    # ── Custom Widgets ───────────────────────────────────────
    for sec_id in sections:
        if sec_id.startswith("widget_"):
            wid = sec_id.replace("widget_", "")
            widget_html = _render_widget_section_v2(wid, d)
            if widget_html:
                pages.append(widget_html)

    return (
        f'<!DOCTYPE html><html><head>'
        f'<meta charset="UTF-8">'
        f'<title>{d["cover_title"]}</title>'
        f'<style>{CSS_V2}</style>'
        f'</head><body>'
        f'{"".join(pages)}'
        f'</body></html>'
    )


# ── Section Renderers ────────────────────────────────────────────

def _render_cover(d):
    """Render cover page."""
    cco = d.get("cover_color", "#0f172a")
    cac = d.get("cover_accent", "#2563eb")
    title = d.get("cover_title", "Security Threat Analysis Report")
    subtitle = d.get("cover_subtitle", "")
    pla = d.get("period_label", "Last 24 Hours")

    # Split title for two-tone effect
    parts = title.rsplit(" ", 2)
    if len(parts) >= 3:
        t1 = " ".join(parts[:-2])
        t2 = " ".join(parts[-2:])
    else:
        t1 = parts[0]
        t2 = " ".join(parts[1:]) if len(parts) > 1 else "Report"

    logo = ''
    if d.get("client_logo"):
        logo = (
            f'<div style="margin-bottom:40px;display:inline-flex;'
            f'align-items:center;background:rgba(255,255,255,0.95);'
            f'padding:16px 24px;border-radius:10px;'
            f'box-shadow:0 4px 16px rgba(0,0,0,0.2)">'
            f'<img src="{d["client_logo"]}" '
            f'style="height:42px;display:block" '
            f'onerror="this.style.display=\'none\'"/>'
            f'</div>'
        )

    return f'''<div class="page" style="padding:0;overflow:hidden;background:{cco}">
  <!-- Decorative circles -->
  <div style="position:absolute;top:-100px;right:-100px;width:500px;height:500px;
    border-radius:50%;background:linear-gradient(135deg,{cac},#14b8a6);opacity:0.12"></div>
  <div style="position:absolute;bottom:-150px;left:-100px;width:450px;height:450px;
    border-radius:50%;background:linear-gradient(135deg,#14b8a6,{cac});opacity:0.08"></div>
  <!-- Top accent stripe -->
  <div style="height:5px;background:linear-gradient(90deg,{cac},#14b8a6,#2dd4bf)"></div>
  <!-- Dot pattern overlay -->
  <div style="position:absolute;top:0;left:0;right:0;bottom:0;
    background-image:radial-gradient(circle,rgba(255,255,255,0.03) 1px,transparent 1px);
    background-size:20px 20px"></div>

  <div style="position:relative;z-index:1;padding:60px 50px 40px">
    {logo}
    <div style="margin-bottom:50px">
      <div style="font-size:13px;color:{cac};text-transform:uppercase;
        letter-spacing:5px;font-weight:600;margin-bottom:16px">Security Report</div>
      <h1 style="font-size:48px;font-weight:800;color:#fff;
        line-height:1.05;margin-bottom:0">{t1}</h1>
      <h1 style="font-size:48px;font-weight:800;color:{cac};
        line-height:1.05;margin-bottom:18px">{t2}</h1>
      <div style="width:60px;height:4px;background:linear-gradient(90deg,{cac},#14b8a6);
        border-radius:2px"></div>
    </div>

    <p style="font-size:13px;color:rgba(255,255,255,0.4);
      letter-spacing:1px;margin-bottom:40px">
      {subtitle} &bull; {pla}
    </p>

    <!-- Info boxes -->
    <div style="display:flex;gap:0;margin-bottom:40px;
      background:rgba(0,0,0,0.25);border-radius:10px;overflow:hidden;
      border:1px solid rgba(255,255,255,0.06)">
      <div style="flex:1;padding:20px 24px;border-left:3px solid {cac}">
        <div style="font-size:8px;text-transform:uppercase;letter-spacing:2px;
          color:rgba(255,255,255,0.35);margin-bottom:8px">Prepared For</div>
        <div style="font-size:15px;font-weight:700;color:#fff;
          margin-bottom:4px">{d["client_name"]}</div>
        <div style="font-size:10px;color:rgba(255,255,255,0.45);
          line-height:1.4">{d["client_address"]}</div>
      </div>
      <div style="flex:1;padding:20px 24px;
        border-left:1px solid rgba(255,255,255,0.06)">
        <div style="font-size:8px;text-transform:uppercase;letter-spacing:2px;
          color:rgba(255,255,255,0.35);margin-bottom:8px">Period</div>
        <div style="font-size:11px;font-weight:600;color:#fff;
          margin-bottom:4px">{d["from_date"]}</div>
        <div style="font-size:11px;font-weight:600;color:#fff">
          {d["to_date"]}</div>
      </div>
      <div style="flex:1;padding:20px 24px;
        border-left:1px solid rgba(255,255,255,0.06)">
        <div style="font-size:8px;text-transform:uppercase;letter-spacing:2px;
          color:rgba(255,255,255,0.35);margin-bottom:8px">Generated</div>
        <div style="font-size:11px;font-weight:600;color:#fff;
          margin-bottom:4px">{d["ist_date"]}</div>
        <div style="font-size:11px;color:rgba(255,255,255,0.45)">
          {d["ist_time"]} IST</div>
      </div>
    </div>
  </div>

  <!-- Bottom accent -->
  <div style="position:absolute;bottom:0;left:0;right:0;height:4px;
    background:linear-gradient(90deg,{cac},#14b8a6,#2dd4bf)"></div>
</div>'''


def _render_executive_summary(d, sc):
    """Render executive summary page."""
    pla = d.get("period_label", "Last 24 Hours")
    is_daily = d.get("period") == "24h"

    # Severity definition
    sev_def = [
        {"key": "Critical", "color": "#BD271E", "range": "Level 15+", "icon": "alert"},
        {"key": "High",     "color": "#E7664C", "range": "Level 12-14", "icon": "shield"},
        {"key": "Medium",   "color": "#D6BF57", "range": "Level 7-11", "icon": "chart"},
        {"key": "Low",      "color": "#6DCCB1", "range": "Level 0-6", "icon": "check"},
    ]

    # Stat cards with gradients
    stat_cards = ''
    for s in sev_def:
        stat_cards += _stat_card(
            s["key"], sc[s["key"]], s["color"],
            icon_name=s["icon"], gradient=True
        )

    # Donut chart
    donut_data = [
        {"value": sc[s["key"]], "color": s["color"]}
        for s in sev_def
    ]
    donut = svg_donut_v2(donut_data, 200, 200, 78, 48)

    # Donut legend
    donut_leg = ''
    for s in sev_def:
        donut_leg += (
            f'<div style="display:flex;align-items:center;margin:5px 0">'
            f'<div style="width:14px;height:14px;border-radius:4px;'
            f'background:{s["color"]};margin-right:10px"></div>'
            f'<div>'
            f'<div style="font-size:10px;font-weight:700">{s["key"]}</div>'
            f'<div style="font-size:8px;color:#94a3b8">'
            f'{s["range"]}: {_fc(sc[s["key"]])}</div>'
            f'</div></div>'
        )

    # Timeline chart — use area chart for v2
    if is_daily:
        tl_points = [{"value": t["count"], "label": t["hour"]} for t in d["timeline"]]
        tl_svg = svg_area_chart(tl_points, 500, 150, color='#2563eb') if tl_points else '<div style="text-align:center;color:#94a3b8;padding:20px">No timeline data</div>'
        tl_label = "Alerts Timeline (24h)"
        # Also build heatmap data for hourly view
        heatmap_data = [{"day": "Today", "hour": t["hour"], "count": t["count"]} for t in d["timeline"]]
    else:
        trend = d.get("daily_trend", [])
        if trend:
            chart_w = 680 if d.get("period") == "30d" else 500
            tl_points = [{"value": t["total"], "label": t["day"]} for t in trend]
            tl_svg = svg_area_chart(tl_points, chart_w, 160, color='#2563eb')
        else:
            tl_svg = '<div style="text-align:center;color:#94a3b8;padding:20px">No timeline data</div>'
        tl_label = "Daily Alert Trend"
        heatmap_data = []

    # Treemap for top rules — only Medium/High/Critical (skip Low level 0-6)
    sorted_for_treemap = sorted(
        [r for r in d.get("top_rules", []) if r.get("level", 0) >= 7],
        key=lambda x: (-x.get("level", 0), -x.get("count", 0))
    )
    treemap_items = [{"value": r["count"], "label": f'L{r.get("level",0)} {r.get("description", r.get("rule_id", ""))[:18]}'} for r in sorted_for_treemap[:15]]
    treemap_svg = svg_treemap(treemap_items, 500, 200) if treemap_items else '<div style="text-align:center;color:#94a3b8;padding:20px;font-size:9px">No Medium/High/Critical rules in this period</div>'

    # Radar for agent risk profile
    radar_items = [{"value": a.get("score", 0), "label": a["name"][:12]} for a in d.get("agent_risk", [])[:8]]
    radar_svg = svg_radar(radar_items, 240, 240, '#7c3aed') if len(radar_items) >= 3 else ""

    # Period comparison
    ps = d["prev_severity"]
    dod = ''
    for k in ("Critical", "High", "Medium", "Low"):
        tv, pv = sc[k], ps[k]
        diff = tv - pv
        pct = f"{(diff / pv * 100):.1f}" if pv > 0 else "N/A"
        arrow = "\u25B2" if diff > 0 else ("\u25BC" if diff < 0 else "\u25CF")
        cl = "#ef4444" if diff > 0 else ("#22c55e" if diff < 0 else "#94a3b8")
        dod += (
            f'<div style="flex:1;text-align:center;padding:10px;'
            f'border-radius:8px;background:#f8fafc;border:1px solid #e2e8f0">'
            f'<div style="font-size:8px;color:#64748b;margin-bottom:4px">{k}</div>'
            f'<div style="font-size:13px;font-weight:700;color:{cl}">'
            f'{arrow} {pct}{"%" if pct != "N/A" else ""}</div>'
            f'<div style="font-size:7px;color:#94a3b8;margin-top:3px">'
            f'{_fc(pv)} &rarr; {_fc(tv)}</div>'
            f'</div>'
        )

    # Total change
    td = d["total_alerts"] - d["prev_total"]
    tp = f"{(td / d['prev_total'] * 100):.1f}" if d["prev_total"] > 0 else "N/A"
    ta = "\u25B2" if td > 0 else ("\u25BC" if td < 0 else "\u25CF")
    tc = "#ef4444" if td > 0 else ("#22c55e" if td < 0 else "#94a3b8")
    dod += (
        f'<div style="flex:1;text-align:center;padding:10px;'
        f'border-radius:8px;background:#f8fafc;border:1px solid #e2e8f0">'
        f'<div style="font-size:8px;color:#64748b;margin-bottom:4px">Total</div>'
        f'<div style="font-size:13px;font-weight:700;color:{tc}">'
        f'{ta} {tp}{"%" if tp != "N/A" else ""}</div>'
        f'<div style="font-size:7px;color:#94a3b8;margin-top:3px">'
        f'{_fc(d["prev_total"])} &rarr; {_fc(d["total_alerts"])}</div>'
        f'</div>'
    )

    # Active agents count — from inventory system index (all enrolled, not just active)
    try:
        client = opensearch_client.get_client()
        idx_prefix = config.OPENSEARCH_INDEX.split('-')[0]
        agent_r = client.search(index=f"{idx_prefix}-states-inventory-system-*",
            body={"size": 0, "aggs": {"unique": {"cardinality": {"field": "agent.name"}}}})
        agent_count = agent_r["aggregations"]["unique"]["value"]
    except:
        agent_count = len(d.get("top_agents", []))
    gauge = f'<div style="text-align:center;padding:12px"><div style="font-size:42px;font-weight:800;color:#2563eb">{agent_count}</div><div style="font-size:10px;color:#64748b;margin-top:4px">Active Agents</div></div>'

    # Executive text
    ta0 = d["top_agents"][0] if d["top_agents"] else {"name": "N/A", "count": 0}
    vuln_text = (
        f'Vulnerability detection identified <strong>{_fc(d["vuln_total"])} '
        f'vulnerability events</strong>.'
        if d["vuln_total"] > 0
        else 'No vulnerability events detected.'
    )

    # Page 1: Summary + comparison + stat cards
    page1 = f'''<div class="page">
  <div class="hdr">
    <h2>Executive Summary</h2>
    <p>{pla} alert overview</p>
  </div>

  <!-- Summary text -->
  <div class="card" style="background:linear-gradient(135deg,#f0f9ff,#e0f2fe);
    border-left:4px solid #2563eb;margin-bottom:12px">
    <div style="font-size:9px;line-height:1.7;color:#334155">
      During the reporting period <strong>{d["from_date"]}</strong> to
      <strong>{d["to_date"]}</strong>, a total of
      <strong>{_fc(d["total_alerts"])}</strong> security alerts were recorded.
      Of these, <strong style="color:#BD271E">{_fc(sc["Critical"])} critical</strong>
      and <strong style="color:#E7664C">{_fc(sc["High"])} high</strong> severity
      alerts (level 12+: {_fc(d["level12_count"])}) require attention.
      There were <strong style="color:#ef4444">{_fc(d["auth_fail_count"])}
      authentication failures</strong> and
      <strong style="color:#22c55e">{_fc(d["auth_success_count"])}
      successful logons</strong>.
      {vuln_text}
      Top agent: <strong>{ta0["name"]}</strong> with {_fc(ta0["count"])} alerts.
      MITRE ATT&amp;CK: <strong>{len(d["mitre_techniques"])} techniques</strong>
      across <strong>{len(d["mitre_tactics"])} tactics</strong>.
    </div>
  </div>

  <!-- Period comparison -->
  <div class="card" style="margin-bottom:12px;padding:10px 16px">
    <div class="stitle" style="margin-bottom:8px">
      <span class="dot" style="background:#7c3aed"></span>Period Comparison
    </div>
    <div style="display:flex;gap:8px">{dod}</div>
  </div>

  <!-- Severity stat cards + gauge -->
  <div style="display:flex;gap:8px;margin-bottom:12px;align-items:center">
    {stat_cards}
    <div style="flex:0 0 auto;text-align:center;padding:4px 8px;
      border-radius:10px;background:#f8fafc;border:1px solid #e2e8f0">
      {gauge}
    </div>
  </div>

  <!-- Donut + Legend -->
  <div class="card">
    <div class="stitle"><span class="dot"></span>Severity Distribution</div>
    <div style="display:flex;align-items:center;justify-content:center;gap:24px">
      {donut}
      <div>{donut_leg}</div>
    </div>
  </div>

  {_footer("Executive Summary")}
</div>'''

    # Heatmap (hourly activity)
    heatmap_svg = ''
    if is_daily and d["timeline"]:
        heatmap_data = [
            {"day": "Today", "hour": t["hour"], "count": t["count"]}
            for t in d["timeline"]
        ]
        heatmap_svg = f'''
  <div class="card">
    <div class="stitle">
      <span class="dot" style="background:#7c3aed"></span>
      Alert Activity Heatmap
    </div>
    <div style="text-align:center">
      {svg_heatmap(heatmap_data, 600, 80)}
    </div>
  </div>'''
    elif not is_daily and d.get("daily_trend"):
        # Build heatmap: rows=days, cols=severity levels
        heatmap_data = []
        for t in d.get("daily_trend", []):
            day_label = t.get("day", "")[:10]
            for sev_key, sev_label in [
                ("critical", "Critical"), ("high", "High"),
                ("medium", "Medium"), ("low", "Low")
            ]:
                val = t.get(sev_key, 0)
                if val > 0:
                    heatmap_data.append({
                        "day": day_label,
                        "hour": sev_label,
                        "count": val
                    })
        n_days = len(d.get("daily_trend", []))
        hm_h = max(60, n_days * 18 + 30)
        if heatmap_data:
            heatmap_svg = f'''
  <div class="card">
    <div class="stitle">
      <span class="dot" style="background:#7c3aed"></span>
      Daily Severity Heatmap
    </div>
    <div style="text-align:center">
      {svg_heatmap(heatmap_data, 400, hm_h)}
    </div>
  </div>'''

    # Page 2: Timeline chart + heatmap
    page2 = f'''<div class="page">
  <div class="hdr">
    <h2>Alert Trends</h2>
    <p>{pla} timeline analysis</p>
  </div>

  <div class="card">
    <div class="stitle"><span class="dot"></span>{tl_label}</div>
    <div style="text-align:center">{tl_svg}</div>
  </div>

  {heatmap_svg}

  {_footer("Alert Trends")}
</div>'''

    # Page 3: Additional charts (treemap + radar) — stacked vertically
    extra_charts = []
    if treemap_svg or radar_svg:
        treemap_section = f'''<div class="card">
    <div class="stitle"><span class="dot" style="background:#0d9488"></span>Alert Rule Distribution</div>
    <p style="font-size:8px;color:#94a3b8;margin:-6px 0 10px 16px">Top rules sized by event count, sorted by severity level (highest first)</p>
    <div style="text-align:center">{treemap_svg}</div>
  </div>''' if treemap_svg else ''

        radar_section = f'''<div class="card">
    <div class="stitle"><span class="dot" style="background:#7c3aed"></span>Agent Risk Profile</div>
    <p style="font-size:8px;color:#94a3b8;margin:-6px 0 10px 16px">Risk score distribution across monitored agents (0-100 scale)</p>
    <div style="text-align:center">{radar_svg}</div>
  </div>''' if radar_svg else ''

        page3 = f'''<div class="page">
  <div class="hdr">
    <h2>{_icon("chart","#fff")} Advanced Analytics</h2>
    <p>{pla} advanced visualizations</p>
  </div>
  {treemap_section}
  {radar_section}
  {_footer("Analytics")}
</div>'''
        extra_charts.append(page3)

    return [page1, page2] + extra_charts


def _render_top_threats(d):
    """Render top threats page."""
    if d["incident_count"] > 0 and d["incidents"]:
        max_inc = 15
        display_inc = d["incidents"][:max_inc]
        rows = ''
        for i, inc in enumerate(display_inc):
            bg = '#fff' if i % 2 == 0 else '#f8fafc'
            lvl_color = '#BD271E' if inc["level"] >= 15 else '#E7664C'
            rows += (
                f'<tr style="background:{bg};'
                f'border-left:3px solid {lvl_color}">'
                f'<td style="padding:6px 8px;border-bottom:1px solid #e2e8f0;'
                f'text-align:center">'
                f'<span style="background:linear-gradient(135deg,{lvl_color},'
                f'{lvl_color}dd);color:#fff;padding:2px 8px;border-radius:6px;'
                f'font-size:8px;font-weight:700">{inc["level"]}</span></td>'
                f'<td style="padding:6px 8px;border-bottom:1px solid #e2e8f0;'
                f'font-size:8px">{inc["description"]}</td>'
                f'<td style="padding:6px 8px;border-bottom:1px solid #e2e8f0;'
                f'text-align:center;font-size:9px;font-weight:700;'
                f'color:#BD271E">{_fc(inc["count"])}</td>'
                f'<td style="padding:6px 8px;border-bottom:1px solid #e2e8f0;'
                f'font-size:8px">{inc["agents"]}</td>'
                f'<td style="padding:6px 8px;border-bottom:1px solid #e2e8f0;'
                f'font-size:7px">{inc["last_seen"]}</td>'
                f'</tr>'
            )

        threats_html = f'''
  <div style="background:linear-gradient(135deg,#fef2f2,#fee2e2);
    border:2px solid #BD271E;border-radius:10px;padding:16px;margin-bottom:14px">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
      <div style="width:30px;height:30px;background:linear-gradient(135deg,#BD271E,#920000);
        border-radius:50%;display:flex;align-items:center;justify-content:center;
        font-size:14px;color:#fff;font-weight:800">!</div>
      <div style="font-size:13px;font-weight:700;color:#BD271E">
        HIGH SEVERITY THREATS DETECTED</div>
    </div>
    <div style="font-size:9px;color:#64748b">
      Events with severity level 12+ may indicate active threats or critical changes.
    </div>
  </div>
  <div style="border-radius:10px;overflow:hidden;border:1px solid #e2e8f0">
  <table>
    <thead><tr>
      <th style="width:40px;border-radius:8px 0 0 0">Level</th>
      <th>Description</th>
      <th style="width:55px;text-align:center">Count</th>
      <th style="width:120px">Affected Agents</th>
      <th style="width:100px;border-radius:0 8px 0 0">Last Seen (IST)</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
  </div>
  {"" if len(d["incidents"]) <= max_inc else f'<div style="text-align:center;font-size:7px;color:#94a3b8;padding:4px">+{len(d["incidents"]) - max_inc} more</div>'}'''
    else:
        threats_html = '''
  <div style="text-align:center;padding:70px 20px">
    <div style="width:64px;height:64px;background:#f0fdf4;border-radius:50%;
      display:inline-flex;align-items:center;justify-content:center;margin-bottom:16px">
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none"
        stroke="#22c55e" stroke-width="2">
        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
        <polyline points="22 4 12 14.01 9 11.01"/>
      </svg>
    </div>
    <div style="font-size:16px;font-weight:700;color:#1e293b;margin-bottom:6px">
      No Top Threats Found</div>
    <div style="font-size:10px;color:#64748b;max-width:400px;margin:0 auto">
      No alerts with severity level 12 or above were detected.</div>
  </div>'''

    subtitle = (
        f'{d["incident_count"]} critical/high severity events'
        if d["incident_count"] > 0
        else 'No high severity threats detected'
    )

    return f'''<div class="page">
  <div class="hdr" style="background:linear-gradient(135deg,#BD271E,#7f1d1d)">
    <h2>Top Threat Alerts</h2>
    <p>{subtitle}</p>
  </div>
  {threats_html}
  {_footer("Top Threats")}
</div>'''


def _render_agents_risk(d):
    """Render agents & risk assessment page."""
    # Agent bar chart
    ag_items = [
        {"value": a["count"], "label": a["name"], "color": PALETTE_V2[i % 24]}
        for i, a in enumerate(d["top_agents"])
    ]
    ag_svg = svg_hbars_v2(ag_items, 500) if ag_items else ""

    # Stacked bar
    stacked = svg_stacked_bars(d["top_agents"][:12], 500, 180)

    # Agent risk table (limit to 12 rows max)
    max_ar = 12
    display_ar = d["agent_risk"][:max_ar]
    ar_rows = ''
    for i, a in enumerate(display_ar):
        bg = '#fff' if i % 2 == 0 else '#f8fafc'
        rc = _rc(a["risk"])
        ar_rows += (
            f'<tr style="background:{bg};border-left:3px solid {rc}">'
            f'<td style="padding:5px 8px;border-bottom:1px solid #e2e8f0;'
            f'font-size:8px;font-weight:600">{a["name"]}</td>'
            f'<td style="padding:5px 8px;border-bottom:1px solid #e2e8f0;'
            f'text-align:center;font-size:8px">{_fc(a["count"])}</td>'
            f'<td style="padding:5px 8px;border-bottom:1px solid #e2e8f0;'
            f'text-align:center;font-size:8px;font-weight:700;'
            f'color:#BD271E">{a["critical"] or "-"}</td>'
            f'<td style="padding:5px 8px;border-bottom:1px solid #e2e8f0;'
            f'text-align:center;font-size:8px;font-weight:700;'
            f'color:#E7664C">{a["high"] or "-"}</td>'
            f'<td style="padding:5px 8px;border-bottom:1px solid #e2e8f0;'
            f'text-align:center;font-size:8px;'
            f'color:#D6BF57">{_fc(a["medium"]) if a["medium"] > 0 else "-"}</td>'
            f'<td style="padding:5px 8px;border-bottom:1px solid #e2e8f0;'
            f'text-align:center">'
            f'<div style="background:#e2e8f0;border-radius:8px;height:12px;'
            f'overflow:hidden;width:50px;display:inline-block">'
            f'<div style="background:linear-gradient(90deg,{rc},{rc}cc);'
            f'height:100%;width:{a["score"]}%;border-radius:8px"></div></div>'
            f'<span style="font-size:7px;font-weight:700;color:{rc};'
            f'margin-left:3px">{a["score"]}</span></td>'
            f'<td style="padding:5px 8px;border-bottom:1px solid #e2e8f0;'
            f'text-align:center">'
            f'<span style="background:linear-gradient(135deg,{rc},{rc}cc);'
            f'color:#fff;padding:2px 8px;border-radius:8px;font-size:7px;'
            f'font-weight:700">{a["risk"]}</span></td>'
            f'<td style="padding:5px 8px;border-bottom:1px solid #e2e8f0;'
            f'font-size:7px;color:#64748b;font-style:italic">{a["note"]}</td>'
            f'</tr>'
        )

    # Recommendations
    recs_html = ''
    for r in d["recommendations"]:
        recs_html += (
            f'<div style="display:flex;align-items:flex-start;margin-bottom:8px;'
            f'padding:10px 14px;border-radius:8px;'
            f'background:linear-gradient(135deg,#f8fafc,#f1f5f9);'
            f'border-left:3px solid {r["color"]}">'
            f'<div style="width:26px;height:26px;border-radius:50%;'
            f'background:linear-gradient(135deg,{r["color"]},{r["color"]}cc);'
            f'color:#fff;display:flex;align-items:center;justify-content:center;'
            f'font-size:9px;font-weight:700;flex-shrink:0;margin-right:12px">'
            f'{r["icon"]}</div>'
            f'<div style="font-size:9px;line-height:1.6;color:#334155">'
            f'{r["text"]}</div>'
            f'</div>'
        )

    # Page 1: Charts
    page1 = f'''<div class="page">
  <div class="hdr">
    <h2>Agents &amp; Risk Assessment</h2>
    <p>Agent overview and severity breakdown</p>
  </div>

  <div class="card">
    <div class="stitle">
      <span class="dot" style="background:#059669"></span>
      Top {len(d["top_agents"])} Agents (Alert Volume)
    </div>
    <div style="text-align:center">{ag_svg}</div>
  </div>

  <div class="card">
    <div class="stitle">
      <span class="dot" style="background:#d97706"></span>
      Severity Breakdown by Agent
    </div>
    <div style="text-align:center">{stacked}</div>
  </div>

  {_footer("Agents")}
</div>'''

    # Page 2: Risk table + recommendations
    page2 = f'''<div class="page">
  <div class="hdr">
    <h2>Agent Risk Scores &amp; Recommendations</h2>
    <p>Risk scoring and actionable recommendations</p>
  </div>

  <div class="card">
    <div class="stitle">
      <span class="dot" style="background:#dc2626"></span>
      Agent Risk Scores
    </div>
    <div class="rtable"><table><thead><tr>
      <th>Agent</th>
      <th style="text-align:center">Total</th>
      <th style="text-align:center;color:#fca5a5">Crit</th>
      <th style="text-align:center;color:#fed7aa">High</th>
      <th style="text-align:center;color:#fde68a">Med</th>
      <th style="text-align:center">Score</th>
      <th style="text-align:center">Risk</th>
      <th>Action</th>
    </tr></thead><tbody>{ar_rows}</tbody></table></div>
  </div>

  <div class="card">
    <div class="stitle">
      <span class="dot" style="background:#f59e0b"></span>
      Recommendations
    </div>
    {recs_html}
  </div>

  {_footer("Risk Assessment")}
</div>'''

    return [page1, page2]


def _render_authentication(d):
    """Render authentication events page."""
    is_daily = d.get("period") == "24h"

    # Auth daily trend
    auth_daily_svg = ''
    if not is_daily and d.get("auth_fail_daily"):
        items = [
            {"value": t["count"], "label": t["day"], "color": "#ef4444"}
            for t in d["auth_fail_daily"]
        ]
        auth_daily_svg = f'''
  <div class="card">
    <div class="stitle">
      <span class="dot" style="background:#ef4444"></span>
      Auth Failures - Daily Trend
    </div>
    <div style="text-align:center">{svg_vbars_v2(items, 500, 110)}</div>
  </div>'''

    return f'''<div class="page">
  <div class="hdr">
    <h2>Authentication Events</h2>
    <p>Login success and failure analysis</p>
  </div>

  <!-- Stat cards -->
  <div style="display:flex;gap:10px;margin-bottom:14px">
    <div style="flex:1;text-align:center;padding:18px;border-radius:10px;
      background:linear-gradient(135deg,#fef2f2,#fee2e2);
      border:1px solid #fecaca">
      <div style="margin-bottom:6px">{_icon("lock", "#ef4444", 24)}</div>
      <div style="font-size:28px;font-weight:800;color:#ef4444">
        {_fc(d["auth_fail_count"])}</div>
      <div style="font-size:9px;color:#64748b;margin-top:4px">
        Authentication Failures</div>
    </div>
    <div style="flex:1;text-align:center;padding:18px;border-radius:10px;
      background:linear-gradient(135deg,#f0fdf4,#dcfce7);
      border:1px solid #bbf7d0">
      <div style="margin-bottom:6px">{_icon("unlock", "#22c55e", 24)}</div>
      <div style="font-size:28px;font-weight:800;color:#22c55e">
        {_fc(d["auth_success_count"])}</div>
      <div style="font-size:9px;color:#64748b;margin-top:4px">
        Successful Logons</div>
    </div>
    <div style="flex:1;text-align:center;padding:18px;border-radius:10px;
      background:linear-gradient(135deg,#eff6ff,#dbeafe);
      border:1px solid #bfdbfe">
      <div style="margin-bottom:6px">{_icon("users", "#2563eb", 24)}</div>
      <div style="font-size:28px;font-weight:800;color:#2563eb">
        {_fc(d["auth_fail_count"] + d["auth_success_count"])}</div>
      <div style="font-size:9px;color:#64748b;margin-top:4px">
        Total Auth Events</div>
    </div>
  </div>

  <!-- Users & IPs tables -->
  <div style="display:flex;gap:12px;margin-bottom:12px">
    <div class="card" style="flex:1">
      <div class="stitle">
        <span class="dot" style="background:#ef4444"></span>
        Top Failed Login Users
      </div>
      {_stbl_v2(d["auth_fail_users"], "user", "User", "Failures", "#ef4444", max_rows=8)}
    </div>
    <div class="card" style="flex:1">
      <div class="stitle">
        <span class="dot" style="background:#f97316"></span>
        Top Source IPs (Failed)
      </div>
      {_stbl_v2(d["auth_fail_ips"], "ip", "IP Address", "Attempts", "#f97316", max_rows=8)}
    </div>
  </div>

  <div class="card">
    <div class="stitle">
      <span class="dot" style="background:#22c55e"></span>
      Successful Logon Users
    </div>
    {_stbl_v2(d["auth_success_users"], "user", "User", "Logons", "#22c55e", max_rows=8)}
  </div>

  <!-- Event tables -->
  <div style="display:flex;gap:12px;margin-bottom:12px">
    <div class="card" style="flex:1">
      <div class="stitle">
        <span class="dot" style="background:#ef4444"></span>
        Top Failed Login Events
      </div>
      {_stbl_v2(d["auth_fail_events"], "desc", "Rule Description", "Count", "#ef4444", font="7.5px", max_rows=8)}
    </div>
    <div class="card" style="flex:1">
      <div class="stitle">
        <span class="dot" style="background:#22c55e"></span>
        Top Success Login Events
      </div>
      {_stbl_v2(d["auth_success_events"], "desc", "Rule Description", "Count", "#22c55e", font="7.5px", max_rows=8)}
    </div>
  </div>

  {auth_daily_svg}
  {_footer("Authentication")}
</div>'''


def _render_source_ips(d):
    """Render source IPs page."""
    if not d["top_srcips"]:
        srcip_html = (
            '<div style="text-align:center;color:#94a3b8;'
            'font-size:9px;padding:20px">No source IP data</div>'
        )
    else:
        max_ips = 15
        display_ips = d["top_srcips"][:max_ips]
        mx_ip = display_ips[0]["count"]
        rows = ''
        for i, ip in enumerate(display_ips):
            bg = '#fff' if i % 2 == 0 else '#f8fafc'
            is_priv = ip["ip"].startswith(("192.168.", "10.", "172.", "fe80"))
            if is_priv:
                tag = (
                    '<span style="background:linear-gradient(135deg,#eff6ff,#dbeafe);'
                    'color:#2563eb;padding:2px 6px;border-radius:4px;'
                    'font-size:7px;font-weight:600">INTERNAL</span>'
                )
                bar_c = '#2563eb'
            else:
                tag = (
                    '<span style="background:linear-gradient(135deg,#fef2f2,#fee2e2);'
                    'color:#ef4444;padding:2px 6px;border-radius:4px;'
                    'font-size:7px;font-weight:600">EXTERNAL</span>'
                )
                bar_c = '#ef4444'
            pct = round(ip["count"] / mx_ip * 100)
            rows += (
                f'<tr style="background:{bg}">'
                f'<td style="padding:6px 8px;border-bottom:1px solid #e2e8f0;'
                f'font-size:8px;text-align:center;font-weight:700;'
                f'color:#94a3b8">{i + 1}</td>'
                f'<td style="padding:6px 8px;border-bottom:1px solid #e2e8f0;'
                f'font-size:9px;font-family:monospace;font-weight:600">'
                f'{ip["ip"]} {tag}</td>'
                f'<td style="padding:6px 8px;border-bottom:1px solid #e2e8f0;'
                f'text-align:right;font-weight:700;font-size:9px">'
                f'{_fc(ip["count"])}</td>'
                f'<td style="padding:6px 8px;border-bottom:1px solid #e2e8f0">'
                f'<div style="background:#e2e8f0;border-radius:5px;height:14px;'
                f'overflow:hidden">'
                f'<div style="background:linear-gradient(90deg,{bar_c},{bar_c}bb);'
                f'height:100%;width:{pct}%;border-radius:5px;min-width:3px">'
                f'</div></div></td>'
                f'</tr>'
            )

        srcip_html = f'''
  <div class="rtable"><table><thead><tr>
    <th style="width:30px">#</th>
    <th>IP Address</th>
    <th style="text-align:right;width:80px">Events</th>
    <th style="width:200px">Activity</th>
  </tr></thead><tbody>{rows}</tbody></table></div>
  {"" if len(d["top_srcips"]) <= max_ips else f'<div style="text-align:center;font-size:7px;color:#94a3b8;padding:4px">+{len(d["top_srcips"]) - max_ips} more</div>'}
  <div style="margin-top:12px;display:flex;gap:16px;font-size:8px;color:#64748b">
    <div><span style="display:inline-block;width:10px;height:10px;
      background:#2563eb;border-radius:3px;vertical-align:middle;
      margin-right:4px"></span>Internal</div>
    <div><span style="display:inline-block;width:10px;height:10px;
      background:#ef4444;border-radius:3px;vertical-align:middle;
      margin-right:4px"></span>External</div>
  </div>'''

    return f'''<div class="page">
  <div class="hdr">
    <h2>Top Source IPs</h2>
    <p>Most active source IP addresses</p>
  </div>
  {srcip_html}
  {_footer("Source IPs")}
</div>'''


def _render_vulnerability(d):
    """Render vulnerability detection page."""
    # Severity cards
    vsev = ''
    if d["vuln_total"] > 0 and d["vuln_by_sev"]:
        vc_map = {
            "Critical": "#BD271E", "High": "#E7664C",
            "Medium": "#D6BF57", "Low": "#6DCCB1"
        }
        items = ''
        for v in d["vuln_by_sev"]:
            vc = vc_map.get(v["severity"], "#94a3b8")
            items += (
                f'<div style="flex:1;text-align:center;padding:14px;'
                f'border-radius:10px;border:1px solid #e2e8f0;'
                f'background:linear-gradient(135deg,#f8fafc,#fff)">'
                f'<div style="font-size:22px;font-weight:800;'
                f'color:{vc}">{_fc(v["count"])}</div>'
                f'<div style="font-size:9px;color:#64748b;margin-top:4px">'
                f'{v["severity"]}</div>'
                f'</div>'
            )
        vsev = f'<div style="display:flex;gap:8px;margin-bottom:14px">{items}</div>'

    return f'''<div class="page">
  <div class="hdr" style="background:linear-gradient(135deg,#7c3aed,#4c1d95)">
    <h2>Vulnerability Detection</h2>
    <p>Vulnerability alerts (rule.groups: vulnerability-detector)</p>
  </div>

  {vsev}

  <div style="display:flex;gap:12px;margin-bottom:12px">
    <div class="card" style="flex:1">
      <div class="stitle">
        <span class="dot" style="background:#ef4444"></span>Top CVEs
      </div>
      {_stbl_v2(d["vuln_top_cve"], "cve", "CVE ID", "Count", "#ef4444", max_rows=10)}
    </div>
    <div class="card" style="flex:1">
      <div class="stitle">
        <span class="dot" style="background:#2563eb"></span>Affected Agents
      </div>
      {_stbl_v2(d["vuln_top_agent"], "agent", "Agent", "Vulns", "#2563eb", max_rows=10)}
    </div>
  </div>

  <div class="card">
    <div class="stitle">
      <span class="dot" style="background:#7c3aed"></span>Affected Packages
    </div>
    {_stbl_v2(d["vuln_top_pkg"], "pkg", "Package", "Count", "#7c3aed", max_rows=10)}
  </div>

  {_footer("Vulnerability")}
</div>'''


def _render_fim(d):
    """Render file integrity monitoring page."""
    is_daily = d.get("period") == "24h"

    # FIM stat cards
    event_colors = {
        "deleted": ("#ef4444", "#fef2f2", "#fecaca"),
        "added": ("#22c55e", "#f0fdf4", "#bbf7d0"),
        "modified": ("#f97316", "#fff7ed", "#fed7aa"),
    }
    fim_cards = (
        f'<div style="flex:1;text-align:center;padding:16px;border-radius:10px;'
        f'background:linear-gradient(135deg,#eff6ff,#dbeafe);'
        f'border:1px solid #bfdbfe">'
        f'<div style="font-size:28px;font-weight:800;color:#2563eb">'
        f'{_fc(d["fim_total"])}</div>'
        f'<div style="font-size:9px;color:#64748b;margin-top:4px">'
        f'Total FIM Events</div>'
        f'</div>'
    )
    for e in d["fim_events"]:
        ec, bg, bd = event_colors.get(e["event"], ("#2563eb", "#eff6ff", "#bfdbfe"))
        fim_cards += (
            f'<div style="flex:1;text-align:center;padding:16px;border-radius:10px;'
            f'background:linear-gradient(135deg,{bg},#fff);border:1px solid {bd}">'
            f'<div style="font-size:28px;font-weight:800;color:{ec}">'
            f'{_fc(e["count"])}</div>'
            f'<div style="font-size:9px;color:#64748b;margin-top:4px">'
            f'{e["event"].capitalize()}</div>'
            f'</div>'
        )

    # FIM daily trend
    fim_daily_svg = ''
    if not is_daily and d.get("fim_daily"):
        items = [
            {"value": t["count"], "label": t["day"], "color": "#7c3aed"}
            for t in d["fim_daily"]
        ]
        fim_daily_svg = f'''
  <div class="card">
    <div class="stitle">
      <span class="dot" style="background:#7c3aed"></span>
      File Changes - Daily Trend
    </div>
    <div style="text-align:center">{svg_vbars_v2(items, 500, 110)}</div>
  </div>'''

    return f'''<div class="page">
  <div class="hdr" style="background:linear-gradient(135deg,#9333ea,#581c87)">
    <h2>File Integrity Monitoring</h2>
    <p>File changes detected (rule.groups: syscheck)</p>
  </div>

  <div style="display:flex;gap:10px;margin-bottom:14px">{fim_cards}</div>

  <div style="display:flex;gap:12px;margin-bottom:12px">
    <div class="card" style="flex:1">
      <div class="stitle">
        <span class="dot" style="background:#2563eb"></span>Top Agents (FIM)
      </div>
      {_stbl_v2(d["fim_agents"], "agent", "Agent", "Changes", "#2563eb", max_rows=8)}
    </div>
    <div class="card" style="flex:1">
      <div class="stitle">
        <span class="dot" style="background:#f97316"></span>Top Modified Paths
      </div>
      {_stbl_v2(d["fim_paths"], "path", "File Path", "Count", "#f97316", font="7px", max_rows=8)}
    </div>
  </div>

  {fim_daily_svg}
  {_footer("File Integrity")}
</div>'''


def _render_mitre(d):
    """Render MITRE ATT&CK analysis page."""
    tech_items = [
        {"value": m["count"], "label": m["technique"], "color": PALETTE_V2[i % 24]}
        for i, m in enumerate(d["mitre_techniques"][:15])
    ]
    tech_svg = (
        svg_hbars_v2(tech_items, 500)
        if tech_items
        else '<div style="text-align:center;color:#94a3b8;padding:20px">No MITRE data</div>'
    )

    tac_items = [
        {"value": m["count"], "label": m["tactic"], "color": PALETTE_V2[i % 24]}
        for i, m in enumerate(d["mitre_tactics"][:12])
    ]
    tac_svg = svg_hbars_v2(tac_items, 500) if tac_items else ""

    return f'''<div class="page">
  <div class="hdr" style="background:linear-gradient(135deg,#0891b2,#164e63)">
    <h2>MITRE ATT&amp;CK Analysis</h2>
    <p>Techniques and tactics detected</p>
  </div>

  <div class="card">
    <div class="stitle">
      <span class="dot" style="background:#ef4444"></span>Top Techniques
    </div>
    <div style="text-align:center">{tech_svg}</div>
  </div>

  <div class="card">
    <div class="stitle">
      <span class="dot" style="background:#f97316"></span>Top Tactics
    </div>
    <div style="text-align:center">{tac_svg}</div>
  </div>

  {_footer("MITRE ATT&CK")}
</div>'''


def _render_compliance(d):
    """Render compliance mapping page."""
    c = d.get("compliance", {})

    fw_info = [
        ("pci",   "PCI-DSS",     "#2563eb", "#eff6ff", "#bfdbfe"),
        ("hipaa", "HIPAA",        "#059669", "#f0fdf4", "#bbf7d0"),
        ("gdpr",  "GDPR",         "#d97706", "#fffbeb", "#fde68a"),
        ("nist",  "NIST 800-53",  "#7c3aed", "#f5f3ff", "#ddd6fe"),
        ("tsc",   "TSC",          "#e11d48", "#fff1f2", "#fecdd3"),
    ]

    # Framework stat cards
    comp_cards = ''
    for k, nm, cl, bg, bd in fw_info:
        total = c.get(k, {}).get("total", 0)
        comp_cards += (
            f'<div style="flex:1;min-width:100px;text-align:center;padding:14px;'
            f'border-radius:10px;background:linear-gradient(135deg,{bg},#fff);'
            f'border:1px solid {bd}">'
            f'<div style="font-size:22px;font-weight:800;color:{cl}">'
            f'{_fc(total)}</div>'
            f'<div style="font-size:8px;color:#64748b;margin-top:4px;'
            f'font-weight:600">{nm}</div>'
            f'</div>'
        )

    def fw_tbl(k, nm, cl, col="Control", max_rows=10):
        ctrls = c.get(k, {}).get("controls", [])
        if not ctrls:
            return (
                f'<div style="text-align:center;color:#94a3b8;'
                f'font-size:9px;padding:12px">No {nm} data</div>'
            )
        display = ctrls[:max_rows]
        rows = ''
        for i, ct in enumerate(display):
            bg = '#fff' if i % 2 == 0 else '#f8fafc'
            rows += (
                f'<tr style="background:{bg}">'
                f'<td style="padding:3px 8px;border-bottom:1px solid #e2e8f0;'
                f'font-size:7.5px;font-family:monospace">{ct["control"]}</td>'
                f'<td style="padding:3px 8px;border-bottom:1px solid #e2e8f0;'
                f'text-align:right;font-weight:700;font-size:7.5px">'
                f'{_fc(ct["count"])}</td>'
                f'</tr>'
            )
        extra = ''
        if len(ctrls) > max_rows:
            extra = (
                f'<div style="text-align:center;font-size:7px;color:#94a3b8;'
                f'padding:4px">+{len(ctrls) - max_rows} more</div>'
            )
        return (
            f'<div class="rtable">'
            f'<table><thead><tr><th>{col}</th>'
            f'<th style="text-align:right">Alerts</th>'
            f'</tr></thead><tbody>{rows}</tbody></table>'
            f'</div>{extra}'
        )

    tsc_sec = ''
    if c.get("tsc", {}).get("total", 0) > 0:
        tsc_sec = f'''
  <div class="card">
    <div class="stitle">
      <span class="dot" style="background:#e11d48"></span>
      TSC (Trust Services Criteria)
    </div>
    {fw_tbl("tsc", "TSC", "#e11d48", "Criteria")}
  </div>'''

    # Page 1: Stats + PCI + HIPAA
    page1 = f'''<div class="page">
  <div class="hdr" style="background:linear-gradient(135deg,#e11d48,#881337)">
    <h2>Regulatory Compliance Mapping</h2>
    <p>Alerts mapped to compliance frameworks</p>
  </div>

  <div style="display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap">
    {comp_cards}
  </div>

  <div style="display:flex;gap:10px;margin-bottom:10px">
    <div class="card" style="flex:1">
      <div class="stitle">
        <span class="dot" style="background:#2563eb"></span>PCI-DSS Controls
      </div>
      {fw_tbl("pci", "PCI-DSS", "#2563eb")}
    </div>
    <div class="card" style="flex:1">
      <div class="stitle">
        <span class="dot" style="background:#059669"></span>HIPAA Controls
      </div>
      {fw_tbl("hipaa", "HIPAA", "#059669")}
    </div>
  </div>

  {_footer("Compliance")}
</div>'''

    # Page 2: GDPR + NIST + TSC
    page2 = f'''<div class="page">
  <div class="hdr">
    <h2>Compliance Frameworks (cont.)</h2>
    <p>GDPR, NIST 800-53, and TSC mappings</p>
  </div>

  <div style="display:flex;gap:10px;margin-bottom:10px">
    <div class="card" style="flex:1">
      <div class="stitle">
        <span class="dot" style="background:#d97706"></span>GDPR Articles
      </div>
      {fw_tbl("gdpr", "GDPR", "#d97706", "Article")}
    </div>
    <div class="card" style="flex:1">
      <div class="stitle">
        <span class="dot" style="background:#7c3aed"></span>NIST 800-53 Controls
      </div>
      {fw_tbl("nist", "NIST 800-53", "#7c3aed")}
    </div>
  </div>

  {tsc_sec}
  {_footer("Compliance (cont.)")}
</div>'''

    return [page1, page2]


def _render_security_events(d):
    """Render security events pages. Returns a list of page HTML strings."""
    sr = sorted(d["top_rules"], key=lambda x: (-x["level"], -x["count"]))
    pp = 40

    the_head = '''<thead><tr>
    <th style="width:25px;text-align:center">#</th>
    <th style="width:50px;text-align:center">Rule ID</th>
    <th>Description</th>
    <th style="width:42px;text-align:center">Level</th>
    <th style="width:65px;text-align:right;padding-right:10px">Count</th>
  </tr></thead>'''

    def mkr(r, i, off):
        sn = off + i + 1
        lc = _sc(r["level"])
        bg = '#fff' if i % 2 == 0 else '#f8fafc'
        desc = r["description"][:90]
        if len(r["description"]) > 90:
            desc += "..."
        return (
            f'<tr style="background:{bg};border-left:3px solid {lc}">'
            f'<td style="padding:4px 6px;border-bottom:1px solid #e2e8f0;'
            f'text-align:center;font-weight:600;color:#94a3b8;'
            f'font-size:7px">{sn}</td>'
            f'<td style="padding:4px 6px;border-bottom:1px solid #e2e8f0;'
            f'text-align:center;font-weight:700;color:#1e293b;'
            f'font-size:8px">{r["rule_id"]}</td>'
            f'<td style="padding:4px 6px;border-bottom:1px solid #e2e8f0;'
            f'font-size:7.5px;color:#334155">{desc}</td>'
            f'<td style="padding:5px 8px;border-bottom:1px solid #e2e8f0;'
            f'text-align:center">'
            f'<span style="background:linear-gradient(135deg,{lc},{lc}cc);'
            f'color:#fff;padding:2px 8px;border-radius:8px;font-size:7px;'
            f'font-weight:700">{r["level"]}</span></td>'
            f'<td style="padding:4px 6px;border-bottom:1px solid #e2e8f0;'
            f'text-align:right;font-weight:700;color:#1e293b;'
            f'font-size:8px">{_fc(r["count"])}</td>'
            f'</tr>'
        )

    rp1 = "".join(mkr(r, i, 0) for i, r in enumerate(sr[:pp]))
    pages = []

    pages.append(f'''<div style="page-break-before:always" class="page">
  <div class="hdr" style="background:linear-gradient(135deg,#1e293b,#0f172a)">
    <h2>Security Events Summary</h2>
    <p>All rules sorted by severity &bull; {len(sr)} unique rules</p>
  </div>
  <div class="card" style="padding:0;overflow:hidden;border-radius:10px">
    <table>{the_head}<tbody>{rp1}</tbody></table>
  </div>
  {_footer("Security Events")}
</div>''')

    if len(sr) > pp:
        rp2 = "".join(mkr(r, i, pp) for i, r in enumerate(sr[pp:pp * 2]))
        pages.append(f'''<div style="page-break-before:always" class="page">
  <div class="card" style="padding:0;overflow:hidden;border-radius:10px">
    <table>{the_head}<tbody>{rp2}</tbody></table>
  </div>
  {_footer("Security Events (cont.)")}
</div>''')

    return pages


def _render_widget_section_v2(widget_id, d):
    """Render a custom widget section with v2 styling."""
    try:
        widgets = database.get_widgets()
        w = next((x for x in widgets if x["id"] == widget_id), None)
        if not w:
            return None

        cfg = json.loads(w["agg_config"]) if isinstance(w["agg_config"], str) else w["agg_config"]
        query_dsl = json.loads(w["query_dsl"]) if isinstance(w["query_dsl"], str) else w["query_dsl"]

        field = cfg.get("field", "rule.level")
        size = cfg.get("size", 10)
        color = cfg.get("color", "#2563eb")
        chart_type = cfg.get("chart_type", "bar")
        time_from = cfg.get("time_from", f"now-{d.get('period', '24h')}")

        # Build query
        must = [{"range": {"timestamp": {"gte": time_from, "lte": "now"}}}]
        if query_dsl and isinstance(query_dsl, dict) and query_dsl.get("bool"):
            must.extend(query_dsl["bool"].get("must", []))

        aggs = {
            "result": {
                "terms": {"field": field, "size": size, "order": {"_count": "desc"}}
            }
        }
        result = opensearch_client.run_aggregation({"bool": {"must": must}}, aggs)
        buckets = result["aggregations"]["result"]["buckets"]

        if not buckets:
            return f'''<div class="page">
  <div class="hdr"><h2>{w["name"]}</h2>
    <p>{w.get("description", "Custom analysis")}</p></div>
  <div style="text-align:center;color:#94a3b8;padding:40px">
    No data for this widget</div>
  {_footer(w["name"])}
</div>'''

        items = [
            {"value": b["doc_count"], "label": str(b["key"]), "color": color}
            for b in buckets
        ]

        # Chart
        if chart_type in ("horizontalBar", "bar"):
            if chart_type == "horizontalBar":
                chart_svg = svg_hbars_v2(items, 500)
            else:
                chart_svg = svg_vbars_v2(items, 500, 180)
        elif chart_type in ("doughnut", "pie"):
            donut_items = [
                {"value": it["value"], "color": PALETTE_V2[idx % 24]}
                for idx, it in enumerate(items)
            ]
            chart_svg = svg_donut_v2(donut_items, 200, 200, 80, 50)
        else:
            chart_svg = svg_vbars_v2(items, 500, 180)

        # Data table
        rows = ''
        for i, it in enumerate(items):
            bg = '#fff' if i % 2 == 0 else '#f8fafc'
            rows += (
                f'<tr style="background:{bg}">'
                f'<td style="padding:5px 10px;border-bottom:1px solid #e2e8f0;'
                f'font-size:8px">{it["label"]}</td>'
                f'<td style="padding:5px 10px;border-bottom:1px solid #e2e8f0;'
                f'text-align:right;font-weight:700;font-size:8px;'
                f'color:{color}">{_fc(it["value"])}</td>'
                f'</tr>'
            )
        table_html = (
            f'<div class="rtable">'
            f'<table><thead><tr><th>{field}</th>'
            f'<th style="text-align:right">Count</th>'
            f'</tr></thead><tbody>{rows}</tbody></table>'
            f'</div>'
        )

        total_events = _fc(result["hits"]["total"]["value"])

        return f'''<div class="page">
  <div class="hdr" style="background:linear-gradient(135deg,{color},#0f172a)">
    <h2>{w["name"]}</h2>
    <p>{w.get("description", "Custom analysis")} &bull; {total_events} total events</p>
  </div>
  <div class="card">
    <div class="stitle">
      <span class="dot" style="background:{color}"></span>{w["name"]}
    </div>
    <div style="text-align:center">{chart_svg}</div>
  </div>
  <div class="card">
    <div class="stitle">
      <span class="dot" style="background:{color}"></span>Data Table
    </div>
    {table_html}
  </div>
  {_footer(w["name"])}
</div>'''

    except Exception as e:
        return f'''<div class="page">
  <div class="hdr"><h2>Widget Error</h2></div>
  <div class="card"><p style="color:#ef4444">{str(e)}</p></div>
</div>'''


# ── Public API ───────────────────────────────────────────────────

async def generate_report_v2(template_id, period="24h"):
    """Generate a v2-styled PDF report from a template."""
    template = database.get_template(template_id)
    if not template:
        return None, "Template not found"
    try:
        query = build_query(period)
        client = opensearch_client.get_client()
        raw = client.search(index=config.OPENSEARCH_INDEX, body=query)
        data = process_data(raw, template, period)

        secs = template.get("sections", [])
        if isinstance(secs, str):
            secs = json.loads(secs)

        html = render_html_v2(data, secs if secs else None)
        pdf_bytes, err = await _html_to_pdf(html)
        if err:
            return None, err

        fname = (
            f"report_v2_{template['name'].replace(' ', '_')}_"
            f"{datetime.now(IST).strftime('%Y%m%d_%H%M')}.pdf"
        )
        fpath = os.path.join(config.REPORTS_DIR, fname)
        os.makedirs(config.REPORTS_DIR, exist_ok=True)
        with open(fpath, "wb") as f:
            f.write(pdf_bytes)

        rid = database.save_report(
            template_id, fname,
            data["from_date"], data["to_date"],
            len(pdf_bytes)
        )
        return {"id": rid, "filename": fname, "size": len(pdf_bytes)}, None

    except Exception as e:
        return None, str(e)


async def generate_quick_report_v2(period="24h"):
    """Generate a v2-styled quick PDF report with all sections."""
    try:
        # Use first template's company info for quick report
        templates = database.get_templates()
        tcfg = templates[0] if templates else None
        query = build_query(period)
        client = opensearch_client.get_client()
        raw = client.search(index=config.OPENSEARCH_INDEX, body=query)
        data = process_data(raw, template_cfg=tcfg, period=period)

        html = render_html_v2(data)
        pdf_bytes, err = await _html_to_pdf(html)
        if err:
            return None, err

        fname = f"quick_report_v2_{datetime.now(IST).strftime('%Y%m%d_%H%M')}.pdf"
        fpath = os.path.join(config.REPORTS_DIR, fname)
        os.makedirs(config.REPORTS_DIR, exist_ok=True)
        with open(fpath, "wb") as f:
            f.write(pdf_bytes)

        rid = database.save_report(
            None, fname,
            data["from_date"], data["to_date"],
            len(pdf_bytes)
        )
        return {"id": rid, "filename": fname, "size": len(pdf_bytes)}, None

    except Exception as e:
        return None, str(e)
