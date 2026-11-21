const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
async function api(url, opt = {}) {
  const r = await fetch(url, {headers: {'Content-Type': 'application/json'}, ...opt});
  if (!r.ok) { let m = r.statusText; try { m = (await r.json()).detail || m } catch {} throw new Error(m); }
  return r.json();
}
const post = (u, b) => api(u, {method: 'POST', body: JSON.stringify(b || {})});
function toast(t) { $('#toastTxt').textContent = t; const e = $('#toast'); e.style.opacity = 1; setTimeout(() => e.style.opacity = 0, 2200); }

let S = {}, st = {src: 'url', dur: '30-60', layout: 'split', count: 10, fileId: null, job: null, timer: null};

/* ---------- Bottom sheet ---------- */
function openSheet(html, mount) {
  $('#sheetBody').innerHTML = html; $('#ov').classList.remove('hidden');
  requestAnimationFrame(() => $('#sheet').classList.remove('translate-y-full'));
  mount && mount();
}
function closeSheet() {
  $('#sheet').classList.add('translate-y-full'); $('#ov').classList.add('hidden');
  $$('#sheetBody video').forEach(v => v.pause());
}
$('#ov').onclick = closeSheet;

/* ---------- Ajustes ---------- */
const SCHEMA = [
  ['#', '📂 Archivos'], ['out_dir', 'Carpeta de salida', 'text'], ['max_source_minutes', 'Máx. minutos a descargar del stream', 'number'],
  ['#', '🧠 IA'], ['whisper_model', 'Modelo Faster-Whisper', 'select', [['tiny', 'tiny (rápido)'], ['base', 'base (recomendado)'], ['small', 'small (preciso, lento)']]],
  ['language', 'Idioma del audio', 'select', [['auto', 'Automático'], ['es', 'Español'], ['en', 'Inglés']]],
  ['sensitivity', 'Sensibilidad IA (exigencia de viralidad)', 'range', [0, 100, 5]],
  ['#', '💬 Subtítulos (estilo Hormozi)'],
  ['sub_font', 'Tipografía', 'select', [['Montserrat', 'Montserrat'], ['DejaVu Sans', 'DejaVu Sans'], ['Liberation Sans', 'Liberation Sans']]],
  ['sub_color', 'Color del texto', 'color'], ['sub_active', 'Color palabra activa', 'color'],
  ['sub_position', 'Posición', 'select', [['bottom', 'Abajo'], ['center', 'Centro'], ['top', 'Arriba']]],
  ['sub_size', 'Tamaño', 'range', [50, 120, 2]],
  ['#', '🏷️ Marca de agua'], ['wm_user', 'Usuario de Kick', 'text'], ['wm_opacity', 'Opacidad', 'range', [0.1, 1, 0.05]],
  ['wm_pos', 'Esquina', 'select', [['tl', 'Arriba izquierda'], ['tr', 'Arriba derecha'], ['bl', 'Abajo izquierda'], ['br', 'Abajo derecha']]],
  ['#', '🎬 Predeterminados'],
  ['default_duration', 'Duración favorita', 'select', [['15-30', '15-30 s'], ['30-60', '30-60 s'], ['60-90', '60-90 s']]],
  ['default_layout', 'Layout inicial', 'select', [['split', 'Split Arriba/Abajo'], ['cam', 'Cámara sola']]],
  ['hashtags', 'Hashtags globales', 'textarea'],
  ['#', '🔊 Audio'], ['target_lufs', 'Volumen objetivo (LUFS)', 'number'], ['anti_fillers', 'Filtro anti-muletillas', 'check'],
  ['#', '🎨 Tema'], ['oled', 'Negro OLED puro', 'check'],
];
function field([k, l, t, o]) {
  if (k === '#') return `<div class="mt-8 mb-1 text-yellow-300 font-bold">${l}</div>`;
  const v = S[k], id = `s_${k}`;
  let inp;
  if (t === 'select') inp = `<select id="${id}" class="inp">${o.map(x => `<option value="${x[0]}" ${x[0] == v ? 'selected' : ''}>${x[1]}</option>`).join('')}</select>`;
  else if (t === 'range') inp = `<input id="${id}" type="range" min="${o[0]}" max="${o[1]}" step="${o[2]}" value="${v}"><div class="text-right text-xs text-zinc-500" id="${id}_v">${v}</div>`;
  else if (t === 'textarea') inp = `<textarea id="${id}" rows="2" class="inp py-3">${esc(v)}</textarea>`;
  else if (t === 'check') return `<label class="tgl mt-2">${l}<input id="${id}" type="checkbox" ${v ? 'checked' : ''}></label>`;
  else if (t === 'color') inp = `<input id="${id}" type="color" value="${v}" class="w-full h-12 rounded-2xl bg-zinc-900 border border-zinc-800">`;
  else inp = `<input id="${id}" type="${t}" class="inp" value="${esc(v)}">`;
  return `<label class="lbl">${l}</label>${inp}`;
}
function openSettings() {
  openSheet(`<h2 class="text-xl font-extrabold mb-2">⚙️ Ajustes</h2>${SCHEMA.map(field).join('')}
    <div class="grid grid-cols-2 gap-3 mt-8"><button id="sClean" class="btn btn-g">🧹 Borrar caché</button><button id="sSave" class="btn btn-y">Guardar</button></div>`, () => {
    $$('#sheetBody input[type=range]').forEach(r => r.oninput = () => $(`#${r.id}_v`).textContent = r.value);
    $('#sSave').onclick = async () => {
      const d = {};
      SCHEMA.forEach(([k, , t]) => { if (k === '#') return; const e = $(`#s_${k}`);
        d[k] = t === 'check' ? e.checked : (t === 'range' || t === 'number') ? Number(e.value) : e.value; });
      S = await post('/api/settings', d); applySettings(true); closeSheet(); toast('Ajustes guardados');
    };
    $('#sClean').onclick = async () => { try { await post('/api/cleanup'); toast('Caché borrada'); } catch (e) { toast(e.message); } };
  });
}
function applySettings(force) {
  document.body.classList.toggle('soft', !S.oled);
  if (force || !st.init) {
    st.dur = S.default_duration; st.layout = S.default_layout; st.init = true;
    $('#wmUser').value = S.wm_user || ''; mark('#gDur', st.dur); mark('#gLay', st.layout);
  }
}
function mark(g, v) { $$(`${g} .chip`).forEach(c => c.classList.toggle('on', c.dataset.v === v)); }

/* ---------- Home ---------- */
$('#btnSettings').onclick = openSettings;
$$('[data-src]').forEach(b => b.onclick = () => {
  st.src = b.dataset.src; $$('[data-src]').forEach(x => x.classList.toggle('on', x === b));
  $('#srcUrl').classList.toggle('hidden', st.src !== 'url'); $('#srcFile').classList.toggle('hidden', st.src !== 'file');
});
$$('#gDur .chip').forEach(c => c.onclick = () => { st.dur = c.dataset.v; mark('#gDur', st.dur); });
$$('#gLay .chip').forEach(c => c.onclick = () => { st.layout = c.dataset.v; mark('#gLay', st.layout); });
$('#cMinus').onclick = () => { st.count = Math.max(1, st.count - 1); $('#cnt').textContent = st.count; };
$('#cPlus').onclick = () => { st.count = Math.min(30, st.count + 1); $('#cnt').textContent = st.count; };
$('#btnPick').onclick = () => $('#file').click();
$('#file').onchange = () => {
  const f = $('#file').files[0]; if (!f) return;
  st.fileId = null; $('#upInfo').classList.remove('hidden'); $('#upName').textContent = f.name;
  const x = new XMLHttpRequest(), fd = new FormData(); fd.append('file', f);
  x.upload.onprogress = e => { if (e.lengthComputable) { const p = Math.round(e.loaded / e.total * 100); $('#upBar').style.width = p + '%'; $('#upPct').textContent = p + '%'; } };
  x.onload = () => { try { const r = JSON.parse(x.responseText); if (x.status >= 300) throw new Error(r.detail); st.fileId = r.file_id; $('#upPct').textContent = '✅ Listo'; } catch (e) { $('#upPct').textContent = '❌ ' + e.message; } };
  x.onerror = () => $('#upPct').textContent = '❌ Error de red';
  x.open('POST', '/api/upload'); x.send(fd);
};
$('#btnGo').onclick = async () => {
  const url = $('#url').value.trim();
  if (st.src === 'url' && !url) return toast('Pega una URL de Kick');
  if (st.src === 'file' && !st.fileId) return toast('Sube un archivo primero');
  try {
    const r = await post('/api/jobs', {
      url: st.src === 'url' ? url : null, file_id: st.src === 'file' ? st.fileId : null,
      start_min: Number($('#startMin').value) || 0, duration: st.dur, layout: st.layout, count: st.count,
      blur: $('#oBlur').checked, hook: $('#oHook').checked, fillers: $('#oFill').checked,
      progress_bar: $('#oBar').checked, stinger: $('#oSting').checked,
      wm_user: $('#wmUser').value.trim(), wm_opacity: S.wm_opacity, wm_pos: S.wm_pos});
    startJob(r.id);
  } catch (e) { toast(e.message); }
};

/* ---------- Vistas y polling ---------- */
function show(v) {
  ['home', 'progress', 'gallery', 'library', 'system'].forEach(x => $('#' + x).classList.toggle('hidden', x !== v));
  $('#homeBar').classList.toggle('hidden', v !== 'home');
  const tab = v === 'library' ? 'library' : v === 'system' ? 'system' : 'create';
  $$('[data-tab]').forEach(b => b.classList.toggle('on', b.dataset.tab === tab));
  window.scrollTo(0, 0);
}
function startJob(id) { st.job = id; localStorage.setItem('cf_job', id); show('progress'); poll(); }
async function poll() {
  clearTimeout(st.timer);
  let j; try { j = await api('/api/jobs/' + st.job); } catch { localStorage.removeItem('cf_job'); return show('home'); }
  $('#pMsg').textContent = j.message; $('#pBar').style.width = j.progress + '%'; $('#pPct').textContent = j.progress + '%';
  if (j.clips.length) { renderGallery(j); if ($('#gallery').classList.contains('hidden')) show('gallery'); }
  else if (['error', 'cancelled'].includes(j.status)) { renderGallery(j); show('gallery'); }
  const busy = !['done', 'error', 'cancelled'].includes(j.status) || j.clips.some(c => ['queued', 'rendering'].includes(c.status));
  if (busy) st.timer = setTimeout(poll, 1800);
}
$('#btnNew').onclick = () => { clearTimeout(st.timer); st.job = null; show('home'); };

/* ---------- Galería ---------- */
const keepPlaying = {};
function renderGallery(j) {
  st.cur = j;
  const clips = j.clips.filter(c => !c.trashed);
  $('#gTitle').textContent = j.status === 'done' ? `${clips.length} clips listos` : (j.status === 'error' ? 'Error' : j.status === 'cancelled' ? 'Cancelado' : j.message);
  $('#gSub').textContent = j.status === 'done' ? 'Toca ▶ para ver con audio' : `${j.progress}%`;
  const err = $('#gErr'); err.classList.toggle('hidden', !['error', 'cancelled'].includes(j.status)); err.textContent = (j.status === 'cancelled' ? '⛔ ' : '❌ ') + j.message;
  $('#btnCancel2').classList.toggle('hidden', ['done', 'error', 'cancelled'].includes(j.status));
  const z = $('#btnZip'); z.classList.toggle('hidden', !clips.some(c => c.status === 'ready')); z.href = `/api/jobs/${j.id}/zip`;
  const list = $('#list');
  // re-render solo tarjetas cuyo estado/versión cambió (no interrumpe videos en reproducción)
  clips.forEach(c => {
    const key = `${c.status}|${c.ver}|${c.start}|${c.end}`;
    let el = $(`#c-${c.id}`);
    if (!el) { el = document.createElement('article'); el.id = `c-${c.id}`; list.appendChild(el); }
    if (el.dataset.key !== key) { el.dataset.key = key; el.className = 'card'; el.innerHTML = cardHTML(c, j); bindCard(el, c, j); }
  });
  $$('#list > article').forEach(el => { if (!clips.some(c => `c-${c.id}` === el.id)) el.remove(); });
}
const fmt = t => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, '0')}`;
function cardHTML(c, j) {
  let media;
  if (c.status === 'ready') media = `<video src="/media/${j.id}/${c.file}" poster="/media/${j.id}/${c.thumb}" controls playsinline loop preload="metadata" class="w-full max-h-[75vh] bg-black object-contain"></video>`;
  else if (c.status === 'error') media = `<div class="h-48 flex items-center justify-center text-red-300 text-sm p-6 text-center">❌ ${esc(c.error)}</div>`;
  else media = `<div class="h-72 flex items-center justify-center gap-3 text-zinc-400"><div class="spin"></div>${c.status === 'queued' ? 'En cola…' : 'Renderizando…'}</div>`;
  const ready = c.status === 'ready', dis = ready ? '' : 'opacity-40 pointer-events-none';
  return `<div class="relative bg-black">${media}<span class="absolute top-3 left-3 bg-black/70 backdrop-blur px-3 py-1 rounded-full text-sm font-bold">🔥 ${c.score}</span></div>
  <div class="p-4">
    <div class="font-bold leading-snug">${esc(c.title) || 'Clip #' + (c.idx + 1)}</div>
    <div class="text-xs text-zinc-500 mt-1">${fmt(c.start)} → ${fmt(c.end)} · ${c.layout}</div>
    <div class="text-xs text-yellow-300/80 mt-2 break-words">${esc(c.tags)}</div>
    <div class="grid grid-cols-5 gap-2 mt-4 ${dis}">
      <a class="btn btn-y !px-0 !min-h-[52px]" href="/api/jobs/${j.id}/clips/${c.id}/download" title="Descargar">⬇</a>
      <button class="btn btn-g !px-0 !min-h-[52px]" data-a="mock" title="Vista previa móvil">📱</button>
      <button class="btn btn-g !px-0 !min-h-[52px]" data-a="edit" title="Editar">✂️</button>
      <button class="btn btn-g !px-0 !min-h-[52px]" data-a="reroll" title="Reroll">🎲</button>
      <button class="btn btn-g !px-0 !min-h-[52px]" data-a="trash" title="Descartar">🗑</button>
    </div>
    ${ready ? `<button class="text-xs text-zinc-500 mt-3 underline" data-a="copy">Copiar título + hashtags</button>` : ''}
  </div>`;
}
function bindCard(el, c, j) {
  const run = {
    mock: () => openMock(c, j), edit: () => openEditor(c, j),
    reroll: async () => { try { await post(`/api/jobs/${j.id}/clips/${c.id}/reroll`); toast('Buscando otro momento…'); poll(); } catch (e) { toast(e.message); } },
    trash: async () => { await post(`/api/jobs/${j.id}/clips/${c.id}/trash`); el.remove(); toast('Clip descartado'); poll(); },
    copy: () => { navigator.clipboard?.writeText(c.desc); toast('Copiado'); },
  };
  $$('[data-a]', el).forEach(b => b.onclick = run[b.dataset.a]);
  const v = $('video', el); if (v) v.addEventListener('play', () => $$('video').forEach(o => o !== v && o.pause()));
}

/* ---------- Mockup de smartphone ---------- */
function openMock(c, j) {
  openSheet(`<div class="mx-auto w-[260px] rounded-[44px] border-[10px] border-zinc-800 bg-black relative overflow-hidden shadow-2xl" style="aspect-ratio:9/19">
    <div class="absolute top-2 left-1/2 -translate-x-1/2 w-24 h-5 bg-zinc-800 rounded-full z-10"></div>
    <video src="/media/${j.id}/${c.file}" autoplay loop playsinline controls class="w-full h-full object-cover"></video>
    <div class="absolute right-2 bottom-24 flex flex-col gap-4 text-xl text-center pointer-events-none"><div>❤️<div class="text-[10px]">12.4K</div></div><div>💬<div class="text-[10px]">318</div></div><div>↗️<div class="text-[10px]">Share</div></div></div>
    <div class="absolute left-3 bottom-16 right-14 text-xs pointer-events-none drop-shadow"><b>@${esc((c.wm.user || 'tu_canal').replace('@', ''))}</b><div class="line-clamp-2">${esc(c.title)} <span class="text-sky-300">${esc(c.tags)}</span></div></div>
  </div><button class="btn btn-g w-full mt-5" onclick="closeSheet()">Cerrar</button>`);
}

/* ---------- Editor manual ---------- */
function openEditor(c, j) {
  const dur = j.info?.duration || 0, wm = c.wm, auto = !c.crop;
  openSheet(`<h2 class="text-xl font-extrabold">✂️ Editar clip</h2>
  <div class="grid grid-cols-2 gap-3"><div><label class="lbl">Inicio (seg)</label><input id="eS" type="number" step="0.5" min="0" max="${dur}" class="inp" value="${c.start}"></div>
  <div><label class="lbl">Fin (seg)</label><input id="eE" type="number" step="0.5" min="0" max="${dur}" class="inp" value="${c.end}"></div></div>
  <div class="grid grid-cols-2 gap-2 mt-2"><button class="chip" id="nS">Inicio −1s</button><button class="chip" id="pS">Inicio +1s</button><button class="chip" id="nE">Fin −1s</button><button class="chip" id="pE">Fin +1s</button></div>
  <label class="lbl">Layout</label><div class="grid grid-cols-2 gap-2" id="eL">${[['split', 'Split'], ['cam', 'Cámara sola'], ['podcast', 'Podcast'], ['original', 'Original']].map(x => `<button class="chip ${c.layout === x[0] ? 'on' : ''}" data-v="${x[0]}">${x[1]}</button>`).join('')}</div>
  <label class="lbl">Reencuadre</label><label class="tgl">Automático (seguimiento de rostro) <input type="checkbox" id="eAuto" ${auto ? 'checked' : ''}></label>
  <div id="eCrop" class="${auto ? 'hidden' : ''}"><label class="lbl">Centro horizontal</label><input type="range" id="eX" min="0" max="100" value="${c.crop?.x ?? 50}"><label class="lbl">Centro vertical</label><input type="range" id="eY" min="0" max="100" value="${c.crop?.y ?? 50}"></div>
  <label class="lbl">Marca de agua</label><input id="eU" class="inp" value="${esc(wm.user)}" placeholder="usuario">
  <input id="eO" type="range" min="0.1" max="1" step="0.05" value="${wm.opacity}">
  <div class="grid grid-cols-4 gap-2" id="eP">${[['tl', '↖'], ['tr', '↗'], ['bl', '↙'], ['br', '↘']].map(x => `<button class="chip ${wm.pos === x[0] ? 'on' : ''}" data-v="${x[0]}">${x[1]}</button>`).join('')}</div>
  <button id="eGo" class="btn btn-y w-full mt-6">Aplicar y re-renderizar</button>`, () => {
    let lay = c.layout, pos = wm.pos;
    const bindG = (g, set) => $$(`${g} .chip`).forEach(b => b.onclick = () => { set(b.dataset.v); $$(`${g} .chip`).forEach(x => x.classList.toggle('on', x === b)); });
    bindG('#eL', v => lay = v); bindG('#eP', v => pos = v);
    const bump = (id, d) => { const e = $(id); e.value = Math.max(0, +e.value + d); };
    $('#nS').onclick = () => bump('#eS', -1); $('#pS').onclick = () => bump('#eS', 1);
    $('#nE').onclick = () => bump('#eE', -1); $('#pE').onclick = () => bump('#eE', 1);
    $('#eAuto').onchange = e => $('#eCrop').classList.toggle('hidden', e.target.checked);
    $('#eGo').onclick = async () => {
      try {
        await post(`/api/jobs/${j.id}/clips/${c.id}/edit`, {
          start: +$('#eS').value, end: +$('#eE').value, layout: lay,
          crop: $('#eAuto').checked ? null : {x: +$('#eX').value, y: +$('#eY').value},
          wm: {user: $('#eU').value, opacity: +$('#eO').value, pos}});
        closeSheet(); toast('Re-renderizando…'); poll();
      } catch (e) { toast(e.message); }
    };
  });
}

/* ---------- Cancelar ---------- */
async function cancelJob() {
  if (!st.job || !confirm('¿Cancelar el trabajo? Los clips ya terminados se conservan.')) return;
  try { await post(`/api/jobs/${st.job}/cancel`); toast('Cancelando…'); poll(); } catch (e) { toast(e.message); }
}
$('#btnCancel').onclick = cancelJob; $('#btnCancel2').onclick = cancelJob;

/* ---------- Pestañas ---------- */
$$('[data-tab]').forEach(b => b.onclick = () => {
  const t = b.dataset.tab;
  if (t === 'library') { show('library'); loadLibrary(); }
  else if (t === 'system') { show('system'); loadSystem(); }
  else if (st.job) { show('progress'); poll(); } else show('home');
});

/* ---------- Biblioteca ---------- */
let libTimer;
async function loadLibrary() {
  const q = encodeURIComponent($('#libQ').value.trim()), l = $('#libL').value;
  let items = []; try { items = await api(`/api/library?q=${q}&layout=${l}`); } catch (e) { toast(e.message); }
  $('#libEmpty').classList.toggle('hidden', items.length > 0);
  $('#libList').innerHTML = items.map(c => `<article class="card" id="l-${c.id}">
    <button data-l="play" data-id="${c.id}" class="relative block w-full bg-black"><img src="/media/${c.job_id}/${c.thumb}" class="w-full aspect-[9/16] object-cover" loading="lazy"><span class="absolute bottom-2 right-2 bg-black/70 rounded-full px-2 py-0.5 text-xs">${fmt(c.duration)}</span><span class="absolute top-2 left-2 bg-black/70 rounded-full px-2 py-0.5 text-xs font-bold">🔥 ${c.score}</span></button>
    <div class="p-3"><div class="text-sm font-bold leading-tight line-clamp-2">${esc(c.title)}</div>
    <div class="text-[11px] text-zinc-500 mt-1">${new Date(c.created * 1000).toLocaleDateString()} · ${c.layout}</div>
    <div class="grid grid-cols-4 gap-1 mt-2">
      <a class="btn btn-y !min-h-[44px] !px-0 !text-sm" href="/api/jobs/${c.job_id}/clips/${c.id}/download">⬇</a>
      <button class="btn btn-g !min-h-[44px] !px-0 !text-sm" data-l="copy" data-id="${c.id}">📋</button>
      <button class="btn btn-g !min-h-[44px] !px-0 !text-sm" data-l="open" data-id="${c.id}">✂️</button>
      <button class="btn btn-g !min-h-[44px] !px-0 !text-sm" data-l="del" data-id="${c.id}">🗑</button></div></div></article>`).join('');
  const by = Object.fromEntries(items.map(c => [c.id, c]));
  $$('#libList [data-l]').forEach(b => b.onclick = async () => {
    const c = by[b.dataset.id], a = b.dataset.l;
    if (a === 'play') openSheet(`<video src="/media/${c.job_id}/${c.file}" controls autoplay playsinline loop class="w-full max-h-[75vh] bg-black rounded-2xl"></video><div class="font-bold mt-3">${esc(c.title)}</div><div class="text-xs text-yellow-300/80 mt-1">${esc(c.tags)}</div>`);
    if (a === 'copy') { navigator.clipboard?.writeText(`${c.title}\n\n${c.tags}`); toast('Título y hashtags copiados'); }
    if (a === 'open') startJob(c.job_id);
    if (a === 'del' && confirm('¿Eliminar este clip?')) { await post(`/api/jobs/${c.job_id}/clips/${c.id}/trash`); loadLibrary(); }
  });
}
$('#libQ').oninput = () => { clearTimeout(libTimer); libTimer = setTimeout(loadLibrary, 300); };
$('#libL').onchange = loadLibrary;

/* ---------- Diagnóstico ---------- */
async function loadSystem() {
  $('#sysSum').textContent = 'Revisando…';
  try {
    const d = await api('/api/diagnostics'), ic = {ok: '✅', warn: '⚠️', fail: '❌'};
    $('#sysSum').textContent = `${d.summary.ok} correctos · ${d.summary.warn} avisos · ${d.summary.fail} errores`;
    $('#sysList').innerHTML = d.checks.map(c => `<div class="card p-4"><div class="flex justify-between gap-3"><div class="font-semibold">${ic[c.status]} ${esc(c.name)}</div></div>
      <div class="text-sm text-zinc-400 mt-1 break-words">${esc(c.detail)}</div>${c.fix ? `<div class="text-xs text-yellow-300/80 mt-2">💡 ${esc(c.fix)}</div>` : ''}</div>`).join('');
  } catch (e) { $('#sysSum').textContent = '❌ ' + e.message; }
}
$('#sysRef').onclick = loadSystem;

/* ---------- Init ---------- */
(async () => {
  try { S = await api('/api/settings'); } catch { S = {}; }
  applySettings(true);
  const last = localStorage.getItem('cf_job');
  if (last) startJob(last);
})();
