// ============================================================
// QUERY.JS - Auto-generated from index.html
// ============================================================

// FILTER BUILDER
let filters = [];

function addFilter() {
  const id = Date.now();
  filters.push({id, field:'', op:'is', value:''});
  renderFilters();
}

function removeFilter(id) {
  filters = filters.filter(f=>f.id!==id);
  renderFilters();
}

function renderFilters() {
  const c = document.getElementById('filters-container');
  if (filters.length === 0) { c.innerHTML = '<div class="text-xs text-gray-400 text-center py-3">No filters — showing all alerts</div>'; return; }
  c.innerHTML = filters.map((f,i) => `
    <div class="filter-row">
      ${i>0?'<select class="w-16" onchange="filters[${i}].logic=this.value"><option>AND</option><option>OR</option></select>':''}
      <select class="flex-1" onchange="filters[${i}].field=this.value;loadFieldValues(${i})">
        <option value="">Field...</option>
        ${allFields.map(af=>`<option value="${af.field}" ${af.field===f.field?'selected':''}>${af.field}</option>`).join('')}
      </select>
      <select class="w-24" onchange="filters[${i}].op=this.value">
        <option value="is" ${f.op==='is'?'selected':''}>is</option>
        <option value="is_not" ${f.op==='is_not'?'selected':''}>is not</option>
        <option value="gt" ${f.op==='gt'?'selected':''}>></option>
        <option value="gte" ${f.op==='gte'?'selected':''}>>=</option>
        <option value="lt" ${f.op==='lt'?'selected':''}><</option>
        <option value="lte" ${f.op==='lte'?'selected':''}><=</option>
        <option value="exists" ${f.op==='exists'?'selected':''}>exists</option>
        <option value="contains" ${f.op==='contains'?'selected':''}>contains</option>
      </select>
      <input type="text" class="flex-1" placeholder="Value..." value="${f.value||''}" onchange="filters[${i}].value=this.value" list="vals-${i}">
      <datalist id="vals-${i}"></datalist>
      <button onclick="removeFilter(${f.id})" class="text-red-500 hover:text-red-700 font-bold">✕</button>
    </div>
  `).join('');
}

async function loadFieldValues(idx) {
  const f = filters[idx];
  if (!f.field) return;
  try {
    const r = await fetch(API+'/fields/'+encodeURIComponent(f.field)+'/values?size=20').then(r=>r.json());
    const dl = document.getElementById('vals-'+idx);
    if (dl) dl.innerHTML = r.values.map(v=>`<option value="${v}">`).join('');
  } catch(e) {}
}

function buildQuery() {
  if (filters.length === 0) return null;
  const musts = [], mustNots = [];
  for (const f of filters) {
    if (!f.field || !f.value && f.op!=='exists') continue;
    if (f.op === 'is') musts.push({term:{[f.field]:f.value}});
    else if (f.op === 'is_not') mustNots.push({term:{[f.field]:f.value}});
    else if (f.op === 'gt') musts.push({range:{[f.field]:{gt:f.value}}});
    else if (f.op === 'gte') musts.push({range:{[f.field]:{gte:f.value}}});
    else if (f.op === 'lt') musts.push({range:{[f.field]:{lt:f.value}}});
    else if (f.op === 'lte') musts.push({range:{[f.field]:{lte:f.value}}});
    else if (f.op === 'exists') musts.push({exists:{field:f.field}});
    else if (f.op === 'contains') musts.push({wildcard:{[f.field]:'*'+f.value+'*'}});
  }
  const q = {bool:{}};
  if (musts.length) q.bool.must = musts;
  if (mustNots.length) q.bool.must_not = mustNots;
  return Object.keys(q.bool).length ? q : null;
}

function clearFilters() { filters = []; renderFilters(); }

// QUERY EXECUTION
async function runCurrentQuery() {
  const result = document.getElementById('query-result');
  result.innerHTML = '<div class="loader"></div>';
  try {
    const q = buildQuery();
    const timeFrom = document.getElementById('time-from').value;
    const r = await fetch(API+'/query', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({query:q, time_from:timeFrom})
    }).then(r=>r.json());
    result.innerHTML = `<span class="font-bold text-teal-700">${r.total.toLocaleString()}</span> matching alerts <span class="text-xs text-gray-400">(${r.took_ms}ms)</span>`;
  } catch(e) {
    result.innerHTML = '<span class="text-red-500">Error: '+e.message+'</span>';
  }
}

// AGGREGATION + CHARTS
function populateFieldSelects() {
  const s = document.getElementById('agg-field');
  const popular = ['agent.name','rule.level','rule.description','rule.id','rule.groups','rule.mitre.technique','rule.mitre.tactic',
    'data.win.eventdata.targetUserName','data.win.eventdata.ipAddress','rule.pci_dss','rule.hipaa','rule.gdpr','rule.nist_800_53'];
  let html = '<option value="">Select field...</option>';
  html += '<optgroup label="Popular Fields">';
  popular.forEach(f => { if (allFields.find(af=>af.field===f)) html += `<option value="${f}">${f}</option>`; });
  html += '</optgroup><optgroup label="All Fields">';
  allFields.forEach(f => html += `<option value="${f.field}">${f.field} (${f.type})</option>`);
  html += '</optgroup>';
  s.innerHTML = html;
}

async function runAggregation() {
  const field = document.getElementById('agg-field').value;
  if (!field) return;
  const chartType = document.getElementById('chart-type').value;
  const size = parseInt(document.getElementById('agg-size').value) || 10;
  const timeFrom = document.getElementById('time-from').value;

  document.getElementById('chart-loader').classList.remove('hidden');
  try {
    const q = buildQuery();
    const r = await fetch(API+'/aggregate', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({query:q, group_by:field, size:size, time_from:timeFrom})
    }).then(r=>r.json());

    document.getElementById('chart-title').textContent = `${field} (${r.total.toLocaleString()} total)`;

    if (chartType === 'table') {
      renderTable(r.data, field);
    } else {
      renderChart(r.data, chartType, field);
    }
  } catch(e) {
    toast('Error: '+e.message, 'red');
  }
  document.getElementById('chart-loader').classList.add('hidden');
}

const COLORS = ['#0D7377','#14919B','#BD271E','#E7664C','#D6BF57','#6DCCB1','#3498db','#9b59b6','#e67e22','#2ecc71','#1abc9c','#e74c3c','#f39c12','#8e44ad','#2c3e50','#1B2A4A','#c0392b','#27ae60','#2980b9','#f1c40f'];

function renderChart(data, type, field) {
  window._lastChartData = data;
  document.getElementById('chart-container').classList.remove('hidden');
  document.getElementById('table-container').classList.add('hidden');
  if (currentChart) currentChart.destroy();
  const ctx = document.getElementById('mainChart').getContext('2d');
  const labels = data.map(d=>d.label);
  const values = data.map(d=>d.value);
  const isHorizontal = type === 'horizontalBar';
  const isGradient = type === 'gradient';
  let actualType = type;
  if (isHorizontal) actualType = 'bar';
  if (isGradient) actualType = 'line';

  let datasets, opts = {};

  if (type==='polarArea' || type==='radar') {
    datasets = [{label:field, data:values, backgroundColor:COLORS.slice(0,data.length).map(c=>c+'CC'), borderColor:COLORS.slice(0,data.length), borderWidth:2, pointBackgroundColor:COLORS.slice(0,data.length)}];
    opts = {plugins:{legend:{display:true,position:'right',labels:{font:{size:11},padding:12,usePointStyle:true}}}};
    if (type==='radar') opts.scales = {r:{angleLines:{color:'#e5e7eb'},grid:{color:'#e5e7eb'},ticks:{font:{size:9}}}};
  } else if (type==='doughnut'||type==='pie') {
    datasets = [{data:values, backgroundColor:COLORS.slice(0,data.length), borderColor:'#fff', borderWidth:3, hoverOffset:8}];
    opts = {cutout:type==='doughnut'?'55%':0, plugins:{legend:{display:true,position:'right',labels:{font:{size:11},padding:12,usePointStyle:true,pointStyle:'circle'}}}};
  } else if (isGradient) {
    const g = ctx.createLinearGradient(0,0,0,400);
    g.addColorStop(0,chartColor+'CC');
    g.addColorStop(1,chartColor+'11');
    datasets = [{label:field, data:values, backgroundColor:g, borderColor:chartColor, borderWidth:2.5, tension:0.4, fill:true, pointRadius:4, pointBackgroundColor:chartColor, pointBorderColor:'#fff', pointBorderWidth:2, pointHoverRadius:6}];
    opts = {plugins:{legend:{display:false}}, scales:{x:{grid:{display:false},ticks:{font:{size:10},maxRotation:45}},y:{grid:{color:'rgba(0,0,0,0.06)'},ticks:{font:{size:10}}}}};
  } else {
    const bgColors = isHorizontal ? values.map((_,i) => COLORS[i%COLORS.length]) : chartColor;
    datasets = [{label:field, data:values, backgroundColor:bgColors, borderColor:(type==='line')?chartColor:'transparent', borderWidth:(type==='line')?2.5:0, borderRadius:6, borderSkipped:false, tension:0.3, fill:type==='line', pointRadius:type==='line'?3:0, pointBackgroundColor:chartColor, barPercentage:0.7}];
    opts = {indexAxis:isHorizontal?'y':'x', plugins:{legend:{display:false}}, scales:{x:{grid:{display:!isHorizontal,color:'rgba(0,0,0,0.06)'},ticks:{font:{size:10},maxRotation:45}},y:{grid:{display:isHorizontal,color:'rgba(0,0,0,0.06)'},ticks:{font:{size:10}}}}};
  }

  currentChart = new Chart(ctx, {
    type: actualType, data: {labels, datasets},
    options: {responsive:true, maintainAspectRatio:false, animation:{duration:600,easing:'easeOutQuart'}, interaction:{intersect:false,mode:'index'},
      plugins:{...opts.plugins, tooltip:{backgroundColor:'rgba(26,26,46,0.95)',titleFont:{size:12,weight:'bold'},bodyFont:{size:11},padding:12,cornerRadius:8}},
      ...opts, plugins:undefined
    }
  });
  // Re-apply plugins after spread
  currentChart.options.plugins = {...opts.plugins, tooltip:{backgroundColor:'rgba(26,26,46,0.95)',titleFont:{size:12,weight:'bold'},bodyFont:{size:11},padding:12,cornerRadius:8}};
  currentChart.update();
}

function renderTable(data, field) {
  document.getElementById('chart-container').classList.add('hidden');
  document.getElementById('table-container').classList.remove('hidden');
  let html = '<table class="w-full text-sm"><thead><tr class="bg-gray-800 text-white"><th class="p-2 text-left">#</th><th class="p-2 text-left">'+field+'</th><th class="p-2 text-right">Count</th></tr></thead><tbody>';
  data.forEach((d,i) => {
    html += `<tr class="${i%2?'bg-gray-50':''}"><td class="p-2 text-gray-400">${i+1}</td><td class="p-2 font-medium">${d.label}</td><td class="p-2 text-right font-bold">${d.value.toLocaleString()}</td></tr>`;
  });
  html += '</tbody></table>';
  document.getElementById('table-container').innerHTML = html;
}

// SAVE WIDGET
async function saveWidget() {
  const name = document.getElementById('widget-name').value || 'Widget ' + new Date().toLocaleTimeString();
  const field = document.getElementById('agg-field').value;
  const chartType = document.getElementById('chart-type').value;
  const size = parseInt(document.getElementById('agg-size').value) || 10;
  const showLabels = document.getElementById('show-labels').checked;
  const timeFrom = document.getElementById('time-from').value;
  const data = {
    name: name,
    description: field + ' (' + chartType + ')',
    query_dsl: buildQuery() || {},
    agg_config: {
      field: field,
      chart_type: chartType,
      size: size,
      color: chartColor,
      show_labels: showLabels,
      time_from: timeFrom
    },
    chart_type: chartType
  };
  try {
    const r = await fetch(API+'/widgets', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}).then(r=>r.json());
    toast('Widget saved: ' + name, 'green');
  } catch(e) { toast('Error saving widget', 'red'); }
}
