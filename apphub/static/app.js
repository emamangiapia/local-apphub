/* Local AppHub by iPhone Facile - no external dependencies. */
"use strict";

const byId = (id) => document.getElementById(id);
const model = { csrf: null, apps: [], category: "Tutte", search: "", busy: false };
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
  byId("loginView").hidden = false;
}

function showDashboard(csrf) {
  model.csrf = csrf;
  byId("dashboard").hidden = false;
  byId("loginView").hidden = true;
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
  const chip = el("span", `status-badge ${status.style}`);
  chip.append(el("span", "status-dot"), document.createTextNode(status.label));
  top.append(icon, chip);
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
  } catch (error) { errorNode.textContent = error.message; errorNode.hidden = false; }
});

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
    if (session.authenticated) { showDashboard(session.csrf); await refresh(); }
    else showLogin();
  } catch { showLogin(); }
  setInterval(refresh, 15000);
})();
