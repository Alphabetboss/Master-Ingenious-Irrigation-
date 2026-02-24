// ===============================================================
// Ingenious Irrigation — Astra UI (Upgraded Edition)
// Clean, safe, modern, and fully equivalent to your original logic
// ===============================================================

// Backend endpoints expected:
//   GET  /api/schedule
//   POST /api/schedule/update  { zone, minutes }
//   POST /astra/chat           { message }

// Local-only metadata (start time + frequency)
const LS_KEY = "ii_ui_zone_meta_v1";

// Global state
let schedule = { zones: {} };
let activeZone = "1";

// ---------------------------------------------------------------
// DOM Helpers
// ---------------------------------------------------------------
function $(id) {
  return document.getElementById(id);
}

const els = {
  connPill: $("connPill"),

  zoneButtons: $("zoneButtons"),
  zoneName: $("zoneName"),
  zoneEnabled: $("zoneEnabled"),
  zoneStart: $("zoneStart"),
  zoneMinutes: $("zoneMinutes"),
  btnSaveZone: $("btnSaveZone"),
  btnSaveAll: $("btnSaveAll"),
  btnRunNow: $("btnRunNow"),
  btnStopZone: $("btnStopZone"),

  scheduleSummary: $("scheduleSummary"),
  audioStatus: $("audioStatus"),

  chatlog: $("chatlog"),
  chatForm: $("chatForm"),
  chatInput: $("chatInput"),
  btnClearChat: $("btnClearChat"),

  btnSettings: $("btnSettings"),
  settingsDrawer: $("settingsDrawer"),
  btnCloseSettings: $("btnCloseSettings"),
  backdrop: $("backdrop"),
  btnReloadSchedule: $("btnReloadSchedule"),
};

// ---------------------------------------------------------------
// Utility
// ---------------------------------------------------------------
function safeText(v) {
  return v == null ? "" : String(v);
}

function addMsg(who, text) {
  if (!els.chatlog) return;
  const row = document.createElement("div");
  row.className = `msg ${who}`;

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = safeText(text);

  row.appendChild(bubble);
  els.chatlog.appendChild(row);
  els.chatlog.scrollTop = els.chatlog.scrollHeight;
}

function setConn(state) {
  if (!els.connPill) return;

  const map = {
    online: { text: "Online", color: "var(--green)" },
    offline: { text: "Offline", color: "var(--red)" },
    loading: { text: "Connecting…", color: "var(--muted)" },
  };

  const cfg = map[state] || map.loading;
  els.connPill.textContent = cfg.text;
  els.connPill.style.color = cfg.color;
}

// ---------------------------------------------------------------
// HTTP Helpers
// ---------------------------------------------------------------
async function httpJson(url, opts = {}) {
  const r = await fetch(url, opts);
  const ct = r.headers.get("content-type") || "";

  if (!r.ok) {
    const body = ct.includes("application/json")
      ? await r.json().catch(() => ({}))
      : await r.text().catch(() => "");
    throw new Error(
      `HTTP ${r.status} ${url} :: ${
        typeof body === "string" ? body : JSON.stringify(body)
      }`
    );
  }

  return ct.includes("application/json") ? r.json() : r.text();
}

const apiGetSchedule = () =>
  httpJson("/api/schedule", { method: "GET" });

const apiUpdateZoneMinutes = (zone, minutes) =>
  httpJson("/api/schedule/update", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ zone, minutes }),
  });

const apiAstraChat = (message) =>
  httpJson("/astra/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });

// ---------------------------------------------------------------
// Local Meta (start time + frequency)
// ---------------------------------------------------------------
function loadMeta() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    return raw ? JSON.parse(raw) : { zones: {} };
  } catch {
    return { zones: {} };
  }
}

function saveMeta(meta) {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(meta));
  } catch {}
}

function getActiveFreq() {
  const checked = document.querySelector('input[name="freq"]:checked');
  return checked ? checked.value : "daily";
}

function setActiveFreq(val) {
  const el = document.querySelector(`input[name="freq"][value="${val}"]`);
  if (el) el.checked = true;
}

// ---------------------------------------------------------------
// UI Rendering
// ---------------------------------------------------------------
function ensureSixZones() {
  schedule.zones = schedule.zones || {};
  for (let i = 1; i <= 6; i++) {
    const z = String(i);
    if (!schedule.zones[z]) {
      schedule.zones[z] = { minutes: 10, enabled: true };
    }
    if (typeof schedule.zones[z].enabled !== "boolean")
      schedule.zones[z].enabled = true;
    if (typeof schedule.zones[z].minutes !== "number")
      schedule.zones[z].minutes = 10;
  }
}

function paintZoneButtons() {
  if (!els.zoneButtons) return;
  els.zoneButtons.innerHTML = "";

  for (let i = 1; i <= 6; i++) {
    const z = String(i);
    const b = document.createElement("button");
    b.type = "button";
    b.className = "zoneBtn" + (z === activeZone ? " active" : "");
    b.textContent = `Zone ${z}`;
    b.addEventListener("click", () => {
      activeZone = z;
      paintZoneButtons();
      paintZoneCard();
      paintSummary();
    });
    els.zoneButtons.appendChild(b);
  }
}

function paintZoneCard() {
  const zones = schedule.zones || {};
  const z = zones[activeZone] || { minutes: 10, enabled: true };
  const meta = loadMeta();
  const zMeta = meta.zones?.[activeZone] || {};

  if (els.zoneName) els.zoneName.textContent = `Zone ${activeZone}`;
  if (els.zoneMinutes) els.zoneMinutes.value = Number(z.minutes);
  if (els.zoneEnabled) els.zoneEnabled.checked = !!z.enabled;

  if (els.zoneStart) els.zoneStart.value = zMeta.start || "05:00";
  setActiveFreq(zMeta.freq || "daily");
}

function paintSummary() {
  if (!els.scheduleSummary) return;

  const zones = schedule.zones || {};
  const meta = loadMeta();

  const parts = [];
  for (let i = 1; i <= 6; i++) {
    const k = String(i);
    const z = zones[k] || { minutes: 10, enabled: true };
    const zMeta = meta.zones?.[k] || {};
    const start = zMeta.start || "05:00";
    const freq = zMeta.freq || "daily";
    const onOff = z.enabled ? "ON" : "OFF";
    parts.push(`Z${k}: ${onOff} • ${start} • ${z.minutes}m • ${freq}`);
  }

  els.scheduleSummary.textContent = parts.join("  |  ");
}

// ---------------------------------------------------------------
// Actions
// ---------------------------------------------------------------
async function loadFromServer() {
  setConn("loading");
  try {
    const j = await apiGetSchedule();
    schedule = typeof j === "object" ? j : { zones: {} };
    ensureSixZones();
    setConn("online");
  } catch (e) {
    schedule = { zones: {} };
    ensureSixZones();
    setConn("offline");
    addMsg(
      "astra",
      "I can’t reach the server right now. UI is running in offline mode."
    );
  }
}

async function saveActiveZone() {
  ensureSixZones();
  const zones = schedule.zones;
  const z = zones[activeZone];

  const minutes = parseInt(els.zoneMinutes?.value || "10", 10);
  z.minutes = isNaN(minutes) ? 10 : Math.max(0, minutes);
  z.enabled = !!els.zoneEnabled?.checked;

  // Save local meta
  const meta = loadMeta();
  meta.zones = meta.zones || {};
  meta.zones[activeZone] = {
    start: els.zoneStart?.value || "05:00",
    freq: getActiveFreq(),
  };
  saveMeta(meta);

  try {
    await apiUpdateZoneMinutes(activeZone, z.minutes);
    addMsg(
      "astra",
      `Saved Zone ${activeZone}: ${z.minutes} minutes. (Start/frequency saved locally)`
    );
  } catch (e) {
    addMsg("astra", `Couldn’t save Zone ${activeZone}. (${e.message})`);
  }

  paintSummary();
}

async function saveAllZones() {
  ensureSixZones();

  // Save meta for active zone
  const meta = loadMeta();
  meta.zones = meta.zones || {};
  meta.zones[activeZone] = {
    start: els.zoneStart?.value || "05:00",
    freq: getActiveFreq(),
  };
  saveMeta(meta);

  let ok = 0,
    fail = 0;
  const zones = schedule.zones;

  for (let i = 1; i <= 6; i++) {
    const k = String(i);
    const z = zones[k];
    try {
      await apiUpdateZoneMinutes(k, Number(z.minutes));
      ok++;
    } catch {
      fail++;
    }
  }

  addMsg(
    "astra",
    `Save All complete. ✅ ${ok} zones saved, ❌ ${fail} failed. (Start/frequency are local.)`
  );
  paintSummary();
}

async function runNow() {
  const mins = parseInt(els.zoneMinutes?.value || "10", 10);
  const m = isNaN(mins) ? 10 : mins;

  addMsg("you", `Run Zone ${activeZone} now for ${m} minutes.`);

  try {
    const j = await apiAstraChat(`Start zone ${activeZone} for ${m} minutes`);
    addMsg("astra", j.reply || "(no reply)");
  } catch (e) {
    addMsg("astra", `Chat failed: ${e.message}`);
  }
}

async function stopZone() {
  addMsg("you", `Stop Zone ${activeZone}.`);
  try {
    const j = await apiAstraChat(`Stop zone ${activeZone}`);
    addMsg("astra", j.reply || "(no reply)");
  } catch (e) {
    addMsg("astra", `Chat failed: ${e.message}`);
  }
}

async function sendChat(text) {
  addMsg("you", text);
  try {
    const j = await apiAstraChat(text);
    addMsg("astra", j.reply || "(no reply)");
  } catch (e) {
    addMsg("astra", `Chat failed: ${e.message}`);
  }
}

// ---------------------------------------------------------------
// UI Bindings
// ---------------------------------------------------------------
function bindUI() {
  els.btnSaveZone?.addEventListener("click", saveActiveZone);
  els.btnSaveAll?.addEventListener("click", saveAllZones);
  els.btnRunNow?.addEventListener("click", runNow);
  els.btnStopZone?.addEventListener("click", stopZone);

  els.btnClearChat?.addEventListener("click", () => {
    if (els.chatlog) els.chatlog.innerHTML = "";
  });

  els.chatForm?.addEventListener("submit", (ev) => {
    ev.preventDefault();
    const text = els.chatInput?.value.trim();
    if (!text) return;
    els.chatInput.value = "";
    sendChat(text);
  });

  document.querySelectorAll(".chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      const p = btn.getAttribute("data-prompt") || "";
      if (!p) return;
      els.chatInput.value = p;
      els.chatInput.focus();
    });
  });

  els.btnSettings?.addEventListener("click", () =>
    els.settingsDrawer.classList.add("open")
  );
  els.btnCloseSettings?.addEventListener("click", () =>
    els.settingsDrawer.classList.remove("open")
  );
  els.backdrop?.addEventListener("click", () =>
    els.settingsDrawer.classList.remove("open")
  );

  els.btnReloadSchedule?.addEventListener("click", async () => {
    await loadFromServer();
    paintZoneButtons();
    paintZoneCard();
    paintSummary();
    addMsg("astra", "Schedule reloaded from server.");
  });

  els.zoneStart?.addEventListener("change", paintSummary);
  document
    .querySelectorAll('input[name="freq"]')
    .forEach((r) => r.addEventListener("change", paintSummary));
}

// ---------------------------------------------------------------
// Boot
// ---------------------------------------------------------------
async function boot() {
  bindUI();
  await loadFromServer();
  paintZoneButtons();
  paintZoneCard();
  paintSummary();

  if (els.audioStatus) {
    els.audioStatus.textContent =
      "Voice: UI ready. (Server TTS can be added next.)";
  }

  addMsg(
    "astra",
    "Astra online. Select a zone, set minutes, Save, or type a message."
  );
}

document.addEventListener("DOMContentLoaded", boot);
