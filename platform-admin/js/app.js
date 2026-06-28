const API = "/api";
let token = localStorage.getItem("platform_token");
let selectedStoreId = null;

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${API}${path}`, { ...options, headers });
  if (res.status === 401) {
    if (path.includes("/auth/")) throw new Error("Невірний email або пароль");
    logout();
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    let msg = await res.text();
    try {
      const j = JSON.parse(msg);
      msg = j.detail || msg;
    } catch (_) {}
    throw new Error(typeof msg === "string" ? msg : "Помилка сервера");
  }
  const ct = res.headers.get("content-type");
  if (ct && ct.includes("application/json")) return res.json();
  return res.text();
}

function logout() {
  token = null;
  selectedStoreId = null;
  localStorage.removeItem("platform_token");
  document.getElementById("login-screen").classList.remove("hidden");
  document.getElementById("app").classList.add("hidden");
}

async function login(e) {
  e.preventDefault();
  const errEl = document.getElementById("login-error");
  errEl.classList.add("hidden");
  try {
    const data = await api("/auth/platform/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: document.getElementById("login-email").value,
        password: document.getElementById("login-password").value,
      }),
    });
    token = data.access_token;
    localStorage.setItem("platform_token", token);
    await showApp();
  } catch (err) {
    errEl.textContent = err.message;
    errEl.classList.remove("hidden");
  }
}

async function showApp() {
  document.getElementById("login-screen").classList.add("hidden");
  document.getElementById("app").classList.remove("hidden");
  const me = await api("/auth/platform/me");
  document.getElementById("user-label").textContent = me.email;
  await loadStats();
  await loadStores();
}

function switchTab(name, { reloadStores = false } = {}) {
  document.querySelectorAll(".tabs button").forEach((b) => {
    b.classList.toggle("active", b.dataset.tab === name);
  });
  document.querySelectorAll(".panel").forEach((p) => {
    p.classList.toggle("active", p.id === `panel-${name}`);
  });
  if (name === "stats") loadStats();
  if (name === "stores" && reloadStores) loadStores();
}

async function loadStats() {
  const s = await api("/platform/stats");
  document.getElementById("stats-grid").innerHTML = `
    <div class="stat-card"><span>Магазинів</span><strong>${s.stores_total}</strong></div>
    <div class="stat-card"><span>Активних</span><strong>${s.stores_active}</strong></div>
    <div class="stat-card"><span>Проєктів</span><strong>${s.projects_total}</strong></div>
    <div class="stat-card"><span>Заявок</span><strong>${s.leads_total}</strong></div>
    <div class="stat-card"><span>Нових заявок</span><strong>${s.leads_new}</strong></div>
  `;
}

function botBadge(store) {
  if (store.has_bot_token) return `<span class="badge badge-ok">є ${store.bot_token_hint || ""}</span>`;
  return '<span class="badge badge-muted">немає</span>';
}

function statusBadge(active) {
  return active
    ? '<span class="badge badge-ok">активний</span>'
    : '<span class="badge badge-off">вимкнений</span>';
}

function renderStoresTable(stores) {
  const tbody = document.querySelector("#stores-table tbody");
  tbody.innerHTML = stores.map((s) => `
    <tr class="${selectedStoreId === s.id ? "row-selected" : ""}" data-store-id="${s.id}">
      <td><strong>${s.name}</strong></td>
      <td><code>${s.slug}</code></td>
      <td>${botBadge(s)}</td>
      <td>${s.admins_count}</td>
      <td>${s.projects_count}</td>
      <td>${s.leads_count}</td>
      <td>${statusBadge(s.active)}</td>
      <td><button class="btn btn-primary" onclick="openStore(${s.id})">Керувати</button></td>
    </tr>
  `).join("") || "<tr><td colspan='8'>Ще немає магазинів</td></tr>";
}

function closeStoreDetail() {
  selectedStoreId = null;
  document.getElementById("store-detail").classList.add("hidden");
  document.querySelectorAll("#stores-table tr.row-selected").forEach((row) => {
    row.classList.remove("row-selected");
  });
}

async function loadStores() {
  const stores = await api("/platform/stores");
  renderStoresTable(stores);

  if (selectedStoreId) {
    const still = stores.find((s) => s.id === selectedStoreId);
    if (still) await refreshStoreDetail(selectedStoreId);
    else closeStoreDetail();
  }
}

async function refreshStoreDetail(id) {
  const store = await api(`/platform/stores/${id}`);
  const panel = document.getElementById("store-detail");
  panel.classList.remove("hidden");
  document.getElementById("detail-title").textContent = store.name;
  document.getElementById("edit-store-id").value = store.id;
  document.getElementById("edit-name").value = store.name;
  document.getElementById("edit-slug").value = store.slug;
  document.getElementById("edit-phone").value = store.phone || "";
  document.getElementById("edit-address").value = store.address || "";
  document.getElementById("edit-telegram").value = store.telegram_username || "";
  document.getElementById("edit-bot-token").value = "";
  document.getElementById("edit-leads-group").value = store.leads_group_chat_id || "";
  document.getElementById("edit-manager-chat").value = store.manager_telegram_chat_id || "";
  document.getElementById("edit-active").checked = store.active;
  document.getElementById("edit-bot-hint").textContent = store.has_bot_token
    ? `Бот підключено${store.bot_token_hint ? ` (${store.bot_token_hint})` : ""}. Введіть новий токен лише для заміни.`
    : "Токен бота не вказано — після збереження перезапустіть bot: docker compose up -d bot";
  await loadStoreAdmins(id);
  await loadCatalogBrands();
  await loadCatalogColors();
}

let catalogBrands = [];

async function loadCatalogBrands() {
  catalogBrands = await api("/platform/brands");
  const opts = catalogBrands.map((b) => `<option value="${b.id}">${b.name}</option>`).join("");
  const filter = document.getElementById("catalog-brand-filter");
  const addSel = document.getElementById("catalog-color-brand");
  if (filter) {
    const prev = filter.value;
    filter.innerHTML = `<option value="">Усі лінійки</option>${opts}`;
    if (prev) filter.value = prev;
  }
  if (addSel) addSel.innerHTML = opts;
}

async function loadCatalogColors() {
  if (!selectedStoreId) return;
  const brandId = document.getElementById("catalog-brand-filter")?.value;
  const q = brandId ? `?brand_id=${brandId}` : "";
  const colors = await api(`/platform/stores/${selectedStoreId}/colors${q}`);
  const tbody = document.querySelector("#catalog-colors-table tbody");
  tbody.innerHTML = colors.map((c) => `
    <tr>
      <td><span class="swatch" style="background:${c.hex}"></span>${c.name}</td>
      <td><code>${c.manufacturer_code || "—"}</code></td>
      <td>
        <input class="price-input" type="number" step="0.01" min="0" value="${c.price_per_sqm ?? ""}"
          onchange="saveCatalogPrice(${c.id}, this.value)">
      </td>
      <td>
        <button class="btn ${c.in_stock ? "btn-success" : "btn-danger"}"
          onclick="toggleCatalogStock(${c.id}, ${c.in_stock ? "false" : "true"})">
          ${c.in_stock ? "В наявності" : "Немає"}
        </button>
      </td>
      <td><button class="btn btn-danger" onclick="removeCatalogColor(${c.id})">Прибрати</button></td>
    </tr>
  `).join("") || "<tr><td colspan='5'>Немає кольорів — додайте нижче або запустіть seed</td></tr>";
}

async function saveCatalogPrice(colorId, value) {
  const price = value === "" ? null : parseFloat(value);
  await api(`/platform/stores/${selectedStoreId}/colors/${colorId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ price_per_sqm: price }),
  });
}

async function toggleCatalogStock(colorId, inStock) {
  await api(`/platform/stores/${selectedStoreId}/colors/${colorId}/stock`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ in_stock: inStock }),
  });
  await loadCatalogColors();
}

async function removeCatalogColor(colorId) {
  if (!confirm("Прибрати колір з каталогу цього магазину?")) return;
  await api(`/platform/stores/${selectedStoreId}/colors/${colorId}`, { method: "DELETE" });
  await loadCatalogColors();
}

async function addCatalogColor(e) {
  e.preventDefault();
  if (!selectedStoreId) return;
  await api(`/platform/stores/${selectedStoreId}/colors`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      brand_id: parseInt(document.getElementById("catalog-color-brand").value, 10),
      name: document.getElementById("catalog-color-name").value,
      hex: document.getElementById("catalog-color-hex").value,
      manufacturer_code: document.getElementById("catalog-color-code").value || null,
      price_per_sqm: parseFloat(document.getElementById("catalog-color-price").value) || null,
      category: document.getElementById("catalog-color-category").value,
    }),
  });
  e.target.reset();
  await loadCatalogColors();
}

function toggleCatalogPanel() {
  const body = document.getElementById("catalog-body");
  const btn = document.getElementById("toggle-catalog");
  const hidden = body.classList.toggle("hidden");
  btn.textContent = hidden ? "Розгорнути каталог" : "Згорнути каталог";
}

async function openStore(id) {
  if (selectedStoreId === id && !document.getElementById("store-detail").classList.contains("hidden")) {
    closeStoreDetail();
    return;
  }
  selectedStoreId = id;
  switchTab("stores");
  await refreshStoreDetail(id);
  document.querySelectorAll("#stores-table tr").forEach((row) => {
    row.classList.toggle("row-selected", parseInt(row.dataset.storeId, 10) === id);
  });
}

async function loadStoreAdmins(storeId) {
  const admins = await api(`/platform/stores/${storeId}/admins`);
  const tbody = document.querySelector("#admins-table tbody");
  tbody.innerHTML = admins.map((a) => `
    <tr>
      <td>${a.email}</td>
      <td>${a.role}</td>
      <td>${a.active ? '<span class="badge badge-ok">активний</span>' : '<span class="badge badge-off">вимкнений</span>'}</td>
      <td>
        ${a.active ? `<button class="btn btn-danger" onclick="deactivateAdmin(${a.id})">Вимкнути</button>` : ""}
      </td>
    </tr>
  `).join("") || "<tr><td colspan='4'>Немає адмінів — створіть нижче</td></tr>";
}

async function saveStore(e) {
  e.preventDefault();
  const id = document.getElementById("edit-store-id").value;
  const groupRaw = document.getElementById("edit-leads-group").value.trim();
  const chatRaw = document.getElementById("edit-manager-chat").value.trim();
  const botToken = document.getElementById("edit-bot-token").value.trim();
  const payload = {
    name: document.getElementById("edit-name").value,
    slug: document.getElementById("edit-slug").value.trim().toLowerCase(),
    phone: document.getElementById("edit-phone").value || null,
    address: document.getElementById("edit-address").value || null,
    telegram_username: document.getElementById("edit-telegram").value || null,
    leads_group_chat_id: groupRaw ? parseInt(groupRaw, 10) : null,
    manager_telegram_chat_id: chatRaw ? parseInt(chatRaw, 10) : null,
    active: document.getElementById("edit-active").checked,
  };
  if (botToken) payload.telegram_bot_token = botToken;

  await api(`/platform/stores/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  alert("Збережено. Якщо змінили токен бота — перезапустіть: docker compose up -d bot");
  const stores = await api("/platform/stores");
  renderStoresTable(stores);
  if (selectedStoreId) await refreshStoreDetail(parseInt(id, 10));
}

async function createStore(e) {
  e.preventDefault();
  const adminEmail = document.getElementById("create-admin-email").value.trim();
  const adminPassword = document.getElementById("create-admin-password").value;
  const payload = {
    name: document.getElementById("create-name").value,
    slug: document.getElementById("create-slug").value.trim().toLowerCase(),
    telegram_bot_token: document.getElementById("create-bot-token").value.trim() || null,
    phone: document.getElementById("create-phone").value || null,
    address: document.getElementById("create-address").value || null,
    telegram_username: document.getElementById("create-telegram").value || null,
  };
  if (adminEmail) {
    payload.admin_email = adminEmail;
    payload.admin_password = adminPassword;
  }

  const store = await api("/platform/stores", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  alert(`Магазин «${store.name}» створено.\nАдмінка магазину: /admin/\nЛогін — email адміна, який ви вказали.`);
  e.target.reset();
  selectedStoreId = store.id;
  switchTab("stores");
  await loadStores();
}

async function createAdmin(e) {
  e.preventDefault();
  if (!selectedStoreId) return;
  await api(`/platform/stores/${selectedStoreId}/admins`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: document.getElementById("new-admin-email").value,
      password: document.getElementById("new-admin-password").value,
      role: document.getElementById("new-admin-role").value,
    }),
  });
  e.target.reset();
  alert("Адміна створено");
  await loadStoreAdmins(selectedStoreId);
  await loadStores();
}

async function deactivateAdmin(adminId) {
  if (!confirm("Вимкнути цього адміна?")) return;
  await api(`/platform/admins/${adminId}`, { method: "DELETE" });
  await loadStoreAdmins(selectedStoreId);
  await loadStores();
}

document.getElementById("create-name").addEventListener("input", (e) => {
  const slugEl = document.getElementById("create-slug");
  if (slugEl.dataset.touched) return;
  slugEl.value = e.target.value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40);
});
document.getElementById("create-slug").addEventListener("input", () => {
  document.getElementById("create-slug").dataset.touched = "1";
});

window.openStore = openStore;
window.deactivateAdmin = deactivateAdmin;
window.closeStoreDetail = closeStoreDetail;
window.saveCatalogPrice = saveCatalogPrice;
window.toggleCatalogStock = toggleCatalogStock;
window.removeCatalogColor = removeCatalogColor;

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("login-form").onsubmit = login;
  document.getElementById("logout-btn").onclick = logout;
  document.getElementById("close-store-detail").onclick = closeStoreDetail;
  document.getElementById("toggle-catalog").onclick = toggleCatalogPanel;
  document.getElementById("catalog-brand-filter").onchange = loadCatalogColors;
  document.getElementById("store-edit-form").onsubmit = saveStore;
  document.getElementById("create-store-form").onsubmit = createStore;
  document.getElementById("admin-create-form").onsubmit = createAdmin;
  document.getElementById("catalog-color-form").onsubmit = addCatalogColor;
  document.querySelectorAll(".tabs button").forEach((b) => {
    b.onclick = () => switchTab(b.dataset.tab, { reloadStores: b.dataset.tab === "stores" });
  });
  if (token) showApp().catch(() => logout());
});
