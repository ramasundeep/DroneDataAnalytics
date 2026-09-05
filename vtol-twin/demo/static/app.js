/* VTOL-1 twin demo UI: SSE-driven, no external dependencies. */
(function () {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const PHASES = ['preflight', 'engine-start', 'hover-climb', 'transition-forward', 'cruise',
                  'transition-back', 'hover-descent', 'landed', 'shutdown'];
  const COMPONENT_ORDER = ['engine', 'ductedFan', 'fuelPump', 'servo1', 'servo2', 'servo3', 'servo4',
                           'avionics', 'payloadGimbal', 'battery'];
  let state = null;
  let es = null;

  // ------------------------------------------------------------ helpers
  const fmt = (v, d = 1) => (v === null || v === undefined) ? '–' : (typeof v === 'number' ? v.toFixed(d) : String(v));
  const kv = (label, value, unit, over) =>
    `<div class="${over ? 'over' : ''}"><span class="k">${label}</span><span class="v">${value}${unit ? `<small>${unit}</small>` : ''}</span></div>`;
  const badge = (level) => `<span class="badge ${level}">${level}</span>`;
  const time = (iso) => iso ? iso.replace('T', ' ').replace('Z', '') : '';
  async function post(url, body) {
    const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' },
                                 body: body ? JSON.stringify(body) : undefined });
    if (!r.ok) { const t = await r.text(); alert(`${url}: ${r.status} ${t}`); }
    return r.ok ? r.json() : null;
  }

  // ------------------------------------------------------------ sparklines
  function drawSpark(canvas, history) {
    const key = canvas.dataset.key, label = canvas.dataset.label, limit = parseFloat(canvas.dataset.limit);
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth, h = canvas.height;
    canvas.width = w * dpr; canvas.style.height = h + 'px';
    const ctx = canvas.getContext('2d'); ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, w, h);
    ctx.font = '10px system-ui'; ctx.fillStyle = '#6b7684'; ctx.fillText(label, 2, 10);
    const pts = history.map((s) => s[key]).filter((v) => typeof v === 'number');
    if (pts.length < 2) return;
    let min = Math.min(...pts), max = Math.max(...pts);
    if (!isNaN(limit)) { max = Math.max(max, limit); }
    if (max - min < 1e-6) { max += 1; min -= 1; }
    const pad = 4, top = 14;
    const x = (i) => pad + (i / (pts.length - 1)) * (w - 2 * pad);
    const y = (v) => top + (1 - (v - min) / (max - min)) * (h - top - pad);
    if (!isNaN(limit)) {
      ctx.strokeStyle = '#c8362b'; ctx.setLineDash([3, 3]); ctx.beginPath();
      ctx.moveTo(pad, y(limit)); ctx.lineTo(w - pad, y(limit)); ctx.stroke(); ctx.setLineDash([]);
    }
    ctx.strokeStyle = '#1f6feb'; ctx.lineWidth = 1.4; ctx.beginPath();
    pts.forEach((v, i) => (i ? ctx.lineTo(x(i), y(v)) : ctx.moveTo(x(i), y(v))));
    ctx.stroke();
    ctx.fillStyle = '#1c2430'; ctx.textAlign = 'right';
    ctx.fillText(pts[pts.length - 1].toFixed(key === 'rpm' ? 0 : 2), w - 2, 10); ctx.textAlign = 'left';
  }

  // ------------------------------------------------------------ render
  function render() {
    if (!state) return;
    const f = state.thing.features, p = (id) => f[id].properties;
    const health = p('health'), counters = p('lifeCounters'), comps = state.thing.attributes.components;

    // header
    const rel = health.aircraft.releaseStatus;
    $('release').textContent = `release: ${rel}` + (health.aircraft.openWorkOrders ? ` · ${health.aircraft.openWorkOrders} open WO` : '');
    $('release').className = `pill ${rel}`;
    const m = state.mqtt;
    $('mqtt').textContent = m.enabled ? `mqtt mirror: ${m.connected ? 'connected' : 'reconnecting'} · ${m.published} msgs` : 'mqtt mirror: off (in-memory only)';
    $('mqtt').className = 'pill' + (m.enabled && m.connected ? ' on' : '');
    $('clock').textContent = time(state.serverTime) + ' UTC';

    // controls / progress
    const s = state.sortie;
    $('start').disabled = !!s; $('abort').disabled = !s;
    $('progressFill').style.width = s ? `${(100 * s.t / s.total).toFixed(1)}%` : '0%';
    $('sortieId').textContent = s ? s.sortieId : 'no sortie in progress';
    $('phaseText').textContent = s ? `· ${s.phase} · t=${s.t}s of ${s.total}s` + (s.degradation !== 'none' ? ` · fault: ${s.degradation} ×${s.severity}` : '') : '';
    $('phaseRow').innerHTML = PHASES.map((ph) => `<span class="${s && s.phase === ph ? 'active' : ''}" style="flex:${ph === 'cruise' ? 4 : 1}">${ph}</span>`).join('');
    if (document.activeElement !== $('speed')) { $('speed').value = state.speed; $('speedVal').textContent = state.speed; }

    // flight
    const fs = p('flightState'), nav = p('navigation');
    $('flightKv').innerHTML = [
      kv('VTOL state', fs.vtolState), kv('mode', fs.flightMode), kv('armed', fs.armed ? 'yes' : 'no'),
      kv('alt AGL', fmt(fs.altAglM, 0), 'm'), kv('airspeed', fmt(fs.airspeedMps), 'm/s'), kv('heading', fmt(fs.headingDeg, 0), '°'),
      kv('flight time', fmt(fs.flightTimeS, 0), 's'), kv('fuel', fmt(fs.fuelRemainingL), 'L'), kv('position', `${fmt(fs.lat, 4)}, ${fmt(fs.lon, 4)}`),
    ].join('');

    // engine
    const e = p('engine');
    $('engineKv').innerHTML = [
      kv('RPM', fmt(e.rpm, 0)), kv('EGT', fmt(e.egtC), '°C', e.egtC > 680), kv('CHT', fmt(e.chtC), '°C', e.chtC > 205),
      kv('fuel flow', fmt(e.fuelFlowLph, 2), 'L/h'), kv('throttle', fmt(e.throttlePct, 0), '%'), kv('oil', fmt(e.oilPressureKpa, 0), 'kPa'),
    ].join('');

    // vibration
    const v = p('vibration');
    $('vibKv').innerHTML = [
      kv('RMS X', fmt(v.rmsX, 2), 'm/s²'), kv('RMS Y', fmt(v.rmsY, 2), 'm/s²'), kv('RMS Z', fmt(v.rmsZ, 2), 'm/s²'),
      kv('RMS total', fmt(v.rmsTotal, 2), 'm/s²', v.rmsTotal > 1.8), kv('clips', fmt(v.clipCount, 0)),
    ].join('');

    // actuation
    const a = p('actuation');
    $('servoTable').innerHTML = '<tr><th>Servo</th><th>Position</th><th>Current</th><th>Health</th></tr>' +
      [1, 2, 3, 4].map((i) => {
        const cur = a[`servo${i}CurrentA`];
        return `<tr><td>servo${i} <span class="muted">${comps[`servo${i}`].position}</span></td><td>${fmt(a[`servo${i}PositionDeg`])}°</td>` +
               `<td style="${cur > 1.9 ? 'color:#c8362b;font-weight:600' : ''}">${fmt(cur, 2)} A</td><td>${badge(health[`servo${i}`].alertLevel)}</td></tr>`;
      }).join('');

    // power + nav
    const pw = p('power');
    $('powerKv').innerHTML = [
      kv('bus', fmt(pw.busVoltageV, 2), 'V', pw.busVoltageV < 24), kv('bus current', fmt(pw.busCurrentA, 2), 'A'),
      kv('battery', fmt(pw.batteryVoltageV, 2), 'V'), kv('batt current', fmt(pw.batteryCurrentA, 2), 'A'),
      kv('batt remaining', fmt(pw.batteryRemainingPct, 0), '%'), kv('batt temp', fmt(pw.batteryTempC), '°C'),
      kv('GPS fix', `${fs.armed ? '3D' : fmt(nav.gpsFixType, 0)} / ${fmt(nav.gpsSatellites, 0)} sats`), kv('HDOP', fmt(nav.gpsHdop, 2)), kv('INS', nav.insStatus),
    ].join('');

    // life table
    $('lifeTable').querySelector('tbody').innerHTML = COMPONENT_ORDER.map((cid) => {
      const c = comps[cid], h = health[cid], lc = counters[cid] || { hours: c.hoursConsumed, cycles: c.cyclesConsumed };
      const ratio = Math.min(1, lc.hours / c.lifeLimitHours);
      const cls = ratio >= 0.9 ? 'cau' : ratio >= 0.8 ? 'adv' : '';
      const cond = state.condition[cid];
      return `<tr><td><b>${c.name}</b>${c.position ? ` <span class="muted">(${c.position})</span>` : ''}</td><td class="muted">${c.serial}</td><td class="muted">${c.installDate}</td>` +
        `<td><span class="lifebar ${cls}"><i style="width:${(ratio * 100).toFixed(1)}%"></i></span>${fmt(lc.hours)} / ${c.lifeLimitHours}</td>` +
        `<td>${lc.cycles} / ${c.lifeLimitCycles}</td>` +
        `<td><span class="score" style="color:${h.healthScore < 50 ? '#c8362b' : h.healthScore < 65 ? '#d9701a' : h.healthScore < 80 ? '#b7860b' : '#1a8f4c'}">${fmt(h.healthScore, 0)}</span>` +
        `${cond ? ` <span class="muted" title="${cond.signal} mean ${cond.mean} / limit ${cond.threshold}">· ${cond.signal.split('.')[1]} mean ${cond.mean.toFixed(2)}</span>` : ''}</td>` +
        `<td>${fmt(h.rulHours)}${cond && cond.trendRulHours !== null && cond.trendRulHours < (c.lifeLimitHours - lc.hours) ? ' <span class="muted">(trend)</span>' : ''}</td><td>${badge(h.alertLevel)}</td></tr>`;
    }).join('');

    // alerts + sorties
    $('alertFeed').innerHTML = state.alerts.length ? state.alerts.slice().reverse().map((al) =>
      `<li><time>${time(al.ts)}</time>${badge(al.level)} <b>${al.component}</b> ${al.text}</li>`).join('') : '<li class="muted">none</li>';
    $('sortieFeed').innerHTML = state.sorties.length ? state.sorties.slice().reverse().map((so) =>
      `<li><time>${time(so.endedAt)}</time><b>${so.sortieId}</b> ${so.flightHours.toFixed(2)} h flown${so.degradation !== 'none' ? ` · fault: ${so.degradation}, wear ${so.wear.toFixed(2)}` : ''}</li>`).join('') : '<li class="muted">none flown yet</li>';

    // work orders
    const wos = state.workOrders.slice().reverse();
    const open = wos.filter((w) => w.status === 'open').length;
    $('woCount').textContent = wos.length ? `${open} open · ${wos.length - open} closed` : '';
    $('woList').innerHTML = wos.length ? wos.map(renderWo).join('') :
      '<p class="muted">No work orders. Fly a sortie with a fault injected, or fly enough sorties to approach a life limit.</p>';

    document.querySelectorAll('canvas.spark').forEach((c) => drawSpark(c, state.history));
  }

  function renderWo(w) {
    const ev = w.evidence;
    return `<article class="wo ${w.status} ${w.priority}">
      <header><b>${w.id}</b> <span>${badge(w.status)} ${badge(w.alertLevel)} <span class="muted">priority ${w.priority}</span></span></header>
      <dl><dt>Component</dt><dd>${w.componentName} <span class="muted">${w.serial}</span></dd>
          <dt>Defect</dt><dd>${w.defect}</dd>
          <dt>Raised</dt><dd>${time(w.createdAt)}</dd>
          ${w.status === 'closed' ? `<dt>Action</dt><dd>${w.action} by ${w.signedOffBy}, ${w.manHours} man-h${w.partsConsumed.length ? `, parts: ${w.partsConsumed.join(', ')}` : ''} · ${time(w.closedAt)}</dd>` : ''}
      </dl>
      ${ev ? `<div class="evidence">evidence: ${ev.signal} mean ${ev.mean}, peak ${ev.peak}, limit ${ev.threshold}, slope ${ev.slopePerHour}/h${ev.trendRulHours !== null ? `, projected ${ev.trendRulHours} h to limit` : ''} · sortie ${ev.sortieId}<br>Grafana window: sortie=${ev.sortieId} (Phase 2 dashboards)</div>` : ''}
      ${w.status === 'open' ? `<form data-wo="${w.id}">
        <select name="action"><option value="repaired">repaired</option><option value="replaced">replaced (new serial, counters reset)</option><option value="inspected-no-fault">inspected, no fault found</option></select>
        <input name="signedOffBy" placeholder="signed off by" value="operator">
        <input name="manHours" type="number" step="0.5" min="0" value="1.5" placeholder="man-hours">
        <input name="parts" placeholder="parts consumed (comma separated)">
        <button type="submit" class="primary">Sign off &amp; close</button></form>` : ''}
    </article>`;
  }

  // ------------------------------------------------------------ wiring
  function connect() {
    es = new EventSource('/api/events');
    es.onopen = () => { $('conn').textContent = 'live'; };
    es.onmessage = (ev) => { state = JSON.parse(ev.data).state; if (!$('degradation').options.length) fillDegradations(); render(); };
    es.onerror = () => { $('conn').textContent = 'reconnecting…'; };
  }
  function fillDegradations() {
    $('degradation').innerHTML = Object.entries(state.degradations).map(([k, d]) => `<option value="${k}">${k === 'none' ? 'none (nominal flight)' : `${k}: ${d}`}</option>`).join('');
  }
  $('severity').oninput = () => { $('severityVal').textContent = parseFloat($('severity').value).toFixed(1); };
  $('speed').onchange = () => post('/api/speed', { speed: parseFloat($('speed').value) });
  $('speed').oninput = () => { $('speedVal').textContent = $('speed').value; };
  $('start').onclick = () => post('/api/sortie/start', {
    degradation: $('degradation').value, severity: parseFloat($('severity').value), cruiseSeconds: parseInt($('cruise').value, 10) });
  $('abort').onclick = () => post('/api/sortie/abort');
  $('reset').onclick = () => { if (confirm('Reset the twin to the model file? Sorties, alerts and work orders are discarded.')) post('/api/reset'); };
  document.addEventListener('submit', async (ev) => {
    const form = ev.target.closest('form[data-wo]'); if (!form) return;
    ev.preventDefault();
    const parts = form.parts.value.split(',').map((x) => x.trim()).filter(Boolean);
    await post(`/api/workorders/${form.dataset.wo}/signoff`, {
      action: form.action.value, signedOffBy: form.signedOffBy.value || 'operator', manHours: parseFloat(form.manHours.value) || 0, partsConsumed: parts });
  });
  window.addEventListener('resize', () => render());
  connect();
})();
