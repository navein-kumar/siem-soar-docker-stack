// ============================================================
// REPORTS.JS - Auto-generated from index.html
// ============================================================

// REPORT GENERATION
async function generateFromTemplate(tid, periodOverride) {
  const periodEl = document.getElementById('tpl-period');
  const p = periodOverride || (periodEl ? periodEl.value : '24h') || '24h';
  toast('📄 Report generation started in background. Check Reports tab when ready.','blue');
  fetch(API+'/generate/'+tid+'?period='+p, {method:'POST'}).then(r=>r.json()).then(r => {
    if (r.download_url) {
      toast('✅ Report ready! ' + ((r.size/1024).toFixed(0)) + 'KB — click Reports tab to download','green');
      loadReports();
    } else {
      toast('❌ ' + (r.detail || 'Generation failed'),'red');
    }
  }).catch(e => toast('❌ Error: '+e.message,'red'));
}

async function generateQuickReport() {
  // Load templates + agents for unified dialog
  let templates = [], agents = [];
  try {
    const [tR, aR] = await Promise.all([
      fetch(API+'/templates').then(r=>r.json()),
      fetch(API+'/agents').then(r=>r.json())
    ]);
    templates = (tR.templates || []).sort((a,b) => {
      const na = parseInt(a.name.match(/^(\d+)/)?.[1] || '999');
      const nb = parseInt(b.name.match(/^(\d+)/)?.[1] || '999');
      return na - nb;
    });
    agents = aR.agents || [];
  } catch(e) {}

  const tplOpts = templates.map(t => `<option value="${t.id}">${t.name}</option>`).join('');
  const agentOpts = agents.map(a => `<option value="${a}">${a}</option>`).join('');

  const overlay = document.createElement('div');
  overlay.id = 'gen-overlay';
  overlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);z-index:9998;display:flex;align-items:center;justify-content:center';
  overlay.innerHTML = `<div style="background:#fff;border-radius:12px;padding:24px;width:460px;box-shadow:0 8px 32px rgba(0,0,0,0.2)">
    <h3 style="font-size:16px;font-weight:700;margin-bottom:16px">📄 Generate PDF Report</h3>
    <div style="margin-bottom:12px">
      <label style="font-size:12px;color:#69707D;display:block;margin-bottom:4px">Report Template</label>
      <select id="gen-template" style="width:100%;padding:8px;border:1px solid #d1d5db;border-radius:6px">
        <option value="quick">Quick Report (All Sections)</option>
        <option value="inventory">IT Asset Inventory</option>
        ${tplOpts}
      </select>
    </div>
    <div style="margin-bottom:12px" id="gen-period-row">
      <label style="font-size:12px;color:#69707D;display:block;margin-bottom:4px">Period</label>
      <select id="gen-period" style="width:100%;padding:8px;border:1px solid #d1d5db;border-radius:6px">
        <option value="24h">Last 24 Hours</option>
        <option value="7d">Last 7 Days</option>
        <option value="30d">Last 30 Days</option>
        <option value="90d">Last 90 Days</option>
      </select>
    </div>
    <div style="margin-bottom:12px">
      <label style="font-size:12px;color:#69707D;display:block;margin-bottom:4px">Filter by Agent</label>
      <select id="gen-agent" style="width:100%;padding:8px;border:1px solid #d1d5db;border-radius:6px">
        <option value="">All Agents (${agents.length})</option>${agentOpts}
      </select>
    </div>
    <div style="margin-bottom:12px">
      <label style="font-size:12px;color:#69707D;display:block;margin-bottom:4px">PDF Style</label>
      <select id="gen-style" style="width:100%;padding:8px;border:1px solid #d1d5db;border-radius:6px">
        <option value="v2">Enhanced (gradient charts, icons, enterprise)</option>
        <option value="classic">Classic (v1)</option>
      </select>
    </div>
    <div style="margin-bottom:16px;font-size:11px;color:#95a5a6">Generates a PDF report with cover page, charts, and data tables. Runs in background.</div>
    <div style="display:flex;gap:8px">
      <button id="gen-go-btn" class="btn btn-primary" style="flex:1">Generate PDF</button>
      <button id="gen-no-btn" class="btn btn-secondary" style="flex:1">Cancel</button>
    </div>
  </div>`;
  document.body.appendChild(overlay);

  document.getElementById('gen-template').onchange = function() {
    document.getElementById('gen-period-row').style.display = this.value === 'inventory' ? 'none' : 'block';
  };

  document.getElementById('gen-no-btn').onclick = () => overlay.remove();
  document.getElementById('gen-go-btn').onclick = () => {
    const tpl = document.getElementById('gen-template').value;
    const period = document.getElementById('gen-period').value;
    const agent = document.getElementById('gen-agent').value;
    const style = document.getElementById('gen-style').value;
    overlay.remove();

    const agentParam = agent ? '&agent='+encodeURIComponent(agent) : '';
    const prefix = style === 'v2' ? '/generate/v2' : '/generate';

    if (tpl === 'quick') {
      toast('📄 Quick report generation started...','blue');
      fetch(API+prefix+'/quick?period='+period+agentParam, {method:'POST'}).then(r=>r.json()).then(r => {
        if (r.download_url) { toast('✅ Report ready!','green'); loadReports(); }
        else { toast('❌ '+(r.detail||'Failed'),'red'); }
      }).catch(e => toast('❌ '+e.message,'red'));
    } else if (tpl === 'inventory') {
      toast('📄 Inventory report generation started...','blue');
      fetch(API+'/generate/inventory?'+agentParam.substring(1), {method:'POST'}).then(r=>r.json()).then(r => {
        if (r.download_url) { toast('✅ Inventory report ready!','green'); loadReports(); }
        else { toast('❌ '+(r.detail||'Failed'),'red'); }
      }).catch(e => toast('❌ '+e.message,'red'));
    } else {
      // Template-based report
      const tplUrl = style === 'v2'
        ? API+'/generate/v2/'+tpl+'?period='+period
        : API+'/generate/'+tpl+'?period='+period;
      toast('📄 Report generation started...','blue');
      fetch(tplUrl, {method:'POST'}).then(r=>r.json()).then(r => {
        if (r.download_url) { toast('✅ Report ready!','green'); loadReports(); }
        else { toast('❌ '+(r.detail||'Failed'),'red'); }
      }).catch(e => toast('❌ '+e.message,'red'));
    }
  };
}

async function generateInventoryExcel(agent) {
  const agentParam = agent ? '?agent='+encodeURIComponent(agent) : '';
  toast('📊 Excel export started in background. Check Reports tab when ready.','blue');
  fetch(API+'/generate/inventory/excel/async'+agentParam, {method:'POST'}).then(r=>r.json()).then(r => {
    if (r.job_id) {
      pollJob(r.job_id);
    }
  }).catch(e => toast('❌ Error: '+e.message,'red'));
}

function pollJob(jobId) {
  const check = () => {
    fetch(API+'/jobs/'+jobId).then(r=>r.json()).then(job => {
      if (job.status === 'completed') {
        toast('✅ Excel export ready! ' + ((job.size/1024).toFixed(0)) + 'KB — downloading...','green');
        window.open(API+'/jobs/'+jobId+'/download','_blank');
        loadReports();
      } else if (job.status === 'failed') {
        toast('❌ Export failed: ' + job.error,'red');
      } else {
        setTimeout(check, 3000);
      }
    });
  };
  setTimeout(check, 2000);
}

// Security Events Excel
async function exportSecurityExcel(period, agent) {
  const params = new URLSearchParams();
  if (period) params.set('period', period);
  if (agent) params.set('agent', agent);
  toast('📊 Security Events Excel export started...','blue');
  fetch(API+'/export/security?'+params.toString(), {method:'POST'}).then(r=>r.json()).then(r => {
    if (r.job_id) pollJob(r.job_id);
  }).catch(e => toast('Error: '+e.message,'red'));
}

// Auth Events Excel
async function exportAuthExcel(period, agent) {
  const params = new URLSearchParams();
  if (period) params.set('period', period);
  if (agent) params.set('agent', agent);
  toast('📊 Auth Events Excel export started...','blue');
  fetch(API+'/export/auth?'+params.toString(), {method:'POST'}).then(r=>r.json()).then(r => {
    if (r.job_id) pollJob(r.job_id);
  }).catch(e => toast('Error: '+e.message,'red'));
}

// Vulnerability Excel
async function exportVulnExcel(agent) {
  const params = agent ? '?agent='+encodeURIComponent(agent) : '';
  toast('📊 Vulnerability Excel export started...','blue');
  fetch(API+'/export/vulnerability'+params, {method:'POST'}).then(r=>r.json()).then(r => {
    if (r.job_id) pollJob(r.job_id);
  }).catch(e => toast('Error: '+e.message,'red'));
}

// Universal Excel Export Dialog
async function showExcelExportDialog() {
  let agents = [];
  try {
    const r = await fetch(API+'/agents').then(r=>r.json());
    agents = r.agents || [];
  } catch(e) {}

  const opts = agents.map(a => '<option value="'+a+'">'+a+'</option>').join('');
  const overlay = document.createElement('div');
  overlay.id = 'excel-overlay';
  overlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);z-index:9998;display:flex;align-items:center;justify-content:center';
  overlay.innerHTML = `<div style="background:#fff;border-radius:12px;padding:24px;width:440px;box-shadow:0 8px 32px rgba(0,0,0,0.2)">
    <h3 style="font-size:16px;font-weight:700;margin-bottom:16px">📊 Excel Data Export</h3>
    <div style="margin-bottom:12px">
      <label style="font-size:12px;color:#69707D;display:block;margin-bottom:4px">Export Type</label>
      <select id="excel-type" style="width:100%;padding:8px;border:1px solid #d1d5db;border-radius:6px">
        <option value="security">Security Events (alerts, rules, agents, MITRE, compliance)</option>
        <option value="auth">Authentication Events (login failures/successes)</option>
        <option value="vulnerability">Vulnerability Assessment (all CVEs)</option>
        <option value="inventory">IT Asset Inventory (hardware, software, ports, users)</option>
      </select>
    </div>
    <div style="margin-bottom:12px" id="excel-period-row">
      <label style="font-size:12px;color:#69707D;display:block;margin-bottom:4px">Period</label>
      <select id="excel-period" style="width:100%;padding:8px;border:1px solid #d1d5db;border-radius:6px">
        <option value="24h">Last 24 Hours</option>
        <option value="7d">Last 7 Days</option>
        <option value="30d">Last 30 Days</option>
        <option value="90d">Last 90 Days</option>
      </select>
    </div>
    <div style="margin-bottom:12px">
      <label style="font-size:12px;color:#69707D;display:block;margin-bottom:4px">Filter by Agent</label>
      <select id="excel-agent" style="width:100%;padding:8px;border:1px solid #d1d5db;border-radius:6px">
        <option value="">All Agents (${agents.length})</option>${opts}
      </select>
    </div>
    <div style="margin-bottom:16px;font-size:11px;color:#95a5a6">Exports raw data to multi-sheet Excel workbook. Large exports run in background.</div>
    <div style="display:flex;gap:8px">
      <button id="excel-go-btn" class="btn" style="flex:1;background:#217346;color:#fff;font-weight:700">Export Excel</button>
      <button id="excel-no-btn" class="btn btn-secondary" style="flex:1">Cancel</button>
    </div>
  </div>`;
  document.body.appendChild(overlay);

  // Toggle period row based on type
  document.getElementById('excel-type').onchange = function() {
    document.getElementById('excel-period-row').style.display = (this.value === 'inventory' || this.value === 'vulnerability') ? 'none' : 'block';
  };

  document.getElementById('excel-no-btn').onclick = () => overlay.remove();
  document.getElementById('excel-go-btn').onclick = () => {
    const type = document.getElementById('excel-type').value;
    const period = document.getElementById('excel-period').value;
    const agent = document.getElementById('excel-agent').value;
    overlay.remove();
    if (type === 'security') exportSecurityExcel(period, agent);
    else if (type === 'auth') exportAuthExcel(period, agent);
    else if (type === 'vulnerability') exportVulnExcel(agent);
    else if (type === 'inventory') generateInventoryExcel(agent);
  };
}

async function generateInventoryPDF() {
  toast('📄 Inventory report generation started...','blue');
  fetch(API+'/generate/inventory', {method:'POST'}).then(r=>r.json()).then(r => {
    if (r.download_url) {
      toast('✅ Inventory report ready! ' + ((r.size/1024).toFixed(0)) + 'KB','green');
      window.open(r.download_url,'_blank');
      loadReports();
    } else {
      toast('❌ ' + (r.detail || 'Failed'),'red');
    }
  }).catch(e => toast('❌ Error: '+e.message,'red'));
}

async function showExcelDialog() {
  let agents = [];
  try {
    const r = await fetch(API+'/agents').then(r=>r.json());
    agents = r.agents || [];
  } catch(e) {}

  const opts = agents.map(a => '<option value="'+a+'">'+a+'</option>').join('');
  const overlay = document.createElement('div');
  overlay.id = 'excel-overlay';
  overlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);z-index:9998;display:flex;align-items:center;justify-content:center';
  overlay.innerHTML = '<div style="background:#fff;border-radius:12px;padding:24px;width:400px;box-shadow:0 8px 32px rgba(0,0,0,0.2)"><h3 style="font-size:16px;font-weight:700;margin-bottom:16px">📊 Export Inventory to Excel</h3><div style="margin-bottom:12px"><label style="font-size:12px;color:#69707D;display:block;margin-bottom:4px">Filter by Agent</label><select id="excel-agent" style="width:100%;padding:8px;border:1px solid #d1d5db;border-radius:6px"><option value="">All Agents ('+agents.length+')</option>'+opts+'</select></div><div style="margin-bottom:16px;font-size:11px;color:#95a5a6">Exports all inventory data (hardware, software, processes, ports, services, users, vulnerabilities) to a multi-sheet Excel workbook.</div><div style="display:flex;gap:8px"><button id="excel-export-btn" class="btn btn-primary" style="flex:1;background:#217346">Export Excel</button><button id="excel-cancel-btn" class="btn btn-secondary" style="flex:1">Cancel</button></div></div>';
  document.body.appendChild(overlay);

  document.getElementById('excel-cancel-btn').onclick = () => overlay.remove();
  document.getElementById('excel-export-btn').onclick = () => {
    const agent = document.getElementById('excel-agent').value;
    overlay.remove();
    generateInventoryExcel(agent);
  };
}

async function previewTemplate(useV2) {
  try {
    await saveTemplate();
  } catch(e) { /* ignore save errors */ }
  if (editingTemplate) {
    const period = document.getElementById('tpl-period')?.value || '24h';
    const isInventory = document.getElementById('tpl-name')?.value?.toLowerCase().includes('inventory');
    const prefix = useV2 ? '/preview/v2' : '/preview';
    const url = isInventory
      ? API+'/preview/inventory'
      : API+prefix+'/'+editingTemplate+'?period='+period;
    window.open(url, '_blank');
    toast('Preview opened in new tab','green');
  } else {
    toast('Save template first','red');
  }
}

// REPORTS ARCHIVE
async function loadReports() {
  const r = await fetch(API+'/reports').then(r=>r.json());
  const c = document.getElementById('reports-list');
  if (r.reports.length === 0) {
    c.innerHTML = '<div class="text-center text-gray-400 py-12">No reports generated yet</div>';
    return;
  }
  let html = '<table class="w-full text-sm"><thead><tr class="bg-gray-800 text-white"><th class="p-3 text-left">Report</th><th class="p-3 text-left">Template</th><th class="p-3 text-left">Period</th><th class="p-3 text-left">Generated</th><th class="p-3 text-right">Size</th><th class="p-3">Action</th></tr></thead><tbody>';
  r.reports.forEach((rpt,i) => {
    html += `<tr class="${i%2?'bg-gray-50':''}">
      <td class="p-3 font-medium">${rpt.filename}</td>
      <td class="p-3">${rpt.template_name||'-'}</td>
      <td class="p-3 text-xs">${rpt.period_from||'-'} → ${rpt.period_to||'-'}</td>
      <td class="p-3 text-xs">${rpt.generated_at}</td>
      <td class="p-3 text-right text-xs">${rpt.file_size ? (rpt.file_size/1024).toFixed(0)+'KB' : '-'}</td>
      <td class="p-3 text-center"><a href="${API}/reports/${rpt.id}/download" class="btn btn-outline text-xs" target="_blank">Download</a> <button data-delete-report="${rpt.id}" class="btn text-xs" style="border:1px solid #e74c3c;color:#e74c3c;margin-left:4px;cursor:pointer">Delete</button></td>
    </tr>`;
  });
  html += '</tbody></table>';
  c.innerHTML = html;

  // Bind delete buttons - no confirmation, instant delete
  c.querySelectorAll('[data-delete-report]').forEach(btn => {
    btn.addEventListener('click', async function() {
      const rid = this.getAttribute('data-delete-report');
      const row = this.closest('tr');
      row.style.opacity = '0.3';
      await fetch(API+'/reports/'+rid, {method:'DELETE'});
      row.remove();
    });
  });

  // Bind delete all button (in header, outside dynamic area)
  const delAllBtn = document.querySelector('[data-delete-all]');
  if(delAllBtn) {
    const newBtn = delAllBtn.cloneNode(true);
    delAllBtn.parentNode.replaceChild(newBtn, delAllBtn);
    newBtn.addEventListener('click', async function() {
      this.textContent = 'Deleting...';
      this.disabled = true;
      for(const rpt of r.reports) {
        await fetch(API+'/reports/'+rpt.id, {method:'DELETE'});
      }
      showPage('reports');
    });
  }
}

function renderRecentReports(reports) {
  const c = document.getElementById('recent-reports');
  if (reports.length === 0) { c.innerHTML = '<div class="text-gray-400">No reports yet</div>'; return; }
  c.innerHTML = reports.map(r => `<div class="flex justify-between items-center py-1 border-b border-gray-100"><span class="text-xs">${r.filename}</span><a href="${API}/reports/${r.id}/download" class="text-xs text-teal-600 hover:underline">Download</a></div>`).join('');
}
