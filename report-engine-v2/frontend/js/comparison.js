// ============================================================
// COMPARISON.JS - Period vs Period comparison
// ============================================================

async function populateCompareAgents() {
  try {
    const r = await fetch(API+'/agents').then(r=>r.json());
    const sel = document.getElementById('compare-agent');
    if (!sel) return;
    sel.innerHTML = '<option value="">All Agents ('+r.agents.length+')</option>' + r.agents.map(a => '<option value="'+a+'">'+a+'</option>').join('');
  } catch(e) {}
}

const COMPARE_PRESETS = [
  {label: "Today vs Yesterday", a: "now-24h", b: "now-48h/now-24h"},
  {label: "This Week vs Last Week", a: "now-7d", b: "now-14d/now-7d"},
  {label: "This Month vs Last Month", a: "now-30d", b: "now-60d/now-30d"},
  {label: "Last 7d vs Previous 7d", a: "now-7d", b: "now-14d/now-7d"},
  {label: "Last 30d vs Previous 30d", a: "now-30d", b: "now-60d/now-30d"},
];

async function loadComparison() {
  const preset = document.getElementById('compare-preset');
  if (!preset) return;
  const val = preset.value;
  const p = COMPARE_PRESETS[parseInt(val)] || COMPARE_PRESETS[0];
  const agent = document.getElementById('compare-agent')?.value || '';

  const container = document.getElementById('compare-results');
  container.innerHTML = '<div class="text-center py-12"><div class="loader"></div><div class="text-sm text-gray-500 mt-3">Comparing periods...</div></div>';

  try {
    const params = new URLSearchParams({period_a: p.a, period_b: p.b});
    if (agent) params.set('agent', agent);
    const data = await fetch(API+'/compare?'+params.toString()).then(r=>r.json());
    renderComparison(data, p.label);
  } catch(e) {
    container.innerHTML = '<div class="text-center text-red-500 py-12">Error: '+e.message+'</div>';
  }
}

function renderComparison(d, label) {
  const s = d.summary;
  const container = document.getElementById('compare-results');

  function deltaCard(title, data, color) {
    const arrow = data.trend === 'up' ? '▲' : (data.trend === 'down' ? '▼' : '●');
    const tColor = data.trend === 'up' ? '#e74c3c' : (data.trend === 'down' ? '#2ecc71' : '#95a5a6');
    const pct = typeof data.pct === 'number' ? (data.pct > 0 ? '+' : '') + data.pct + '%' : data.pct;
    return `<div class="card p-4 text-center" style="border-left:4px solid ${color}">
      <div class="text-xs text-gray-500 mb-1">${title}</div>
      <div class="text-2xl font-bold" style="color:${color}">${data.value.toLocaleString()}</div>
      <div class="text-sm mt-1" style="color:${tColor}">${arrow} ${pct}</div>
      <div class="text-xs text-gray-400 mt-1">${data.prev.toLocaleString()} → ${data.value.toLocaleString()}</div>
    </div>`;
  }

  // Summary cards
  let html = `<div class="grid grid-cols-5 gap-3 mb-4">
    ${deltaCard('Total Alerts', s.total, '#3498db')}
    ${deltaCard('Critical', s.critical, '#BD271E')}
    ${deltaCard('High', s.high, '#E7664C')}
    ${deltaCard('Medium', s.medium, '#D6BF57')}
    ${deltaCard('Low', s.low, '#6DCCB1')}
  </div>`;

  html += `<div class="grid grid-cols-5 gap-3 mb-6">
    ${deltaCard('Auth Failures', s.auth_fail, '#e74c3c')}
    ${deltaCard('Auth Successes', s.auth_success, '#2ecc71')}
    ${deltaCard('Level 12+', s.level12, '#BD271E')}
    ${deltaCard('MITRE Techniques', s.mitre_techniques, '#9b59b6')}
    ${deltaCard('Active Agents', s.agents, '#3498db')}
  </div>`;

  // Severity comparison chart
  html += `<div class="grid grid-cols-2 gap-4 mb-4">
    <div class="card p-4">
      <h3 class="font-semibold text-gray-700 mb-3">Severity Comparison</h3>
      <div style="height:250px;position:relative"><canvas id="compare-sev-chart"></canvas></div>
    </div>
    <div class="card p-4">
      <h3 class="font-semibold text-gray-700 mb-3">Top Rules (Current vs Previous)</h3>
      <div class="overflow-auto max-h-64">
        <table class="w-full text-xs">
          <thead><tr class="bg-gray-800 text-white"><th class="p-2 text-left">Rule</th><th class="p-2 text-left">Description</th><th class="p-2 text-right">Current</th><th class="p-2 text-right">Previous</th><th class="p-2 text-right">Change</th></tr></thead>
          <tbody>${d.rules.map((r,i) => {
            const diffColor = r.diff > 0 ? '#e74c3c' : (r.diff < 0 ? '#2ecc71' : '#95a5a6');
            const pct = typeof r.pct === 'number' ? (r.pct > 0 ? '+' : '') + r.pct + '%' : r.pct;
            return `<tr class="${i%2?'bg-gray-50':''}"><td class="p-2 font-mono">${r.rule_id}</td><td class="p-2" style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${r.description}</td><td class="p-2 text-right font-bold">${r.current.toLocaleString()}</td><td class="p-2 text-right text-gray-500">${r.previous.toLocaleString()}</td><td class="p-2 text-right font-bold" style="color:${diffColor}">${pct}</td></tr>`;
          }).join('')}</tbody>
        </table>
      </div>
    </div>
  </div>`;

  // Agents comparison
  html += `<div class="card p-4">
    <h3 class="font-semibold text-gray-700 mb-3">Agent Comparison</h3>
    <div class="overflow-auto max-h-72">
      <table class="w-full text-xs">
        <thead><tr class="bg-gray-800 text-white"><th class="p-2 text-left">Agent</th><th class="p-2 text-right">Current Period</th><th class="p-2 text-right">Previous Period</th><th class="p-2 text-right">Change</th><th class="p-2" style="width:150px">Trend</th></tr></thead>
        <tbody>${d.agents.map((a,i) => {
          const diffColor = a.diff > 0 ? '#e74c3c' : (a.diff < 0 ? '#2ecc71' : '#95a5a6');
          const pct = typeof a.pct === 'number' ? (a.pct > 0 ? '+' : '') + a.pct + '%' : a.pct;
          const maxVal = Math.max(a.current, a.previous) || 1;
          const currW = Math.round(a.current / maxVal * 100);
          const prevW = Math.round(a.previous / maxVal * 100);
          return `<tr class="${i%2?'bg-gray-50':''}"><td class="p-2 font-semibold">${a.agent}</td><td class="p-2 text-right font-bold">${a.current.toLocaleString()}</td><td class="p-2 text-right text-gray-500">${a.previous.toLocaleString()}</td><td class="p-2 text-right font-bold" style="color:${diffColor}">${pct}</td><td class="p-2"><div style="display:flex;gap:2px;align-items:center"><div style="background:#3498db;height:8px;width:${currW}%;border-radius:4px"></div><div style="background:#95a5a6;height:8px;width:${prevW}%;border-radius:4px;opacity:0.5"></div></div></td></tr>`;
        }).join('')}</tbody>
      </table>
    </div>
  </div>`;

  container.innerHTML = html;

  // Render severity chart
  setTimeout(() => {
    const ctx = document.getElementById('compare-sev-chart');
    if (!ctx) return;
    new Chart(ctx, {
      type: 'bar',
      data: {
        labels: ['Critical', 'High', 'Medium', 'Low'],
        datasets: [
          {label: 'Current Period', data: [d.severity_a.Critical, d.severity_a.High, d.severity_a.Medium, d.severity_a.Low], backgroundColor: ['#BD271E','#E7664C','#D6BF57','#6DCCB1'], borderRadius: 6},
          {label: 'Previous Period', data: [d.severity_b.Critical, d.severity_b.High, d.severity_b.Medium, d.severity_b.Low], backgroundColor: ['#BD271E55','#E7664C55','#D6BF5755','#6DCCB155'], borderRadius: 6}
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {legend: {position: 'top'}, datalabels: {display: false}},
        scales: {x: {grid: {display: false}}, y: {grid: {color: 'rgba(0,0,0,0.05)'}}}
      }
    });
  }, 100);
}
