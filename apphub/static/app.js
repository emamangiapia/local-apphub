/* Local AppHub by iPhone Facile - no external dependencies. */
"use strict";

const byId = (id) => document.getElementById(id);
const model = { csrf: null, apps: [], category: "Tutte", search: "", busy: false, editingSlug: null };
const statuses = {
  running: { label: "In esecuzione", style: "live" },
  deploying: { label: "Installazione...", style: "working" },
  stopped: { label: "In pausa", style: "paused" },
  "not-installed": { label: "Da installare", style: "new" },
  error: { label: "Attenzione", style: "problem" },
};

async function request(path, method = "GET", body = undefined) {
  const options = { method, credentials: "same-origin", headers: {} };
  if (method !== "GET") {
    options.headers["Content-Type"] = "application/json";
    if (model.csrf) options.headers["X-AppHub-CSRF"] = model.csrf;
    options.body = JSON.stringify(body || {});
  }
  const response = await fetch(path, options);
  let data;
  try { data = await response.json(); } catch { data = {}; }
  if (!response.ok) {
    if (response.status === 401 && path !== "/api/login") showLogin();
    throw new Error(data.error || `Richiesta fallita (${response.status})`);
  }
  return data;
}

function showLogin() {
  model.csrf = null;
  byId("dashboard").hidden = true;
  byId("firstRunView").hidden = true;
  byId("loginView").hidden = false;
}

function showFirstRun() {
  model.csrf = null;
  byId("dashboard").hidden = true;
  byId("loginView").hidden = true;
  byId("firstRunView").hidden = false;
}

function showDashboard(csrf) {
  model.csrf = csrf;
  byId("dashboard").hidden = false;
  byId("loginView").hidden = true;
  byId("firstRunView").hidden = true;
}

let toastTimer;
function notify(message) {
  const toast = byId("toast");
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.hidden = true; }, 4500);
}

function el(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function dateLabel(value) {
  if (!value) return "Mai";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return "Mai";
  return new Intl.DateTimeFormat("it-IT", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }).format(date);
}

function statusOf(app) {
  return statuses[app.status] || statuses["not-installed"];
}

function createButton(label, kind, action, app) {
  const button = el("button", `card-button ${kind}`, label);
  button.type = "button";
  button.disabled = model.busy || app.status === "deploying";
  button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      await request(`/api/apps/${app.id}/${action}`, "POST");
      notify(`${app.title}: operazione avviata. Lo stato si aggiornerà a breve.`);
      setTimeout(refresh, 1700);
    } catch (error) { notify(error.message); button.disabled = false; }
  });
  return button;
}

function appCard(app, index) {
  const card = el("article", "app-card");
  const top = el("div", "card-top");
  const icon = el("div", `app-icon tone-${index % 5}`, app.title.trim().charAt(0).toUpperCase() || "A");
  const status = statusOf(app);
  const slot = el("span", "slot-chip", `#${String(app.slot).padStart(2, "0")}`);
  const chip = el("span", `status-badge ${status.style}`);
  chip.append(el("span", "status-dot"), document.createTextNode(status.label));
  top.append(icon, slot, chip);
  const category = el("div", "card-category", app.category);
  const title = el("h3", "card-title", app.title);
  const repo = el("p", "card-repo", app.repository.replace("https://github.com/", ""));
  const meta = el("div", "card-meta");
  meta.append(el("span", "meta-key", "Ultimo deploy"), el("span", "meta-value", dateLabel(app.lastDeployedAt)));
  const footer = el("div", "card-footer");

  if (app.status === "running") {
    if (app.url) {
      const launch = el("a", "card-button card-primary", "Apri app ↗");
      launch.href = app.url;
      launch.target = "_blank";
      launch.rel = "noopener noreferrer";
      footer.append(launch);
    }
    footer.append(createButton("Pausa", "card-quiet", "stop", app));
    if (app.availableSha && app.availableSha !== app.deployedSha)
      footer.append(createButton("Aggiorna", "card-quiet", "deploy", app));
  } else if (app.status === "stopped") {
    footer.append(createButton("Riavvia", "card-primary", "start", app));
    footer.append(createButton("Aggiorna", "card-quiet", "deploy", app));
  } else {
    footer.append(createButton(app.status === "deploying" ? "In corso..." : "Installa / aggiorna", "card-primary", "deploy", app));
  }
  card.append(top, category, title, repo, meta, footer);
  if (app.error) {
    const warning = el("p", "card-warning", app.error);
    card.append(warning);
  }
  const manage = el("div", "card-manage");
  const edit = el("button", "manage-link", "✎ Modifica configurazione");
  edit.type = "button";
  edit.addEventListener("click", () => openAppDialog(app));
  manage.append(edit);
  card.append(manage);
  return card;
}

function renderFilters() {
  const filters = byId("categoryFilters");
  const categories = ["Tutte", ...new Set(model.apps.map((app) => app.category))];
  if (!categories.includes(model.category)) model.category = "Tutte";
  filters.replaceChildren();
  for (const category of categories) {
    const button = el("button", `filter-chip${category === model.category ? " active" : ""}`, category);
    button.type = "button";
    button.setAttribute("aria-pressed", String(category === model.category));
    button.addEventListener("click", () => { model.category = category; renderFilters(); renderApps(); });
    filters.append(button);
  }
}

function renderApps() {
  const target = byId("appGrid");
  target.replaceChildren();
  const apps = model.apps.filter((app) =>
    (model.category === "Tutte" || app.category === model.category) &&
    `${app.title} ${app.category} ${app.id}`.toLocaleLowerCase("it").includes(model.search));
  apps.forEach((app, index) => target.append(appCard(app, index)));
  byId("emptyState").hidden = model.apps.length !== 0;
  byId("noResults").hidden = model.apps.length === 0 || apps.length !== 0;
  byId("collectionCount").textContent = String(model.apps.length);
}

async function refresh() {
  if (!model.csrf) return;
  try {
    const data = await request("/api/status");
    model.apps = data.apps || [];
    byId("totalApps").textContent = String(model.apps.length);
    byId("runningApps").textContent = String(model.apps.filter((app) => app.status === "running").length);
    byId("pendingApps").textContent = String(model.apps.filter((app) => app.status === "not-installed").length);
    byId("lastSync").textContent = dateLabel(data.lastSyncAt);
    byId("syncFrequency").textContent = `Controllo automatico ogni ${data.syncIntervalSeconds || 60} s`;
    byId("syncInterval").textContent = `Sincronizzazione ogni ${data.syncIntervalSeconds || 60} secondi`;
    byId("configMode").textContent = data.remoteConfig ? "Catalogo GitHub privato" : "Configurazione locale";
    byId("syncButton").disabled = Boolean(data.syncing);
    byId("syncButton").classList.toggle("is-spinning", Boolean(data.syncing));
    const banner = byId("syncError");
    banner.hidden = !data.lastSyncError;
    banner.textContent = data.lastSyncError || "";
    renderFilters();
    renderApps();
  } catch (error) {
    if (model.csrf) notify(`Impossibile aggiornare la dashboard: ${error.message}`);
  }
}

function openAppDialog(app = null) {
  model.editingSlug = app?.id || null;
  byId("appForm").reset();
  byId("appDialogTitle").textContent = app ? `Modifica ${app.title}` : "Collega una repository";
  byId("appId").value = app?.id || "";
  byId("appId").readOnly = Boolean(app);
  byId("appTitle").value = app?.title || "";
  byId("appRepo").value = app?.repository || "";
  byId("appBranch").value = app?.branch || "main";
  byId("appCompose").value = app?.composeFile || "compose.yaml";
  byId("appCategory").value = app?.category || "Altro";
  byId("appUrl").value = app?.url || "";
  byId("appSlot").value = app ? app.slot : "";
  byId("appAutoDeploy").checked = Boolean(app?.autoDeploy);
  byId("removeAppButton").hidden = !app;
  byId("appDialog").showModal();
}

async function loadConfig() {
  if (!model.csrf) return;
  try {
    const data = await request("/api/config");
    const settings = data.settings;
    byId("configSource").value = settings.configRepository ? "remote" : "local";
    byId("settingsRepo").value = settings.configRepository || "";
    byId("settingsBranch").value = settings.configBranch || "main";
    byId("settingsFile").value = settings.configFile || "apps.json";
    byId("settingsInterval").value = settings.syncIntervalSeconds || 60;
    byId("remoteHostname").value = settings.remoteHostname || "";
    updateConfigMode();
  } catch (error) { notify(error.message); }
  checkRequirements();
}

function updateConfigMode() {
  const remote = byId("configSource").value === "remote";
  byId("remoteSettings").hidden = !remote;
  byId("settingsRepo").required = remote;
}

async function checkRequirements() {
  if (!model.csrf) return;
  try {
    const values = await request("/api/diagnostics");
    for (const [key, id] of [["gitAvailable", "healthGit"], ["composeAvailable", "healthCompose"], ["containerEngineRunning", "healthEngine"]]) {
      byId(id).textContent = values[key] ? "Disponibile ✓" : "Da configurare";
      byId(id).classList.toggle("healthy", Boolean(values[key]));
    }
  } catch (error) { notify(`Impossibile verificare i requisiti: ${error.message}`); }
}

byId("firstRunForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const warning = byId("firstRunError");
  warning.hidden = true;
  try {
    const session = await request("/api/setup", "POST", {
      password: byId("firstPassword").value,
      confirm: byId("confirmPassword").value,
    });
    byId("firstPassword").value = "";
    byId("confirmPassword").value = "";
    showDashboard(session.csrf);
    await refresh();
    await loadConfig();
    byId("setup").scrollIntoView({ behavior: "smooth" });
    notify("Password creata. Ora scegli dove salvare le app e aggiungi la prima repository.");
  } catch (error) { warning.textContent = error.message; warning.hidden = false; }
});

byId("loginForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const errorNode = byId("loginError");
  errorNode.hidden = true;
  try {
    const password = byId("passwordInput").value;
    const session = await request("/api/login", "POST", { password });
    byId("passwordInput").value = "";
    showDashboard(session.csrf);
    await refresh();
    await loadConfig();
  } catch (error) { errorNode.textContent = error.message; errorNode.hidden = false; }
});

byId("addAppButton").addEventListener("click", () => openAppDialog());
byId("emptyAddButton").addEventListener("click", () => openAppDialog());
byId("closeAppDialog").addEventListener("click", () => byId("appDialog").close());
byId("cancelAppButton").addEventListener("click", () => byId("appDialog").close());

byId("appForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = byId("saveAppButton");
  button.disabled = true;
  const item = {
    id: byId("appId").value.trim(),
    title: byId("appTitle").value.trim(),
    repository: byId("appRepo").value.trim(),
    branch: byId("appBranch").value.trim(),
    composeFile: byId("appCompose").value.trim(),
    category: byId("appCategory").value.trim(),
    url: byId("appUrl").value.trim(),
    autoDeploy: byId("appAutoDeploy").checked,
  };
  if (byId("appSlot").value.trim() !== "") item.slot = Number(byId("appSlot").value);
  try {
    const path = model.editingSlug ? `/api/catalog/apps/${model.editingSlug}/update` : "/api/catalog/apps";
    await request(path, "POST", item);
    byId("appDialog").close();
    notify(model.editingSlug ? "Modifiche salvate nel catalogo." : "Repository aggiunta. Controllo Git avviato.");
    await refresh();
  } catch (error) { notify(error.message); }
  finally { button.disabled = false; }
});

byId("removeAppButton").addEventListener("click", async () => {
  if (!model.editingSlug) return;
  if (!window.confirm("Rimuovere questa app dal catalogo? I suoi container e dati NON verranno cancellati dal PC.")) return;
  try {
    await request(`/api/catalog/apps/${model.editingSlug}/remove`, "POST");
    byId("appDialog").close();
    notify("App rimossa dal catalogo. Container e dati restano sul PC.");
    await refresh();
  } catch (error) { notify(error.message); }
});

byId("configSource").addEventListener("change", updateConfigMode);
byId("settingsForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = byId("settingsForm").querySelector("button[type=submit]");
  button.disabled = true;
  try {
    const remote = byId("configSource").value === "remote";
    await request("/api/settings", "POST", {
      configRepository: remote ? byId("settingsRepo").value.trim() : null,
      configBranch: byId("settingsBranch").value.trim(),
      configFile: byId("settingsFile").value.trim(),
      syncIntervalSeconds: Number(byId("settingsInterval").value),
    });
    notify(remote ? "Catalogo privato collegato. Sto verificando l'accesso a GitHub." : "Catalogo locale attivato.");
    setTimeout(refresh, 1200);
  } catch (error) { notify(error.message); }
  finally { button.disabled = false; }
});

byId("checkRequirements").addEventListener("click", checkRequirements);

byId("remoteAccessForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = byId("remoteAccessForm").querySelector("button[type=submit]");
  button.disabled = true;
  try {
    await request("/api/settings", "POST", { remoteHostname: byId("remoteHostname").value.trim() });
    notify("Hostname salvato. L'accesso esterno richiede ancora Tailscale Serve e un dispositivo autorizzato.");
  } catch (error) { notify(error.message); }
  finally { button.disabled = false; }
});

byId("copyServeCommand").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText("tailscale serve --bg 8766");
    notify("Comando copiato. Eseguilo sul PC dove gira Local AppHub.");
  } catch { notify("Copia manualmente: tailscale serve --bg 8766"); }
});

let deferredInstallPrompt = null;
const installButton = byId("installAppButton");
const installHelp = byId("installHelp");

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  deferredInstallPrompt = event;
  installHelp.textContent = "Questo browser supporta l'installazione diretta. Tocca il pulsante per continuare.";
});

window.addEventListener("appinstalled", () => {
  deferredInstallPrompt = null;
  installHelp.textContent = "Local AppHub è stato aggiunto al tuo dispositivo.";
});

installButton.addEventListener("click", async () => {
  if (window.matchMedia("(display-mode: standalone)").matches || navigator.standalone) {
    installHelp.textContent = "Stai già utilizzando Local AppHub dalla schermata Home.";
    return;
  }
  if (deferredInstallPrompt) {
    const prompt = deferredInstallPrompt;
    deferredInstallPrompt = null;
    await prompt.prompt();
    return;
  }
  if (location.protocol !== "https:" && !["127.0.0.1", "localhost", "::1"].includes(location.hostname)) {
    installHelp.textContent = "Per installare l'app dal telefono apri l'indirizzo HTTPS privato configurato con Tailscale Serve.";
  } else if (/iphone|ipad|ipod/i.test(navigator.userAgent)) {
    installHelp.textContent = "Su iPhone: apri questa pagina in Safari, tocca Condividi e poi Aggiungi alla schermata Home.";
  } else {
    installHelp.textContent = "Nel browser apri il menu e scegli Installa app oppure Aggiungi alla schermata Home.";
  }
});

// Offline fallback contains no private information. API requests always go directly to the PC.
if ("serviceWorker" in navigator && window.isSecureContext) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {
      installHelp.textContent = "Il browser non ha potuto attivare la modalità app. La dashboard web resta disponibile.";
    });
  });
}

byId("syncButton").addEventListener("click", async () => {
  try {
    await request("/api/sync", "POST");
    notify("Sincronizzazione avviata: sto controllando i repository GitHub.");
    setTimeout(refresh, 1200);
  } catch (error) { notify(error.message); }
});

byId("logoutButton").addEventListener("click", async () => {
  try { await request("/api/logout", "POST"); }
  catch { /* The UI still logs out locally if the server is unreachable. */ }
  showLogin();
});

byId("searchInput").addEventListener("input", (event) => {
  model.search = event.target.value.toLocaleLowerCase("it").trim();
  renderApps();
});

(async function bootstrap() {
  try {
    const session = await request("/api/session");
    if (session.setupRequired) showFirstRun();
    else if (session.authenticated) { showDashboard(session.csrf); await refresh(); await loadConfig(); }
    else showLogin();
  } catch { showLogin(); }
  setInterval(refresh, 15000);
})();
