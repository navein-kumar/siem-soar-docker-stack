// ============================================================
// WIDGETS.JS - Auto-generated from index.html
// ============================================================

// WIDGETS MANAGEMENT
async function loadWidgets() {
  const r = await fetch(API+'/widgets').then(r=>r.json());
  const c = document.getElementById('widgets-gallery');
  if (!r.widgets || r.widgets.length === 0) {
    c.innerHTML = '<div class="text-center text-gray-400 py-12 col-span-3">No saved widgets. Go to Query Builder to create one.</div>';
    return;
  }
  c.innerHTML = r.widgets.map(w => {
    const cfg = typeof w.agg_config === 'string' ? JSON.parse(w.agg_config) : (w.agg_config||{});
    const color = cfg.color || '#0D7377';
    const chartType = cfg.chart_type || w.chart_type || 'bar';
    const field = cfg.field || '';
    return `<div class="card p-4">
      <div class="flex items-center gap-2 mb-2">
        <div style="width:12px;height:12px;border-radius:3px;background:${color}"></div>
        <h3 class="font-bold text-sm">${w.name}</h3>
      </div>
      <p class="text-xs text-gray-500 mb-1">${w.description||''}</p>
      <div class="text-xs text-gray-400 mb-3">Type: ${chartType} | Field: ${field}</div>
      <div id="widget-preview-${w.id}" class="mb-3" style="height:100px;background:#f9fafb;border-radius:8px;display:flex;align-items:center;justify-content:center;overflow:hidden">
        <div class="text-xs text-gray-300">Loading...</div>
      </div>
      <div class="flex gap-2">
        <button onclick="editWidgetInQuery('${w.id}')" class="btn btn-outline flex-1 text-xs">Open in Query</button>
        <button data-delete-widget="${w.id}" class="btn text-xs" style="border:1px solid #e74c3c;color:#e74c3c">Delete</button>
      </div>
    </div>`;
  }).join('');

  // Bind delete buttons
  c.querySelectorAll('[data-delete-widget]').forEach(btn => {
    btn.addEventListener('click', async function() {
      const wid = this.getAttribute('data-delete-widget');
      await fetch(API+'/widgets/'+wid, {method:'DELETE'});
      loadWidgets();
    });
  });

  // Auto-preview each widget
  r.widgets.forEach(w => previewWidget(w.id));
}

async function previewWidget(wid) {
  try {
    const r = await fetch(API+'/widgets').then(r=>r.json());
    const w = r.widgets.find(x => x.id === wid);
    if (!w) return;
    const cfg = typeof w.agg_config === 'string' ? JSON.parse(w.agg_config) : (w.agg_config||{});
    const field = cfg.field || '';
    const size = cfg.size || 10;
    const timeFrom = cfg.time_from || 'now-24h';
    const color = cfg.color || '#0D7377';

    const query = typeof w.query_dsl === 'string' ? JSON.parse(w.query_dsl) : (w.query_dsl||{});
    const body = {group_by: field, time_from: timeFrom, size: size};
    if (query && Object.keys(query).length > 0) body.query = query;

    const data = await fetch(API+'/aggregate', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json());

    const container = document.getElementById('widget-preview-'+wid);
    if (!container) return;

    if (!data.data || data.data.length === 0) {
      container.innerHTML = '<div class="text-xs text-gray-400">No data</div>';
      return;
    }

    // Render SVG mini bar chart
    const items = data.data.slice(0, 8);
    const maxVal = Math.max(...items.map(d=>d.value)) || 1;
    const w2 = 280, h2 = 90;
    const barW = Math.floor((w2 - 10) / items.length) - 2;

    let svg = '<svg width="'+w2+'" height="'+h2+'" style="font-family:Inter,sans-serif">';
    items.forEach((d, i) => {
      const barH = Math.max(3, Math.round((d.value / maxVal) * (h2 - 20)));
      const x = 5 + i * (barW + 2);
      const y = h2 - 14 - barH;
      svg += '<rect x="'+x+'" y="'+y+'" width="'+barW+'" height="'+barH+'" fill="'+color+'" rx="2" opacity="0.85"/>';
      svg += '<text x="'+(x+barW/2)+'" y="'+(h2-3)+'" text-anchor="middle" font-size="6" fill="#999">'+(d.label.length>6?d.label.substring(0,6)+'..':d.label)+'</text>';
      svg += '<text x="'+(x+barW/2)+'" y="'+(y-2)+'" text-anchor="middle" font-size="5" fill="#666">'+(d.value>=1000000?(d.value/1000000).toFixed(1)+'M':(d.value>=1000?(d.value/1000).toFixed(0)+'k':d.value))+'</text>';
    });
    svg += '<text x="'+w2/2+'" y="10" text-anchor="middle" font-size="7" fill="#999">'+data.total.toLocaleString()+' total</text>';
    svg += '</svg>';
    container.innerHTML = svg;
  } catch(e) { console.log('Widget preview error:', wid, e); }
}

async function editWidgetInQuery(wid) {
  try {
    const r = await fetch(API+'/widgets').then(r=>r.json());
    const w = r.widgets.find(x=>x.id===wid);
    if (!w) return;
    const agg = typeof w.agg_config === 'string' ? JSON.parse(w.agg_config) : w.agg_config;
    showTab('query');
    document.getElementById('agg-field').value = agg.field || agg.group_by || '';
    document.getElementById('chart-type').value = agg.chart_type || 'bar';
    document.getElementById('agg-size').value = agg.size || 10;
    document.getElementById('widget-name').value = w.name || '';
    if (agg.color) { chartColor = agg.color; }
    runAggregation();
  } catch(e) { toast('Error loading widget','red'); }
}

async function deleteWidget(wid) {
  if (!confirm('Delete this widget?')) return;
  await fetch(API+'/widgets/'+wid, {method:'DELETE'});
  loadWidgets();
  toast('Widget deleted','green');
}
