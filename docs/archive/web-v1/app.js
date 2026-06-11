/* Interface d'entrainement ATC - radar live + radio (push-to-talk) + panneau instructeur.
   Le radar reprend le rendu de radar_anim.py (anneaux, balayage, blips, bloc de donnees).
   Voix : mode ROMEO -> capture WAV 16k vers /api/voice ; mode local -> Web Speech API. */
"use strict";

const $ = (id) => document.getElementById(id);
const canvas = $("radar"), ctx = canvas.getContext("2d");

let NAV = { waypoints: [], airports: [], routes: [], fixes: [], sector: [], range_nm: 70 };
let STATE = { t: 0, aircraft: [], conflicts: [], paused: false, speed: 1 };
let CAPS = { romeo: false, asr: false, llm: false, tts: false };
let MODE = "local";
let trails = {};            // id -> [{x,y}, ...]
let sweep = 0;              // angle du balayage (deg)
let lastFrame = 0;

/* ============================ initialisation ============================ */
async function init() {
  await refreshHealth();
  try { NAV = await (await fetch("/api/nav")).json(); } catch (e) {}
  await loadScenarioList();
  connectWS();
  wireUI();
  resize();
  window.addEventListener("resize", resize);
  requestAnimationFrame(render);
}

async function refreshHealth() {
  try {
    const h = await (await fetch("/api/health")).json();
    CAPS = h.caps; MODE = h.mode;
  } catch (e) { CAPS = { romeo: false, asr: false, llm: false, tts: false }; MODE = "local"; }
  const badge = $("mode-badge");
  badge.textContent = (MODE === "romeo" ? "ROMEO" : "LOCAL");
  badge.className = (MODE === "romeo" ? "romeo" : "local");
  badge.title = "IA : " + (MODE === "romeo" ? "serveur ROMEO (Whisper/Mistral/XTTS)"
    : "repli local (voix navigateur). Cliquer pour re-détecter ROMEO.");
}

async function loadScenarioList() {
  try {
    const r = await (await fetch("/api/scenarios")).json();
    const sel = $("scenario-list");
    sel.innerHTML = '<option value="">— scénarios sauvegardés —</option>';
    (r.scenarios || []).forEach(s => {
      const o = document.createElement("option");
      o.value = s.name; o.textContent = s.title;
      sel.appendChild(o);
    });
  } catch (e) {}
}

/* ============================ WebSocket ============================ */
function connectWS() {
  const ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws");
  ws.onmessage = (ev) => {
    let msg; try { msg = JSON.parse(ev.data); } catch (e) { return; }
    if (msg.type === "state") onState(msg);
    else if (msg.type === "exchange") onExchange(msg);
    else if (msg.type === "situation") onSituation(msg);
    else if (msg.type === "info") logLine(msg.message, "");
  };
  ws.onclose = () => setTimeout(connectWS, 1500);
}

function onState(s) {
  STATE = s;
  const ids = new Set(s.aircraft.map(a => a.id));
  s.aircraft.forEach(a => {
    (trails[a.id] = trails[a.id] || []).push({ x: a.x, y: a.y });
    if (trails[a.id].length > 12) trails[a.id].shift();
  });
  Object.keys(trails).forEach(id => { if (!ids.has(id)) delete trails[id]; });
  const nlos = (s.conflicts || []).length, npred = (s.predicted || []).length;
  $("hud-clock").textContent = `t=${String(Math.round(s.t)).padStart(3, "0")}s · ${s.aircraft.length} vol`
    + (s.paused ? " · PAUSE" : "") + (s.cd_engine ? ` · CD ${s.cd_engine === "bluesky" ? "BlueSky" : "géo"}` : "");
  const nzone = (s.aircraft || []).filter(a => a.inzone).length;
  const bn = $("alert-banner");
  if (nlos) {
    bn.textContent = `⚠ PERTE DE SÉPARATION (${nlos})`; bn.className = "los"; bn.style.display = "block";
  } else if (npred) {
    const tmin = Math.min(...s.predicted.map(p => p.t));
    bn.textContent = `⚠ CONFLIT PRÉVU — impact possible dans ${tmin}s`; bn.className = "predicted"; bn.style.display = "block";
  } else if (nzone) {
    bn.textContent = `⚠ TRAFIC EN ZONE MÉTÉO / INTERDITE (${nzone})`; bn.className = "zone"; bn.style.display = "block";
  } else {
    bn.style.display = "none";
  }
}

function onExchange(m) {
  let html = `<div class="you">📡 « ${escapeHtml(m.transcript)} »</div>`;
  if (m.trafscript && m.trafscript.length)
    html += `<div class="cmd">→ ${m.trafscript.map(escapeHtml).join(" · ")}</div>`;
  if (m.readback) html += `<div class="pilot">🔊 ${escapeHtml(m.readback)}</div>`;
  if (m.rejected && m.rejected.length)
    html += `<div class="rej">⊘ ${m.rejected.map(escapeHtml).join(" · ")}</div>`;
  if (!m.trafscript?.length && !m.rejected?.length)
    html += `<div class="rej">⊘ aucun ordre reconnu</div>`;
  $("last-exchange").innerHTML = html;

  logLine(`📡 ${m.transcript}`, "t");
  (m.trafscript || []).forEach(l => logLine(`   → ${l}`, "b"));
  if (m.readback) logLine(`   🔊 ${m.readback}`, "o");
  (m.rejected || []).forEach(r => logLine(`   ⊘ ${r}`, "r"));

  // En mode local, le pilote "parle" via la synthese vocale du navigateur.
  if (MODE !== "romeo" && m.readback) speak(m.readback);
}

function onSituation(m) {
  logLine(`✈ situation : ${m.description} → ${(m.created || []).join(", ") || "—"}`, "o");
}

/* ============================ rendu radar ============================ */
function resize() {
  const r = canvas.parentElement.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.floor(r.width * dpr);
  canvas.height = Math.floor(r.height * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

function geom() {
  const w = canvas.clientWidth, h = canvas.clientHeight;
  const cx = w / 2, cy = h / 2;
  const scale = (Math.min(w, h) / 2 - 24) / (NAV.range_nm * 1.12);
  return { cx, cy, scale };
}
const SX = (g, x) => g.cx + x * g.scale;
const SY = (g, y) => g.cy - y * g.scale;

function render(ts) {
  const dt = lastFrame ? (ts - lastFrame) / 1000 : 0; lastFrame = ts;
  if (!STATE.paused) sweep = (sweep + dt * 42) % 360;   // ~42 deg/s

  const g = geom();
  ctx.clearRect(0, 0, canvas.clientWidth, canvas.clientHeight);
  ctx.fillStyle = "#04140a";
  ctx.fillRect(0, 0, canvas.clientWidth, canvas.clientHeight);
  ctx.font = "11px monospace"; ctx.textBaseline = "alphabetic";

  drawRings(g); drawSector(g); drawZones(g); drawRoutes(g);
  drawWaypoints(g); drawAirports(g); drawFixes(g);
  drawFlightRoutes(g);
  drawSweep(g);
  drawConflicts(g);
  (STATE.aircraft || []).forEach(a => drawAircraft(g, a));
  drawCenter(g); drawWind(g);
  requestAnimationFrame(render);
}

function drawRings(g) {
  ctx.strokeStyle = "#1d6b33"; ctx.fillStyle = "#1d6b33"; ctx.lineWidth = 0.8;
  for (let r = 20; r <= NAV.range_nm; r += 20) {
    ctx.beginPath(); ctx.arc(g.cx, g.cy, r * g.scale, 0, 2 * Math.PI); ctx.stroke();
    ctx.fillText(String(r), g.cx - 6, g.cy - r * g.scale - 2);
  }
  for (let deg = 0; deg < 360; deg += 30) {
    const a = (90 - deg) * Math.PI / 180;
    const r1 = (NAV.range_nm - 3) * g.scale, r2 = NAV.range_nm * g.scale;
    ctx.beginPath();
    ctx.moveTo(g.cx + r1 * Math.cos(a), g.cy - r1 * Math.sin(a));
    ctx.lineTo(g.cx + r2 * Math.cos(a), g.cy - r2 * Math.sin(a));
    ctx.stroke();
    const rt = NAV.range_nm * 1.06 * g.scale;
    ctx.fillText(String(deg).padStart(3, "0"),
      g.cx + rt * Math.cos(a) - 8, g.cy - rt * Math.sin(a) + 4);
  }
}

function drawSector(g) {
  if (!NAV.sector || !NAV.sector.length) return;
  ctx.strokeStyle = "#2e8bff"; ctx.globalAlpha = 0.7; ctx.lineWidth = 1.2;
  ctx.setLineDash([6, 5]); ctx.beginPath();
  NAV.sector.forEach((p, i) => i ? ctx.lineTo(SX(g, p[0]), SY(g, p[1])) : ctx.moveTo(SX(g, p[0]), SY(g, p[1])));
  ctx.stroke(); ctx.setLineDash([]); ctx.globalAlpha = 1;
}

function drawRoutes(g) {
  ctx.strokeStyle = "#14506b"; ctx.lineWidth = 0.7;
  (NAV.routes || []).forEach(([i, j]) => {
    const a = NAV.waypoints[i], b = NAV.waypoints[j]; if (!a || !b) return;
    ctx.beginPath(); ctx.moveTo(SX(g, a.x), SY(g, a.y)); ctx.lineTo(SX(g, b.x), SY(g, b.y)); ctx.stroke();
  });
}

function drawWaypoints(g) {
  ctx.fillStyle = "#2e8bff"; ctx.strokeStyle = "#2e8bff"; ctx.lineWidth = 1;
  (NAV.waypoints || []).forEach(w => {
    triangle(SX(g, w.x), SY(g, w.y), 4);
    ctx.fillStyle = "#2e8bff"; ctx.font = "9px monospace"; ctx.fillText(w.name, SX(g, w.x) + 5, SY(g, w.y) + 3);
  });
}

function drawFixes(g) {
  ctx.font = "10px monospace";
  (NAV.fixes || []).forEach(f => {
    const x = SX(g, f.x), y = SY(g, f.y);
    ctx.strokeStyle = "#46d6c0"; ctx.fillStyle = "#46d6c0"; ctx.lineWidth = 1.2;
    ctx.beginPath(); ctx.moveTo(x - 4, y); ctx.lineTo(x, y - 4); ctx.lineTo(x + 4, y);
    ctx.lineTo(x, y + 4); ctx.closePath(); ctx.stroke();
    ctx.fillText(f.name, x + 6, y - 4);
  });
}

function drawAirports(g) {
  ctx.font = "bold 11px monospace";
  (NAV.airports || []).forEach(p => {
    const x = SX(g, p.x), y = SY(g, p.y);
    ctx.strokeStyle = "#ffae42"; ctx.lineWidth = 1.3; ctx.strokeRect(x - 4, y - 4, 8, 8);
    ctx.fillStyle = "#ffae42"; ctx.fillText(p.name, x + 6, y - 4);
  });
}

function drawSweep(g) {
  const R = NAV.range_nm * g.scale;
  for (let k = 13; k >= 0; k--) {
    const a = (90 - (sweep - k * 4)) * Math.PI / 180;
    ctx.strokeStyle = "#33ff66";
    ctx.globalAlpha = k === 0 ? 0.9 : Math.max(0, 0.28 - k * 0.02);
    ctx.lineWidth = k === 0 ? 1.5 : 1.2;
    ctx.beginPath(); ctx.moveTo(g.cx, g.cy); ctx.lineTo(g.cx + R * Math.cos(a), g.cy - R * Math.sin(a)); ctx.stroke();
  }
  ctx.globalAlpha = 1;
}

function drawAircraft(g, a) {
  const col = a.alert === "los" ? "#ff4350" : (a.alert === "predicted" ? "#ffae42" : "#33ff66");
  const x = SX(g, a.x), y = SY(g, a.y);
  // trainee (echos)
  const tr = trails[a.id] || [];
  ctx.fillStyle = "#1d6b33";
  tr.slice(0, -1).forEach(p => ctx.fillRect(SX(g, p.x) - 1, SY(g, p.y) - 1, 2, 2));
  // vecteur vitesse (projection 1 min = gs/60 NM)
  const lead = (a.gs / 60) * g.scale;
  const ah = (90 - (a.trk != null ? a.trk : a.hdg)) * Math.PI / 180;
  ctx.strokeStyle = col; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + lead * Math.cos(ah), y - lead * Math.sin(ah)); ctx.stroke();
  // blip
  ctx.lineWidth = 1.6; ctx.strokeRect(x - 4, y - 4, 8, 8);
  if (a.inzone) {                                     // avion dans une zone orage/interdite
    ctx.strokeStyle = "#ff5ab0"; ctx.lineWidth = 1.2;
    ctx.beginPath(); ctx.arc(x, y, 9, 0, 2 * Math.PI); ctx.stroke();
    ctx.strokeStyle = col;
  }
  // bloc de donnees : indicatif / FL GS
  ctx.fillStyle = col; ctx.font = "11px monospace";
  ctx.fillText(a.id, x + 7, y - 4);
  ctx.fillText(`${String(a.fl).padStart(3, "0")} ${String(a.gs).padStart(3, "0")}`, x + 7, y + 8);
}

function drawZones(g) {
  (STATE.zones || []).forEach(z => {
    ctx.save();
    ctx.strokeStyle = z.color; ctx.lineWidth = 1.4;
    ctx.fillStyle = z.color + "26";          // ~15% alpha
    if (z.shape === "CIRCLE") {
      ctx.beginPath(); ctx.arc(SX(g, z.cx), SY(g, z.cy), z.r * g.scale, 0, 2 * Math.PI);
      ctx.fill(); ctx.stroke();
      ctx.fillStyle = z.color; ctx.font = "10px monospace";
      ctx.fillText(z.type === "storm" ? "ORAGE" : "INTERDIT", SX(g, z.cx) - 16, SY(g, z.cy));
    } else if (z.points && z.points.length) {
      ctx.beginPath();
      z.points.forEach((p, i) => i ? ctx.lineTo(SX(g, p[0]), SY(g, p[1])) : ctx.moveTo(SX(g, p[0]), SY(g, p[1])));
      ctx.closePath(); ctx.fill(); ctx.stroke();
    }
    ctx.restore();
  });
}

function drawFlightRoutes(g) {
  ctx.save();
  (STATE.aircraft || []).forEach(a => {
    const r = a.route || []; if (r.length < 1) return;
    ctx.strokeStyle = "#7a5cff"; ctx.lineWidth = 0.9; ctx.setLineDash([2, 3]);
    ctx.beginPath(); ctx.moveTo(SX(g, a.x), SY(g, a.y));
    r.forEach(p => ctx.lineTo(SX(g, p[0]), SY(g, p[1])));
    ctx.stroke(); ctx.setLineDash([]);
    if (a.actwp >= 0 && a.actwp < r.length) {            // prochain point actif
      const w = r[a.actwp];
      ctx.strokeStyle = "#b9a6ff"; ctx.lineWidth = 1.2;
      ctx.beginPath(); ctx.arc(SX(g, w[0]), SY(g, w[1]), 3, 0, 2 * Math.PI); ctx.stroke();
    }
  });
  ctx.restore();
}

function drawWind(g) {
  const w = STATE.wind; if (!w) return;
  const ox = 64, oy = canvas.clientHeight - 56, len = 26;        // coin bas-gauche
  const a = (90 - (w.dir + 180)) * Math.PI / 180;                 // fleche = vers où va le vent
  ctx.save();
  ctx.strokeStyle = "#69d0ff"; ctx.fillStyle = "#69d0ff"; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(ox, oy); ctx.lineTo(ox + len * Math.cos(a), oy - len * Math.sin(a)); ctx.stroke();
  const hx = ox + len * Math.cos(a), hy = oy - len * Math.sin(a);
  ctx.beginPath(); ctx.arc(hx, hy, 2.5, 0, 2 * Math.PI); ctx.fill();
  ctx.font = "11px monospace";
  ctx.fillText(`VENT ${String(w.dir).padStart(3, "0")}/${w.spd}kt${w.alt ? " FL" + Math.round(w.alt / 100) : ""}`, ox - 30, oy + 18);
  ctx.restore();
}

function drawConflicts(g) {
  const pos = {}; (STATE.aircraft || []).forEach(a => pos[a.id] = a);
  // perte de separation (avions trop proches) : trait rouge plein
  (STATE.conflicts || []).forEach(pair => {
    const a = pos[pair[0]], b = pos[pair[1]]; if (!a || !b) return;
    ctx.strokeStyle = "#ff4350"; ctx.lineWidth = 1.5; ctx.setLineDash([]);
    ctx.beginPath(); ctx.moveTo(SX(g, a.x), SY(g, a.y)); ctx.lineTo(SX(g, b.x), SY(g, b.y)); ctx.stroke();
  });
  // conflit predit (impact possible) : trait ambre pointille + tCPA / distance mini
  (STATE.predicted || []).forEach(p => {
    const a = pos[p.pair[0]], b = pos[p.pair[1]]; if (!a || !b) return;
    ctx.strokeStyle = "#ffae42"; ctx.lineWidth = 1.1; ctx.setLineDash([5, 4]);
    ctx.beginPath(); ctx.moveTo(SX(g, a.x), SY(g, a.y)); ctx.lineTo(SX(g, b.x), SY(g, b.y)); ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = "#ffae42"; ctx.font = "10px monospace";
    ctx.fillText(`${p.t}s · ${p.d}NM`, (SX(g, a.x) + SX(g, b.x)) / 2 + 3, (SY(g, a.y) + SY(g, b.y)) / 2 - 3);
  });
}

function drawCenter(g) {
  ctx.strokeStyle = "#33ff66"; ctx.lineWidth = 1.2;
  ctx.beginPath(); ctx.moveTo(g.cx - 6, g.cy); ctx.lineTo(g.cx + 6, g.cy);
  ctx.moveTo(g.cx, g.cy - 6); ctx.lineTo(g.cx, g.cy + 6); ctx.stroke();
}

function triangle(x, y, s) {
  ctx.beginPath(); ctx.moveTo(x, y - s); ctx.lineTo(x - s, y + s); ctx.lineTo(x + s, y + s);
  ctx.closePath(); ctx.stroke();
}

/* ============================ actions UI ============================ */
function wireUI() {
  $("mode-badge").onclick = async () => { logLine("re-détection ROMEO…", "");
    try { const h = await (await fetch("/api/health/refresh", { method: "POST" })).json(); CAPS = h.caps; MODE = h.mode; } catch (e) {}
    refreshHealth(); };

  $("gen-btn").onclick = generateScenario;
  $("scenario-text").addEventListener("keydown", e => { if (e.key === "Enter" && e.ctrlKey) generateScenario(); });
  $("load-btn").onclick = loadScenario;
  $("scenario-mic").onclick = () => dictateInto($("scenario-text"));

  $("send-btn").onclick = sendTyped;
  $("cmd-text").addEventListener("keydown", e => { if (e.key === "Enter") sendTyped(); });

  $("reset-btn").onclick = () => { fetch("/api/sim/reset", { method: "POST" }); trails = {}; };
  let paused = false;
  $("pause-btn").onclick = () => { paused = !paused;
    fetch("/api/sim/" + (paused ? "pause" : "resume"), { method: "POST" });
    $("pause-btn").textContent = paused ? "▶" : "⏸"; };
  $("speed").oninput = (e) => { $("speed-val").textContent = e.target.value + "×";
    fetch("/api/sim/speed", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ value: +e.target.value }) }); };

  $("hide-instr").onclick = () => { $("instructor").classList.add("hidden"); $("show-instr").classList.remove("hidden"); };
  $("show-instr").onclick = () => { $("instructor").classList.remove("hidden"); $("show-instr").classList.add("hidden"); };

  // --- météo & zones ---
  const postJSON = (url, body) => fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
  $("wind-btn").onclick = () => {
    const dir = $("wind-dir").value.trim(); if (dir === "") return;
    const body = { dir: +dir, spd: +($("wind-spd").value.trim() || 0) };
    const fl = $("wind-fl").value.trim(); if (fl) body.alt = (+fl) * 100;
    postJSON("/api/weather/wind", body);
  };
  $("wind-clr").onclick = () => postJSON("/api/weather/wind", { dir: "" });
  $("turb").oninput = (e) => { $("turb-val").textContent = e.target.value; postJSON("/api/weather/turbulence", { level: +e.target.value }); };
  let placeMode = null;
  const setPlace = (m) => {
    placeMode = m; const h = $("place-hint");
    if (m) { h.classList.remove("hidden"); h.textContent = "Cliquez sur le radar pour placer " + (m === "storm" ? "la cellule orageuse ⛈" : "la zone interdite ⛔"); }
    else { h.classList.add("hidden"); }
  };
  $("storm-btn").onclick = () => setPlace(placeMode === "storm" ? null : "storm");
  $("zone-btn").onclick = () => setPlace(placeMode === "zone" ? null : "zone");
  $("zone-clr").onclick = () => postJSON("/api/weather/clearzones", {});
  canvas.addEventListener("click", (e) => {
    if (!placeMode) return;
    const r = canvas.getBoundingClientRect(), g = geom();
    const xnm = (e.clientX - r.left - g.cx) / g.scale, ynm = (g.cy - (e.clientY - r.top)) / g.scale;
    postJSON("/api/weather/zone", { ztype: placeMode === "storm" ? "storm" : "restricted", shape: "CIRCLE", x: xnm, y: ynm, r: placeMode === "storm" ? 14 : 10 });
    setPlace(null);
  });
  $("gui-btn").onclick = async () => {
    logLine("lancement du GUI BlueSky natif…", "");
    try { const r = await fetch("/api/gui/launch", { method: "POST" }); const j = await r.json();
      logLine(r.ok ? "GUI BlueSky natif lancé (situation exportée)." : "GUI : " + (j.detail || "erreur"), r.ok ? "o" : "r");
    } catch (e) { logLine("GUI : " + e, "r"); }
  };

  setupPTT();
}

async function generateScenario() {
  const desc = $("scenario-text").value.trim(); if (!desc) return;
  logLine("✈ génération : " + desc, "o");
  try {
    await fetch("/api/scenario", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ description: desc }) });
  } catch (e) { logLine("erreur génération : " + e, "r"); }
}

async function loadScenario() {
  const name = $("scenario-list").value; if (!name) return;
  try {
    await fetch("/api/scenario/load", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }) });
  } catch (e) { logLine("erreur chargement : " + e, "r"); }
}

async function sendTyped() {
  const t = $("cmd-text").value.trim(); if (!t) return;
  $("cmd-text").value = "";
  await sendCommand(t);
}

async function sendCommand(text) {
  try {
    await fetch("/api/command", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }) });
  } catch (e) { logLine("erreur commande : " + e, "r"); }
}

/* ============================ voix (push-to-talk) ============================ */
let recog = null, audio = { ctx: null, stream: null, proc: null, src: null, buf: [], rate: 48000, on: false };

function setupPTT() {
  const ptt = $("ptt");
  const down = (e) => { e.preventDefault(); startTalk(); };
  const up = (e) => { e.preventDefault(); stopTalk(); };
  ptt.addEventListener("mousedown", down);
  ptt.addEventListener("touchstart", down, { passive: false });
  window.addEventListener("mouseup", up);
  ptt.addEventListener("touchend", up);
  // barre espace = alternative push-to-talk
  window.addEventListener("keydown", e => { if (e.code === "Space" && e.target.tagName !== "INPUT" && e.target.tagName !== "TEXTAREA" && !audio.on && !talking) { e.preventDefault(); startTalk(); } });
  window.addEventListener("keyup", e => { if (e.code === "Space" && e.target.tagName !== "INPUT" && e.target.tagName !== "TEXTAREA") { e.preventDefault(); stopTalk(); } });
}

let talking = false;
function startTalk() {
  if (talking) return; talking = true;
  $("ptt").classList.add("live"); $("ptt").textContent = "🔴 TRANSMISSION…";
  if (CAPS.asr) startAudioCapture(); else startRecognition();
}
function stopTalk() {
  if (!talking) return; talking = false;
  $("ptt").classList.remove("live"); $("ptt").textContent = "🎙 MAINTENIR POUR PARLER";
  if (CAPS.asr) stopAudioCapture(); else stopRecognition();
}

/* -- mode local : reconnaissance vocale du navigateur -- */
function getRecognition() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) return null;
  const r = new SR(); r.lang = "en-US"; r.interimResults = false; r.maxAlternatives = 1; r.continuous = false;
  return r;
}
function startRecognition() {
  recog = getRecognition();
  if (!recog) { logLine("Reconnaissance vocale indisponible — tapez la clairance.", "r"); stopTalk(); return; }
  recog.onresult = (e) => { const t = e.results[0][0].transcript; if (t) sendCommand(t); };
  recog.onerror = (e) => logLine("STT : " + e.error, "r");
  try { recog.start(); } catch (e) {}
}
function stopRecognition() { if (recog) { try { recog.stop(); } catch (e) {} } }

/* -- mode ROMEO : capture WAV 16k -> /api/voice -- */
async function startAudioCapture() {
  try {
    audio.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audio.ctx = new (window.AudioContext || window.webkitAudioContext)();
    audio.rate = audio.ctx.sampleRate;
    audio.src = audio.ctx.createMediaStreamSource(audio.stream);
    audio.proc = audio.ctx.createScriptProcessor(4096, 1, 1);
    audio.buf = []; audio.on = true;
    audio.proc.onaudioprocess = (e) => { if (audio.on) audio.buf.push(new Float32Array(e.inputBuffer.getChannelData(0))); };
    audio.src.connect(audio.proc); audio.proc.connect(audio.ctx.destination);
  } catch (e) { logLine("micro indisponible : " + e, "r"); stopTalk(); }
}
async function stopAudioCapture() {
  audio.on = false;
  try { audio.proc.disconnect(); audio.src.disconnect(); audio.stream.getTracks().forEach(t => t.stop()); } catch (e) {}
  const data = mergeFloat(audio.buf);
  try { audio.ctx.close(); } catch (e) {}
  if (!data.length) return;
  const wav = encodeWav(downsample(data, audio.rate, 16000), 16000);
  $("ptt").classList.add("busy");
  try {
    const fd = new FormData(); fd.append("file", new Blob([wav], { type: "audio/wav" }), "utt.wav");
    const r = await fetch("/api/voice", { method: "POST", body: fd });
    const j = await r.json();
    if (j.audio_b64) playB64Wav(j.audio_b64);     // voix pilote synthetisee (ROMEO)
  } catch (e) { logLine("erreur /api/voice : " + e, "r"); }
  $("ptt").classList.remove("busy");
}

function mergeFloat(chunks) {
  let n = 0; chunks.forEach(c => n += c.length);
  const out = new Float32Array(n); let o = 0;
  chunks.forEach(c => { out.set(c, o); o += c.length; });
  return out;
}
function downsample(buf, from, to) {
  if (to >= from) return buf;
  const ratio = from / to, n = Math.round(buf.length / ratio), out = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const start = Math.floor(i * ratio), end = Math.min(buf.length, Math.floor((i + 1) * ratio));
    let s = 0, c = 0; for (let j = start; j < end; j++) { s += buf[j]; c++; }
    out[i] = c ? s / c : 0;
  }
  return out;
}
function encodeWav(samples, rate) {
  const buf = new ArrayBuffer(44 + samples.length * 2), v = new DataView(buf);
  const wr = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
  wr(0, "RIFF"); v.setUint32(4, 36 + samples.length * 2, true); wr(8, "WAVE"); wr(12, "fmt ");
  v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
  v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true);
  v.setUint16(34, 16, true); wr(36, "data"); v.setUint32(40, samples.length * 2, true);
  let o = 44; for (let i = 0; i < samples.length; i++) { const s = Math.max(-1, Math.min(1, samples[i])); v.setInt16(o, s < 0 ? s * 0x8000 : s * 0x7FFF, true); o += 2; }
  return buf;
}
function playB64Wav(b64) {
  const bin = atob(b64), arr = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
  const url = URL.createObjectURL(new Blob([arr], { type: "audio/wav" }));
  new Audio(url).play().catch(() => {});
}

function speak(text) {
  if (!window.speechSynthesis) return;
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "en-US"; u.rate = 1.05; u.pitch = 0.9;
  window.speechSynthesis.speak(u);
}

function dictateInto(el) {
  const r = getRecognition();
  if (!r) { logLine("dictée indisponible.", "r"); return; }
  r.onresult = (e) => { el.value = e.results[0][0].transcript; };
  try { r.start(); } catch (e) {}
}

/* ============================ utilitaires ============================ */
function logLine(text, cls) {
  const log = $("log"), div = document.createElement("div");
  if (cls) div.className = cls;
  div.textContent = text;
  log.appendChild(div);
  while (log.childNodes.length > 200) log.removeChild(log.firstChild);
  log.scrollTop = log.scrollHeight;
}
function escapeHtml(s) {
  return String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

init();
