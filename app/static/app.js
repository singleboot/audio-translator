// Audio Translator v1 — UI logic.
// Talks to the FastAPI backend; WebSocket pushes job updates live.

const $ = (id) => document.getElementById(id);

const state = {
  engines: [],                 // [{id, display_name, supports_voice_clone, requires_network}]
  translators: [],             // [{id, display_name}]
  languages: [],               // [{code, name}]
  perEngine: {},               // engine_id -> [code, ...]
  configured: [],              // [code, ...]
  ttsEnabled: [],              // [engine_id, ...]
  translatorDefault: "nllb_local",
  jobs: [],                    // latest first
  queue: [],                   // playback items
  queueIndex: -1,
  watcherRunning: false,
};

// ----------------------------------------------------------------------
// Boot
// ----------------------------------------------------------------------
async function boot() {
  await Promise.all([loadEngines(), loadTranslators(), loadLanguages(), loadSettings()]);
  renderEngines();
  renderTranslators();
  renderLanguages();
  await loadJobs();
  await loadPlayback();
  connectWS();
}

async function loadEngines() {
  const r = await fetch("/api/engines").then((r) => r.json());
  state.engines = r.engines;
  state.ttsEnabled = r.enabled;
}
async function loadTranslators() {
  const r = await fetch("/api/translators").then((r) => r.json());
  state.translators = r.translators;
  state.translatorDefault = r.default;
}
async function loadLanguages() {
  const r = await fetch("/api/languages").then((r) => r.json());
  state.languages = r.languages;
  state.perEngine = r.per_engine;
  state.configured = r.configured;
}
async function loadSettings() {
  const r = await fetch("/api/settings").then((r) => r.json());
  $("watch-folder").value = r.watch_folder;
  state.watcherRunning = r.watcher_running;
  state.ttsEnabled = r.tts_enabled;
  state.configured = r.languages;
  state.translatorDefault = r.translator_default;
  setWatcherBadge(r.watcher_running);
}
async function loadJobs() {
  const r = await fetch("/api/jobs?limit=50").then((r) => r.json());
  state.jobs = r.jobs;
  renderJobs();
}
async function loadPlayback() {
  const r = await fetch("/api/playback?limit=200").then((r) => r.json());
  state.queue = r.items;
  renderQueue();
}

// ----------------------------------------------------------------------
// Render
// ----------------------------------------------------------------------
function renderEngines() {
  const c = $("engine-list");
  c.innerHTML = "";
  for (const e of state.engines) {
    const id = `eng-${e.id}`;
    const wrap = document.createElement("label");
    wrap.innerHTML = `
      <input type="checkbox" id="${id}" ${state.ttsEnabled.includes(e.id) ? "checked" : ""} />
      <span>${e.display_name}</span>
    `;
    c.appendChild(wrap);
  }
}
function renderTranslators() {
  const c = $("translator-list");
  c.innerHTML = "";
  for (const t of state.translators) {
    const id = `tr-${t.id}`;
    const wrap = document.createElement("label");
    wrap.innerHTML = `
      <input type="radio" name="translator" id="${id}" value="${t.id}" ${t.id === state.translatorDefault ? "checked" : ""} />
      <span>${t.display_name}</span>
    `;
    c.appendChild(wrap);
  }
}
function renderLanguages() {
  const filter = ($("lang-filter").value || "").toLowerCase();
  const c = $("lang-list");
  c.innerHTML = "";
  const list = state.languages.filter((l) =>
    !filter || l.code.includes(filter) || l.name.toLowerCase().includes(filter)
  );
  for (const l of list) {
    const id = `lang-${l.code}`;
    const supportedBy = state.engines
      .filter((e) => state.ttsEnabled.includes(e.id))
      .filter((e) => (state.perEngine[e.id] || []).includes(l.code))
      .map((e) => e.id);
    const supportedLabel = supportedBy.length
      ? `<span class="meta">${supportedBy.length}/${state.engines.length}</span>`
      : `<span class="meta" style="color:var(--err)">0</span>`;
    const wrap = document.createElement("label");
    wrap.title = `Supported by: ${supportedBy.join(", ") || "none"}`;
    wrap.innerHTML = `
      <input type="checkbox" id="${id}" data-code="${l.code}" ${state.configured.includes(l.code) ? "checked" : ""} />
      <span>${l.name} (${l.code})</span>
      ${supportedLabel}
    `;
    c.appendChild(wrap);
  }
}
function renderJobs() {
  const tbody = $("jobs-table").querySelector("tbody");
  tbody.innerHTML = "";
  for (const j of state.jobs) {
    const tr = document.createElement("tr");
    tr.className = `row-${j.status}`;
    const updated = new Date(j.updated_at * 1000).toLocaleTimeString();
    const arts = (j.artifacts || []).length;
    const engines = (() => { try { return JSON.parse(j.engines || "[]").length; } catch { return 0; } })();
    const langs = (() => { try { return JSON.parse(j.languages || "[]").length; } catch { return 0; } })();
    tr.innerHTML = `
      <td class="status-cell"><span class="status-${j.status}">${j.status}</span></td>
      <td>${j.source_stem}</td>
      <td>${j.src_lang || ""}</td>
      <td>${engines}</td>
      <td>${langs}</td>
      <td>${arts}</td>
      <td>${updated}</td>
    `;
    tbody.appendChild(tr);
  }
}
function renderQueue() {
  const ol = $("playback-list");
  ol.innerHTML = "";
  state.queue.forEach((item, i) => {
    const li = document.createElement("li");
    if (i === state.queueIndex) li.classList.add("active");
    li.innerHTML = `
      <span>${item.source_stem} <span class="meta">[${item.engine} / ${item.language}]</span></span>
      <span class="meta">${item.duration_s ? item.duration_s.toFixed(1) + "s" : ""}</span>
    `;
    li.addEventListener("click", () => playIndex(i));
    ol.appendChild(li);
  });
}

function setWatcherBadge(running) {
  const el = $("watcher-status");
  el.textContent = `watcher: ${running ? "on" : "off"}`;
  el.style.background = running ? "var(--ok)" : "var(--border)";
  el.style.color = running ? "#0e1116" : "var(--text)";
}

// ----------------------------------------------------------------------
// WebSocket
// ----------------------------------------------------------------------
function connectWS() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onopen = () => {
    $("ws-status").className = "dot dot-on";
    $("ws-status").textContent = "online";
  };
  ws.onclose = () => {
    $("ws-status").className = "dot dot-off";
    $("ws-status").textContent = "offline";
    setTimeout(connectWS, 2000);
  };
  ws.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data);
      if (msg.type === "hello") {
        state.watcherRunning = msg.watcher_running;
        setWatcherBadge(msg.watcher_running);
        if (msg.settings) {
          $("watch-folder").value = msg.settings.watch_folder;
          state.ttsEnabled = msg.settings.tts_enabled;
          state.configured = msg.settings.languages;
          state.translatorDefault = msg.settings.translator_default;
          renderEngines(); renderTranslators(); renderLanguages();
        }
      } else if (msg.type === "job_update") {
        upsertJob(msg.job);
        // When a job is done, refresh the playback queue.
        if (msg.job && (msg.job.status === "done" || msg.job.status === "error")) {
          loadPlayback();
        }
      }
    } catch (e) {
      console.error("bad ws message", e);
    }
  };
}

function upsertJob(job) {
  if (!job) return;
  const i = state.jobs.findIndex((j) => j.job_uuid === job.job_uuid);
  if (i >= 0) state.jobs[i] = job;
  else state.jobs.unshift(job);
  renderJobs();
}

// ----------------------------------------------------------------------
// Actions
// ----------------------------------------------------------------------
$("watcher-start").addEventListener("click", async () => {
  await fetch("/api/watcher/start", { method: "POST" });
  state.watcherRunning = true; setWatcherBadge(true);
});
$("watcher-stop").addEventListener("click", async () => {
  await fetch("/api/watcher/stop", { method: "POST" });
  state.watcherRunning = false; setWatcherBadge(false);
});
$("reload-settings").addEventListener("click", async () => {
  await loadSettings();
  renderEngines(); renderTranslators(); renderLanguages();
});

$("engine-all").addEventListener("click", () => {
  document.querySelectorAll("#engine-list input").forEach((el) => (el.checked = true));
});
$("engine-none").addEventListener("click", () => {
  document.querySelectorAll("#engine-list input").forEach((el) => (el.checked = false));
});

$("lang-all").addEventListener("click", () => {
  document.querySelectorAll("#lang-list input").forEach((el) => (el.checked = true));
});
$("lang-none").addEventListener("click", () => {
  document.querySelectorAll("#lang-list input").forEach((el) => (el.checked = false));
});
$("lang-filter").addEventListener("input", renderLanguages);

$("save-settings").addEventListener("click", async () => {
  const engines = [...document.querySelectorAll("#engine-list input:checked")].map((el) => el.id.replace(/^eng-/, ""));
  const langs = [...document.querySelectorAll("#lang-list input:checked")].map((el) => el.dataset.code);
  const translator = (document.querySelector('input[name="translator"]:checked') || {}).value || "nllb_local";
  const r = await fetch("/api/settings", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ tts_enabled: engines, languages: langs, translator_default: translator }),
  }).then((r) => r.json());
  if (r.ok) {
    state.ttsEnabled = engines;
    state.configured = langs;
    state.translatorDefault = translator;
    $("save-feedback").textContent = "Saved.";
    setTimeout(() => ($("save-feedback").textContent = ""), 1500);
  }
});

$("file-submit").addEventListener("click", async () => {
  const f = $("file-input").files[0];
  if (!f) return;
  const fd = new FormData();
  fd.append("file", f);
  await fetch("/api/watcher/process", { method: "POST", body: fd });
  $("file-input").value = "";
});

// ----------------------------------------------------------------------
// Player
// ----------------------------------------------------------------------
const player = $("player");
function playIndex(i) {
  if (i < 0 || i >= state.queue.length) return;
  state.queueIndex = i;
  const item = state.queue[i];
  player.src = `/api/audio?path=${encodeURIComponent(item.output_path)}`;
  $("now-playing").textContent = `${item.source_stem} — ${item.engine} / ${item.language}`;
  player.play().catch(() => {});
  renderQueue();
}
player.addEventListener("ended", () => playIndex(state.queueIndex + 1));
$("play-prev").addEventListener("click", () => playIndex(Math.max(0, state.queueIndex - 1)));
$("play-next").addEventListener("click", () => playIndex(state.queueIndex + 1));
$("play-clear").addEventListener("click", () => {
  state.queue = []; state.queueIndex = -1; player.pause(); player.src = "";
  $("now-playing").textContent = "—";
  renderQueue();
});

boot();
