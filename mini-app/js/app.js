const API_BASE = "/api";

const FINISH_LABELS = {
  matte: "Матова",
  silk_matte: "Шовк.-матова",
  gloss: "Глянцева",
};

const COLORS_PAGE_SIZE = 50;

const PROCESS_STATUS_LABELS = {
  received: "📷 Фото отримано…",
  queued: "⏳ Очікує в черзі…",
  processing: "🔄 AI визначає стіни…",
};

let state = {
  token: null,
  project: null,
  store: null,
  wallAreaSqm: null,
  paintEstimate: null,
  mode: "paint",
  finish: "matte",
  brands: [],
  colors: [],
  colorsTotal: 0,
  colorsPage: 1,
  colorFilters: {},
  materials: [],
  materialColors: [],
  selectedColor: null,
  selectedMaterial: null,
  selectedMaterialColor: null,
  textureScale: 1.0,
  promotions: [],
};

function safeGetQueryParam(name) {
  const search = window.location.search;
  if (!search || search.length < 2) return null;
  const body = search.startsWith("?") ? search.slice(1) : search;
  for (const segment of body.split("&")) {
    if (!segment) continue;
    const eq = segment.indexOf("=");
    const key = eq === -1 ? segment : segment.slice(0, eq);
    if (key !== name) continue;
    const raw = eq === -1 ? "" : segment.slice(eq + 1);
    try {
      return decodeURIComponent(raw.replace(/\+/g, " "));
    } catch {
      return raw;
    }
  }
  return null;
}

function normalizeHex(hex) {
  if (!hex) return "#cccccc";
  const h = String(hex).trim();
  if (/^#[0-9a-f]{6}$/i.test(h)) return h;
  if (/^[0-9a-f]{6}$/i.test(h)) return `#${h}`;
  return "#cccccc";
}

function formatUah(amount) {
  if (amount == null || Number.isNaN(amount)) return "";
  return `₴${Math.round(amount).toLocaleString("uk-UA")}`;
}

function formatPricePerSqm(price) {
  if (price == null || price <= 0) return "";
  return `${formatUah(price)}/м²`;
}

function escapeHtml(text) {
  if (text == null) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatPriceHtml(item) {
  if (!item?.price_per_sqm || item.price_per_sqm <= 0) return "";
  if (item.discount_percent && item.original_price_per_sqm) {
    return `<span class="price-old">${formatPricePerSqm(item.original_price_per_sqm)}</span> `
      + `<span class="price-tag price-tag--sale">${formatPricePerSqm(item.price_per_sqm)}</span>`;
  }
  return `<span class="price-tag">${formatPricePerSqm(item.price_per_sqm)}</span>`;
}

function getActiveCatalogItem() {
  if (state.mode === "decor" && state.selectedMaterialColor) return state.selectedMaterialColor;
  if (state.mode === "paint" && state.selectedColor) return state.selectedColor;
  return null;
}

function getActiveDiscountPercent() {
  const item = getActiveCatalogItem();
  if (item?.discount_percent) return item.discount_percent;
  if (state.paintEstimate?.discount_percent) return state.paintEstimate.discount_percent;
  if (state.mode === "paint" && state.selectedColor) {
    const brand = getSelectedBrand();
    if (brand?.discount_percent) return brand.discount_percent;
  }
  if (state.mode === "decor" && state.selectedMaterial?.discount_percent) {
    return state.selectedMaterial.discount_percent;
  }
  return null;
}

function getOriginalTotal() {
  const total = calcTotal();
  const disc = getActiveDiscountPercent();
  if (total == null || !disc) return null;
  return Math.round(total / (1 - disc / 100));
}

async function loadPromotions() {
  if (!state.project?.id) return;
  try {
    state.promotions = await api(`/catalog/promotions?project_id=${state.project.id}`);
  } catch (err) {
    console.warn("promotions failed", err);
    state.promotions = [];
  }
  renderPromoBanner();
}

function renderPromoBanner() {
  const el = document.getElementById("promo-banner");
  if (!el) return;
  if (!state.promotions?.length) {
    el.classList.add("hidden");
    el.innerHTML = "";
    return;
  }
  el.classList.remove("hidden");
  el.innerHTML = state.promotions
    .map((p) => `<div class="promo-chip">🔥 ${escapeHtml(p.message)}</div>`)
    .join("");
}

function getActivePriceItem() {
  if (state.mode === "decor" && state.selectedMaterialColor) return state.selectedMaterialColor;
  if (state.mode === "paint" && state.selectedColor) return state.selectedColor;
  return null;
}

function calcTotal() {
  if (state.paintEstimate?.total_uah) {
    return Math.round(state.paintEstimate.total_uah);
  }
  const item = getActivePriceItem();
  if (!item?.price_per_sqm || !state.wallAreaSqm || state.wallAreaSqm <= 0) return null;
  return Math.round(item.price_per_sqm * state.wallAreaSqm);
}

let estimateTimer = null;
function scheduleEstimate() {
  clearTimeout(estimateTimer);
  estimateTimer = setTimeout(refreshEstimate, 350);
}

async function refreshEstimate() {
  state.paintEstimate = null;
  if (!state.project?.id || !state.wallAreaSqm) {
    updateCostBar();
    return;
  }
  try {
    if (state.mode === "paint" && state.selectedColor?.id) {
      const q = new URLSearchParams({
        project_id: String(state.project.id),
        color_id: String(state.selectedColor.id),
        wall_area_sqm: String(state.wallAreaSqm),
      });
      state.paintEstimate = await api(`/catalog/paint-estimate?${q}`);
    } else if (state.mode === "decor" && state.selectedMaterial?.id) {
      const q = new URLSearchParams({
        project_id: String(state.project.id),
        material_id: String(state.selectedMaterial.id),
        wall_area_sqm: String(state.wallAreaSqm),
      });
      if (state.selectedMaterialColor?.id) {
        q.set("decor_color_id", String(state.selectedMaterialColor.id));
      }
      state.paintEstimate = await api(`/catalog/decor-estimate?${q}`);
    }
  } catch (err) {
    console.warn("estimate failed", err);
    state.paintEstimate = null;
  }
  updateCostBar();
  if (state.mode === "paint") updatePaintSelectionInfo();
  else updateDecorSelectionInfo();
}

function updateCostBar() {
  const bar = document.getElementById("cost-bar");
  const totalEl = document.getElementById("cost-total");
  const detailEl = document.getElementById("cost-detail");
  const total = calcTotal();
  const disc = getActiveDiscountPercent();
  const original = getOriginalTotal();
  if (total != null) {
    bar.classList.remove("hidden");
    if (disc && original && original > total) {
      totalEl.innerHTML = `<span class="price-old">${formatUah(original)}</span> `
        + `<span class="price-sale">${formatUah(total)}</span> `
        + `<span class="discount-badge-inline">−${disc}%</span>`;
    } else {
      totalEl.textContent = formatUah(total);
    }
    if (state.paintEstimate) {
      const est = state.paintEstimate;
      const packs = (est.packs || [])
        .map((p) => `${p.count}×${p.label}`)
        .join(", ");
      let detail = state.mode === "paint"
        ? `~${est.liters_needed} л · ${packs}`
        : `~${est.liters_needed} м² · ${packs}`;
      if (est.tint_base) detail += ` · база ${est.tint_base}`;
      detailEl.textContent = detail;
      detailEl.classList.remove("hidden");
    } else {
      detailEl.textContent = "";
      detailEl.classList.add("hidden");
    }
  } else {
    bar.classList.add("hidden");
    totalEl.textContent = "—";
    detailEl.textContent = "";
  }
}

let syncTimer = null;
let resultSaveTimer = null;

function scheduleSyncState() {
  clearTimeout(syncTimer);
  syncTimer = setTimeout(syncProjectState, 400);
}

function scheduleResultSave() {
  clearTimeout(resultSaveTimer);
  resultSaveTimer = setTimeout(() => {
    window.renderer?.persistResult?.().catch((err) => console.warn("result save failed", err));
  }, 1200);
}

function readWallAreaSqm() {
  const fromState = state.wallAreaSqm;
  if (fromState && fromState > 0) return fromState;
  const raw = document.getElementById("wall-area")?.value;
  const fromInput = raw ? parseFloat(raw) : NaN;
  return fromInput > 0 ? fromInput : null;
}

async function syncProjectState() {
  if (!state.project?.id) return;
  const wallAreaSqm = readWallAreaSqm();
  const body = {
    wall_area_sqm: wallAreaSqm,
    selected_finish: state.finish,
    mode: state.mode,
  };
  if (state.mode === "paint") {
    body.selected_color_id = state.selectedColor?.id ?? null;
    body.selected_decor_color_id = null;
    body.selected_material_id = null;
  } else {
    body.selected_color_id = null;
    body.selected_decor_color_id = state.selectedMaterialColor?.id ?? null;
    body.selected_material_id = state.selectedMaterial?.id ?? null;
  }
  try {
    await api(`/projects/${state.project.id}/state`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (err) {
    console.warn("sync state failed", err);
  }
}

async function api(path, options = {}) {
  const headers = {
    "ngrok-skip-browser-warning": "1",
    ...(options.headers || {}),
  };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    if (res.status === 401) {
      throw new Error("Сесія недійсна. Закрийте і знову відкрийте редактор з бота");
    }
    const text = await res.text();
    if (res.status === 502 || text.includes("502 Bad Gateway")) {
      throw new Error(
        "Сервер тимчасово недоступний (502). Зачекайте 10 сек і спробуйте знову. Якщо не допоможе — на ноутбуці: docker compose up -d api bot"
      );
    }
    if (text.trimStart().startsWith("<")) {
      throw new Error(`Помилка сервера (${res.status}). Спробуйте ще раз через кілька секунд.`);
    }
    throw new Error(text || `HTTP ${res.status}`);
  }
  const ct = res.headers.get("content-type") || "";
  if (!ct.includes("application/json")) {
    throw new Error("Сервер повернув некоректну відповідь. Перевірте ngrok / WEBAPP_URL");
  }
  return res.json();
}

async function authenticate(projectId) {
  const urlToken = safeGetQueryParam("access_token");
  if (urlToken) {
    state.token = urlToken;
    return;
  }
  const tg = window.Telegram?.WebApp;
  if (!tg) throw new Error("Відкрийте редактор з Telegram-бота");
  tg.ready();
  tg.expand();
  const initData = tg.initData;
  if (!initData) {
    throw new Error("Немає авторизації. Відкрийте редактор з бота ще раз");
  }
  const data = await api("/auth/telegram", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ init_data: initData, project_id: projectId ? parseInt(projectId, 10) : null }),
  });
  state.token = data.access_token;
}

function getProjectId() {
  let id = safeGetQueryParam("project_id");
  if (id && /^\d+$/.test(id)) return id;
  const tg = window.Telegram?.WebApp;
  const startParam = tg?.initDataUnsafe?.start_param;
  if (startParam && /^\d+$/.test(startParam)) return startParam;
  return null;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function setLoadingMessage(text) {
  const loading = document.getElementById("loading");
  if (!loading) return;
  loading.textContent = text;
  loading.classList.remove("hidden");
}

async function loadProject() {
  const id = getProjectId();
  if (!id) throw new Error("Немає project_id. Відкрийте через бота");

  const maxAttempts = 100;
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    state.project = await api(`/projects/${id}`);
    const status = state.project.status;

    if (status === "ready") {
      return;
    }
    if (status === "error") {
      throw new Error(
        state.project.error_message ||
          "Помилка обробки фото. Спробуйте надіслати інше фото в бот."
      );
    }

    const label = PROCESS_STATUS_LABELS[status] || "⏳ Обробка…";
    setLoadingMessage(`${label}\nЗачекайте, це займе 1–2 хв.`);
    await sleep(3000);
  }

  throw new Error(
    "Обробка триває занадто довго. Закрийте редактор і відкрийте з Telegram, коли прийде «Готово»."
  );
}

async function trackEditorOpen() {
  if (!state.project?.id) return;
  try {
    await api(`/projects/${state.project.id}/open`, { method: "POST" });
  } catch (err) {
    console.warn("track open failed", err);
  }
}

async function loadStore() {
  state.store = await api(`/catalog/store?project_id=${state.project.id}`);
  const bar = document.getElementById("store-bar");
  const label = document.getElementById("store-name-label");
  if (state.store?.name) {
    bar.classList.remove("hidden");
    label.textContent = state.store.name;
  }
}

async function loadBrands() {
  const params = new URLSearchParams({
    project_id: String(state.project.id),
    finish: state.finish,
  });
  state.brands = await api(`/catalog/brands?${params}`);
  renderBrands();
}

function getSelectedBrand() {
  if (!state.selectedColor) return null;
  return state.brands.find((b) => b.id === state.selectedColor.brand_id) || null;
}

function syncFinishFromBrand() {
  const brand = getSelectedBrand();
  if (brand?.paint_finish && brand.paint_finish !== state.finish) {
    setFinish(brand.paint_finish, { reload: false });
  }
}

async function setFinish(finish, { reload = true } = {}) {
  state.finish = finish;
  document.querySelectorAll(".finish-row button").forEach((b) => {
    b.classList.toggle("active", b.dataset.finish === finish);
  });
  if (!reload) {
    window.renderer.render();
    return;
  }
  state.selectedColor = null;
  state.paintEstimate = null;
  document.getElementById("brand-filter").value = "";
  await loadBrands();
  state.colors = [];
  renderColors();
  if (state.brands.length) {
    document.getElementById("brand-filter").value = String(state.brands[0].id);
    await loadColors({ brand_id: state.brands[0].id });
  }
  onSelectionChanged();
  window.renderer.render();
  scheduleSyncState();
}

async function loadColors(filters = {}, { append = false } = {}) {
  const activeFilters = append ? { ...state.colorFilters } : { ...filters };
  if (!append) {
    state.colorFilters = activeFilters;
    state.colorsPage = 1;
  } else {
    state.colorsPage += 1;
  }

  const params = new URLSearchParams({
    project_id: String(state.project.id),
    page: String(state.colorsPage),
    page_size: String(COLORS_PAGE_SIZE),
  });
  if (activeFilters.brand_id) params.set("brand_id", activeFilters.brand_id);
  if (activeFilters.category) params.set("category", activeFilters.category);
  if (activeFilters.search) params.set("search", activeFilters.search);

  const data = await api(`/catalog/colors?${params}`);
  if (append) {
    const existing = new Set(state.colors.map((c) => c.id));
    const merged = [...state.colors];
    for (const item of data.items || []) {
      if (!existing.has(item.id)) merged.push(item);
    }
    state.colors = merged;
  } else {
    state.colors = data.items || [];
  }
  state.colorsTotal = data.total ?? state.colors.length;
  renderColors();
}

function updateLoadMoreButton() {
  const btn = document.getElementById("color-load-more");
  if (!btn) return;
  const hasMore = state.colors.length < state.colorsTotal;
  if (hasMore && state.colors.length > 0) {
    btn.classList.remove("hidden");
    btn.disabled = false;
    btn.textContent = `Показати ще (${state.colors.length} з ${state.colorsTotal})`;
  } else {
    btn.classList.add("hidden");
  }
}

async function loadMaterials() {
  state.materials = await api(`/catalog/materials?project_id=${state.project.id}`);
  renderMaterials();
}

async function loadMaterialColors(materialId) {
  state.materialColors = await api(`/catalog/materials/${materialId}/colors?project_id=${state.project.id}`);
  renderMaterialColors();
}

function shortText(text, max = 14) {
  if (!text) return "";
  return text.length > max ? `${text.slice(0, max)}…` : text;
}

function colorSwatchLabel(c) {
  const code = c.display_code || c.manufacturer_code;
  const codeShort = code ? shortText(code, 10) : "";
  const name = shortText(c.name, 10);
  const price = formatPricePerSqm(c.price_per_sqm);
  const main = codeShort && name ? `${codeShort} · ${name}` : codeShort || name || "—";
  return price ? `${main}\n${price}` : main;
}

function selectionLine(c) {
  if (!c) return "";
  const code = c.display_code || c.manufacturer_code;
  return code ? `${code} · ${c.name}` : c.name;
}

function updatePaintSelectionInfo() {
  const el = document.getElementById("paint-selection-info");
  if (!el) return;
  if (!state.selectedColor) {
    const n = state.brands.length;
    el.textContent = n
      ? `Оберіть колір (${FINISH_LABELS[state.finish]}, ${n} лінійок)`
      : `Немає лінійок: ${FINISH_LABELS[state.finish]}`;
    return;
  }
  const brand = getSelectedBrand();
  let text = brand ? `${brand.name}` : "";
  if (brand?.color_code_system_label && brand.color_code_system !== "manufacturer") {
    text += ` (${brand.color_code_system_label})`;
  }
  if (text) text += " · ";
  text += selectionLine(state.selectedColor);
  if (brand?.discount_percent) text += ` · акція −${brand.discount_percent}%`;
  const total = calcTotal();
  if (total != null) text += ` · ${formatUah(total)}`;
  if (state.paintEstimate?.packs?.length) {
    const packs = state.paintEstimate.packs.map((p) => `${p.count}×${p.label}`).join(", ");
    text += ` · ${packs}`;
  }
  el.textContent = text;
}

function updateDecorSelectionInfo() {
  const el = document.getElementById("decor-selection-info");
  if (!el) return;
  if (!state.selectedMaterial && !state.selectedMaterialColor) {
    el.textContent = "Оберіть матеріал і відтінок";
    return;
  }
  const parts = [];
  if (state.selectedMaterial) parts.push(state.selectedMaterial.name);
  if (state.selectedMaterialColor) parts.push(state.selectedMaterialColor.name);
  if (state.selectedMaterial?.discount_percent) parts.push(`акція −${state.selectedMaterial.discount_percent}%`);
  let text = parts.join(" · ");
  const total = calcTotal();
  if (total != null) text += ` · ${formatUah(total)}`;
  el.textContent = text;
}

function onSelectionChanged() {
  updateCostBar();
  if (state.mode === "paint") {
    scheduleEstimate();
    updatePaintSelectionInfo();
  } else {
    scheduleEstimate();
    updateDecorSelectionInfo();
  }
  scheduleSyncState();
  scheduleResultSave();
}

function resetPaintView() {
  state.selectedColor = null;
  renderColors();
  onSelectionChanged();
  window.renderer.render();
}

function resetDecorView() {
  state.selectedMaterialColor = null;
  renderMaterialColors();
  onSelectionChanged();
  window.renderer.render();
}

function createColorItem(c, isSelected, onSelect) {
  const outOfStock = c.in_stock === false;
  const item = document.createElement("div");
  item.className = "color-item" + (isSelected ? " selected" : "") + (outOfStock ? " out-of-stock" : "");
  const swatchWrap = document.createElement("div");
  swatchWrap.className = "swatch-wrap";
  const swatch = document.createElement("div");
  swatch.className = "color-swatch";
  swatch.style.background = normalizeHex(c.hex);
  swatchWrap.appendChild(swatch);
  if (outOfStock) {
    const badge = document.createElement("span");
    badge.className = "stock-badge";
    badge.textContent = "немає";
    swatchWrap.appendChild(badge);
  }
  if (c.discount_percent) {
    const discBadge = document.createElement("span");
    discBadge.className = "discount-badge";
    discBadge.textContent = `−${c.discount_percent}%`;
    swatchWrap.appendChild(discBadge);
  }
  const label = document.createElement("div");
  label.className = "color-label";
  const priceHtml = formatPriceHtml(c);
  const stockLine = outOfStock ? '<br><span class="stock-label">немає в наявності</span>' : "";
  label.innerHTML = priceHtml
    ? `${shortText(c.display_code || c.manufacturer_code || c.name, 12)}<br>${priceHtml}${stockLine}`
    : colorSwatchLabel(c).replace("\n", "<br>") + stockLine;
  label.title = `${selectionLine(c) || c.name}${c.price_per_sqm ? ` — ${formatPricePerSqm(c.price_per_sqm)}` : ""}${c.discount_percent ? ` (знижка −${c.discount_percent}%)` : ""}${outOfStock ? " (немає в наявності)" : ""}`;
  item.appendChild(swatchWrap);
  item.appendChild(label);
  item.onclick = () => onSelect(c);
  return item;
}

function renderBrands() {
  const sel = document.getElementById("brand-filter");
  const finishLabel = FINISH_LABELS[state.finish] || state.finish;
  sel.innerHTML = "";
  if (!state.brands.length) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = `Немає лінійок (${finishLabel})`;
    sel.appendChild(opt);
    sel.disabled = true;
    return;
  }
  sel.disabled = false;
  const all = document.createElement("option");
  all.value = "";
  all.textContent = `Усі лінійки (${finishLabel})`;
  sel.appendChild(all);
  state.brands.forEach((b) => {
    const opt = document.createElement("option");
    opt.value = b.id;
    opt.textContent = b.discount_percent ? `${b.name} (−${b.discount_percent}%)` : b.name;
    sel.appendChild(opt);
  });
  updateBrandDiscountHint();
}

function updateBrandDiscountHint() {
  const hint = document.getElementById("brand-discount-hint");
  const sel = document.getElementById("brand-filter");
  if (!hint || !sel) return;
  const brandId = sel.value ? parseInt(sel.value, 10) : null;
  const brand = brandId ? state.brands.find((b) => b.id === brandId) : null;
  const storeWide = state.promotions?.find((p) => p.scope === "all" || p.scope === "paint");
  if (brand?.discount_percent) {
    hint.textContent = `Акція: −${brand.discount_percent}% на ${brand.name}`;
    hint.classList.remove("hidden");
  } else if (!brandId && storeWide) {
    hint.textContent = storeWide.message;
    hint.classList.remove("hidden");
  } else {
    hint.classList.add("hidden");
    hint.textContent = "";
  }
}

function renderColors() {
  const grid = document.getElementById("color-grid");
  grid.innerHTML = "";
  if (!state.brands.length) {
    grid.innerHTML = `<div class="color-grid-empty">Для типу «${FINISH_LABELS[state.finish]}» поки немає лінійок у цьому магазині.<br>Спробуйте інший тип або запитайте консультанта.</div>`;
    updatePaintSelectionInfo();
    updateLoadMoreButton();
    return;
  }
  if (!state.colors.length) {
    grid.innerHTML = `<div class="color-grid-empty">Оберіть лінійку або змініть фільтр категорії.</div>`;
    updatePaintSelectionInfo();
    updateLoadMoreButton();
    return;
  }
  state.colors.forEach((c) => {
    const isSelected = state.selectedColor?.id === c.id;
    grid.appendChild(
      createColorItem(c, isSelected, (color) => {
        state.selectedColor = isSelected ? null : color;
        syncFinishFromBrand();
        renderColors();
        onSelectionChanged();
        window.renderer.render();
      })
    );
  });
  updatePaintSelectionInfo();
  updateLoadMoreButton();
}

function renderMaterials() {
  const list = document.getElementById("material-list");
  list.innerHTML = "";
  state.materials.forEach((m) => {
    const card = document.createElement("div");
    const outOfStock = m.in_stock === false;
    card.className = "material-card" + (state.selectedMaterial?.id === m.id ? " active" : "") + (outOfStock ? " out-of-stock" : "");
    const discBadge = m.discount_percent ? `<span class="discount-badge">−${m.discount_percent}%</span> ` : "";
    card.innerHTML = `${discBadge}<strong>${escapeHtml(m.name)}</strong>${outOfStock ? '<br><span class="stock-label">немає</span>' : ""}`;
    card.onclick = async () => {
      state.selectedMaterial = m;
      state.textureScale = m.texture_scale || 1.0;
      document.getElementById("texture-scale").value = state.textureScale;
      renderMaterials();
      await loadMaterialColors(m.id);
      if (state.materialColors.length) {
        state.selectedMaterialColor = state.materialColors[0];
        renderMaterialColors();
      } else {
        state.selectedMaterialColor = null;
        updateDecorSelectionInfo();
      }
      await window.renderer.loadTexture(m.texture_url);
      window.renderer.render();
      onSelectionChanged();
    };
    list.appendChild(card);
  });
}

function renderMaterialColors() {
  const grid = document.getElementById("material-color-grid");
  grid.innerHTML = "";
  state.materialColors.forEach((c) => {
    const isSelected = state.selectedMaterialColor?.id === c.id;
    grid.appendChild(
      createColorItem(c, isSelected, (color) => {
        state.selectedMaterialColor = isSelected ? null : color;
        renderMaterialColors();
        onSelectionChanged();
        window.renderer.render();
      })
    );
  });
  updateDecorSelectionInfo();
}

function buildSelectionSummary() {
  const parts = [];
  if (state.mode === "paint" && state.selectedColor) {
    const brand = getSelectedBrand();
    if (brand) parts.push(brand.name);
    parts.push(selectionLine(state.selectedColor));
    if (state.finish) parts.push(FINISH_LABELS[state.finish] || state.finish);
  } else if (state.selectedMaterial) {
    parts.push(state.selectedMaterial.name);
    if (state.selectedMaterialColor) parts.push(state.selectedMaterialColor.name);
  }
  return parts.length ? parts.join(" · ") : null;
}

function buildLeadSummary() {
  const parts = [];
  const area = readWallAreaSqm();
  if (area) parts.push(`Площа: ${area} м²`);
  if (state.mode === "paint" && state.selectedColor) {
    const brand = getSelectedBrand();
    if (brand) parts.push(brand.name);
    parts.push(selectionLine(state.selectedColor));
    parts.push(FINISH_LABELS[state.finish] || state.finish);
  } else if (state.selectedMaterial) {
    parts.push(state.selectedMaterial.name);
    if (state.selectedMaterialColor) parts.push(state.selectedMaterialColor.name);
  }
  const total = calcTotal();
  if (total != null) parts.push(`Разом: ${formatUah(total)}`);
  if (state.paintEstimate?.summary_detail) {
    parts.push(state.paintEstimate.summary_detail.replace(/\n/g, " | "));
  }
  return parts.join(" · ") || "Оберіть колір і вкажіть площу";
}

function openContactModal() {
  const store = state.store;
  if (!store) return;
  document.getElementById("contact-title").textContent = store.name || "Магазин";
  const phoneEl = document.getElementById("contact-phone");
  const addrEl = document.getElementById("contact-address");
  const tgEl = document.getElementById("contact-telegram");
  const callBtn = document.getElementById("contact-call");
  phoneEl.textContent = store.phone ? `📞 ${store.phone}` : "";
  phoneEl.style.display = store.phone ? "block" : "none";
  addrEl.textContent = store.address ? `📍 ${store.address}` : "";
  addrEl.style.display = store.address ? "block" : "none";
  const tg = store.telegram_username?.replace(/^@/, "");
  tgEl.textContent = tg ? `💬 @${tg}` : "";
  tgEl.style.display = tg ? "block" : "none";
  if (store.phone) {
    callBtn.href = `tel:${store.phone.replace(/\s/g, "")}`;
    callBtn.classList.remove("hidden");
  } else if (tg) {
    callBtn.href = `https://t.me/${tg}`;
    callBtn.textContent = "Написати в Telegram";
    callBtn.classList.remove("hidden");
  } else {
    callBtn.classList.add("hidden");
  }
  document.getElementById("contact-modal").classList.remove("hidden");
}

function openLeadModal() {
  document.getElementById("lead-summary").textContent = buildLeadSummary();
  const tg = window.Telegram?.WebApp;
  const user = tg?.initDataUnsafe?.user;
  if (user?.first_name) {
    document.getElementById("lead-name").value = user.first_name;
  }
  document.getElementById("lead-modal").classList.remove("hidden");
}

function isSelectionOutOfStock() {
  if (state.mode === "paint" && state.selectedColor) return state.selectedColor.in_stock === false;
  if (state.mode === "decor") {
    if (state.selectedMaterial?.in_stock === false) return true;
    if (state.selectedMaterialColor?.in_stock === false) return true;
  }
  return false;
}

async function submitLead() {
  const phone = document.getElementById("lead-phone").value.trim();
  if (!phone || phone.length < 7) {
    alert("Вкажіть номер телефону");
    return;
  }
  if (isSelectionOutOfStock()) {
    const tg = window.Telegram?.WebApp;
    const warn = "Обраний колір/матеріал зараз не в наявності. Надіслати заявку все одно?";
    let proceed = true;
    if (tg?.showConfirm) {
      proceed = await new Promise((resolve) => tg.showConfirm(warn, resolve));
    } else {
      proceed = confirm(warn);
    }
    if (!proceed) return;
  }
  const btn = document.getElementById("lead-submit");
  btn.disabled = true;
  btn.textContent = "Надсилаємо...";
  try {
    await syncProjectState();
    await refreshEstimate();
    const wallAreaSqm = readWallAreaSqm();
    const result = await api("/leads", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_id: state.project.id,
        phone,
        customer_name: document.getElementById("lead-name").value.trim() || null,
        comment: document.getElementById("lead-comment").value.trim() || null,
        wall_area_sqm: wallAreaSqm,
        estimated_total_uah: calcTotal(),
        selection_summary: buildSelectionSummary(),
        paint_plan_summary: state.paintEstimate?.summary_detail || null,
      }),
    });
    try {
      await window.renderer.persistResult();
    } catch (err) {
      console.warn("result snapshot failed", err);
    }
    document.getElementById("lead-modal").classList.add("hidden");
    const tg = window.Telegram?.WebApp;
    let msg = result.customer_ack_text
      ? `✅ ${result.customer_ack_text}`
      : "✅ Заявку надіслано! Консультант зв'яжеться з вами.";
    if (result.telegram_notified === false) {
      msg += "\n\n(Сповіщення менеджеру в Telegram не дійшло — заявка збережена в адмінці.)";
    }
    if (tg?.showAlert) tg.showAlert(msg);
    else alert(msg);
  } catch (err) {
    alert(`Помилка: ${err.message}`);
  } finally {
    btn.disabled = false;
    btn.textContent = "Надіслати";
  }
}

function setupUI() {
  document.querySelectorAll(".mode-tabs button").forEach((btn) => {
    btn.onclick = () => {
      document.querySelectorAll(".mode-tabs button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.mode = btn.dataset.mode;
      document.getElementById("paint-panel").classList.toggle("hidden", state.mode !== "paint");
      document.getElementById("decor-panel").classList.toggle("hidden", state.mode !== "decor");
      onSelectionChanged();
      window.renderer.render();
    };
  });

  document.querySelectorAll(".finish-row button").forEach((btn) => {
    btn.onclick = () => {
      if (btn.dataset.finish === state.finish) return;
      setFinish(btn.dataset.finish);
    };
  });

  document.getElementById("wall-area").oninput = (e) => {
    const v = parseFloat(e.target.value);
    state.wallAreaSqm = v > 0 ? v : null;
    onSelectionChanged();
    renderColors();
    if (state.materialColors.length) renderMaterialColors();
  };

  document.getElementById("brand-filter").onchange = (e) => {
    updateBrandDiscountHint();
    loadColors({ brand_id: e.target.value || undefined, category: document.getElementById("category-filter").value || undefined });
  };
  document.getElementById("category-filter").onchange = (e) => {
    loadColors({ brand_id: document.getElementById("brand-filter").value || undefined, category: e.target.value || undefined });
  };
  document.getElementById("search-input").oninput = (e) => {
    clearTimeout(window._searchTimer);
    window._searchTimer = setTimeout(() => {
      loadColors({
        brand_id: document.getElementById("brand-filter").value || undefined,
        category: document.getElementById("category-filter").value || undefined,
        search: e.target.value || undefined,
      });
    }, 300);
  };

  const loadMoreBtn = document.getElementById("color-load-more");
  if (loadMoreBtn) {
    loadMoreBtn.onclick = async () => {
      loadMoreBtn.disabled = true;
      loadMoreBtn.textContent = "Завантаження…";
      try {
        await loadColors(state.colorFilters, { append: true });
      } finally {
        updateLoadMoreButton();
      }
    };
  }

  document.getElementById("texture-scale").oninput = (e) => {
    state.textureScale = parseFloat(e.target.value);
    document.getElementById("scale-value").textContent = state.textureScale.toFixed(1);
    window.renderer.render();
  };

  document.getElementById("contact-store-btn").onclick = openContactModal;
  document.getElementById("contact-close").onclick = () => document.getElementById("contact-modal").classList.add("hidden");
  document.getElementById("lead-btn").onclick = openLeadModal;
  document.getElementById("lead-cancel").onclick = () => document.getElementById("lead-modal").classList.add("hidden");
  document.getElementById("lead-submit").onclick = submitLead;

  document.getElementById("download-btn").onclick = async () => {
    const btn = document.getElementById("download-btn");
    const label = btn.textContent;
    btn.disabled = true;
    btn.textContent = "⏳ Зберігаємо...";
    try {
      await window.renderer.download();
      const tg = window.Telegram?.WebApp;
      if (tg?.showConfirm) {
        tg.showConfirm("Надіслати цей варіант консультанту для розрахунку?", (ok) => {
          if (ok) openLeadModal();
        });
      }
    } catch (err) {
      const tg = window.Telegram?.WebApp;
      const msg = `Не вдалось зберегти: ${err.message}`;
      if (tg?.showAlert) tg.showAlert(msg);
      else alert(msg);
    } finally {
      btn.disabled = false;
      btn.textContent = label;
    }
  };

  document.getElementById("reset-paint-btn").onclick = resetPaintView;
  document.getElementById("reset-decor-btn").onclick = resetDecorView;
}

async function loadCategories() {
  const cats = await api("/catalog/categories");
  const sel = document.getElementById("category-filter");
  sel.innerHTML = '<option value="">Всі категорії</option>';
  cats.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c;
    opt.textContent = c;
    sel.appendChild(opt);
  });
}

async function restoreSavedState() {
  const p = state.project;
  if (!p) return;

  if (p.wall_area_sqm > 0) {
    state.wallAreaSqm = p.wall_area_sqm;
    const areaInput = document.getElementById("wall-area");
    if (areaInput) areaInput.value = String(p.wall_area_sqm);
  }

  const useDecor =
    p.editor_mode === "decor" ||
    Boolean(p.selected_material_id || p.selected_decor_color_id);

  if (useDecor) {
    state.mode = "decor";
    document.querySelectorAll(".mode-tabs button").forEach((b) => {
      b.classList.toggle("active", b.dataset.mode === "decor");
    });
    document.getElementById("paint-panel").classList.add("hidden");
    document.getElementById("decor-panel").classList.remove("hidden");

    const materialId = p.selected_material_id;
    const material = materialId
      ? state.materials.find((m) => m.id === materialId)
      : null;
    if (material) {
      state.selectedMaterial = material;
      state.textureScale = material.texture_scale || 1.0;
      document.getElementById("texture-scale").value = state.textureScale;
      await loadMaterialColors(material.id);
      if (p.selected_decor_color_id) {
        state.selectedMaterialColor =
          state.materialColors.find((c) => c.id === p.selected_decor_color_id) || null;
      }
      await window.renderer.loadTexture(material.texture_url);
      renderMaterials();
      renderMaterialColors();
    }
    return;
  }

  state.mode = "paint";
  document.querySelectorAll(".mode-tabs button").forEach((b) => {
    b.classList.toggle("active", b.dataset.mode === "paint");
  });
  document.getElementById("paint-panel").classList.remove("hidden");
  document.getElementById("decor-panel").classList.add("hidden");

  if (p.selected_finish) {
    state.finish = p.selected_finish;
    document.querySelectorAll(".finish-row button").forEach((b) => {
      b.classList.toggle("active", b.dataset.finish === p.selected_finish);
    });
    await loadBrands();
  }

  if (p.selected_color_id) {
    const data = await api(
      `/catalog/colors?project_id=${p.id}&color_id=${p.selected_color_id}`
    );
    const color = data.items?.[0];
    if (color) {
      state.selectedColor = color;
      const brandFilter = document.getElementById("brand-filter");
      if (color.brand_id) {
        brandFilter.value = String(color.brand_id);
        await loadColors({ brand_id: color.brand_id });
        state.selectedColor = state.colors.find((c) => c.id === color.id) || color;
      }
      renderColors();
    }
  }
}

function hasSavedSelection(project) {
  if (!project) return false;
  return Boolean(
    project.editor_mode === "decor" ||
      project.selected_color_id ||
      project.selected_material_id ||
      project.selected_decor_color_id ||
      (project.wall_area_sqm && project.wall_area_sqm > 0)
  );
}

async function init() {
  const loading = document.getElementById("loading");
  try {
    const projectId = getProjectId();
    if (!projectId) throw new Error("Немає project_id. Відкрийте через бота");
    await authenticate(projectId);
    window.renderer.setAuthToken(state.token);
    await loadProject();
    await trackEditorOpen();
    await loadStore();
    await window.renderer.init(state.project);
    await loadBrands();
    await loadCategories();
    await loadMaterials();
    await loadPromotions();
    setupUI();
    if (hasSavedSelection(state.project)) {
      await restoreSavedState();
    } else if (state.brands.length) {
      document.getElementById("brand-filter").value = String(state.brands[0].id);
      await loadColors({ brand_id: state.brands[0].id });
    } else {
      renderColors();
    }
    onSelectionChanged();
    window.renderer.render();
    loading.classList.add("hidden");
    const tg = window.Telegram?.WebApp;
    if (tg?.MainButton) {
      tg.MainButton.setText("📨 Запитати розрахунок");
      tg.MainButton.onClick(openLeadModal);
      tg.MainButton.show();
    }
  } catch (err) {
    loading.textContent = `Помилка: ${err.message}`;
  }
}

document.addEventListener("DOMContentLoaded", init);
