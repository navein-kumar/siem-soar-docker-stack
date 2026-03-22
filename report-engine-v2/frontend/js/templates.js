// ============================================================
// TEMPLATES.JS - Auto-generated from index.html
// ============================================================

// TEMPLATES
async function loadTemplates() {
  const r = await fetch(API+'/templates').then(r=>r.json());
  const c = document.getElementById('templates-list');
  if (r.templates.length === 0) {
    c.innerHTML = '<div class="col-span-3 text-center text-gray-400 py-12">No templates yet. Click "+ New Template" to create one.</div>';
    return;
  }
  c.innerHTML = r.templates.sort((a,b) => {
    const na = parseInt(a.name.match(/^(\d+)/)?.[1] || '999');
    const nb = parseInt(b.name.match(/^(\d+)/)?.[1] || '999');
    return na - nb || a.name.localeCompare(b.name);
  }).map(t => `
    <div class="card p-4">
      <div class="flex items-center gap-2 mb-2">
        <div class="w-6 h-6 rounded" style="background:${t.cover_color}"></div>
        <h3 class="font-semibold text-gray-800">${t.name}</h3>
      </div>
      <p class="text-xs text-gray-500 mb-3">${t.description||'No description'}</p>
      <div class="text-xs text-gray-400 mb-3">${JSON.parse(t.sections||'[]').length} sections</div>
      <div class="flex gap-2 items-center mb-2">
        <select id="period-${t.id}" class="text-xs" style="padding:6px 8px;border:1px solid #e5e7eb;border-radius:6px;flex:1">
          <option value="24h" ${t.name.toLowerCase().includes('daily')?'selected':''}>Last 24 Hours</option>
          <option value="7d" ${t.name.toLowerCase().includes('weekly')?'selected':''}>Last 7 Days</option>
          <option value="30d" ${t.name.toLowerCase().includes('monthly')?'selected':''}>Last 30 Days</option>
          <option value="90d">Last 90 Days</option>
        </select>
      </div>
      <div class="flex gap-2">
        <button onclick="editTemplate('${t.id}')" class="btn btn-outline flex-1 text-xs">Edit</button>
        <button onclick="${t.name.toLowerCase().includes('inventory') ? "generateInventoryPDF()" : "generateFromTemplate('"+t.id+"',document.getElementById('period-"+t.id+"').value)"}" class="btn btn-primary flex-1 text-xs">Generate</button>
        <button onclick="${t.name.toLowerCase().includes('inventory') ? "showExcelDialog()" : "showExcelExportDialog()"}" class="btn text-xs" style="background:#217346;color:#fff;flex:1">📊 Excel</button>
        ${/^\d+\./.test(t.name) ? '' : '<button onclick="deleteTemplate(\''+t.id+'\')" class="btn btn-danger text-xs">✕</button>'}
      </div>
    </div>
  `).join('');
}

async function createTemplate() {
  editingTemplate = null;
  document.getElementById('template-editor').classList.remove('hidden');
  document.getElementById('templates-list').classList.add('hidden');
  document.getElementById('tpl-name').value = '';
  document.getElementById('tpl-cover-title').value = 'Security Threat Analysis Report';
  document.getElementById('tpl-cover-subtitle').value = '';
  document.getElementById('tpl-logo').value = 'https://codesecure.in/images/codesec-logo1.png';
  document.getElementById('tpl-company').value = 'Codesecure Solutions';
  document.getElementById('tpl-address').value = 'Chennai, Tamil Nadu, India';
  renderSections([]);
}

async function editTemplate(id) {
  const t = await fetch(API+'/templates/'+id).then(r=>r.json());
  editingTemplate = id;
  document.getElementById('template-editor').classList.remove('hidden');
  document.getElementById('templates-list').classList.add('hidden');
  document.getElementById('tpl-name').value = t.name;
  document.getElementById('tpl-cover-title').value = t.cover_title;
  document.getElementById('tpl-cover-subtitle').value = t.cover_subtitle||'';
  document.getElementById('tpl-logo').value = t.logo_url||'';
  document.getElementById('tpl-company').value = t.description||'Codesecure Solutions';
  document.getElementById('tpl-address').value = t.client_address||'Chennai, Tamil Nadu, India';
  selectedColor = t.cover_color;
  selectedAccent = t.cover_accent;
  const sections = JSON.parse(t.sections||'[]');
  renderSections(sections);
}

function renderSections(activeSections) {
  const activeIds = activeSections.map(s => typeof s === 'string' ? s : s.id);
  const ac = document.getElementById('active-sections');
  const av = document.getElementById('available-sections');

  if (activeIds.length === 0) {
    ac.innerHTML = '<div class="text-xs text-gray-400 text-center py-6">Drag sections here or click + to add</div>';
  } else {
    ac.innerHTML = activeIds.map((sid,i) => {
      const s = SECTIONS.find(x=>x.id===sid);
      if (!s) return '';
      return `<div class="section-card active flex items-center justify-between">
        <div class="flex items-center gap-2">
          <span class="text-gray-400 text-xs font-bold">${i+1}</span>
          <span>${s.icon} ${s.name}</span>
        </div>
        <div class="flex gap-1">
          ${i>0?`<button onclick="moveSection(${i},-1)" class="text-xs text-gray-400 hover:text-gray-700">▲</button>`:''}
          ${i<activeIds.length-1?`<button onclick="moveSection(${i},1)" class="text-xs text-gray-400 hover:text-gray-700">▼</button>`:''}
          <button onclick="removeSection(${i})" class="text-xs text-red-400 hover:text-red-700">✕</button>
        </div>
      </div>`;
    }).join('');
  }

  av.innerHTML = SECTIONS.filter(s => !activeIds.includes(s.id)).map(s => `
    <div class="section-card flex items-center justify-between" onclick="addSection('${s.id}')">
      <div>
        <div class="font-medium text-sm">${s.icon} ${s.name}</div>
        <div class="text-xs text-gray-400">${s.desc}</div>
      </div>
      <span class="text-teal-600 font-bold">+</span>
    </div>
  `).join('');

  // Store current sections
  window._activeSections = activeIds;
}

function addSection(id) {
  const s = window._activeSections || [];
  s.push(id);
  renderSections(s);
}

function removeSection(idx) {
  const s = window._activeSections || [];
  s.splice(idx,1);
  renderSections(s);
}

function moveSection(idx, dir) {
  const s = window._activeSections || [];
  const newIdx = idx+dir;
  if (newIdx<0||newIdx>=s.length) return;
  [s[idx],s[newIdx]] = [s[newIdx],s[idx]];
  renderSections(s);
}

function selectColor(el,color) {
  selectedColor = color;
  el.parentElement.querySelectorAll('.color-swatch').forEach(s=>s.classList.remove('selected'));
  el.classList.add('selected');
}

function selectAccent(el,color) {
  selectedAccent = color;
  el.parentElement.querySelectorAll('.color-swatch').forEach(s=>s.classList.remove('selected'));
  el.classList.add('selected');
}

async function saveTemplate() {
  const data = {
    name: document.getElementById('tpl-name').value || 'Untitled',
    description: document.getElementById('tpl-company').value || 'Codesecure Solutions',
    client_address: document.getElementById('tpl-address').value || 'Chennai, Tamil Nadu, India',
    cover_title: document.getElementById('tpl-cover-title').value,
    cover_subtitle: document.getElementById('tpl-cover-subtitle').value,
    cover_color: selectedColor,
    cover_accent: selectedAccent,
    logo_url: document.getElementById('tpl-logo').value,
    sections: window._activeSections || []
  };

  try {
    if (editingTemplate) {
      await fetch(API+'/templates/'+editingTemplate, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
    } else {
      const r = await fetch(API+'/templates', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)}).then(r=>r.json());
      editingTemplate = r.id;
    }
    toast('Template saved!','green');
  } catch(e) { toast('Error saving','red'); }
}

function closeEditor() {
  document.getElementById('template-editor').classList.add('hidden');
  document.getElementById('templates-list').classList.remove('hidden');
  loadTemplates();
}

async function deleteTemplate(id) {
  if (!confirm('Delete this template?')) return;
  await fetch(API+'/templates/'+id, {method:'DELETE'});
  loadTemplates();
}
