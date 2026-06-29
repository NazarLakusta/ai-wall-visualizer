const API = "/api";
let token = localStorage.getItem("admin_token");
let adminRole = "owner";
let importPreview = null;

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${API}${path}`, { ...options, headers });
  if (res.status === 401) {
    if (path.includes("/auth/")) throw new Error("Невірний email або пароль");
    logout();
    throw new Error("Unauthorized");
  }
  if (!res.ok) throw new Error(await res.text());
  const ct = res.headers.get("content-type");
  if (ct && ct.includes("application/json")) return res.json();
  return res.text();
}

function logout() {
  token = null;
  localStorage.removeItem("admin_token");
  document.getElementById("login-screen").classList.remove("hidden");
  document.getElementById("admin-app").classList.add("hidden");
}

async function login(e) {
  e.preventDefault();
  const errEl = document.getElementById("login-error");
  errEl.style.display = "none";
  try {
    const email = document.getElementById("login-email").value;
    const password = document.getElementById("login-password").value;
    const data = await api("/auth/admin/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    token = data.access_token;
    localStorage.setItem("admin_token", token);
    showApp();
  } catch (err) {
    errEl.textContent = "Помилка входу: " + err.message;
    errEl.style.display = "block";
  }
}

function showApp() {
  document.getElementById("login-screen").classList.add("hidden");
  document.getElementById("admin-app").classList.remove("hidden");
  loadAdminProfile()
    .then(() => {
      applyRoleUi();
      loadStats().catch(console.error);
      return loadBrands();
    })
    .catch((err) => {
      console.error(err);
      document.getElementById("login-error").textContent = "Помилка: " + err.message;
      document.getElementById("login-error").style.display = "block";
    });
}

async function loadAdminProfile() {
  const me = await api("/auth/admin/me");
  adminRole = me.role || "owner";
  const badge = document.getElementById("admin-role-badge");
  if (badge) {
    badge.textContent = adminRole === "owner" ? "Власник" : "Редактор";
    badge.className = `role-badge role-${adminRole}`;
  }
}

function isOwner() {
  return adminRole === "owner";
}

function applyRoleUi() {
  const ownerOnly = document.querySelectorAll(".owner-only");
  ownerOnly.forEach((el) => {
    if (el.tagName === "FIELDSET") {
      el.disabled = !isOwner();
    } else {
      el.classList.toggle("hidden", !isOwner());
    }
  });
  const editorHint = document.getElementById("brands-editor-hint");
  if (editorHint) editorHint.classList.toggle("hidden", isOwner());
  const tokenInput = document.getElementById("store-bot-token");
  if (tokenInput) {
    tokenInput.disabled = !isOwner();
    tokenInput.placeholder = isOwner()
      ? "Токен від @BotFather"
      : "Лише власник може змінити токен";
  }
}

async function loadStats() {
  const days = document.getElementById("stats-period")?.value ?? "30";
  const s = await api(`/admin/stats?days=${days}`);
  const periodLabel = s.period_days ? `${s.period_days} дн.` : "весь час";
  document.getElementById("stats-grid").innerHTML = `
    <div class="stat-card"><span>Проєктів (${periodLabel})</span><strong>${s.projects_total}</strong></div>
    <div class="stat-card"><span>Реальних фото</span><strong>${s.projects_real}</strong></div>
    <div class="stat-card"><span>Відкриттів редактора</span><strong>${s.editor_opens}</strong></div>
    <div class="stat-card"><span>Заявок</span><strong>${s.leads_total}</strong></div>
    <div class="stat-card"><span>Нових заявок</span><strong>${s.leads_new}</strong></div>
    <div class="stat-card"><span>Збережень фото</span><strong>${s.downloads_estimate}</strong></div>
  `;

  const fmtRate = (v) => (v == null ? "—" : `${v}%`);
  document.getElementById("funnel-panel").innerHTML = `
    <h4>Воронка продажів (${periodLabel})</h4>
    <div class="funnel-steps">
      <div class="funnel-step">
        <span class="funnel-num">${s.funnel_uploads}</span>
        <span class="funnel-label">Завантаження фото</span>
      </div>
      <div class="funnel-arrow">→ ${fmtRate(s.funnel_rate_upload_to_editor)}</div>
      <div class="funnel-step">
        <span class="funnel-num">${s.funnel_editor}</span>
        <span class="funnel-label">Відкрили редактор</span>
      </div>
      <div class="funnel-arrow">→ ${fmtRate(s.funnel_rate_editor_to_lead)}</div>
      <div class="funnel-step">
        <span class="funnel-num">${s.funnel_leads}</span>
        <span class="funnel-label">Заявки</span>
      </div>
      <div class="funnel-arrow">→ ${fmtRate(s.funnel_rate_lead_to_contacted)}</div>
      <div class="funnel-step">
        <span class="funnel-num">${s.funnel_contacted}</span>
        <span class="funnel-label">В обробці / contacted</span>
      </div>
      <div class="funnel-arrow">→ ${fmtRate(s.funnel_rate_contacted_to_closed)}</div>
      <div class="funnel-step">
        <span class="funnel-num">${s.funnel_closed}</span>
        <span class="funnel-label">Закриті</span>
      </div>
    </div>
  `;
}

async function downloadBlob(path, filename) {
  const res = await fetch(`${API}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    let msg = `Помилка ${res.status}`;
    try {
      const data = await res.json();
      msg = typeof data.detail === "string" ? data.detail : msg;
    } catch {
      const text = await res.text();
      if (text) msg = text;
    }
    throw new Error(msg);
  }
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    throw new Error("Сервер повернув JSON замість файлу");
  }
  const blob = await res.blob();
  if (!blob.size) throw new Error("Порожній файл");
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    a.remove();
    URL.revokeObjectURL(url);
  }, 1000);
}

let _leadPdfObjectUrl = null;

function resetLeadPdfPanel() {
  if (_leadPdfObjectUrl) {
    URL.revokeObjectURL(_leadPdfObjectUrl);
    _leadPdfObjectUrl = null;
  }
  const panel = document.getElementById("lead-pdf-panel");
  const frame = document.getElementById("lead-pdf-frame");
  const status = document.getElementById("lead-pdf-status");
  const download = document.getElementById("lead-pdf-download");
  if (panel) panel.classList.add("hidden");
  if (frame) {
    frame.classList.add("hidden");
    frame.removeAttribute("src");
  }
  if (status) {
    status.classList.add("hidden");
    status.textContent = "";
  }
  if (download) {
    download.classList.add("hidden");
    download.removeAttribute("href");
  }
}

async function fetchLeadQuotePdf(leadId, triggerBtn) {
  if (!token) {
    alert("Увійдіть в адмінку знову");
    logout();
    return;
  }

  const btn = triggerBtn || document.getElementById("lead-quote-btn");
  const panel = document.getElementById("lead-pdf-panel");
  const frame = document.getElementById("lead-pdf-frame");
  const status = document.getElementById("lead-pdf-status");
  const download = document.getElementById("lead-pdf-download");
  const filename = `koshtorys-lead-${leadId}.pdf`;

  if (!panel || !status) {
    alert("PDF-панель не знайдена. Оновіть сторінку (Ctrl+F5).");
    return;
  }

  resetLeadPdfPanel();
  panel.classList.remove("hidden");
  status.classList.remove("hidden");
  status.textContent = "⏳ Генеруємо PDF-кошторис...";

  const prevLabel = btn ? btn.textContent : "";
  if (btn) {
    btn.disabled = true;
    btn.classList.add("is-loading");
    btn.textContent = "Генеруємо PDF...";
  }

  try {
    const res = await fetch(`${API}/admin/leads/${leadId}/quote`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.status === 401) {
      logout();
      throw new Error("Сесія закінчилась. Увійдіть знову.");
    }
    if (!res.ok) {
      let msg = `Помилка ${res.status}`;
      try {
        const data = await res.json();
        msg = typeof data.detail === "string" ? data.detail : msg;
      } catch {
        const text = await res.text();
        if (text) msg = text;
      }
      throw new Error(msg);
    }

    const blob = await res.blob();
    if (!blob.size) throw new Error("Порожній PDF");

    const pdfBlob = blob.type.includes("pdf") ? blob : new Blob([blob], { type: "application/pdf" });
    _leadPdfObjectUrl = URL.createObjectURL(pdfBlob);

    if (frame) {
      frame.src = _leadPdfObjectUrl;
      frame.classList.remove("hidden");
    }
    if (download) {
      download.href = _leadPdfObjectUrl;
      download.download = filename;
      download.classList.remove("hidden");
    }

    status.textContent = "✅ PDF готовий. Перегляньте нижче або натисніть «Завантажити PDF».";
  } catch (err) {
    status.textContent = `❌ ${err.message || "Не вдалося отримати PDF"}`;
    if (frame) frame.classList.add("hidden");
    if (download) download.classList.add("hidden");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.classList.remove("is-loading");
      btn.textContent = prevLabel || "PDF-кошторис";
    }
  }
}

async function loadStoreSettings() {
  const store = await api("/admin/store");
  document.getElementById("store-name").value = store.name || "";
  document.getElementById("store-phone").value = store.phone || "";
  document.getElementById("store-address").value = store.address || "";
  document.getElementById("store-open-time").value = store.business_open_time || "09:00";
  document.getElementById("store-close-time").value = store.business_close_time || "19:00";
  document.getElementById("store-timezone").value = store.business_timezone || "Europe/Kyiv";
  document.getElementById("store-telegram").value = store.telegram_username || "";
  document.getElementById("store-leads-group").value = store.leads_group_chat_id || "";
  document.getElementById("store-manager-chat").value = store.manager_telegram_chat_id || "";
  document.getElementById("store-bot-token").value = "";
  const hint = document.getElementById("store-bot-hint");
  if (store.has_bot_token) {
    hint.textContent = `Бот підключено${store.bot_token_hint ? ` (токен ${store.bot_token_hint})` : ""}`;
  } else {
    hint.textContent = "Токен бота не вказано — клієнти не зможуть користуватись ботом магазину.";
  }
}

async function testStoreNotification() {
  try {
    await api("/admin/store/test-notification", { method: "POST" });
    alert("Тестове сповіщення надіслано в Telegram");
  } catch (err) {
    alert(err.message);
  }
}

async function saveStoreSettings(e) {
  e.preventDefault();
  const groupRaw = document.getElementById("store-leads-group").value.trim();
  const chatRaw = document.getElementById("store-manager-chat").value.trim();
  const botToken = document.getElementById("store-bot-token").value.trim();
  const payload = {
    name: document.getElementById("store-name").value,
    phone: document.getElementById("store-phone").value,
    address: document.getElementById("store-address").value,
    business_open_time: document.getElementById("store-open-time").value || "09:00",
    business_close_time: document.getElementById("store-close-time").value || "19:00",
    business_timezone: document.getElementById("store-timezone").value || "Europe/Kyiv",
    telegram_username: document.getElementById("store-telegram").value,
    leads_group_chat_id: groupRaw ? parseInt(groupRaw, 10) : null,
    manager_telegram_chat_id: chatRaw ? parseInt(chatRaw, 10) : null,
  };
  if (botToken) payload.telegram_bot_token = botToken;
  await api("/admin/store", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  alert("Збережено");
}

const LEAD_STATUS_LABELS = {
  new: "Нова",
  contacted: "В обробці",
  closed: "Закрита",
};

const LEADS_DATE_TZ = "Europe/Kyiv";

function formatLeadDate(iso) {
  return new Date(iso).toLocaleString("uk-UA", { timeZone: LEADS_DATE_TZ });
}

function buildLeadsFilterParams() {
  const params = new URLSearchParams();
  const status = document.getElementById("leads-status-filter")?.value;
  const sort = document.getElementById("leads-sort")?.value || "date_desc";
  const from = document.getElementById("leads-from")?.value;
  const to = document.getElementById("leads-to")?.value;
  if (status) params.set("status", status);
  if (from) params.set("date_from", from);
  if (to) params.set("date_to", to);
  params.set("sort", sort);
  return params;
}

function getLeadsQuery() {
  const q = buildLeadsFilterParams().toString();
  return q ? `?${q}` : "";
}

async function loadLeads() {
  const leads = await api(`/admin/leads${getLeadsQuery()}`);
  const tbody = document.querySelector("#leads-table tbody");
  tbody.innerHTML = leads.map((l) => `
    <tr>
      <td>${formatLeadDate(l.created_at)}</td>
      <td>${escapeHtml(l.customer_name) || "—"}</td>
      <td>${escapeHtml(l.phone)}</td>
      <td>${renderPhotoPair(l.original_url, l.result_url, l.is_test)}</td>
      <td>${l.wall_area_sqm ? l.wall_area_sqm + " м²" : "—"}</td>
      <td>${l.estimated_total_uah ? "₴" + Math.round(l.estimated_total_uah) : "—"}</td>
      <td>
        <select class="lead-status-select" onchange="markLead(${l.id}, this.value)">
          ${Object.entries(LEAD_STATUS_LABELS).map(([val, label]) => `
            <option value="${val}" ${l.status === val ? "selected" : ""}>${label}</option>
          `).join("")}
        </select>
      </td>
      <td><button type="button" class="btn btn-primary" onclick="showLeadDetail(${l.id})">Деталі</button></td>
    </tr>
  `).join("") || "<tr><td colspan='8'>Заявок ще немає</td></tr>";
  window._leadsCache = leads;
}

function escapeHtml(text) {
  if (text == null) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderPhotoPair(originalUrl, resultUrl, isTest, mode = "compact") {
  const items = [];
  if (originalUrl) {
    items.push({
      url: originalUrl,
      label: isTest ? "Тест" : "Кімната",
    });
  }
  if (resultUrl && resultUrl !== originalUrl) {
    items.push({ url: resultUrl, label: "Результат" });
  } else if (resultUrl && !originalUrl) {
    items.push({ url: resultUrl, label: "Результат" });
  }
  if (!items.length) {
    return mode === "compact" ? "—" : '<p class="hint small">Фото ще немає (обробка або клієнт не завантажив)</p>';
  }
  const missingResult = originalUrl && !resultUrl;
  const cls = mode === "detail" ? "photo-pair photo-pair--detail" : "photo-pair photo-pair--compact";
  return `<div class="${cls}">${items.map((item) => `
    <a class="photo-thumb" href="${escapeHtml(item.url)}" target="_blank" rel="noopener" title="${escapeHtml(item.label)}">
      <img src="${escapeHtml(item.url)}" alt="${escapeHtml(item.label)}" loading="lazy">
      <span>${escapeHtml(item.label)}</span>
    </a>
  `).join("")}</div>${missingResult && mode === "detail" ? '<p class="hint small">Результат візуалізації не збережено — лише для старих заявок до оновлення.</p>' : ""}`;
}

function formatTelegramUsername(username) {
  if (!username) return "—";
  const clean = String(username).replace(/^@/, "");
  return `<a href="https://t.me/${escapeHtml(clean)}" target="_blank" rel="noopener">@${escapeHtml(clean)}</a>`;
}

async function sendLeadQuoteToCustomer(leadId, btn) {
  const prev = btn?.textContent;
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Надсилаємо...";
  }
  try {
    await api(`/admin/leads/${leadId}/send-quote-customer`, { method: "POST" });
    alert("PDF надіслано клієнту в Telegram");
  } catch (err) {
    alert(err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = prev;
    }
  }
}

async function notifyLeadContacted(leadId, btn) {
  const prev = btn?.textContent;
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Надсилаємо...";
  }
  try {
    await api(`/admin/leads/${leadId}/notify-contacted`, { method: "POST" });
    alert("Клієнту надіслано: «Ваша заявка в обробці»");
    loadLeads();
  } catch (err) {
    alert(err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = prev;
    }
  }
}

function showLeadDetail(id) {
  const lead = (window._leadsCache || []).find((l) => l.id === id);
  if (!lead) return;

  document.getElementById("lead-detail-id").textContent = `#${lead.id}`;
  const testBadge = lead.is_test ? ' <span class="hint small">(тестове фото)</span>' : "";

  const paintPlan = lead.paint_plan_summary
    ? `<pre class="lead-plan">${escapeHtml(lead.paint_plan_summary)}</pre>`
    : "<p>—</p>";

  document.getElementById("lead-detail-body").innerHTML = `
    <p><strong>Дата:</strong> ${formatLeadDate(lead.created_at)}</p>
    <p><strong>Клієнт:</strong> ${escapeHtml(lead.customer_name) || "—"}</p>
    <p><strong>Телефон:</strong> <a href="tel:${escapeHtml(lead.phone)}">${escapeHtml(lead.phone)}</a></p>
    <p><strong>Telegram:</strong> ${formatTelegramUsername(lead.telegram_username)}</p>
    <p><strong>Проєкт:</strong> #${lead.project_id}${testBadge}</p>
    <p><strong>Площа:</strong> ${lead.wall_area_sqm ? lead.wall_area_sqm + " м²" : "—"}</p>
    <p><strong>Сума:</strong> ${lead.estimated_total_uah ? "₴" + Math.round(lead.estimated_total_uah) : "—"}</p>
    <p><strong>Вибір:</strong> ${escapeHtml(lead.selection_summary) || "—"}</p>
    <p><strong>План банок:</strong></p>
    ${paintPlan}
    <p><strong>Коментар:</strong> ${escapeHtml(lead.comment) || "—"}</p>
    <p><strong>Візуалізація:</strong></p>
    ${renderPhotoPair(lead.original_url, lead.result_url, lead.is_test, "detail")}
    <div class="lead-actions">
      <button type="button" class="btn btn-primary" id="lead-quote-btn">PDF-кошторис</button>
      <button type="button" class="btn btn-success" id="lead-send-pdf-btn">Надіслати PDF клієнту</button>
      <button type="button" class="btn" id="lead-contacted-btn">В обробці → клієнту</button>
    </div>
    <div id="lead-pdf-panel" class="lead-pdf-panel hidden">
      <p id="lead-pdf-status" class="hint hidden"></p>
      <iframe id="lead-pdf-frame" class="pdf-preview-frame hidden" title="PDF-кошторис"></iframe>
      <div class="lead-actions">
        <a id="lead-pdf-download" class="btn btn-primary hidden" download>Завантажити PDF</a>
      </div>
    </div>
  `;

  const quoteBtn = document.getElementById("lead-quote-btn");
  if (quoteBtn) {
    quoteBtn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      fetchLeadQuotePdf(lead.id, quoteBtn);
    });
  }

  const sendPdfBtn = document.getElementById("lead-send-pdf-btn");
  if (sendPdfBtn) {
    sendPdfBtn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      sendLeadQuoteToCustomer(lead.id, sendPdfBtn);
    });
  }

  const contactedBtn = document.getElementById("lead-contacted-btn");
  if (contactedBtn) {
    contactedBtn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      notifyLeadContacted(lead.id, contactedBtn);
    });
  }

  document.getElementById("lead-detail-modal").classList.remove("hidden");
}

function closeLeadDetail() {
  resetLeadPdfPanel();
  document.getElementById("lead-detail-modal").classList.add("hidden");
}

async function exportLeadsCsv() {
  const params = buildLeadsFilterParams();
  params.delete("sort");
  const q = params.toString();
  await downloadBlob(
    `/admin/leads/export${q ? `?${q}` : ""}`,
    `leads-${new Date().toISOString().slice(0, 10)}.csv`,
  );
}

async function markLead(id, status) {
  await api(`/admin/leads/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  loadLeads();
}

async function loadInbox() {
  const projects = await api("/admin/projects");
  const tbody = document.querySelector("#inbox-table tbody");
  tbody.innerHTML = projects.map((p) => `
    <tr>
      <td>#${p.id}${p.is_test ? " (тест)" : ""}</td>
      <td>${escapeHtml(p.user_name) || "—"} ${escapeHtml(p.user_phone_hint) || ""}</td>
      <td>${renderPhotoPair(p.original_url, p.result_url, p.is_test)}</td>
      <td>${p.wall_area_sqm ? p.wall_area_sqm + " м²" : "—"}</td>
      <td>${escapeHtml(p.selection_summary) || "—"}</td>
      <td>${p.estimated_total_uah ? "₴" + Math.round(p.estimated_total_uah) : "—"}</td>
    </tr>
  `).join("") || "<tr><td colspan='6'>Проєктів ще немає</td></tr>";
}

function switchTab(name) {
  document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("active", p.id === `panel-${name}`));
  if (name === "stats") loadStats();
  if (name === "store") loadStoreSettings();
  if (name === "leads") loadLeads();
  if (name === "inbox") loadInbox();
  if (name === "colors") {
    loadBrands().then(() => {
      const filter = document.getElementById("colors-filter-brand");
      if (filter && !filter.value && filter.options.length) {
        filter.selectedIndex = 0;
        document.getElementById("color-brand-id").value = filter.value;
      }
      loadColors();
    });
    return;
  }
  if (name === "materials") loadMaterials();
  if (name === "brands") loadBrands();
  if (name === "pricing") loadPricingPanel();
  if (name === "broadcast") loadBroadcastPanel();
}

const BROADCAST_STATUS_LABELS = {
  queued: "В черзі",
  sending: "Надсилається…",
  sent: "Надіслано",
  partial: "Частково",
  failed: "Помилка",
};

async function loadBroadcastPanel() {
  try {
    const audience = await api("/admin/broadcasts/audience");
    document.getElementById("broadcast-audience").innerHTML =
      `<strong>Аудиторія:</strong> ${audience.count} клієнт(ів) у Telegram`;
  } catch (err) {
    document.getElementById("broadcast-audience").textContent = "Аудиторія: —";
    console.error(err);
  }
  await loadBroadcasts();
}

async function loadBroadcasts() {
  const tbody = document.querySelector("#broadcasts-table tbody");
  if (!tbody) return;
  try {
    const rows = await api("/admin/broadcasts");
    tbody.innerHTML = rows.map((b) => `
      <tr>
        <td>${new Date(b.created_at).toLocaleString("uk-UA")}</td>
        <td>${escapeHtml(b.title)}</td>
        <td>${BROADCAST_STATUS_LABELS[b.status] || b.status}</td>
        <td>${b.sent_count}${b.total_recipients ? ` / ${b.total_recipients}` : ""}</td>
        <td>${b.failed_count || "—"}${b.error_message ? `<br><span class="hint small">${escapeHtml(b.error_message)}</span>` : ""}</td>
      </tr>
    `).join("") || "<tr><td colspan='5'>Розсилок ще не було</td></tr>";
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan='5'>${escapeHtml(err.message)}</td></tr>`;
  }
}

async function submitBroadcast(e) {
  e.preventDefault();
  if (!isOwner()) {
    alert("Лише власник може надсилати розсилки");
    return;
  }
  const title = document.getElementById("broadcast-title").value.trim();
  const body = document.getElementById("broadcast-body").value.trim();
  if (!title || !body) {
    alert("Заповніть заголовок і текст");
    return;
  }
  const audienceText = document.getElementById("broadcast-audience").textContent || "";
  if (!confirm(`Надіслати розсилку?\n${audienceText}`)) return;

  const form = new FormData();
  form.append("title", title);
  form.append("body", body);
  const fileInput = document.getElementById("broadcast-image");
  if (fileInput?.files?.[0]) {
    form.append("image", fileInput.files[0]);
  }

  const btn = document.getElementById("broadcast-submit");
  btn.disabled = true;
  btn.textContent = "Надсилаємо…";
  try {
    const res = await fetch(`${API}/admin/broadcasts`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: form,
    });
    if (!res.ok) throw new Error(await res.text());
    document.getElementById("broadcast-form").reset();
    alert("Розсилку поставлено в чергу. Статус оновиться в історії через кілька хвилин.");
    await loadBroadcastPanel();
  } catch (err) {
    alert("Помилка: " + err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Надіслати розсилку";
  }
}

let brandsCache = [];
let materialsCache = [];

const PRICING_SCOPE_LABELS = {
  all: "Весь каталог",
  paint: "Уся фарба",
  decor: "Уся декоративка",
  brand: "Бренд",
  material: "Матеріал",
  color: "Колір фарби",
  decor_color: "Відтінок декору",
};

const BULK_MODE_LABELS = {
  add_uah: "додати ₴",
  sub_uah: "відняти ₴",
  add_percent: "підняти на %",
  sub_percent: "знизити на %",
};

function formatColorPrice(c) {
  if (c.discount_percent && c.original_price_per_sqm != null) {
    return `<span class="price-discount">-${c.discount_percent}%</span> `
      + `<s>₴${c.original_price_per_sqm}</s> <strong>₴${c.price_per_sqm}</strong>`;
  }
  return c.price_per_sqm != null ? `₴${c.price_per_sqm}` : "—";
}

function updateBulkTargetUi() {
  const scope = document.getElementById("bulk-scope")?.value;
  const wrap = document.getElementById("bulk-target-wrap");
  const select = document.getElementById("bulk-target-id");
  if (!wrap || !select) return;
  const needsTarget = scope === "brand" || scope === "material";
  wrap.classList.toggle("hidden", !needsTarget);
  if (!needsTarget) return;
  if (scope === "brand") {
    select.innerHTML = brandsCache.map((b) => `<option value="${b.id}">${escapeHtml(b.name)}</option>`).join("")
      || "<option value=\"\">Немає брендів</option>";
  } else {
    select.innerHTML = materialsCache.map((m) => `<option value="${m.id}">${escapeHtml(m.name)}</option>`).join("")
      || "<option value=\"\">Немає матеріалів</option>";
  }
}

function updateDiscountTargetUi() {
  const scope = document.getElementById("discount-scope")?.value;
  const brandWrap = document.getElementById("discount-brand-wrap");
  const colorWrap = document.getElementById("discount-color-wrap");
  const materialWrap = document.getElementById("discount-material-wrap");
  const shadeWrap = document.getElementById("discount-shade-wrap");
  if (!scope) return;

  brandWrap?.classList.toggle("hidden", scope !== "brand" && scope !== "color");
  colorWrap?.classList.toggle("hidden", scope !== "color");
  materialWrap?.classList.toggle("hidden", scope !== "material" && scope !== "decor_color");
  shadeWrap?.classList.toggle("hidden", scope !== "decor_color");

  const brandSelect = document.getElementById("discount-brand-id");
  if (brandSelect && (scope === "brand" || scope === "color")) {
    brandSelect.innerHTML = brandsCache.map((b) => `<option value="${b.id}">${escapeHtml(b.name)}</option>`).join("")
      || "<option value=\"\">Немає брендів</option>";
    if (scope === "color") loadDiscountColors();
  }

  const materialSelect = document.getElementById("discount-material-id");
  if (materialSelect && (scope === "material" || scope === "decor_color")) {
    materialSelect.innerHTML = materialsCache.map((m) => `<option value="${m.id}">${escapeHtml(m.name)}</option>`).join("")
      || "<option value=\"\">Немає матеріалів</option>";
    if (scope === "decor_color") loadDiscountShades();
  }
}

async function loadDiscountColors() {
  const brandId = document.getElementById("discount-brand-id")?.value;
  const select = document.getElementById("discount-color-id");
  if (!select || !brandId) {
    if (select) select.innerHTML = "<option value=\"\">Оберіть бренд</option>";
    return;
  }
  const colors = await api(`/admin/colors?brand_id=${brandId}`);
  select.innerHTML = colors.map((c) => `<option value="${c.id}">${escapeHtml(c.name)} (${c.hex})</option>`).join("")
    || "<option value=\"\">Немає кольорів</option>";
}

async function loadDiscountShades() {
  const materialId = document.getElementById("discount-material-id")?.value;
  const select = document.getElementById("discount-shade-id");
  if (!select || !materialId) {
    if (select) select.innerHTML = "<option value=\"\">Оберіть матеріал</option>";
    return;
  }
  const shades = await api(`/admin/materials/${materialId}/colors`);
  select.innerHTML = shades.map((s) => `<option value="${s.id}">${escapeHtml(s.name)} (${s.hex})</option>`).join("")
    || "<option value=\"\">Немає відтінків</option>";
}

async function loadDiscounts() {
  const tbody = document.querySelector("#discounts-table tbody");
  if (!tbody) return;
  try {
    const rows = await api("/admin/discounts");
    tbody.innerHTML = rows.filter((d) => d.active).map((d) => `
      <tr>
        <td>${escapeHtml(PRICING_SCOPE_LABELS[d.scope] || d.scope)}</td>
        <td>${escapeHtml(d.target_label || "—")}</td>
        <td><span class="price-discount">-${d.discount_percent}%</span></td>
        <td>${escapeHtml(d.label) || "—"}</td>
        <td><button type="button" class="btn btn-danger" onclick="removeDiscount(${d.id})">Вимкнути</button></td>
      </tr>
    `).join("") || "<tr><td colspan='5'>Знижок ще немає</td></tr>";
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan='5'>Помилка: ${escapeHtml(err.message)}</td></tr>`;
  }
}

async function loadPricingPanel() {
  await Promise.all([loadBrands(), loadMaterials()]);
  updateBulkTargetUi();
  updateDiscountTargetUi();
  await loadDiscounts();
}

async function submitBulkAdjust(e) {
  e.preventDefault();
  const scope = document.getElementById("bulk-scope").value;
  const mode = document.getElementById("bulk-mode").value;
  const value = parseFloat(document.getElementById("bulk-value").value);
  const body = { scope, mode, value };
  if (scope === "brand" || scope === "material") {
    const targetId = parseInt(document.getElementById("bulk-target-id").value, 10);
    if (!targetId) {
      alert("Оберіть ціль");
      return;
    }
    body.target_id = targetId;
  }
  const scopeLabel = PRICING_SCOPE_LABELS[scope] || scope;
  const modeLabel = BULK_MODE_LABELS[mode] || mode;
  if (!confirm(`Застосувати «${modeLabel}» = ${value} для «${scopeLabel}»? Ціни зміняться одразу.`)) return;
  try {
    const res = await api("/admin/pricing/bulk-adjust", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    alert(res.message);
    loadColors();
    loadBrands();
    loadMaterials();
  } catch (err) {
    alert("Помилка: " + err.message);
  }
}

async function submitDiscount(e) {
  e.preventDefault();
  const scope = document.getElementById("discount-scope").value;
  const body = {
    scope,
    discount_percent: parseFloat(document.getElementById("discount-percent").value),
    label: document.getElementById("discount-label").value.trim() || null,
  };
  if (scope === "brand") {
    body.target_id = parseInt(document.getElementById("discount-brand-id").value, 10);
  } else if (scope === "color") {
    body.target_id = parseInt(document.getElementById("discount-color-id").value, 10);
  } else if (scope === "material") {
    body.target_id = parseInt(document.getElementById("discount-material-id").value, 10);
  } else if (scope === "decor_color") {
    body.target_id = parseInt(document.getElementById("discount-shade-id").value, 10);
  }
  if (scope_requires_target(scope) && !body.target_id) {
    alert("Оберіть ціль для знижки");
    return;
  }
  try {
    await api("/admin/discounts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    document.getElementById("discount-form").reset();
    updateDiscountTargetUi();
    await loadDiscounts();
    loadColors();
  } catch (err) {
    alert("Помилка: " + err.message);
  }
}

function scope_requires_target(scope) {
  return ["brand", "color", "material", "decor_color"].includes(scope);
}

async function removeDiscount(id) {
  if (!confirm("Вимкнути цю знижку?")) return;
  await api(`/admin/discounts/${id}`, { method: "DELETE" });
  await loadDiscounts();
  loadColors();
}

function decorPackRowHtml(pack = {}) {
  return `
    <div class="pack-row">
      <input type="hidden" class="pack-id" value="${pack.id || ""}">
      <input class="pack-coverage" type="number" step="0.1" min="0.1" placeholder="м²/уп." value="${pack.coverage_sqm ?? ""}" required>
      <input class="pack-price" type="number" step="1" min="1" placeholder="Ціна ₴" value="${pack.price_uah ?? ""}" required>
      <input class="pack-label" type="text" placeholder="Підпис (25 кг)" value="${pack.label || ""}">
      <button type="button" class="btn btn-danger pack-remove">×</button>
    </div>`;
}

function readDecorPackRows() {
  return [...document.querySelectorAll("#decor-packs-editor .pack-row")].map((row, i) => ({
    id: row.querySelector(".pack-id")?.value ? parseInt(row.querySelector(".pack-id").value, 10) : null,
    coverage_sqm: parseFloat(row.querySelector(".pack-coverage").value),
    price_uah: parseFloat(row.querySelector(".pack-price").value),
    label: row.querySelector(".pack-label").value.trim() || null,
    sort_order: i,
  }));
}

function packRowHtml(pack = {}) {
  return `
    <div class="pack-row">
      <input type="hidden" class="pack-id" value="${pack.id || ""}">
      <input class="pack-volume" type="number" step="0.1" min="0.1" placeholder="Обʼєм, л" value="${pack.volume_liters ?? ""}" required>
      <input class="pack-price" type="number" step="1" min="1" placeholder="Ціна ₴" value="${pack.price_uah ?? ""}" required>
      <input class="pack-label" type="text" placeholder="Підпис (5 л)" value="${pack.label || ""}">
      <button type="button" class="btn btn-danger pack-remove">×</button>
    </div>`;
}

function readPackRows() {
  return [...document.querySelectorAll("#brand-packs-editor .pack-row")].map((row, i) => ({
    id: row.querySelector(".pack-id")?.value ? parseInt(row.querySelector(".pack-id").value, 10) : null,
    volume_liters: parseFloat(row.querySelector(".pack-volume").value),
    price_uah: parseFloat(row.querySelector(".pack-price").value),
    label: row.querySelector(".pack-label").value.trim() || null,
    sort_order: i,
    active: true,
  })).filter((p) => p.volume_liters > 0 && p.price_uah > 0);
}

function resetBrandForm() {
  document.getElementById("brand-edit-id").value = "";
  document.getElementById("brand-form").reset();
  document.getElementById("brand-coverage").value = "10";
  document.getElementById("brand-coats").value = "2";
  document.getElementById("brand-finish").value = "matte";
  document.getElementById("brand-packs-editor").innerHTML = "";
}

function editBrand(brand) {
  document.getElementById("brand-edit-id").value = brand.id;
  document.getElementById("brand-name").value = brand.name;
  document.getElementById("brand-country").value = brand.country || "";
  document.getElementById("brand-coverage").value = brand.coverage_sqm_per_liter || 10;
  document.getElementById("brand-coats").value = brand.recommended_coats || 2;
  document.getElementById("brand-finish").value = brand.paint_finish || "matte";
  const editor = document.getElementById("brand-packs-editor");
  editor.innerHTML = (brand.pack_sizes || []).map((p) => packRowHtml(p)).join("");
  document.getElementById("panel-brands").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function loadBrands() {
  const brands = await api("/admin/brands");
  brandsCache = brands;
  const tbody = document.querySelector("#brands-table tbody");
  tbody.innerHTML = brands.map((b) => {
    const packs = (b.pack_sizes || []).map((p) => `${p.label || p.volume_liters + "л"} — ₴${p.price_uah}`).join(", ");
    const finish = b.paint_finish_label || b.paint_finish || "—";
    const ownerActions = isOwner()
      ? `<button class="btn btn-primary" onclick="editBrandById(${b.id})">Редагувати</button>
         <button class="btn btn-danger" onclick="deleteBrand(${b.id})">Видалити</button>`
      : `<span class="hint small">Лише перегляд</span>`;
    return `
    <tr>
      <td>${b.name}</td>
      <td>${finish}</td>
      <td>${b.coverage_sqm_per_liter || 10} м²/л × ${b.recommended_coats || 2}</td>
      <td>${packs || "—"}</td>
      <td>${ownerActions}</td>
    </tr>`;
  }).join("");
  const sel = document.getElementById("color-brand-id");
  const filterSel = document.getElementById("colors-filter-brand");
  const brandOptions = brands.map((b) => `<option value="${b.id}">${b.name}</option>`).join("");
  if (sel) sel.innerHTML = brandOptions;
  if (filterSel) {
    const prev = filterSel.value;
    filterSel.innerHTML = brandOptions;
    if (prev) filterSel.value = prev;
    else if (sel?.value) filterSel.value = sel.value;
  }
  const importSel = document.getElementById("import-brand-id");
  if (importSel) {
    importSel.innerHTML = brands.map((b) => `<option value="${b.id}">${b.name}</option>`).join("");
  }
}

async function createBrand(e) {
  e.preventDefault();
  if (!isOwner()) {
    alert("Лише власник може змінювати бренди");
    return;
  }
  const editId = document.getElementById("brand-edit-id").value;
  const payload = {
    name: document.getElementById("brand-name").value.trim(),
    country: document.getElementById("brand-country").value.trim() || null,
    coverage_sqm_per_liter: parseFloat(document.getElementById("brand-coverage").value) || 10,
    recommended_coats: parseInt(document.getElementById("brand-coats").value, 10) || 2,
    paint_finish: document.getElementById("brand-finish").value,
    pack_sizes: readPackRows(),
  };
  if (editId) {
    await api(`/admin/brands/${editId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } else {
    await api("/admin/brands", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  }
  resetBrandForm();
  loadBrands();
}

function editBrandById(id) {
  const brand = brandsCache.find((b) => b.id === id);
  if (brand) editBrand(brand);
}

async function deleteBrand(id) {
  if (!confirm("Деактивувати бренд?")) return;
  await api(`/admin/brands/${id}`, { method: "DELETE" });
  loadBrands();
}

async function loadColors() {
  const brandId = document.getElementById("colors-filter-brand")?.value
    || document.getElementById("color-brand-id")?.value;
  const tbody = document.querySelector("#colors-table tbody");
  if (!brandId) {
    tbody.innerHTML = "<tr><td colspan='8'>Оберіть виробника</td></tr>";
    return;
  }
  document.getElementById("color-brand-id").value = brandId;
  const colors = await api(`/admin/colors?brand_id=${brandId}`);
  tbody.innerHTML = colors.map((c) => `
    <tr>
      <td><span class="swatch" style="background:${c.hex}"></span> ${c.name}</td>
      <td>${c.hex}</td>
      <td>${c.manufacturer_code || ""}</td>
      <td>${c.tint_base ? "База " + c.tint_base : "—"}</td>
      <td>${formatColorPrice(c)}</td>
      <td>${c.category}</td>
      <td>
        <button class="btn ${c.in_stock ? "btn-success" : "btn-danger"}" onclick="toggleColorStock(${c.id}, ${c.in_stock ? "false" : "true"})">
          ${c.in_stock ? "В наявності" : "Немає"}
        </button>
      </td>
      <td><button class="btn btn-danger" onclick="deleteColor(${c.id})">Приховати</button></td>
    </tr>
  `).join("") || "<tr><td colspan='8'>Немає кольорів для цього виробника</td></tr>";
}

async function toggleColorStock(id, inStock) {
  await api(`/admin/colors/${id}/stock`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ in_stock: inStock }),
  });
  loadColors();
}

async function createColor(e) {
  e.preventDefault();
  await api("/admin/colors", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      brand_id: parseInt(document.getElementById("color-brand-id").value),
      name: document.getElementById("color-name").value,
      hex: document.getElementById("color-hex").value,
      manufacturer_code: document.getElementById("color-code").value,
      tint_base: document.getElementById("color-tint-base").value || null,
      price_per_sqm: parseFloat(document.getElementById("color-price").value) || null,
      category: document.getElementById("color-category").value,
    }),
  });
  e.target.reset();
  loadColors();
}

async function deleteColor(id) {
  await api(`/admin/colors/${id}`, { method: "DELETE" });
  loadColors();
}

async function previewImport(e) {
  e.preventDefault();
  const form = new FormData();
  form.append("file", document.getElementById("import-file").files[0]);
  const res = await fetch(`${API}/admin/import/colors/preview`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  importPreview = await res.json();
  const div = document.getElementById("import-preview");
  div.innerHTML = `<p>Валідних: ${importPreview.valid_count}, помилок: ${importPreview.invalid_count}</p>
    <table><thead><tr><th>Назва</th><th>HEX</th><th>Категорія</th><th>OK</th></tr></thead>
    <tbody>${importPreview.rows.map((r) => `<tr><td>${r.name}</td><td>${r.hex}</td><td>${r.category}</td><td>${r.valid ? "✓" : r.error}</td></tr>`).join("")}</tbody></table>`;
}

async function confirmImport() {
  if (!importPreview) return;
  const brandId = parseInt(document.getElementById("import-brand-id").value);
  await api("/admin/import/colors/confirm", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ brand_id: brandId, rows: importPreview.rows }),
  });
  alert("Імпорт завершено");
  loadColors();
}

async function loadMaterials() {
  const materials = await api("/admin/materials");
  materialsCache = materials;
  const tbody = document.querySelector("#materials-table tbody");
  tbody.innerHTML = materials.map((m) => {
    const packs = (m.pack_sizes || []).map((p) => `${p.label || p.coverage_sqm + " м²"} — ₴${p.price_uah}`).join(", ");
    return `
    <tr>
      <td>${escapeHtml(m.name)}</td>
      <td>${escapeHtml(m.category) || "—"}</td>
      <td>${packs || "—"}</td>
      <td>${m.texture_scale}</td>
      <td>
        <button type="button" class="btn ${m.in_stock ? "btn-success" : "btn-danger"}" onclick="toggleMaterialStock(${m.id}, ${m.in_stock ? "false" : "true"})">
          ${m.in_stock ? "В наявності" : "Немає"}
        </button>
      </td>
      <td>
        <button type="button" class="btn btn-primary" onclick="showMaterialShades(${m.id}, '${escapeHtml(m.name).replace(/'/g, "\\'")}')">Відтінки</button>
        <button type="button" class="btn" onclick="editMaterialPacks(${m.id})">Фасування</button>
        <button type="button" class="btn" onclick="uploadTexture(${m.id})">Текстура</button>
        <button type="button" class="btn btn-danger" onclick="deleteMaterial(${m.id})">×</button>
      </td>
    </tr>`;
  }).join("") || "<tr><td colspan='6'>Матеріалів ще немає</td></tr>";
}

async function editMaterialPacks(materialId) {
  const materials = await api("/admin/materials");
  const material = materials.find((m) => m.id === materialId);
  if (!material) return;
  activeMaterialId = materialId;
  activeMaterialName = material.name;
  const panel = document.getElementById("material-shades-panel");
  panel.classList.remove("hidden");
  panel.innerHTML = `
    <h4>Фасування: ${escapeHtml(material.name)}</h4>
    <p class="hint small">Упаковка декору: скільки м² покриває і ціна за упаковку.</p>
    <label>Шарів за замовчуванням
      <input id="material-coats" type="number" min="1" max="5" value="${material.recommended_coats || 1}">
    </label>
    <div id="decor-packs-editor">${(material.pack_sizes || []).map((p) => decorPackRowHtml(p)).join("")}</div>
    <button type="button" class="btn" id="decor-add-pack">+ Додати упаковку</button>
    <button type="button" class="btn btn-primary" id="decor-save-packs">Зберегти фасування</button>
    <button type="button" class="btn" onclick="showMaterialShades(${materialId}, '${escapeHtml(material.name).replace(/'/g, "\\'")}')">← До відтінків</button>
  `;
  document.getElementById("decor-add-pack").onclick = () => {
    document.getElementById("decor-packs-editor").insertAdjacentHTML("beforeend", decorPackRowHtml({}));
  };
  document.getElementById("decor-packs-editor").onclick = (e) => {
    if (e.target.classList.contains("pack-remove")) e.target.closest(".pack-row")?.remove();
  };
  document.getElementById("decor-save-packs").onclick = async () => {
    const coats = parseInt(document.getElementById("material-coats").value, 10) || 1;
    await api(`/admin/materials/${materialId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        recommended_coats: coats,
        pack_sizes: readDecorPackRows(),
      }),
    });
    alert("Збережено");
    loadMaterials();
    editMaterialPacks(materialId);
  };
}

async function toggleMaterialStock(id, inStock) {
  await api(`/admin/materials/${id}/stock`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ in_stock: inStock }),
  });
  loadMaterials();
}

async function showMaterialShades(materialId, materialName) {
  activeMaterialId = materialId;
  activeMaterialName = materialName;
  editingDecorColorId = null;
  const colors = await api(`/admin/materials/${materialId}/colors`);
  shadesCache = colors;
  const panel = document.getElementById("material-shades-panel");
  panel.classList.remove("hidden");
  panel.innerHTML = `
    <h4>Відтінки: ${materialName}</h4>
    <form id="decor-color-form" class="inline-form">
      <input type="hidden" id="decor-edit-color-id" value="">
      <input id="decor-color-name" placeholder="Назва (Срібний)" required>
      <input id="decor-color-hex" placeholder="#C0C0C0" pattern="#[0-9A-Fa-f]{6}" required>
      <input id="decor-color-price" type="number" step="1" min="0" placeholder="Ціна ₴/м²">
      <button type="submit" class="btn btn-primary" id="decor-color-submit">Додати відтінок</button>
      <button type="button" class="btn hidden" id="decor-color-cancel-edit">Скасувати</button>
    </form>
    <table>
      <thead><tr><th>Назва</th><th>HEX</th><th>₴/м²</th><th>Наявність</th><th></th></tr></thead>
      <tbody>
        ${colors.map((c) => `
          <tr>
            <td><span class="swatch" style="background:${c.hex}"></span> ${c.name}</td>
            <td>${c.hex}</td>
            <td>${c.price_per_sqm != null ? "₴" + c.price_per_sqm : "—"}</td>
            <td>
              <button class="btn ${c.in_stock ? "btn-success" : "btn-danger"}"
                onclick="toggleDecorColorStock(${materialId}, ${c.id}, ${c.in_stock ? "false" : "true"})">
                ${c.in_stock ? "В наявності" : "Немає"}
              </button>
            </td>
            <td>
              <button class="btn btn-primary" onclick="editDecorColorById(${c.id})">Редагувати</button>
              <button class="btn btn-danger" onclick="deleteDecorColor(${materialId}, ${c.id})">Видалити</button>
            </td>
          </tr>
        `).join("") || "<tr><td colspan='5'>Немає відтінків — додайте перший вище</td></tr>"}
      </tbody>
    </table>
  `;
  document.getElementById("decor-color-form").onsubmit = saveDecorColor;
  document.getElementById("decor-color-cancel-edit").onclick = resetDecorColorForm;
}

let activeMaterialId = null;
let activeMaterialName = "";
let editingDecorColorId = null;
let shadesCache = [];

function editDecorColorById(id) {
  const color = shadesCache.find((c) => c.id === id);
  if (color) editDecorColor(color);
}

function resetDecorColorForm() {
  editingDecorColorId = null;
  document.getElementById("decor-edit-color-id").value = "";
  document.getElementById("decor-color-name").value = "";
  document.getElementById("decor-color-hex").value = "";
  document.getElementById("decor-color-price").value = "";
  document.getElementById("decor-color-submit").textContent = "Додати відтінок";
  document.getElementById("decor-color-cancel-edit").classList.add("hidden");
}

function editDecorColor(color) {
  editingDecorColorId = color.id;
  document.getElementById("decor-edit-color-id").value = String(color.id);
  document.getElementById("decor-color-name").value = color.name;
  document.getElementById("decor-color-hex").value = color.hex;
  document.getElementById("decor-color-price").value = color.price_per_sqm ?? "";
  document.getElementById("decor-color-submit").textContent = "Зберегти зміни";
  document.getElementById("decor-color-cancel-edit").classList.remove("hidden");
  document.getElementById("decor-color-form").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function saveDecorColor(e) {
  e.preventDefault();
  if (!activeMaterialId) return;
  const hex = document.getElementById("decor-color-hex").value.trim();
  const payload = {
    name: document.getElementById("decor-color-name").value.trim(),
    hex: hex.startsWith("#") ? hex : `#${hex}`,
    price_per_sqm: parseFloat(document.getElementById("decor-color-price").value) || null,
  };
  if (editingDecorColorId) {
    await api(`/admin/materials/${activeMaterialId}/colors/${editingDecorColorId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } else {
    await api(`/admin/materials/${activeMaterialId}/colors`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  }
  showMaterialShades(activeMaterialId, activeMaterialName);
}

async function deleteDecorColor(materialId, colorId) {
  if (!confirm("Видалити цей відтінок?")) return;
  await api(`/admin/materials/${materialId}/colors/${colorId}`, { method: "DELETE" });
  showMaterialShades(materialId, activeMaterialName);
}

async function toggleDecorColorStock(materialId, colorId, inStock) {
  await api(`/admin/materials/${materialId}/colors/${colorId}/stock`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ in_stock: inStock }),
  });
  const name = document.querySelector("#material-shades-panel h4")?.textContent?.replace("Відтінки: ", "") || "";
  showMaterialShades(materialId, name);
}

async function createMaterial(e) {
  e.preventDefault();
  await api("/admin/materials", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: document.getElementById("material-name").value,
      category: document.getElementById("material-category").value,
      texture_scale: parseFloat(document.getElementById("material-scale").value) || 1,
    }),
  });
  e.target.reset();
  loadMaterials();
}

async function deleteMaterial(id) {
  await api(`/admin/materials/${id}`, { method: "DELETE" });
  loadMaterials();
}

async function uploadTexture(materialId) {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = "image/*";
  input.onchange = async () => {
    const form = new FormData();
    form.append("file", input.files[0]);
    await fetch(`${API}/admin/materials/${materialId}/texture`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: form,
    });
    alert("Текстуру завантажено");
    loadMaterials();
  };
  input.click();
}

window.editBrandById = editBrandById;
window.markLead = markLead;
window.showLeadDetail = showLeadDetail;
window.closeLeadDetail = closeLeadDetail;
window.editDecorColorById = editDecorColorById;
window.editMaterialPacks = editMaterialPacks;
window.downloadLeadQuote = (id) => {
  const btn = document.getElementById("lead-quote-btn");
  fetchLeadQuotePdf(id, btn);
};
window.removeDiscount = removeDiscount;
window.toggleColorStock = toggleColorStock;
window.toggleMaterialStock = toggleMaterialStock;
window.toggleDecorColorStock = toggleDecorColorStock;
window.showMaterialShades = showMaterialShades;
window.deleteDecorColor = deleteDecorColor;

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("login-form").onsubmit = login;
  document.getElementById("logout-btn").onclick = logout;
  document.getElementById("brand-form").onsubmit = createBrand;
  document.getElementById("brand-form-reset").onclick = resetBrandForm;
  document.getElementById("brand-add-pack").onclick = () => {
    document.getElementById("brand-packs-editor").insertAdjacentHTML("beforeend", packRowHtml({}));
  };
  document.getElementById("brand-packs-editor").onclick = (e) => {
    if (e.target.classList.contains("pack-remove")) {
      e.target.closest(".pack-row")?.remove();
    }
  };
  document.getElementById("color-form").onsubmit = createColor;
  document.getElementById("import-form").onsubmit = previewImport;
  document.getElementById("confirm-import-btn").onclick = confirmImport;
  document.getElementById("material-form").onsubmit = createMaterial;
  document.getElementById("broadcast-form").onsubmit = submitBroadcast;
  document.getElementById("bulk-price-form").onsubmit = submitBulkAdjust;
  document.getElementById("discount-form").onsubmit = submitDiscount;
  document.getElementById("bulk-scope").onchange = updateBulkTargetUi;
  document.getElementById("discount-scope").onchange = updateDiscountTargetUi;
  document.getElementById("discount-brand-id").onchange = () => {
    if (document.getElementById("discount-scope")?.value === "color") loadDiscountColors();
  };
  document.getElementById("discount-material-id").onchange = () => {
    if (document.getElementById("discount-scope")?.value === "decor_color") loadDiscountShades();
  };
  document.getElementById("store-form").onsubmit = saveStoreSettings;
  document.getElementById("store-test-notify").onclick = testStoreNotification;
  document.getElementById("leads-status-filter").onchange = loadLeads;
  document.getElementById("leads-sort").onchange = loadLeads;
  document.getElementById("leads-apply-filter").onclick = loadLeads;
  document.getElementById("leads-clear-dates").onclick = () => {
    const fromEl = document.getElementById("leads-from");
    const toEl = document.getElementById("leads-to");
    if (fromEl) fromEl.value = "";
    if (toEl) toEl.value = "";
    loadLeads();
  };
  ["leads-from", "leads-to"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener("change", loadLeads);
  });
  document.getElementById("leads-export-csv").onclick = () => {
    exportLeadsCsv().catch((err) => alert("Експорт не вдався: " + err.message));
  };
  document.getElementById("stats-period").onchange = loadStats;
  document.getElementById("lead-detail-close").onclick = closeLeadDetail;
  document.getElementById("lead-detail-backdrop").onclick = closeLeadDetail;
  document.getElementById("colors-filter-brand").onchange = () => {
    document.getElementById("color-brand-id").value = document.getElementById("colors-filter-brand").value;
    loadColors();
  };
  document.querySelectorAll(".tabs button").forEach((b) => b.onclick = () => switchTab(b.dataset.tab));
  if (token) showApp();
});
