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
      <div id="widget-preview-${w.id}" class="mb-3" style="height:120px;background:#f9fafb;border-radius:8px;display:flex;align-items:center;justify-content:center">
        <canvas id="wcanvas-${w.id}" width="300" height="120"></canvas>
      </div>
      <div class="flex gap-2">
        <button onclick="previewWidget('${w.id}')" class="btn btn-outline flex-1 text-xs">Preview</button>
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
    const chartType = cfg.chart_type || w.chart_type || 'bar';

    const query = typeof w.query_dsl === 'string' ? JSON.parse(w.query_dsl) : (w.query_dsl||{});
    const body = {group_by: field, time_from: timeFrom, size: size};
    if (query && Object.keys(query).length > 0) body.query = query;

    const data = await fetch(API+'/aggregate', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json());
    if (!data.data || data.data.length === 0) return;

    const canvas = document.getElementById('wcanvas-'+wid);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    const COLORS = [color, '#3498db','#e74c3c','#9b59b6','#e67e22','#2ecc71','#f39c12','#1abc9c'];
    const labels = data.data.map(d=>d.label);
    const values = data.data.map(d=>d.value);

    const isPie = chartType === 'doughnut' || chartType === 'pie' || chartType === 'polarArea';
    new Chart(ctx, {
      type: isPie ? chartType : (chartType === 'horizontalBar' ? 'bar' : (chartType === 'gradient' ? 'line' : chartType)),
      data: {
        labels: labels,
        datasets: [{
          data: values,
          backgroundColor: isPie ? COLORS.slice(0, values.length) : color,
          borderColor: isPie ? '#fff' : color,
          borderWidth: isPie ? 2 : 0,
          borderRadius: 4,
          tension: 0.3,
          fill: chartType === 'gradient',
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        indexAxis: chartType === 'horizontalBar' ? 'y' : 'x',
        plugins: {legend:{display:isPie,position:'right',labels:{font:{size:8},boxWidth:8}},datalabels:{display:false}},
        scales: isPie ? {} : {x:{display:false},y:{display:false}}
      }
    });
  } catch(e) { /* silent */ }
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
