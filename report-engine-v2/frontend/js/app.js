// ============================================================
// APP.JS - Auto-generated from index.html
// ============================================================

// ============================================================
// APP.JS - Global state, initialization, tab navigation
// ============================================================
// Register Chart.js plugins
if (typeof ChartDataLabels !== 'undefined') {
  Chart.register(ChartDataLabels);
  Chart.defaults.plugins.datalabels = { display: false };  // disabled by default
}

const API = '/api';
let allFields = [];
let currentChart = null;
let chartColor = '#0D7377';

// Built-in report sections
let SECTIONS = [
  {id:'executive_summary', name:'Executive Summary', icon:'📊', desc:'Severity overview, day-over-day, timeline'},
  {id:'top_threats', name:'Top Threat Alerts', icon:'🔴', desc:'Level 12+ events grouped by rule'},
  {id:'agents_risk', name:'Agents & Risk Assessment', icon:'💻', desc:'Agent volumes, severity breakdown'},
  {id:'authentication', name:'Authentication Events', icon:'🔑', desc:'Login failures, successes, top users'},
  {id:'source_ips', name:'Top Source IPs', icon:'🌐', desc:'Most active source IP addresses'},
  {id:'vulnerability', name:'Vulnerability Detection', icon:'🔵', desc:'CVEs, affected agents'},
  {id:'fim', name:'File Integrity Monitoring', icon:'📁', desc:'File changes, modified paths'},
  {id:'mitre', name:'MITRE ATT&CK Analysis', icon:'⚔', desc:'Techniques and tactics mapping'},
  {id:'compliance', name:'Regulatory Compliance', icon:'📋', desc:'PCI-DSS, HIPAA, GDPR, NIST'},
  {id:'security_events', name:'Security Events Summary', icon:'📑', desc:'All rules sorted by severity'},
];

async function loadWidgetSections() {
  try {
    const r = await fetch(API+'/widgets').then(r=>r.json());
    if (r.widgets && r.widgets.length > 0) {
      r.widgets.forEach(w => {
        if (!SECTIONS.find(s => s.id === 'widget_' + w.id)) {
          SECTIONS.push({id: 'widget_' + w.id, name: w.name, icon: '📊', desc: w.description || 'Custom widget'});
        }
      });
    }
  } catch(e) { console.log('Widget sections load error:', e); }
}
let editingTemplate = null;
let selectedColor = '#1B2A4A';
let selectedAccent = '#0D7377';

function selectChartColor(el, color) {
  chartColor = color;
  document.querySelectorAll('#chart-colors .color-swatch').forEach(s => s.classList.remove('selected'));
  el.classList.add('selected');
  if (window._lastChartData) {
    renderChart(window._lastChartData, document.getElementById('chart-type').value, document.getElementById('agg-field').value);
  }
}

// INIT
async function init() {
  try { renderFilters(); } catch(e) {}
  try { await loadWidgetSections(); } catch(e) { console.log('loadWidgetSections:', e); }
  try {
    const h = await fetch(API+'/health').then(r=>r.json());
    document.getElementById('health-badge').className = 'text-xs px-3 py-1 rounded-full bg-green-100 text-green-700';
    document.getElementById('health-badge').textContent = 'Connected: ' + h.cluster;
  } catch(e) {
    document.getElementById('health-badge').className = 'text-xs px-3 py-1 rounded-full bg-red-100 text-red-700';
    document.getElementById('health-badge').textContent = 'Disconnected';
  }

  // Load fields
  try {
    const f = await fetch(API+'/fields').then(r=>r.json());
    allFields = f.fields.filter(x=>x.filterable);
    populateFieldSelects();
  } catch(e) {}

  // Live metrics
  try {
    const q24 = await fetch(API+'/query', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({time_from:'now-24h'})}).then(r=>r.json());
    document.getElementById('os-alerts24h').textContent = q24.total.toLocaleString();
  } catch(e) {}
  try {
    const qc = await fetch(API+'/query', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({query:{range:{'rule.level':{gte:12}}},time_from:'now-24h'})}).then(r=>r.json());
    document.getElementById('os-critical').textContent = qc.total.toLocaleString();
  } catch(e) {}
  try {
    const qa = await fetch(API+'/aggregate', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({group_by:'agent.name',time_from:'now-24h',size:50})}).then(r=>r.json());
    document.getElementById('os-agents').textContent = qa.data.length;
  } catch(e) {}

  // Load templates count
  try {
    const t = await fetch(API+'/templates').then(r=>r.json());
    document.getElementById('os-templates').textContent = t.templates.length;
  } catch(e) {}

  // Load reports
  try {
    const r = await fetch(API+'/reports').then(r=>r.json());
    document.getElementById('os-reports').textContent = r.reports.length;
    renderRecentReports(r.reports.slice(0,5));
  } catch(e) {}

  // Dashboard live charts
  loadDashboardCharts();
}

async function loadDashboardCharts() {
  // Severity donut
  try {
    const sev = await fetch(API+'/aggregate', {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({group_by:'rule.level', time_from:'now-24h', size:20})}).then(r=>r.json());
    const sevData = {Critical:0, High:0, Medium:0, Low:0};
    sev.data.forEach(d => {
      const l = parseInt(d.label);
      if (l >= 15) sevData.Critical += d.value;
      else if (l >= 12) sevData.High += d.value;
      else if (l >= 7) sevData.Medium += d.value;
      else sevData.Low += d.value;
    });
    const ctx = document.getElementById('dash-severity');
    if (ctx) new Chart(ctx, {
      type:'doughnut', data:{labels:['Critical','High','Medium','Low'],
        datasets:[{data:[sevData.Critical,sevData.High,sevData.Medium,sevData.Low],
          backgroundColor:['#BD271E','#E7664C','#D6BF57','#6DCCB1'],borderColor:'#fff',borderWidth:3}]},
      options:{responsive:true,maintainAspectRatio:false,cutout:'55%',
        plugins:{legend:{position:'right',labels:{font:{size:11},usePointStyle:true}},datalabels:{display:false}}}
    });
  } catch(e) {}

  // Timeline
  try {
    const tl = await fetch(API+'/aggregate', {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({group_by:'_date_histogram', time_from:'now-24h', size:24})}).then(r=>r.json());
    const ctx2 = document.getElementById('dash-timeline');
    if (ctx2 && tl.data.length > 0) new Chart(ctx2, {
      type:'line', data:{labels:tl.data.map(d=>d.label.substring(11,16)||d.label),
        datasets:[{data:tl.data.map(d=>d.value),borderColor:'#0D7377',backgroundColor:'rgba(13,115,119,0.1)',
          fill:true,tension:0.3,pointRadius:2,borderWidth:2}]},
      options:{responsive:true,maintainAspectRatio:false,
        plugins:{legend:{display:false},datalabels:{display:false}},
        scales:{x:{grid:{display:false},ticks:{font:{size:9},maxRotation:45}},y:{grid:{color:'rgba(0,0,0,0.05)'},ticks:{font:{size:9}}}}}
    });
  } catch(e) {}

  // Top Agents bar
  try {
    const ag = await fetch(API+'/aggregate', {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({group_by:'agent.name', time_from:'now-24h', size:8})}).then(r=>r.json());
    const ctx3 = document.getElementById('dash-agents');
    if (ctx3 && ag.data.length > 0) new Chart(ctx3, {
      type:'bar', data:{labels:ag.data.map(d=>d.label.length>12?d.label.substring(0,12)+'..':d.label),
        datasets:[{data:ag.data.map(d=>d.value),backgroundColor:'#0D7377',borderRadius:6}]},
      options:{responsive:true,maintainAspectRatio:false,indexAxis:'y',
        plugins:{legend:{display:false},datalabels:{display:false}},
        scales:{x:{grid:{color:'rgba(0,0,0,0.05)'},ticks:{font:{size:9}}},y:{grid:{display:false},ticks:{font:{size:10}}}}}
    });
  } catch(e) {}
}

// TABS
function showTab(tab) {
  ['dashboard','query','widgets','templates','compare','reports'].forEach(t => {
    const page = document.getElementById('page-'+t);
    const tabEl = document.getElementById('tab-'+t);
    if (page) page.classList.toggle('hidden', t!==tab);
    if (tabEl) tabEl.classList.toggle('tab-active', t===tab);
  });
  if (tab==='widgets') loadWidgets();
  if (tab==='templates') loadTemplates();
  if (tab==='reports') loadReports();
  if (tab==='compare') { populateCompareAgents(); loadComparison(); }
}
