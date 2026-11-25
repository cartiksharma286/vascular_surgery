'use strict';
/* Surgical Simulation Studio front end: dependency-free canvas rendering. */

const $ = id => document.getElementById(id);
const clamp = (x, lo, hi) => Math.min(hi, Math.max(lo, x));
const lerp = (a, b, t) => a + (b - a) * t;
const ease = t => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

function money(n) {
  if (n === null || n === undefined || !isFinite(n)) return '—';
  const a = Math.abs(n), s = n < 0 ? '−' : '';
  if (a >= 1e9) return `${s}$${(a / 1e9).toFixed(2)}B`;
  if (a >= 1e6) return `${s}$${(a / 1e6).toFixed(1)}M`;
  if (a >= 1e3) return `${s}$${(a / 1e3).toFixed(0)}k`;
  return `${s}$${a.toFixed(0)}`;
}
const pct = (x, d = 1) => (x === null || x === undefined ? '—' : `${(x * 100).toFixed(d)}%`);
const sci = x => (x === 0 ? '0' : Math.abs(x) < 0.01 || Math.abs(x) >= 1e4 ? x.toExponential(2) : x.toFixed(4));

async function api(path, body) {
  const opts = body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
  const res = await fetch(path, opts);
  const data = await res.json();
  if (!res.ok || data.success === false) throw new Error(data.error || 'Request failed');
  return data;
}

function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

/* ------------------------------------------------------------------ colour maps */
const INFERNO = [[0, 0, 4], [31, 12, 72], [85, 15, 109], [136, 34, 106], [186, 54, 85], [227, 89, 51], [249, 140, 10], [249, 201, 50], [252, 255, 164]];
const PLASMA = [[13, 8, 135], [84, 2, 163], [139, 10, 165], [185, 50, 137], [219, 92, 104], [244, 136, 73], [254, 188, 43], [240, 249, 33]];
const VIRIDIS = [[68, 1, 84], [72, 40, 120], [62, 74, 137], [49, 104, 142], [38, 130, 142], [31, 158, 137], [53, 183, 121], [109, 205, 89], [180, 222, 44], [253, 231, 37]];
function cmap(stops, t) {
  t = clamp(t, 0, 1) * (stops.length - 1);
  const i = Math.min(stops.length - 2, Math.floor(t)), f = t - i, a = stops[i], b = stops[i + 1];
  return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f];
}
const css = (c, a = 1) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a})`;

function fit(cv) {
  const r = window.devicePixelRatio || 1, w = cv.clientWidth, h = cv.clientHeight;
  if (w > 0 && h > 0 && (cv.width !== Math.round(w * r) || cv.height !== Math.round(h * r))) { cv.width = Math.round(w * r); cv.height = Math.round(h * r); }
  const ctx = cv.getContext('2d'); ctx.setTransform(1, 0, 0, 1, 0, 0);
  return { ctx, W: cv.width, H: cv.height, r };
}

/* ------------------------------------------------------------------- background */
(function bgfx() {
  const cv = $('bgfx'); if (!cv) return;
  const ctx = cv.getContext('2d'); let W, H, pts = [];
  function size() { W = cv.width = innerWidth; H = cv.height = innerHeight; pts = Array.from({ length: 110 }, () => ({ x: Math.random() * W, y: Math.random() * H, h: Math.random() })); ctx.fillStyle = '#050813'; ctx.fillRect(0, 0, W, H); }
  size(); addEventListener('resize', debounce(size, 200));
  function field(x, y, t) {
    const f1 = [W * (0.3 + 0.05 * Math.sin(t / 5)), H * 0.45], f2 = [W * (0.7 + 0.05 * Math.cos(t / 6)), H * 0.55];
    let vx = 0, vy = 0;
    for (const [f, s] of [[f1, 1], [f2, -1]]) { const dx = x - f[0], dy = y - f[1], r2 = dx * dx + dy * dy + 2500; vx += s * dx / r2; vy += s * dy / r2; }
    return [vx * 900, vy * 900];
  }
  let t = 0;
  function frame() {
    t += 0.016; ctx.fillStyle = 'rgba(5,8,19,0.07)'; ctx.fillRect(0, 0, W, H);
    for (const p of pts) {
      const [vx, vy] = field(p.x, p.y, t); const nx = p.x + vx, ny = p.y + vy;
      ctx.strokeStyle = `hsla(${190 + 120 * p.h},90%,65%,0.35)`; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(nx, ny); ctx.stroke();
      p.x = nx; p.y = ny; if (p.x < 0 || p.x > W || p.y < 0 || p.y > H || Math.random() < 0.004) { p.x = Math.random() * W; p.y = Math.random() * H; }
    }
    requestAnimationFrame(frame);
  }
  frame();
})();

/* ------------------------------------------------------------------------ tabs */
const tabLoaded = {};
document.querySelectorAll('#tabs button').forEach(b => b.addEventListener('click', () => showTab(b.dataset.tab)));
function showTab(name) {
  document.querySelectorAll('#tabs button').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  document.querySelectorAll('section.panel').forEach(s => s.classList.toggle('active', s.id === 'tab-' + name));
  if (!tabLoaded[name]) { tabLoaded[name] = true; ({ gi: initGi, stent: initStent, elliptic: initElliptic, ehr: initEhr, qml: initQml, econ: initEcon }[name] || (() => {}))(); }
  else requestAnimationFrame(() => ({ gi: () => bemData && drawBem($('bemCanvas'), bemData, bemMode), stent: () => femData && drawFemStatic(), elliptic: () => ellData && drawElliptic(), ehr: () => ehrData && drawEhr(), qml: () => qmlData && drawQml(), econ: () => econData && drawEcon() }[name] || (() => {}))());
}

/* ============================================================== BEM rendering */
function contourSegments(field, n, level) {
  const segs = [];
  for (let i = 0; i < n - 1; i++) for (let j = 0; j < n - 1; j++) {
    const v = [field[i][j], field[i][j + 1], field[i + 1][j + 1], field[i + 1][j]];
    if (v.some(x => x === null || x === undefined)) continue;
    const pts = [], P = [[j, i], [j + 1, i], [j + 1, i + 1], [j, i + 1]];
    for (let k = 0; k < 4; k++) {
      const a = v[k], b = v[(k + 1) % 4];
      if ((a < level) !== (b < level)) { const t = (level - a) / (b - a), p = P[k], q = P[(k + 1) % 4]; pts.push([p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t]); }
    }
    if (pts.length === 2) segs.push(pts); else if (pts.length === 4) { segs.push([pts[0], pts[1]]); segs.push([pts[2], pts[3]]); }
  }
  return segs;
}

function drawBem(cv, d, mode, opts = {}) {
  const { ctx, W, H, r } = fit(cv);
  ctx.clearRect(0, 0, W, H);
  const R = d.R, S = (Math.min(W, H) / 2 - 22 * r) / R, cx = W / 2, cy = H / 2, n = d.grid, field = mode === 'pot' ? d.u : d.heat;
  const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, R * S); g.addColorStop(0, '#0c1633'); g.addColorStop(1, '#060a18');
  ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, cy, R * S, 0, 7); ctx.fill();
  const off = document.createElement('canvas'); off.width = n; off.height = n; const octx = off.getContext('2d'), img = octx.createImageData(n, n);
  for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
    const v = field[i][j], p = ((n - 1 - i) * n + j) * 4;
    if (v === null || v === undefined) { img.data[p + 3] = 0; continue; }
    const t = mode === 'pot' ? clamp(v, 0, 1) : clamp((Math.log10(Math.max(v, 1e-4)) + 3) / 3, 0, 1), c = cmap(mode === 'pot' ? PLASMA : INFERNO, t);
    img.data[p] = c[0]; img.data[p + 1] = c[1]; img.data[p + 2] = c[2]; img.data[p + 3] = 255;
  }
  octx.putImageData(img, 0, 0);
  ctx.save(); ctx.beginPath(); ctx.arc(cx, cy, R * S, 0, 7); ctx.clip(); ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(off, cx - R * S - (S * 2 * R / (n - 1)) / 2, cy - R * S - (S * 2 * R / (n - 1)) / 2, 2 * R * S + S * 2 * R / (n - 1), 2 * R * S + S * 2 * R / (n - 1)); ctx.restore();
  const toXY = (j, i) => [cx + (-R + j / (n - 1) * 2 * R) * S, cy - (-R + i / (n - 1) * 2 * R) * S];
  // equipotentials
  ctx.lineWidth = 1 * r; ctx.strokeStyle = 'rgba(255,255,255,0.28)';
  for (let L = 0.1; L < 0.95; L += 0.1) { ctx.beginPath(); for (const [a, b] of contourSegments(d.u, n, L)) { const p = toXY(...a), q = toXY(...b); ctx.moveTo(p[0], p[1]); ctx.lineTo(q[0], q[1]); } ctx.stroke(); }
  // injury-zone contour
  ctx.save(); ctx.shadowColor = '#22d3ee'; ctx.shadowBlur = 12 * r; ctx.strokeStyle = '#22d3ee'; ctx.lineWidth = 2.2 * r; ctx.beginPath();
  for (const [a, b] of contourSegments(d.heat, n, d.heat_fraction)) { const p = toXY(...a), q = toXY(...b); ctx.moveTo(p[0], p[1]); ctx.lineTo(q[0], q[1]); } ctx.stroke(); ctx.restore();
  // current-density arrows (-grad u)
  const h = 2 * R / (n - 1); ctx.strokeStyle = 'rgba(255,255,255,0.6)'; ctx.fillStyle = 'rgba(255,255,255,0.6)'; ctx.lineWidth = 1.1 * r;
  const step = Math.max(4, Math.round(n / 14));
  for (let i = 2; i < n - 2; i += step) for (let j = 2; j < n - 2; j += step) {
    const u = d.u; if ([u[i][j + 1], u[i][j - 1], u[i + 1][j], u[i - 1][j], u[i][j]].some(x => x === null)) continue;
    const gx = -(u[i][j + 1] - u[i][j - 1]) / (2 * h), gy = -(u[i + 1][j] - u[i - 1][j]) / (2 * h), m = Math.hypot(gx, gy); if (m < 1e-6) continue;
    const L = clamp(Math.log10(m + 1) * 14 + 7, 6, 22) * r, [px, py] = toXY(j, i), ux = gx / m, uy = -gy / m;
    ctx.beginPath(); ctx.moveTo(px - ux * L / 2, py - uy * L / 2); ctx.lineTo(px + ux * L / 2, py + uy * L / 2); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(px + ux * L / 2, py + uy * L / 2); ctx.lineTo(px + ux * L / 2 - ux * 4 * r - uy * 2.6 * r, py + uy * L / 2 - uy * 4 * r + ux * 2.6 * r);
    ctx.lineTo(px + ux * L / 2 - ux * 4 * r + uy * 2.6 * r, py + uy * L / 2 - uy * 4 * r - ux * 2.6 * r); ctx.fill();
  }
  // boundaries
  ctx.save(); ctx.shadowColor = '#a78bfa'; ctx.shadowBlur = 16 * r; ctx.strokeStyle = '#a78bfa'; ctx.lineWidth = 3 * r; ctx.beginPath(); ctx.arc(cx, cy, R * S, 0, 7); ctx.stroke(); ctx.restore();
  const ex = cx + d.e * S, ea = d.a * S, eg = ctx.createRadialGradient(ex, cy, ea * 0.1, ex, cy, ea * 1.0); eg.addColorStop(0, '#fff'); eg.addColorStop(0.6, '#ffe9a8'); eg.addColorStop(1, '#fbbf24');
  ctx.save(); ctx.shadowColor = '#fbbf24'; ctx.shadowBlur = 24 * r; ctx.fillStyle = eg; ctx.beginPath(); ctx.arc(ex, cy, ea, 0, 7); ctx.fill(); ctx.restore();
  ctx.fillStyle = 'rgba(255,255,255,0.5)'; for (let k = 0; k < d.boundary.length; k += 3) { const p = d.boundary[k]; ctx.beginPath(); ctx.arc(cx + p[0] * S, cy - p[1] * S, 1.4 * r, 0, 7); ctx.fill(); }
  // lesion
  const L = d.lesion; ctx.save(); ctx.setLineDash([5 * r, 4 * r]); ctx.strokeStyle = '#34d399'; ctx.lineWidth = 2 * r; ctx.beginPath(); ctx.arc(cx + L.x * S, cy - L.y * S, L.r * S, 0, 7); ctx.stroke(); ctx.restore();
  ctx.fillStyle = '#34d399'; ctx.font = `${11 * r}px system-ui`; ctx.fillText('lesion', cx + (L.x + L.r) * S + 6 * r, cy - L.y * S + 4 * r);
  ctx.fillStyle = 'rgba(255,255,255,0.8)'; ctx.fillText('electrode', ex - ea * 0.8, cy + ea + 14 * r);
  ctx.fillStyle = '#a78bfa'; ctx.fillText('serosa (u = 0)', cx - 40 * r, cy - R * S - 8 * r + 2);
}

function bemLegend(mode, frac) {
  const grad = mode === 'pot' ? 'linear-gradient(90deg,#0d0887,#cc4778,#f0f921)' : 'linear-gradient(90deg,#000004,#ba3655,#fcffa4)';
  $('bemLegend').innerHTML = `<span><i style="background:${grad}"></i>${mode === 'pot' ? 'potential u' : 'Joule heating (log scale)'}</span><span><i style="background:#22d3ee"></i>injury zone (≥ ${(frac * 100).toFixed(0)}% of peak)</span><span><i style="background:#34d399"></i>target lesion</span><span><i style="background:#fff"></i>current arrows &amp; equipotentials</span>`;
}

/* ----------------------------------------------------------------- GI tab logic */
let bemData = null, bemMode = 'heat', bemSeq = 0, bemOptData = null;
async function loadBem() {
  const seq = ++bemSeq, a = +$('bemA').value, f = +$('bemF').value;
  $('bemE').max = Math.max(0, +(4 - a - 0.45).toFixed(2)); if (+$('bemE').value > +$('bemE').max) $('bemE').value = $('bemE').max;
  const e = +$('bemE').value;
  $('bemAv').textContent = a.toFixed(2) + ' mm'; $('bemEv').textContent = e.toFixed(2) + ' mm'; $('bemFv').textContent = (f * 100).toFixed(0) + '%';
  try {
    const d = await api('/api/bem', { R: 4.0, a, e, heat_fraction: f });
    if (seq !== bemSeq) return; bemData = d; $('bemErr').textContent = '';
    const m = d.metrics; $('mRho').textContent = m.log_rho.toFixed(4); $('mRes').textContent = `R_e = ${m.resistance.toFixed(4)} (normalized)`;
    $('mCur').textContent = m.current.toFixed(4); $('mCurS').textContent = `exact ${m.exact_current.toFixed(4)} · error ${(Math.abs(m.current - m.exact_current) / m.exact_current * 100).toFixed(2)}%`;
    $('mZone').textContent = pct(m.zone_fraction); $('mSero').textContent = pct(m.serosal_exposure, 0);
    $('mLes').textContent = pct(m.lesion_coverage, 0); $('mWin').innerHTML = d.within_window ? '<span class="pill ok">inside</span>' : '<span class="pill bad">outside</span>';
    $('mWinS').textContent = `R_e ∈ [${d.impedance_window[0]}, ${d.impedance_window[1]}]`;
    bemLegend(bemMode, f); drawBem($('bemCanvas'), d, bemMode);
  } catch (err) { if (seq === bemSeq) $('bemErr').textContent = err.message; }
}
const loadBemD = debounce(loadBem, 180);
function initGi() {
  ['bemA', 'bemE', 'bemF'].forEach(id => $(id).addEventListener('input', loadBemD));
  document.querySelectorAll('#bemMode button').forEach(b => b.addEventListener('click', () => { bemMode = b.dataset.m; document.querySelectorAll('#bemMode button').forEach(x => x.classList.toggle('on', x === b)); if (bemData) { bemLegend(bemMode, bemData.heat_fraction); drawBem($('bemCanvas'), bemData, bemMode); } }));
  $('bemOpt').addEventListener('click', runBemOpt);
  loadBem();
  api('/api/bem/verify').then(v => {
    const rows = v.convergence.map(r => `<tr><td>${r.n_inner}+${r.n_outer}</td><td>${r.current.toFixed(5)}</td><td>${r.exact.toFixed(5)}</td><td>${(r.relative_error * 100).toFixed(4)}%</td><td>${r.observed_order ? r.observed_order.toFixed(2) : '—'}</td></tr>`).join('');
    $('bemVerify').innerHTML = `<table><tr><th>Elements (el + out)</th><th>Current</th><th>Exact 2π/ln ρ</th><th>Error</th><th>Order</th></tr>${rows}</table><p class="note">Concentric ring: max potential error ${sci(v.concentric.max_potential_error)} vs V ln(R/r)/ln(R/a). Observed second-order convergence against the exact conformal modulus.</p>`;
  }).catch(e => { $('bemVerify').textContent = e.message; });
}
async function runBemOpt() {
  const btn = $('bemOpt'); btn.disabled = true; btn.innerHTML = '<span class="spin"></span>Optimizing…';
  try {
    const o = await api('/api/bem/optimize'); bemOptData = o; const ex = o.exhaustive, sa = o.annealing, b = o.baseline;
    const best = sa.J <= ex.J ? { a: sa.a, e: sa.e } : { a: ex.a, e: ex.e };
    $('bemOptOut').innerHTML = `<table><tr><th>Method</th><th>a</th><th>e</th><th>J</th><th>Evals</th></tr>
      <tr><td>Baseline (centred)</td><td>${b.a}</td><td>${b.e}</td><td>${b.J.toFixed(3)}</td><td>—</td></tr>
      <tr><td>Exhaustive grid</td><td>${ex.a}</td><td>${ex.e}</td><td>${ex.J.toFixed(3)}</td><td>${ex.evaluations}</td></tr>
      <tr><td>Simulated annealing</td><td>${sa.a}</td><td>${sa.e}</td><td>${sa.J.toFixed(3)}</td><td>${sa.evaluations}</td></tr></table>
      <p class="note">J = serosal exposure + 5·max(0, 0.9 − lesion coverage), within the impedance window. Annealing searches continuous offsets, so it can beat the coarse grid.</p>
      <div class="row"><button class="btn" id="bemApply">Apply best electrode</button></div>`;
    $('bemApply').addEventListener('click', () => { $('bemA').value = best.a; $('bemE').max = Math.max(0, +(4 - best.a - 0.45).toFixed(2)); $('bemE').value = best.e; loadBem(); });
  } catch (err) { $('bemOptOut').textContent = err.message; }
  btn.disabled = false; btn.innerHTML = '⚡ Optimize electrode';
}

/* ============================================================== FEM rendering */
let femData = null, femMode = 'deploy', femSeq = 0, femAnim = null, femPlaque = null, femState = { prog: 1, relax: 0 };
function prepFem(d) {
  const edge = new Map();
  d.tris.forEach((t, e) => { if (d.tag[e] !== 1) return; for (let k = 0; k < 3; k++) { const a = t[k], b = t[(k + 1) % 3], key = a < b ? a + '_' + b : b + '_' + a; edge.set(key, (edge.get(key) || 0) + 1); } });
  femPlaque = [...edge.entries()].filter(([, c]) => c === 1).map(([k]) => k.split('_').map(Number));
  d.vmax = Math.max(...d.vm_deploy.filter((v, i) => d.tag[i] !== 2)) * 1.05;
}
function drawFem(cv, d, st, mag = 4.5) {
  const { ctx, W, H, r } = fit(cv); ctx.clearRect(0, 0, W, H);
  const S = (Math.min(W, H) / 2 - 26 * r) / (d.ro * 1.06), cx = W / 2, cy = H / 2, n = d.nodes.length, P = new Array(n);
  for (let k = 0; k < n; k++) {
    const ud = d.u_deploy[k], ua = d.u_after[k];
    const ux = lerp(ud[0] * st.prog, ua[0] * st.prog, st.relax), uy = lerp(ud[1] * st.prog, ua[1] * st.prog, st.relax);
    P[k] = [cx + (d.nodes[k][0] + mag * ux) * S, cy - (d.nodes[k][1] + mag * uy) * S];
  }
  const halo = ctx.createRadialGradient(cx, cy, d.ri * S * 0.2, cx, cy, d.ro * S * 1.1); halo.addColorStop(0, 'rgba(34,211,238,0.07)'); halo.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = halo; ctx.fillRect(0, 0, W, H);
  d.tris.forEach((t, e) => {
    let c;
    if (d.tag[e] === 2) { const sh = 0.55 + 0.45 * Math.sin((t[0] % 24) / 24 * Math.PI * 2 + 1); c = [245 * sh + 10, 190 * sh + 20, 66 * sh + 10]; }
    else { const vm = lerp(d.vm_deploy[e] * st.prog, d.vm_after[e] * st.prog, st.relax); c = cmap(INFERNO, vm / d.vmax); if (d.tag[e] === 1) c = [c[0] * 0.9 + 6, c[1] * 0.95 + 14, c[2] * 0.95 + 22]; }
    ctx.fillStyle = css(c); ctx.strokeStyle = css(c); ctx.lineWidth = 0.6 * r;
    ctx.beginPath(); ctx.moveTo(...P[t[0]]); ctx.lineTo(...P[t[1]]); ctx.lineTo(...P[t[2]]); ctx.closePath(); ctx.fill(); ctx.stroke();
  });
  ctx.strokeStyle = 'rgba(255,255,255,0.06)'; ctx.lineWidth = 0.5 * r;
  for (let e = 0; e < d.tris.length; e += 2) { const t = d.tris[e]; ctx.beginPath(); ctx.moveTo(...P[t[0]]); ctx.lineTo(...P[t[1]]); ctx.lineTo(...P[t[2]]); ctx.closePath(); ctx.stroke(); }
  if (femPlaque && femPlaque.length) { ctx.save(); ctx.setLineDash([5 * r, 4 * r]); ctx.strokeStyle = '#22d3ee'; ctx.lineWidth = 1.8 * r; ctx.shadowColor = '#22d3ee'; ctx.shadowBlur = 8 * r; ctx.beginPath(); femPlaque.forEach(([a, b]) => { ctx.moveTo(...P[a]); ctx.lineTo(...P[b]); }); ctx.stroke(); ctx.restore(); }
  const nt = d.n_theta, lum = new Path2D(); for (let i = 0; i < nt; i++) { const p = P[i]; if (i === 0) lum.moveTo(p[0], p[1]); else lum.lineTo(p[0], p[1]); } lum.closePath();
  const lg = ctx.createRadialGradient(cx, cy, 0, cx, cy, d.ri * S * 1.1); lg.addColorStop(0, '#2a0b14'); lg.addColorStop(0.7, '#12040a'); lg.addColorStop(1, '#3a0f1b');
  ctx.fillStyle = lg; ctx.fill(lum); ctx.save(); ctx.strokeStyle = 'rgba(251,113,133,0.9)'; ctx.shadowColor = '#fb7185'; ctx.shadowBlur = 14 * r; ctx.lineWidth = 2 * r; ctx.stroke(lum); ctx.restore();
  ctx.fillStyle = 'rgba(255,255,255,0.8)'; ctx.font = `${12 * r}px system-ui`; ctx.textAlign = 'center'; ctx.fillText('lumen', cx, cy + 4 * r); ctx.textAlign = 'left';
}
function drawFemStatic() { if (!femData) return; femState = femMode === 'after' ? { prog: 1, relax: 1 } : { prog: 1, relax: 0 }; drawFem($('femCanvas'), femData, femState); $('femPhase').textContent = femMode === 'after' ? 'after recoil' : 'deployed (balloon inflated)'; }
function playFem() {
  if (!femData) return; cancelAnimationFrame(femAnim); const t0 = performance.now();
  const T1 = 1700, T2 = 500, T3 = 1700;
  function frame(now) {
    const t = now - t0; let prog = 1, relax = 0, label = 'balloon inflating…';
    if (t < T1) prog = ease(t / T1); else if (t < T1 + T2) label = 'deployed (hold)'; else if (t < T1 + T2 + T3) { relax = ease((t - T1 - T2) / T3); label = 'balloon withdrawn — tissue recoils against the stent'; }
    else { relax = 1; label = 'after recoil'; }
    femState = { prog, relax }; drawFem($('femCanvas'), femData, femState); $('femPhase').textContent = label;
    if (t < T1 + T2 + T3) femAnim = requestAnimationFrame(frame); else { femMode = 'after'; document.querySelectorAll('#femMode button').forEach(x => x.classList.toggle('on', x.dataset.m === 'after')); }
  }
  femAnim = requestAnimationFrame(frame);
}
async function loadFem(animate) {
  const seq = ++femSeq;
  const v = { n_struts: +$('fn').value, layers: +$('fl').value, target_gain: +$('fg').value, plaque_arc: +$('fa').value, plastic_fraction: +$('fp').value, stress_limit: +$('fs').value };
  $('fnV').textContent = v.n_struts; $('flV').textContent = v.layers; $('fgV').textContent = (v.target_gain * 100).toFixed(0) + '%'; $('faV').textContent = v.plaque_arc + '°'; $('fpV').textContent = v.plastic_fraction.toFixed(2); $('fsV').textContent = v.stress_limit.toFixed(2);
  try {
    const d = await api('/api/fem', v); if (seq !== femSeq) return; femData = d; prepFem(d); $('femErr').textContent = '';
    const m = d.metrics;
    $('fRet').textContent = pct(m.retained_gain_fraction, 1); $('fRetS').textContent = `no stent: ${pct(d.baseline_recoil_loss, 0)} retained · lumen area +${m.lumen_area_retained.toFixed(2)} mm²`;
    $('fOver').textContent = pct(m.overstress_fraction, 1); $('fMax').textContent = m.max_vm_tissue.toFixed(3); $('fMaxS').textContent = `MPa · limit ${m.stress_limit.toFixed(2)} MPa`; $('fMetal').textContent = m.metal_burden.toFixed(3);
    if (animate) playFem(); else drawFemStatic();
  } catch (err) { if (seq === femSeq) $('femErr').textContent = err.message; }
}
const loadFemD = debounce(() => loadFem(false), 200);
function initStent() {
  ['fn', 'fl', 'fg', 'fa', 'fp', 'fs'].forEach(id => $(id).addEventListener('input', loadFemD));
  document.querySelectorAll('#femMode button').forEach(b => b.addEventListener('click', () => { femMode = b.dataset.m; document.querySelectorAll('#femMode button').forEach(x => x.classList.toggle('on', x === b)); cancelAnimationFrame(femAnim); drawFemStatic(); }));
  $('femPlay').addEventListener('click', () => loadFem(true)); $('femOpt').addEventListener('click', runFemOpt);
  loadFem(true);
  api('/api/fem/verify').then(v => {
    const rows = v.lame.map(r => `<tr><td>${r.n_theta}</td><td>${r.graded_dof}</td><td>${(r.graded_error * 100).toFixed(3)}%</td><td>${(r.uniform_error * 100).toFixed(3)}%</td><td>${r.graded_order ? r.graded_order.toFixed(2) : '—'}</td></tr>`).join('');
    $('femVerify').innerHTML = `<table><tr><th>n<sub>θ</sub></th><th>DOF</th><th>Conformal grid error</th><th>Uniform grid error</th><th>Order</th></tr>${rows}</table><p class="note">Error in inner-wall displacement vs the exact Lamé solution (thick cylinder, plane strain). The conformal (geometric) radial grading beats a uniform radial grid at equal DOF.</p>`;
  }).catch(e => { $('femVerify').textContent = e.message; });
}
async function runFemOpt() {
  const btn = $('femOpt'); btn.disabled = true; btn.innerHTML = '<span class="spin"></span>Optimizing…';
  try {
    const o = await api('/api/fem/optimize'), ex = o.exhaustive, sa = o.annealing, em = o.elliptic_modulus, b = o.baseline;
    const sens = o.weight_sensitivity.map(r => `<tr><td>${r.w_metal}</td><td>${r.n_struts}</td><td>${r.layers}</td><td>${pct(r.recoil_loss, 2)}</td><td>${r.metal_burden.toFixed(3)}</td></tr>`).join('');
    $('femOptOut').innerHTML = `<table><tr><th>Method</th><th>Struts</th><th>Layers</th><th>J</th><th>Evals</th></tr>
      <tr><td>Baseline</td><td>${b.n_struts}</td><td>${b.layers}</td><td>${b.J.toFixed(4)}</td><td>—</td></tr>
      <tr><td>Exhaustive</td><td>${ex.n_struts}</td><td>${ex.layers}</td><td>${ex.J.toFixed(4)}</td><td>${ex.evaluations}</td></tr>
      <tr><td>Simulated annealing</td><td>${sa.n_struts}</td><td>${sa.layers}</td><td>${sa.J.toFixed(4)}</td><td>${sa.evaluations}</td></tr>
      <tr><td>Golden section in k</td><td>${em.n_struts_continuous.toFixed(2)}</td><td>${em.layers}</td><td>${em.J.toFixed(4)}</td><td>${em.evaluations}</td></tr></table>
      <p class="note">Elliptic coordinate: k = ${em.k.toFixed(3)}, K′/K = ${em.ratio_Kp_over_K.toFixed(3)} → n(k) = ${em.n_struts_continuous.toFixed(2)} struts.</p>
      <h3 style="margin-top:10px">Sensitivity to the metal-burden weight</h3><table><tr><th>w<sub>metal</sub></th><th>Struts</th><th>Layers</th><th>Recoil</th><th>Burden</th></tr>${sens}</table>
      <p class="note">The optimum sits at the 6-strut design bound for most weightings: it is a constraint-limited, assumption-dependent result.</p>
      <div class="row"><button class="btn" id="femApply">Apply exhaustive optimum</button></div>`;
    $('femApply').addEventListener('click', () => { $('fn').value = ex.n_struts; $('fl').value = ex.layers; loadFem(true); });
  } catch (err) { $('femOptOut').textContent = err.message; }
  btn.disabled = false; btn.innerHTML = '⚡ Optimize stent';
}

/* ============================================================ elliptic tab */
let ellData = null, ellSeq = 0;
function drawRing(cv, radii, nTheta, ro, palette) {
  const { ctx, W, H, r } = fit(cv); ctx.clearRect(0, 0, W, H); const S = (Math.min(W, H) / 2 - 16 * r) / ro, cx = W / 2, cy = H / 2, nr = radii.length - 1;
  for (let j = 0; j < nr; j++) for (let i = 0; i < nTheta; i++) {
    const a0 = i / nTheta * 2 * Math.PI, a1 = (i + 1) / nTheta * 2 * Math.PI, t = j / Math.max(1, nr - 1), c = cmap(palette, 0.15 + 0.7 * t);
    ctx.fillStyle = css(c, (i + j) % 2 ? 0.5 : 0.28); ctx.beginPath(); ctx.arc(cx, cy, radii[j + 1] * S, a0, a1); ctx.arc(cx, cy, radii[j] * S, a1, a0, true); ctx.closePath(); ctx.fill();
  }
  ctx.strokeStyle = 'rgba(255,255,255,0.35)'; ctx.lineWidth = 0.8 * r;
  radii.forEach(rad => { ctx.beginPath(); ctx.arc(cx, cy, rad * S, 0, 7); ctx.stroke(); });
  for (let i = 0; i < nTheta; i++) { const a = i / nTheta * 2 * Math.PI; ctx.beginPath(); ctx.moveTo(cx + radii[0] * S * Math.cos(a), cy - radii[0] * S * Math.sin(a)); ctx.lineTo(cx + ro * S * Math.cos(a), cy - ro * S * Math.sin(a)); ctx.stroke(); }
}
function drawElliptic() {
  const d = ellData; drawRing($('ellConf'), d.conformal_radii, d.n_theta, d.ro, VIRIDIS); drawRing($('ellUni'), d.uniform_radii, d.n_theta, d.ro, PLASMA);
  const uAspect = (d.uniform_radii[1] - d.uniform_radii[0]) / (d.ri * 2 * Math.PI / d.n_theta), lastU = (d.uniform_radii[d.n_r] - d.uniform_radii[d.n_r - 1]) / (d.ro * 2 * Math.PI / d.n_theta);
  $('ellConfN').innerHTML = `n<sub>r</sub> = ${d.n_r}: every cell is conformally ${d.conformal_aspect.toFixed(3)} : 1 (square in ln r, θ). Ring modulus ln(r<sub>o</sub>/r<sub>i</sub>)/2π = ${d.annulus_modulus.toFixed(4)}.`;
  $('ellUniN').innerHTML = `Cell aspect varies from ${uAspect.toFixed(2)} (inner) to ${lastU.toFixed(2)} (outer): thin tall cells at the lumen, wide flat cells outside.`;
  const { ctx, W, H, r } = fit($('ellCurve')); ctx.clearRect(0, 0, W, H); const m = 40 * r, pw = W - 2 * m, ph = H - 2 * m, c = d.curve;
  const maxR = Math.max(...c.ratio), maxS = Math.max(...c.struts), X = k => m + k * pw, YR = v => H - m - v / maxR * ph, YS = v => H - m - v / maxS * ph;
  ctx.strokeStyle = 'rgba(255,255,255,0.15)'; ctx.lineWidth = r; ctx.strokeRect(m, m, pw, ph); ctx.fillStyle = '#8fa0c8'; ctx.font = `${11 * r}px system-ui`;
  for (let i = 0; i <= 5; i++) { const x = m + i / 5 * pw; ctx.fillText((i / 5).toFixed(1), x - 8 * r, H - m + 16 * r); ctx.strokeStyle = 'rgba(255,255,255,0.06)'; ctx.beginPath(); ctx.moveTo(x, m); ctx.lineTo(x, H - m); ctx.stroke(); }
  ctx.fillText('modulus k →', W / 2 - 30 * r, H - 8 * r);
  const line = (ys, color, fy) => { ctx.save(); ctx.strokeStyle = color; ctx.shadowColor = color; ctx.shadowBlur = 8 * r; ctx.lineWidth = 2.4 * r; ctx.beginPath(); ys.forEach((v, i) => i ? ctx.lineTo(X(c.k[i]), fy(v)) : ctx.moveTo(X(c.k[i]), fy(v))); ctx.stroke(); ctx.restore(); };
  line(c.ratio, '#22d3ee', YR); line(c.struts, '#fbbf24', YS);
  const kx = X(d.current.k); ctx.strokeStyle = 'rgba(255,255,255,0.6)'; ctx.setLineDash([4 * r, 4 * r]); ctx.beginPath(); ctx.moveTo(kx, m); ctx.lineTo(kx, H - m); ctx.stroke(); ctx.setLineDash([]);
  [[YR(d.current.ratio), '#22d3ee'], [YS(d.current.struts), '#fbbf24']].forEach(([y, col]) => { ctx.fillStyle = col; ctx.beginPath(); ctx.arc(kx, y, 6 * r, 0, 7); ctx.fill(); });
}
async function loadElliptic() {
  const seq = ++ellSeq, ratio = +$('eR').value, nT = +$('eN').value, k = +$('eK').value;
  $('eRv').textContent = ratio.toFixed(1); $('eNv').textContent = nT; $('eKv').textContent = k.toFixed(2);
  try {
    const d = await api('/api/elliptic', { ri: 1.5, ro: 1.5 * ratio, n_theta: nT, k }); if (seq !== ellSeq) return; ellData = d; $('ellErr').textContent = '';
    const t = (kk, vv, ss) => `<div class="tile ${ss}"><div class="k">${kk}</div><div class="v" style="font-size:20px">${vv}</div></div>`;
    $('ellTiles').innerHTML = t('K′/K', d.current.ratio.toFixed(4), 'cyan') + t('K, K′', `${d.current.K.toFixed(3)}, ${d.current.K_prime.toFixed(3)}`, 'violet') + t('RECT. ASPECT 2K/K′', d.current.aspect.toFixed(3), 'green') + t('STRUTS n(k)', d.current.struts.toFixed(2), 'amber');
    $('ellTable').innerHTML = `<table><tr><th>K′/K</th><th>k</th><th>K</th><th>K′</th></tr>${d.table.map(r => `<tr><td>${r.ratio}</td><td>${r.k.toFixed(6)}</td><td>${r.K.toFixed(5)}</td><td>${r.K_prime.toFixed(5)}</td></tr>`).join('')}</table><p class="note">Square rectangle: k = (√2 − 1)² = ${d.square_modulus.toFixed(6)}.</p>`;
    drawElliptic();
  } catch (err) { if (seq === ellSeq) $('ellErr').textContent = err.message; }
}
function initElliptic() { ['eR', 'eN', 'eK'].forEach(id => $(id).addEventListener('input', debounce(loadElliptic, 120))); loadElliptic(); }

/* ================================================================== EHR tab */
let ehrData = null, ehrSeq = 0;
function hue(id) { return (id * 47) % 360; }
function drawEhr() {
  const d = ehrData; let { ctx, W, H, r } = fit($('ehrNet')); ctx.clearRect(0, 0, W, H);
  const groups = new Map(); d.nodes.forEach(n => { if (!groups.has(n.entity)) groups.set(n.entity, []); groups.get(n.entity).push(n); });
  const keys = [...groups.keys()], cols = Math.ceil(Math.sqrt(keys.length * W / H)), rows = Math.ceil(keys.length / cols), cw = W / cols, ch = H / rows, pos = new Map();
  keys.forEach((k, gi) => { const gx = (gi % cols + 0.5) * cw, gy = (Math.floor(gi / cols) + 0.5) * ch, m = groups.get(k), rad = Math.min(cw, ch) * 0.26; m.forEach((n, i) => { const a = i / m.length * 2 * Math.PI + 0.6; pos.set(n.id, [gx + (m.length > 1 ? rad * Math.cos(a) : 0), gy + (m.length > 1 ? rad * Math.sin(a) : 0)]); }); });
  const colr = { tp: '#34d399', fp: '#fb7185', fn: '#fbbf24' };
  d.edges.forEach(e => { const a = pos.get(e.a), b = pos.get(e.b); if (!a || !b) return; ctx.save(); ctx.strokeStyle = colr[e.kind]; ctx.lineWidth = (e.kind === 'fn' ? 1.6 : 2.2) * r; if (e.kind === 'fn') ctx.setLineDash([5 * r, 4 * r]); ctx.shadowColor = colr[e.kind]; ctx.shadowBlur = 6 * r; ctx.beginPath(); ctx.moveTo(...a); ctx.lineTo(...b); ctx.stroke(); ctx.restore(); });
  d.nodes.forEach(n => { const p = pos.get(n.id); ctx.fillStyle = `hsl(${hue(n.cluster)},85%,62%)`; ctx.beginPath(); ctx.arc(p[0], p[1], 5.5 * r, 0, 7); ctx.fill(); ctx.strokeStyle = 'rgba(0,0,0,0.5)'; ctx.lineWidth = r; ctx.stroke(); });
  // PR curve
  ({ ctx, W, H, r } = fit($('ehrPR'))); ctx.clearRect(0, 0, W, H); const m = 34 * r, pw = W - 2 * m, ph = H - 2 * m, cv = d.curve, X = t => m + (t - 0.6) / 0.38 * pw, Y = v => H - m - v * ph;
  ctx.strokeStyle = 'rgba(255,255,255,0.15)'; ctx.strokeRect(m, m, pw, ph); ctx.fillStyle = '#8fa0c8'; ctx.font = `${10 * r}px system-ui`;
  for (let v = 0; v <= 1; v += 0.25) { ctx.fillText(v.toFixed(2), 2 * r, Y(v) + 3 * r); ctx.strokeStyle = 'rgba(255,255,255,0.06)'; ctx.beginPath(); ctx.moveTo(m, Y(v)); ctx.lineTo(W - m, Y(v)); ctx.stroke(); }
  [['precision', '#34d399'], ['recall', '#22d3ee'], ['f1', '#a78bfa']].forEach(([k, c]) => { ctx.save(); ctx.strokeStyle = c; ctx.shadowColor = c; ctx.shadowBlur = 6 * r; ctx.lineWidth = 2.2 * r; ctx.beginPath(); cv.forEach((p, i) => i ? ctx.lineTo(X(p.threshold), Y(p[k])) : ctx.moveTo(X(p.threshold), Y(p[k]))); ctx.stroke(); ctx.restore(); });
  const tx = X(d.metrics.threshold); ctx.strokeStyle = '#fff'; ctx.setLineDash([4 * r, 4 * r]); ctx.beginPath(); ctx.moveTo(tx, m); ctx.lineTo(tx, H - m); ctx.stroke(); ctx.setLineDash([]);
  ctx.fillStyle = '#34d399'; ctx.fillText('● precision', m, 14 * r); ctx.fillStyle = '#22d3ee'; ctx.fillText('● recall', m + 80 * r, 14 * r); ctx.fillStyle = '#a78bfa'; ctx.fillText('● F1', m + 150 * r, 14 * r);
  // Gantt
  const s = d.schedule; ({ ctx, W, H, r } = fit($('ehrGantt'))); ctx.clearRect(0, 0, W, H);
  const maxT = Math.max(...s.segments.map(x => x.end)) * 1.04, lm = 70 * r, tm = 26 * r, rh = (H - tm - 14 * r) / s.rooms, X2 = t => lm + t / maxT * (W - lm - 14 * r);
  ctx.fillStyle = '#8fa0c8'; ctx.font = `${11 * r}px system-ui`; for (let t = 0; t <= maxT; t += 120) { ctx.fillText(`${t / 60}h`, X2(t) - 6 * r, 16 * r); ctx.strokeStyle = 'rgba(255,255,255,0.07)'; ctx.beginPath(); ctx.moveTo(X2(t), tm - 6 * r); ctx.lineTo(X2(t), H - 10 * r); ctx.stroke(); }
  for (let k = 0; k < s.rooms; k++) ctx.fillText(`OR ${k + 1}`, 8 * r, tm + k * rh + rh / 2 + 4 * r);
  s.segments.forEach(g => {
    const y = tm + g.room * rh + 5 * r, h = rh - 10 * r, c = g.weight >= 5 ? '#e879f9' : g.weight >= 2 ? '#a78bfa' : '#22d3ee', late = g.end > g.due;
    const gr = ctx.createLinearGradient(0, y, 0, y + h); gr.addColorStop(0, c); gr.addColorStop(1, 'rgba(20,30,70,0.9)'); ctx.fillStyle = gr; ctx.beginPath(); ctx.roundRect(X2(g.start), y, X2(g.end) - X2(g.start) - 1.5 * r, h, 6 * r); ctx.fill();
    if (late) { ctx.strokeStyle = '#fb7185'; ctx.lineWidth = 2 * r; ctx.stroke(); }
    ctx.fillStyle = '#fff'; ctx.fillText(`#${g.id}`, X2(g.start) + 5 * r, y + h / 2 + 4 * r);
    ctx.fillStyle = '#fbbf24'; ctx.beginPath(); ctx.moveTo(X2(g.due), y - 1 * r); ctx.lineTo(X2(g.due) - 4 * r, y - 7 * r); ctx.lineTo(X2(g.due) + 4 * r, y - 7 * r); ctx.fill();
  });
}
async function loadEhr() {
  const seq = ++ehrSeq, v = { n: +$('hn').value, dup_rate: +$('hd').value, threshold: +$('ht').value, seed: +$('hs').value };
  $('hnV').textContent = v.n; $('hdV').textContent = pct(v.dup_rate, 0); $('htV').textContent = v.threshold.toFixed(2); $('hsV').textContent = v.seed;
  try {
    const d = await api('/api/ehr', v); if (seq !== ehrSeq) return; ehrData = d; $('ehrErr').textContent = '';
    $('hF1').textContent = d.metrics.f1.toFixed(3); $('hPR').textContent = `precision ${pct(d.metrics.precision, 1)} · recall ${pct(d.metrics.recall, 1)}`;
    $('hRR').textContent = pct(d.reduction_ratio, 2); $('hRRS').textContent = `${d.candidate_pairs.toLocaleString()} of ${d.total_pairs.toLocaleString()} pairs compared`;
    $('hSG').textContent = pct(d.schedule.improvement_vs_best_rule, 0); $('hSGS').textContent = 'tardiness cut vs best priority rule';
    $('hEnt').textContent = `${d.predicted_entities} / ${d.entities}`; $('hEntS').textContent = `${d.n_records} records → predicted / true patients`;
    const sc = d.schedule; $('ehrRules').innerHTML = `Weighted tardiness (minutes·weight): FIFO ${sc.rules.FIFO.toFixed(0)} · EDD ${sc.rules.EDD.toFixed(0)} · WSPT ${sc.rules.WSPT.toFixed(0)} · <b>annealing ${sc.annealing.toFixed(0)}</b> (best rule: ${sc.best_rule}).`;
    drawEhr();
  } catch (err) { if (seq === ehrSeq) $('ehrErr').textContent = err.message; }
}
function initEhr() { ['hn', 'hd', 'ht', 'hs'].forEach(id => $(id).addEventListener('input', debounce(loadEhr, 220))); loadEhr(); }

/* ================================================================ economics */
let econData = null, ecCtx = 'us_canada', ecPrism = 'mc';
const REG_COLORS = { us: '#22d3ee', canada: '#60a5fa', japan: '#e879f9', china: '#fb7185', india: '#fbbf24', australia: '#34d399' };
function axisBox(ctx, W, H, r, m) { ctx.strokeStyle = 'rgba(255,255,255,0.14)'; ctx.lineWidth = r; ctx.strokeRect(m.l, m.t, W - m.l - m.r, H - m.t - m.b); }
function drawFan() {
  const c = econData.contexts[ecCtx], { ctx, W, H, r } = fit($('ecFan')); ctx.clearRect(0, 0, W, H);
  const m = { l: 62 * r, r: 16 * r, t: 16 * r, b: 30 * r }, fan = c.revenue_fan, ymax = Math.max(...fan.p95) * 1.08, X = i => m.l + i / 9 * (W - m.l - m.r), Y = v => H - m.b - v / ymax * (H - m.t - m.b);
  axisBox(ctx, W, H, r, m); ctx.font = `${11 * r}px system-ui`; ctx.fillStyle = '#8fa0c8';
  for (let k = 0; k <= 4; k++) { const v = ymax * k / 4; ctx.fillText(money(v), 4 * r, Y(v) + 4 * r); ctx.strokeStyle = 'rgba(255,255,255,0.06)'; ctx.beginPath(); ctx.moveTo(m.l, Y(v)); ctx.lineTo(W - m.r, Y(v)); ctx.stroke(); }
  for (let i = 0; i < 10; i++) ctx.fillText(`Y${i + 1}`, X(i) - 8 * r, H - 8 * r);
  const g = ctx.createLinearGradient(0, m.t, 0, H - m.b); g.addColorStop(0, 'rgba(34,211,238,0.45)'); g.addColorStop(1, 'rgba(167,139,250,0.12)');
  ctx.fillStyle = g; ctx.beginPath(); fan.p95.forEach((v, i) => i ? ctx.lineTo(X(i), Y(v)) : ctx.moveTo(X(i), Y(v))); for (let i = 9; i >= 0; i--) ctx.lineTo(X(i), Y(fan.p5[i])); ctx.closePath(); ctx.fill();
  const line = (arr, col, dash, w = 2.4) => { ctx.save(); ctx.strokeStyle = col; ctx.lineWidth = w * r; ctx.shadowColor = col; ctx.shadowBlur = 8 * r; if (dash) ctx.setLineDash([6 * r, 5 * r]); ctx.beginPath(); arr.forEach((v, i) => i ? ctx.lineTo(X(i), Y(v)) : ctx.moveTo(X(i), Y(v))); ctx.stroke(); ctx.restore(); };
  line(fan.p50, '#22d3ee', false); line(c.revenue, '#fbbf24', true);
  $('fanTitle').textContent = `Annual revenue fan chart · ${ecCtx === 'us_canada' ? 'US & Canada' : 'Asia-Pacific'}`;
  $('fanLegend').innerHTML = '<span><i style="background:rgba(34,211,238,.5)"></i>Monte Carlo 5–95%</span><span><i style="background:#22d3ee"></i>median</span><span><i style="background:#fbbf24"></i>deterministic base</span>';
}
function forestRows() {
  const regs = econData.contexts[ecCtx].members, R = econData.regions;
  if (ecPrism === 'scenario') return { title: '10-year cumulative revenue · low / base / high scenarios', fmt: money, rows: regs.map(k => ({ k, lo: R[k].scenarios.low.revenue_10y, mid: R[k].scenarios.base.revenue_10y, hi: R[k].scenarios.high.revenue_10y })), legend: 'low · base · high' };
  if (ecPrism === 'mc') return { title: 'Monte Carlo NPV · P5–P95 and median', fmt: money, zero: true, rows: regs.map(k => ({ k, lo: R[k].monte_carlo.npv.p5, mid: R[k].monte_carlo.npv.p50, hi: R[k].monte_carlo.npv.p95 })), legend: 'P5 · P50 · P95' };
  if (ecPrism === 'boot') return { title: 'Pilot volume at month 48 · bootstrap vs regression interval (relative to point)', fmt: v => v.toFixed(2) + '×', two: true, rows: regs.map(k => ({ k, lo: R[k].bootstrap.p5 / R[k].regression.point, mid: 1, hi: R[k].bootstrap.p95 / R[k].regression.point, lo2: R[k].regression.p5 / R[k].regression.point, hi2: R[k].regression.p95 / R[k].regression.point })), legend: 'bootstrap (top) · analytic prediction interval (bottom)' };
  return { title: 'Bayesian per-site adoption · posterior mean and 90% credible interval', fmt: v => (v * 100).toFixed(0) + '%', ref: econData.lines.ehr.smax, rows: regs.map(k => ({ k, lo: R[k].bayes.cri_low, mid: R[k].bayes.posterior_mean, hi: R[k].bayes.cri_high })), legend: 'posterior · assumed ceiling marked' };
}
function drawForest() {
  const f = forestRows(), { ctx, W, H, r } = fit($('ecForest')); ctx.clearRect(0, 0, W, H); $('forestTitle').textContent = f.title;
  const m = { l: 92 * r, r: 24 * r, t: 14 * r, b: 30 * r }, vals = f.rows.flatMap(x => [x.lo, x.hi, x.lo2 ?? x.lo, x.hi2 ?? x.hi, x.mid]).concat(f.ref ? [f.ref] : []).concat(f.zero ? [0] : []);
  let lo = Math.min(...vals), hi = Math.max(...vals); const pad = (hi - lo) * 0.08 || 1; lo -= pad; hi += pad; const X = v => m.l + (v - lo) / (hi - lo) * (W - m.l - m.r), rh = (H - m.t - m.b) / f.rows.length;
  axisBox(ctx, W, H, r, m); ctx.font = `${11 * r}px system-ui`;
  for (let k = 0; k <= 4; k++) { const v = lo + (hi - lo) * k / 4; ctx.fillStyle = '#8fa0c8'; ctx.fillText(f.fmt(v), X(v) - 16 * r, H - 10 * r); ctx.strokeStyle = 'rgba(255,255,255,0.06)'; ctx.beginPath(); ctx.moveTo(X(v), m.t); ctx.lineTo(X(v), H - m.b); ctx.stroke(); }
  if (f.zero) { ctx.strokeStyle = 'rgba(251,113,133,0.7)'; ctx.setLineDash([4 * r, 4 * r]); ctx.beginPath(); ctx.moveTo(X(0), m.t); ctx.lineTo(X(0), H - m.b); ctx.stroke(); ctx.setLineDash([]); }
  if (f.ref !== undefined) { ctx.strokeStyle = 'rgba(251,191,36,0.9)'; ctx.setLineDash([4 * r, 4 * r]); ctx.beginPath(); ctx.moveTo(X(f.ref), m.t); ctx.lineTo(X(f.ref), H - m.b); ctx.stroke(); ctx.setLineDash([]); ctx.fillStyle = '#fbbf24'; ctx.fillText('assumed', X(f.ref) + 4 * r, m.t + 12 * r); }
  f.rows.forEach((row, i) => {
    const y = m.t + rh * (i + 0.5), col = REG_COLORS[row.k]; ctx.fillStyle = '#e8eeff'; ctx.fillText(econData.regions[row.k].name, 8 * r, y + 4 * r);
    const bar = (a, b, yy, c) => { const g = ctx.createLinearGradient(X(a), 0, X(b), 0); g.addColorStop(0, c + '55'); g.addColorStop(0.5, c); g.addColorStop(1, c + '55'); ctx.fillStyle = g; ctx.beginPath(); ctx.roundRect(X(a), yy - 6 * r, Math.max(3 * r, X(b) - X(a)), 12 * r, 6 * r); ctx.fill(); };
    if (f.two) { bar(row.lo, row.hi, y - 8 * r, col); bar(row.lo2, row.hi2, y + 8 * r, '#a78bfa'); } else bar(row.lo, row.hi, y, col);
    ctx.save(); ctx.fillStyle = '#fff'; ctx.shadowColor = '#fff'; ctx.shadowBlur = 8 * r; ctx.beginPath(); ctx.arc(X(row.mid), y, 4.5 * r, 0, 7); ctx.fill(); ctx.restore();
  });
  $('forestLegend').innerHTML = `<span>${f.legend}</span>`;
}
function renderEconTable() {
  const regs = econData.contexts[ecCtx].members, R = econData.regions, V = econData.value_ratios, CEA = econData.cea;
  $('ecTable').innerHTML = `<table><tr><th>Region</th><th>10-yr revenue</th><th>EBITDA (10y)</th><th>NPV</th><th>EV</th><th>Payback</th><th>MC NPV P5/P95</th><th>QALYs (10y)</th><th>ICER</th><th>NMB (10y)</th><th>Payer ROI</th></tr>${regs.map(k => { const x = R[k], mc = x.monte_carlo, c = CEA[k];
    return `<tr><td><span style="color:${REG_COLORS[k]}">●</span> ${x.name}</td><td>${money(x.cumulative_revenue)}</td><td>${money(x.ebitda_10y)}</td><td>${money(x.npv)}</td><td>${money(x.ev)}</td><td>${x.payback_year ? 'yr ' + x.payback_year : 'none'}</td><td>${money(mc.npv.p5)} / ${money(mc.npv.p95)}</td><td>${c.qalys_gained_10y.toFixed(0)}</td><td>${c.dominant ? '<span style="color:#34d399">Dominant</span>' : money(c.icer) + '/QALY'}</td><td>${money(c.nmb_10y)}</td><td>${c.payer_roi.toFixed(2)}×</td></tr>`; }).join('')}</table>`;
}
function drawLines() {
  const c = econData.contexts[ecCtx], { ctx, W, H, r } = fit($('ecLines')); ctx.clearRect(0, 0, W, H);
  const m = { l: 62 * r, r: 16 * r, t: 16 * r, b: 30 * r };
  const lby = c.line_by_year, keys = ['cv', 'gi', 'ehr', 'qml'], cols = { cv: '#22d3ee', gi: '#34d399', ehr: '#a78bfa', qml: '#e879f9' };
  const totals = Array.from({ length: 10 }, (_, i) => keys.reduce((s, k) => s + lby[k][i], 0));
  const ymax = Math.max(...totals, ...c.ebitda) * 1.12 || 1;
  const X = i => m.l + (i + 0.5) / 10 * (W - m.l - m.r), bw = (W - m.l - m.r) / 10 * 0.58;
  const Y = v => H - m.b - Math.max(0, v) / ymax * (H - m.t - m.b);
  axisBox(ctx, W, H, r, m); ctx.font = `${10 * r}px system-ui`; ctx.fillStyle = '#8fa0c8';
  for (let k = 0; k <= 4; k++) { const v = ymax * k / 4; ctx.fillText(money(v), 4 * r, Y(v) + 4 * r); ctx.strokeStyle = 'rgba(255,255,255,0.06)'; ctx.beginPath(); ctx.moveTo(m.l, Y(v)); ctx.lineTo(W - m.r, Y(v)); ctx.stroke(); }
  for (let i = 0; i < 10; i++) {
    ctx.fillStyle = '#8fa0c8'; ctx.fillText(`Y${i + 1}`, X(i) - 7 * r, H - 8 * r);
    let acc = 0;
    for (const k of keys) {
      const val = lby[k][i], y0 = Y(acc), y1 = Y(acc + val);
      ctx.fillStyle = cols[k]; ctx.fillRect(X(i) - bw / 2, y1, bw, Math.max(1, y0 - y1));
      acc += val;
    }
  }
  ctx.save(); ctx.strokeStyle = '#fbbf24'; ctx.lineWidth = 2.4 * r; ctx.shadowColor = '#fbbf24'; ctx.shadowBlur = 8 * r; ctx.beginPath();
  c.ebitda.forEach((v, i) => i ? ctx.lineTo(X(i), Y(v)) : ctx.moveTo(X(i), Y(v))); ctx.stroke(); ctx.restore();
  $('linesTitle').textContent = `Revenue by product line & EBITDA · ${ecCtx === 'us_canada' ? 'US & Canada' : 'Asia-Pacific'}`;
  $('linesLegend').innerHTML = '<span><i style="background:#22d3ee"></i>CV Stent</span><span><i style="background:#34d399"></i>GI BEM</span><span><i style="background:#a78bfa"></i>EHR</span><span><i style="background:#e879f9"></i>QML Traj</span><span><i style="background:#fbbf24"></i>EBITDA</span>';
}
function drawCea() {
  const regs = econData.contexts[ecCtx].members, CEA = econData.cea, { ctx, W, H, r } = fit($('ecCea')); ctx.clearRect(0, 0, W, H);
  const m = { l: 92 * r, r: 24 * r, t: 18 * r, b: 30 * r };
  const vals = regs.map(k => CEA[k].nmb_10y), vmax = Math.max(...vals, 1) * 1.1;
  const X = v => m.l + Math.max(0, v) / vmax * (W - m.l - m.r), rh = (H - m.t - m.b) / regs.length;
  axisBox(ctx, W, H, r, m); ctx.font = `${10.5 * r}px system-ui`;
  for (let k = 0; k <= 4; k++) { const v = vmax * k / 4; ctx.fillStyle = '#8fa0c8'; ctx.fillText(money(v), X(v) - 16 * r, H - 10 * r); ctx.strokeStyle = 'rgba(255,255,255,0.06)'; ctx.beginPath(); ctx.moveTo(X(v), m.t); ctx.lineTo(X(v), H - m.b); ctx.stroke(); }
  regs.forEach((k, i) => {
    const c = CEA[k], y = m.t + rh * (i + 0.5), bh = Math.min(22 * r, rh * 0.55);
    ctx.fillStyle = '#e8eeff'; ctx.fillText(econData.regions[k].name, 8 * r, y + 4 * r);
    const gr = ctx.createLinearGradient(m.l, 0, X(c.nmb_10y), 0); gr.addColorStop(0, REG_COLORS[k] + '55'); gr.addColorStop(1, REG_COLORS[k]);
    ctx.fillStyle = gr; ctx.beginPath(); ctx.roundRect(m.l, y - bh / 2, Math.max(4 * r, X(c.nmb_10y) - m.l), bh, 5 * r); ctx.fill();
    ctx.fillStyle = '#e8eeff'; ctx.fillText(`${c.qalys_gained_10y.toFixed(0)} QALYs · ${c.payer_roi.toFixed(1)}× ROI`, Math.min(W - m.r - 135 * r, X(c.nmb_10y) + 6 * r), y + 4 * r);
  });
  $('ceaTitle').textContent = `10-year Net Monetary Benefit (NMB) & QALYs · ${ecCtx === 'us_canada' ? 'US & Canada' : 'Asia-Pacific'}`;
  $('ceaLegend').innerHTML = '<span>Bar = NMB = WTP × ΔQALY − Net Payer Cost</span><span>Label = QALYs gained &amp; Payer ROI</span>';
}
function renderEcon() {
  const c = econData.contexts[ecCtx], name = ecCtx === 'us_canada' ? 'US & Canada' : 'Asia-Pacific';
  const t = (k, v, s, cl) => `<div class="tile ${cl}"><div class="k">${k}</div><div class="v">${v}</div><div class="s">${s}</div></div>`;
  $('ecTiles').innerHTML = t('10-YEAR REVENUE', money(c.cumulative_revenue), `Monte Carlo 5–95%: ${money(c.cumulative_quantiles.p5)} – ${money(c.cumulative_quantiles.p95)}`, 'cyan') +
    t('NET PRESENT VALUE', money(c.npv), `MC median ${money(c.npv_quantiles.p50)} · EBITDA ${money(c.ebitda_10y)}`, 'green') +
    t('ENTERPRISE VALUE', money(c.ev), `MC 5–95%: ${money(c.ev_quantiles.p5)} – ${money(c.ev_quantiles.p95)}`, 'violet') +
    t('PAYER NMB & QALYs', money(c.nmb_10y), `${c.qalys_gained_10y.toFixed(0)} QALYs · ${money(c.total_payer_savings_10y)} savings`, 'amber');
  renderEconTable(); drawFan(); drawForest(); drawLines(); drawCea();
}
function drawEcon() { if (econData) { drawFan(); drawForest(); drawLines(); drawCea(); } }
async function initEcon() {
  $('ecTiles').innerHTML = '<div class="tile cyan"><div class="k">LOADING</div><div class="v"><span class="spin"></span></div></div>';
  try {
    econData = await api('/api/economics'); const L = econData.physics_link, Q = econData.qml_value, a = econData.assumptions;
    $('ecLink').innerHTML = `Optimized physics (FEM/BEM) + QML trajectory stratification reduce complications and 30-day readmissions.<table><tr><th>Line</th><th>J base → opt</th><th>Complication Δ</th><th>30d Readmit Δ</th><th>QALY / case</th></tr>
      <tr><td>Stent (FE+QML)</td><td>${L.cv.J_baseline.toFixed(3)} → ${L.cv.J_optimized.toFixed(3)}</td><td>−${pct(L.cv.relative_risk_reduction, 1)}</td><td>−${pct(Q.cv.readmission_reduction, 1)}</td><td>+${Q.cv.qaly_per_case.toFixed(3)}</td></tr>
      <tr><td>GI (BEM+QML)</td><td>${L.gi.J_baseline.toFixed(3)} → ${L.gi.J_optimized.toFixed(3)}</td><td>−${pct(L.gi.relative_risk_reduction, 1)}</td><td>−${pct(Q.gi.readmission_reduction, 1)}</td><td>+${Q.gi.qaly_per_case.toFixed(3)}</td></tr></table>
      <p class="note">Net Monetary Benefit NMB = WTP × ΔQALY − (Software Fees − Complication &amp; Readmission Savings). Dominant indicates net cost savings for payers.</p>`;
    $('ecAssume').innerHTML = `<ul style="padding-left:18px;line-height:1.7"><li>4 revenue lines: CV Stent FE, GI BEM, EHR Platform, and QML Post-Op Trajectory Suite.</li><li>Logistic adoption, steepness ${a.steepness}, midpoint ${a.midpoint} y after regulatory lead time; COGS ${pct(a.cogs, 0)}.</li><li>Regional WTP thresholds ($8k–$100k/QALY), volumes, discount rates and lead times are illustrative archetypes.</li><li>Monte Carlo: Beta adoption ceilings, lognormal price (σ 0.15), uniform lead shift, normal growth, triangular discount rate.</li><li>Bootstrap and regression use a synthetic 36-month pilot history; the Bayesian prism uses a synthetic 24-site pilot.</li></ul>`;
    document.querySelectorAll('#ecCtx button').forEach(b => b.addEventListener('click', () => { ecCtx = b.dataset.c; document.querySelectorAll('#ecCtx button').forEach(x => x.classList.toggle('on', x === b)); renderEcon(); }));
    document.querySelectorAll('#ecPrism button').forEach(b => b.addEventListener('click', () => { ecPrism = b.dataset.p; document.querySelectorAll('#ecPrism button').forEach(x => x.classList.toggle('on', x === b)); drawForest(); }));
    renderEcon();
  } catch (err) { $('ecTiles').innerHTML = `<div class="err">${err.message}</div>`; }
}

/* ======================================================== QML trajectories */
let qmlData = null, qmlProc = 'stent', qmlOpt = true, qmlSeq = 0;
function drawQml() {
  const d = qmlData; if (!d) return;
  const days = d.days;
  // 1. Recovery Probability Trajectory
  let { ctx, W, H, r } = fit($('qmlTrajCanvas')); ctx.clearRect(0, 0, W, H);
  let m = { l: 54 * r, r: 20 * r, t: 18 * r, b: 32 * r };
  let X = t => m.l + t / 90 * (W - m.l - m.r), Y = v => H - m.b - v * (H - m.t - m.b);
  axisBox(ctx, W, H, r, m); ctx.font = `${10.5 * r}px system-ui`; ctx.fillStyle = '#8fa0c8';
  for (let k = 0; k <= 5; k++) { const v = k * 0.2; ctx.fillText(pct(v, 0), 8 * r, Y(v) + 4 * r); ctx.strokeStyle = 'rgba(255,255,255,0.06)'; ctx.beginPath(); ctx.moveTo(m.l, Y(v)); ctx.lineTo(W - m.r, Y(v)); ctx.stroke(); }
  [0, 14, 30, 60, 90].forEach(day => { ctx.fillText(`D${day}`, X(day) - 10 * r, H - 10 * r); ctx.strokeStyle = 'rgba(255,255,255,0.06)'; ctx.beginPath(); ctx.moveTo(X(day), m.t); ctx.lineTo(X(day), H - m.b); ctx.stroke(); });
  // Band p5 - p95
  const grad = ctx.createLinearGradient(0, m.t, 0, H - m.b); grad.addColorStop(0, 'rgba(34,211,238,0.35)'); grad.addColorStop(1, 'rgba(34,211,238,0.06)');
  ctx.fillStyle = grad; ctx.beginPath();
  days.forEach((day, i) => i ? ctx.lineTo(X(day), Y(d.p95[i])) : ctx.moveTo(X(day), Y(d.p95[i])));
  for (let i = days.length - 1; i >= 0; i--) ctx.lineTo(X(days[i]), Y(d.p5[i]));
  ctx.closePath(); ctx.fill();
  const plotCurve = (arr, col, dash) => {
    ctx.save(); ctx.strokeStyle = col; ctx.lineWidth = 2.4 * r; ctx.shadowColor = col; ctx.shadowBlur = 7 * r;
    if (dash) ctx.setLineDash(dash.map(x => x * r));
    ctx.beginPath(); days.forEach((day, i) => i ? ctx.lineTo(X(day), Y(arr[i])) : ctx.moveTo(X(day), Y(arr[i]))); ctx.stroke(); ctx.restore();
  };
  plotCurve(d.p_baseline_physics, '#fb7185', [3, 4]);
  plotCurve(d.p_classical, '#fbbf24', [6, 4]);
  plotCurve(d.p_recovery, '#22d3ee', null);
  days.forEach((day, i) => { ctx.fillStyle = '#22d3ee'; ctx.beginPath(); ctx.arc(X(day), Y(d.p_recovery[i]), 3.5 * r, 0, 7); ctx.fill(); });

  // 2. Hazard & Functional Score
  ({ ctx, W, H, r } = fit($('qmlHazardCanvas'))); ctx.clearRect(0, 0, W, H);
  m = { l: 50 * r, r: 46 * r, t: 18 * r, b: 30 * r };
  X = t => m.l + t / 90 * (W - m.l - m.r);
  const hMax = Math.max(...d.hazard, 2.0) * 1.15;
  const Yh = v => H - m.b - v / hMax * (H - m.t - m.b), Yf = v => H - m.b - v / 100 * (H - m.t - m.b);
  axisBox(ctx, W, H, r, m); ctx.font = `${10 * r}px system-ui`;
  for (let k = 0; k <= 4; k++) {
    ctx.fillStyle = '#fb7185'; ctx.fillText((hMax * k / 4).toFixed(1), 8 * r, Yh(hMax * k / 4) + 4 * r);
    ctx.fillStyle = '#34d399'; ctx.fillText(`${k * 25}`, W - m.r + 8 * r, Yf(k * 25) + 4 * r);
  }
  [0, 14, 30, 60, 90].forEach(day => { ctx.fillStyle = '#8fa0c8'; ctx.fillText(`D${day}`, X(day) - 10 * r, H - 8 * r); });
  ctx.save(); ctx.strokeStyle = '#fb7185'; ctx.lineWidth = 2.2 * r; ctx.beginPath(); days.forEach((day, i) => i ? ctx.lineTo(X(day), Yh(d.hazard[i])) : ctx.moveTo(X(day), Yh(d.hazard[i]))); ctx.stroke(); ctx.restore();
  ctx.save(); ctx.strokeStyle = '#34d399'; ctx.lineWidth = 2.4 * r; ctx.beginPath(); days.forEach((day, i) => i ? ctx.lineTo(X(day), Yf(d.functional_score[i])) : ctx.moveTo(X(day), Yf(d.functional_score[i]))); ctx.stroke(); ctx.restore();

  // 3. Feature Attribution
  ({ ctx, W, H, r } = fit($('qmlAttrCanvas'))); ctx.clearRect(0, 0, W, H);
  m = { l: 150 * r, r: 24 * r, t: 18 * r, b: 28 * r };
  const attrs = d.attributions, maxAbs = Math.max(...attrs.map(a => Math.abs(a.delta_30d)), 0.02) * 1.15;
  const Xa = v => m.l + (v + maxAbs) / (2 * maxAbs) * (W - m.l - m.r), rh = (H - m.t - m.b) / attrs.length;
  axisBox(ctx, W, H, r, m); ctx.font = `${10 * r}px system-ui`;
  ctx.strokeStyle = 'rgba(255,255,255,0.25)'; ctx.beginPath(); ctx.moveTo(Xa(0), m.t); ctx.lineTo(Xa(0), H - m.b); ctx.stroke();
  attrs.forEach((a, i) => {
    const y = m.t + rh * (i + 0.5), bh = Math.min(18 * r, rh * 0.58), x0 = Xa(0), x1 = Xa(a.delta_30d);
    ctx.fillStyle = '#e8eeff'; ctx.fillText(a.label, 8 * r, y + 4 * r);
    ctx.fillStyle = a.delta_30d >= 0 ? '#34d399' : '#a78bfa';
    ctx.beginPath(); ctx.roundRect(Math.min(x0, x1), y - bh / 2, Math.max(3 * r, Math.abs(x1 - x0)), bh, 4 * r); ctx.fill();
    ctx.fillStyle = '#8fa0c8'; ctx.fillText(`${a.delta_30d >= 0 ? '+' : ''}${(a.delta_30d * 100).toFixed(1)}%`, x1 + (a.delta_30d >= 0 ? 5 * r : -38 * r), y + 4 * r);
  });
}

async function loadQml() {
  const seq = ++qmlSeq;
  const body = {
    procedure: qmlProc,
    age: +$('qAge').value,
    comorbidity: +$('qCom').value,
    burden: +$('qBur').value,
    ehr_delay: +$('qDel').value,
    gamma: +$('qGam').value,
    use_optimized: qmlOpt,
  };
  $('qAgeV').textContent = `${body.age} y`; $('qComV').textContent = body.comorbidity.toFixed(2);
  $('qBurV').textContent = body.burden.toFixed(2); $('qDelV').textContent = body.ehr_delay.toFixed(2);
  $('qGamV').textContent = body.gamma.toFixed(2);
  try {
    const d = await api('/api/qml', body); if (seq !== qmlSeq) return;
    qmlData = d; $('qmlErr').textContent = '';
    const s = d.summary, dg = d.diagnostics;
    $('qRec30').textContent = pct(s.recovery_30d, 1);
    $('qRec30S').textContent = `gain vs unoptimized: ${s.recovery_gain_vs_baseline >= 0 ? '+' : ''}${pct(s.recovery_gain_vs_baseline, 1)}`;
    $('qRec90').textContent = pct(s.recovery_90d, 1);
    $('qRec90S').textContent = `functional score ${s.functional_90d.toFixed(1)} / 100`;
    $('qRead').textContent = pct(s.readmission_30d, 1);
    $('qReadS').textContent = `expected LOS ${s.expected_los_days.toFixed(1)} days · −${pct(s.readmission_reduction, 1)} vs base`;
    $('qAuc').textContent = `${dg.auroc_30d.toFixed(3)} · ${dg.gram_eig_min.toExponential(1)}`;
    $('qAucS').textContent = `RBF AUROC ${dg.auroc_classical_30d.toFixed(3)} · Brier ${dg.brier_30d.toFixed(3)}`;
    $('qmlChars').innerHTML = `<table><tr><th>Archetype</th><th>Quantum Kernel K<sub>Q</sub></th><th>Expected 90d</th></tr>${d.archetypes.map(a =>
      `<tr><td>${a.label}</td><td>${a.similarity.toFixed(4)}</td><td>${pct(a.expected_90d, 0)}</td></tr>`).join('')}</table>
      <p class="note">Procedure: <b>${d.procedure}</b> (${d.use_optimized ? 'physics-optimized' : 'baseline'}). Gram trace = ${dg.gram_trace.toFixed(1)}, effective rank = ${dg.effective_rank.toFixed(2)}, 90d MAE = ${dg.mae_90d.toFixed(3)}.</p>`;
    drawQml();
  } catch (err) { if (seq === qmlSeq) $('qmlErr').textContent = err.message; }
}

function initQml() {
  ['qAge', 'qCom', 'qBur', 'qDel', 'qGam'].forEach(id => $(id).addEventListener('input', debounce(loadQml, 140)));
  document.querySelectorAll('#qmlProc button').forEach(b => b.addEventListener('click', () => {
    qmlProc = b.dataset.p;
    document.querySelectorAll('#qmlProc button').forEach(x => x.classList.toggle('on', x === b));
    loadQml();
  }));
  $('qmlOptBtn').addEventListener('click', () => {
    qmlOpt = !qmlOpt;
    $('qmlOptBtn').textContent = `⚡ Physics-optimized: ${qmlOpt ? 'ON' : 'OFF'}`;
    loadQml();
  });
  loadQml();
}

/* ================================================================== overview */
async function initOverview() {
  try {
    const s = await api('/api/summary');
    const t = (k, v, sub, cl) => `<div class="tile ${cl}"><div class="k">${k}</div><div class="v">${v}</div><div class="s">${sub}</div></div>`;
    $('heroTiles').innerHTML =
      t('BEM · VERIFIED', `order ${s.bem.order.toFixed(2)}`, `current error ${(s.bem.final_error * 100).toFixed(3)}% vs exact ring modulus`, 'cyan') +
      t('FEM · VERIFIED', `${(s.fem.final_error * 100).toFixed(2)}%`, `Lamé error; conformal grid ${s.fem.graded_vs_uniform.toFixed(2)}× better`, 'green') +
      t('QML · TRAJECTORIES', `${(s.qml.recovery_90d * 100).toFixed(1)}% 90d`, `AUROC ${s.qml.auroc_30d.toFixed(3)} · 30d readmit ${(s.qml.readmission_30d * 100).toFixed(1)}%`, 'violet') +
      t('10-YR REVENUE (ILLUSTRATIVE)', `${money(s.contexts.us_canada.cumulative)} · ${money(s.contexts.asia_pacific.cumulative)}`, `US/CA & APAC · NMB ${money(s.contexts.us_canada.nmb + s.contexts.asia_pacific.nmb)}`, 'amber');
  } catch (e) { $('heroTiles').innerHTML = `<div class="err">${e.message}</div>`; }
  try {
    const d = await api('/api/bem', { R: 4.0, a: 1.0, e: 1.4, heat_fraction: 0.2 }); drawBem($('ovBem'), d, 'heat');
    const f = await api('/api/fem', { n_struts: 12, layers: 1, target_gain: 0.10, plaque_arc: 120, plastic_fraction: 0.55, stress_limit: 0.25 }); prepFem(f); drawFem($('ovFem'), f, { prog: 1, relax: 0 });
    const e = await api('/api/elliptic', { ri: 1.5, ro: 3.0, n_theta: 48, k: 0.5 }); drawRing($('ovEll'), e.conformal_radii, e.n_theta, e.ro, VIRIDIS);
  } catch (e) { /* visuals are best-effort */ }
}
initOverview();
addEventListener('resize', debounce(() => { const act = document.querySelector('#tabs button.active').dataset.tab; if (act !== 'overview') { tabLoaded[act] = true; showTab(act); } }, 250));
