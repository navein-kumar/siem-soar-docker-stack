// ============================================================
// APP.JS - Auto-generated from index.html
// ============================================================

// ============================================================
// APP.JS - Global state, initialization, tab navigation
// ============================================================
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
}

// TABS
function showTab(tab) {
  ['dashboard','query','widgets','templates','reports'].forEach(t => {
    document.getElementById('page-'+t).classList.toggle('hidden', t!==tab);
    document.getElementById('tab-'+t).classList.toggle('tab-active', t===tab);
  });
  if (tab==='widgets') loadWidgets();
  if (tab==='templates') loadTemplates();
  if (tab==='reports') loadReports();
}
