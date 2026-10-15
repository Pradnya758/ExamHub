// toasts, sidebar, confirm dialogs, copy SQL
document.querySelectorAll('.toast').forEach(t => setTimeout(() => t.remove(), 4500));
const side = document.querySelector('.side');
document.querySelector('.menu')?.addEventListener('click', () => side.classList.toggle('open'));
document.querySelectorAll('form[data-confirm]').forEach(f =>
  f.addEventListener('submit', e => { if (!confirm(f.dataset.confirm)) e.preventDefault(); }));
document.querySelectorAll('[data-copy]').forEach(b => b.addEventListener('click', () => {
  navigator.clipboard?.writeText(document.querySelector(b.dataset.copy).innerText); b.textContent = 'Copied';
}));

// searchable, sortable, paginated tables
document.querySelectorAll('table.dt').forEach(tbl => {
  const body = tbl.tBodies[0], all = [...body.rows];
  if (!all.length) return;
  let page = 1, size = 10, q = '';
  const bar = document.createElement('div'); bar.className = 'dtbar';
  bar.innerHTML = '<label style="margin:0;font-weight:500">Show <select><option>5</option><option selected>10</option><option>25</option><option>50</option></select> entries</label><input placeholder="Search...">';
  const foot = document.createElement('div'); foot.className = 'dtfoot';
  tbl.parentNode.before(bar); tbl.parentNode.after(foot);
  bar.querySelector('select').onchange = e => { size = +e.target.value; page = 1; draw(); };
  bar.querySelector('input').oninput = e => { q = e.target.value.toLowerCase(); page = 1; draw(); };
  tbl.tHead.querySelectorAll('th:not(.nosort)').forEach((th, i) => {
    th.classList.add('sortable'); let asc = true;
    th.onclick = () => {
      all.sort((a, b) => {
        const x = a.cells[i].innerText.trim(), y = b.cells[i].innerText.trim();
        const r = (!isNaN(x) && !isNaN(y) && x !== '' && y !== '') ? x - y : x.localeCompare(y);
        return asc ? r : -r;
      });
      asc = !asc; all.forEach(r => body.appendChild(r)); draw();
    };
  });
  function draw() {
    const hit = all.filter(r => r.innerText.toLowerCase().includes(q));
    const pages = Math.max(1, Math.ceil(hit.length / size)); page = Math.min(page, pages);
    all.forEach(r => r.style.display = 'none');
    hit.slice((page - 1) * size, page * size).forEach(r => r.style.display = '');
    foot.innerHTML = '<span>Showing ' + (hit.length ? (page - 1) * size + 1 : 0) + ' to ' + Math.min(page * size, hit.length) + ' of ' + hit.length + ' entries</span><div class="pg"></div>';
    const pg = foot.querySelector('.pg');
    const add = (t, p, dis, on) => { const b = document.createElement('button'); b.textContent = t; b.disabled = dis; if (on) b.className = 'on'; b.onclick = () => { page = p; draw(); }; pg.appendChild(b); };
    add('Prev', page - 1, page === 1);
    for (let p = 1; p <= pages; p++) if (pages <= 7 || Math.abs(p - page) < 2 || p === 1 || p === pages) add(p, p, false, p === page);
    add('Next', page + 1, page === pages);
  }
  draw();
});

// edit button on Students / Exams
const form = document.getElementById('entform');
if (form) {
  const cancel = document.getElementById('cancel'), title = document.getElementById('formtitle'), t0 = title.textContent;
  const reset = () => { form.reset(); form.editing.value = 0; form.elements[1].readOnly = false; cancel.hidden = true; title.textContent = t0; };
  document.querySelectorAll('[data-edit]').forEach(b => b.addEventListener('click', () => {
    const d = JSON.parse(b.dataset.edit);
    for (const k in d) if (form.elements[k]) form.elements[k].value = d[k] ?? '';
    form.editing.value = 1; form.elements[1].readOnly = true; cancel.hidden = false;
    title.textContent = 'Edit record'; form.scrollIntoView({behavior: 'smooth', block: 'center'});
  }));
  cancel.onclick = reset;
}

document.getElementById('result')?.scrollIntoView({block: 'start'});
