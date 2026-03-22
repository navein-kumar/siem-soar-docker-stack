// ============================================================
// UTILS.JS - Auto-generated from index.html
// ============================================================

// UTILS
function toast(msg, color='green') {
  const t = document.createElement('div');
  t.className = 'toast';
  t.style.background = color==='green'?'#0D7377':color==='red'?'#BD271E':color==='blue'?'#3498db':'#333';
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(()=>t.remove(), 3000);
}

// Init
init();
renderFilters();
