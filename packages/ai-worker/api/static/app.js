const API = "";
let currentPage = 1;
let currentCompanyId = null;
let lastMatches = [];
let lastStats = null;
let lastPageData = null;

const PRESETS = {
  gastro: {
    name: "Müller Gastronomie GmbH",
    region: "Nordrhein-Westfalen",
    sector: "Gastronomie Restaurant Hotellerie",
    employees: 42,
    company_size: "mittel",
    investment_need: "Küchenmodernisierung Energieeffizienz Digitalisierung",
  },
  hotel: {
    name: "Alpenblick Hotel & Spa",
    region: "Bayern",
    sector: "Hotellerie Tourismus",
    employees: 85,
    company_size: "mittel",
    investment_need: "Sanierung Nachhaltigkeit Barrierefreiheit",
  },
  food: {
    name: "FreshBite Food Tech UG",
    region: "Berlin",
    sector: "Lebensmittel Startup Innovation",
    employees: 12,
    company_size: "klein",
    investment_need: "Forschung Digitalisierung Markteinführung",
  },
};

async function api(path, options = {}) {
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function switchTab(name) {
  document.querySelectorAll(".tab").forEach((el) => el.classList.remove("active"));
  document.querySelectorAll(".nav-btn").forEach((el) => el.classList.remove("active"));
  document.getElementById(`tab-${name}`).classList.add("active");
  document.querySelector(`[data-tab="${name}"]`).classList.add("active");
}

document.querySelectorAll(".nav-btn").forEach((btn) => {
  btn.addEventListener("click", () => switchTab(btn.dataset.tab));
});

document.getElementById("lang-select").addEventListener("change", (e) => {
  setLang(e.target.value);
});

function onLangChange() {
  if (lastStats) updateStatsLine(lastStats);
  if (lastPageData) renderPrograms(lastPageData);
  if (lastMatches.length) renderMatches(lastMatches);
  refreshFilterLabels();
}

async function loadStats() {
  lastStats = await api("/api/stats");
  updateStatsLine(lastStats);
}

function updateStatsLine(stats) {
  const locale = uiLang === "de" ? "de-DE" : uiLang === "tr" ? "tr-TR" : "en-US";
  document.getElementById("stats-line").textContent = t("catalog.stats", {
    count: stats.program_count.toLocaleString(locale),
    regions: stats.top_regions.slice(0, 3).map((r) => r.region).join(", "),
  });
}

function refreshFilterLabels() {
  const regionSel = document.getElementById("filter-region");
  const typeSel = document.getElementById("filter-type");
  if (regionSel.options[0]) regionSel.options[0].textContent = t("catalog.allRegions");
  if (typeSel.options[0]) typeSel.options[0].textContent = t("catalog.allTypes");
}

async function loadFilters() {
  const [regions, types] = await Promise.all([api("/api/regions"), api("/api/funding-types")]);
  const regionSelects = [document.getElementById("filter-region"), document.getElementById("profile-region")];
  regionSelects.forEach((sel) => {
    while (sel.options.length > 1) sel.remove(1);
    regions.forEach((r) => {
      const opt = document.createElement("option");
      opt.value = r;
      opt.textContent = r;
      sel.appendChild(opt);
    });
  });
  while (document.getElementById("filter-type").options.length > 1) {
    document.getElementById("filter-type").remove(1);
  }
  types.forEach((typeName) => {
    const opt = document.createElement("option");
    opt.value = typeName;
    opt.textContent = typeName;
    document.getElementById("filter-type").appendChild(opt);
  });
  refreshFilterLabels();
}

function statusBadge(status) {
  if (!status || status === "unknown") return "";
  const key = `status.${status}`;
  const label = t(key);
  return `<span class="tag status-${escapeHtml(status)}">${escapeHtml(label)}</span>`;
}

function renderPrograms(data) {
  lastPageData = data;
  const list = document.getElementById("program-list");
  list.innerHTML = data.items
    .map(
      (p) => `
    <article class="program-card" data-id="${p.id}">
      <h3>${escapeHtml(p.title)}</h3>
      <div class="meta">${escapeHtml(p.region || "—")} · ${escapeHtml(p.provider_name || t("catalog.providerNa"))}</div>
      <div class="tags">${statusBadge(p.status)}${(p.funding_type || []).slice(0, 3).map((tag) => `<span class="tag accent">${escapeHtml(tag)}</span>`).join("")}</div>
    </article>`
    )
    .join("");
  list.querySelectorAll(".program-card").forEach((card) => {
    card.addEventListener("click", () => openProgram(card.dataset.id));
  });
  const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));
  document.getElementById("page-info").textContent = t("catalog.page", {
    page: data.page,
    totalPages,
    total: data.total,
  });
}

async function searchPrograms(page = 1) {
  currentPage = page;
  const list = document.getElementById("program-list");
  try {
    const params = new URLSearchParams({ page, page_size: 12 });
    const q = document.getElementById("search-q").value;
    const region = document.getElementById("filter-region").value;
    const funding_type = document.getElementById("filter-type").value;
    if (q) params.set("q", q);
    if (region) params.set("region", region);
    if (funding_type) params.set("funding_type", funding_type);
    renderPrograms(await api(`/api/programs?${params}`));
  } catch (err) {
    list.innerHTML = `<div class="card">${escapeHtml(t("catalog.loadError"))}</div>`;
    console.error(err);
  }
}

async function openProgram(id) {
  const p = await api(`/api/programs/${id}`);
  document.getElementById("modal-body").innerHTML = `
    <h2>${escapeHtml(p.title)}</h2>
    <div class="meta">${escapeHtml(p.region || "")} · ${escapeHtml(p.provider_name || "")}</div>
    <div class="tags">${statusBadge(p.status)}${(p.funding_type || []).map((tag) => `<span class="tag accent">${escapeHtml(tag)}</span>`).join("")}</div>
    <div class="body-text">${escapeHtml(p.raw_text.slice(0, 2500))}</div>
    ${p.application_url ? `<p><a href="${escapeHtml(p.application_url)}" target="_blank" rel="noopener">${escapeHtml(t("catalog.applyLink"))}</a></p>` : ""}
    <small style="color:var(--muted)">${escapeHtml(p.license_attribution)}</small>`;
  document.getElementById("program-modal").showModal();
}

document.querySelector(".close-modal").addEventListener("click", () => document.getElementById("program-modal").close());
document.getElementById("search-btn").addEventListener("click", () => searchPrograms(1));
document.getElementById("prev-page").addEventListener("click", () => { if (currentPage > 1) searchPrograms(currentPage - 1); });
document.getElementById("next-page").addEventListener("click", () => searchPrograms(currentPage + 1));

function fillForm(data) {
  Object.entries(data).forEach(([k, v]) => {
    const el = document.getElementById("company-form").elements[k];
    if (el) el.value = v ?? "";
  });
}

document.querySelectorAll(".preset").forEach((btn) => {
  btn.addEventListener("click", () => fillForm(PRESETS[btn.dataset.preset]));
});
document.getElementById("demo-btn").addEventListener("click", () => fillForm(PRESETS.gastro));
document.getElementById("demo-restaurant-btn").addEventListener("click", async () => {
  fillForm(await api("/api/seeds/demo-company"));
});

document.getElementById("company-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = Object.fromEntries(new FormData(e.target));
  if (body.employees) body.employees = Number(body.employees);
  if (!body.company_size) delete body.company_size;
  const company = await api("/api/companies", { method: "POST", body: JSON.stringify(body) });
  currentCompanyId = company.id;
  document.getElementById("run-match").disabled = false;
  document.getElementById("match-subtitle").textContent = t("profile.saved", {
    name: company.name,
    region: company.region,
  });
  switchTab("matches");
});

document.getElementById("run-match").addEventListener("click", async () => {
  if (!currentCompanyId) return;
  const loading = document.getElementById("match-loading");
  loading.classList.remove("hidden");
  try {
    lastMatches = await api(`/api/companies/${currentCompanyId}/match`, { method: "POST" });
    renderMatches(lastMatches);
  } catch (err) {
    document.getElementById("match-list").innerHTML = `<div class="card">${escapeHtml(t("matches.error", { msg: err.message }))}</div>`;
  } finally {
    loading.classList.add("hidden");
  }
});

function renderMatches(matches) {
  lastMatches = matches;
  const list = document.getElementById("match-list");
  if (!matches.length) {
    list.innerHTML = `<div class="card">${escapeHtml(t("matches.none"))}</div>`;
    return;
  }
  list.innerHTML = matches
    .map(
      (m) => `
    <article class="match-card">
      <div style="display:flex;justify-content:space-between;gap:1rem;align-items:flex-start">
        <div>
          <h3>${escapeHtml(m.program.title)} ${statusBadge(m.program.status)}</h3>
          <div class="meta">${escapeHtml(m.program.region || "")} · ${escapeHtml(m.program.provider_name || "")}</div>
          ${m.estimated_amount_range ? `<div class="meta">${escapeHtml(m.estimated_amount_range)}</div>` : ""}
        </div>
        <div class="score">${m.score}%</div>
      </div>
      <details class="why-box" open>
        <summary>${escapeHtml(t("matches.why"))}</summary>
        <div class="tags">
          ${(m.matched_terms || []).map((term) => `<span class="tag accent">${escapeHtml(term)}</span>`).join("")}
          ${Object.entries(m.score_breakdown)
            .filter(([k]) => k !== "total" && k !== "live_check")
            .map(([k, v]) => `<span class="tag">${escapeHtml(k)}: ${escapeHtml(v.detail || "")}</span>`)
            .join("")}
        </div>
        ${m.score_breakdown?.live_check && !m.score_breakdown.live_check.skipped ? `<p class="meta live-check ${m.score_breakdown.live_check.ok ? "live-ok" : "live-warn"}">${escapeHtml(t("matches.liveCheck"))} (${escapeHtml(m.score_breakdown.live_check.method || "regex")}): ${escapeHtml(m.score_breakdown.live_check.detail || "")}${m.score_breakdown.live_check.funding_period ? ` · ${escapeHtml(m.score_breakdown.live_check.funding_period)}` : ""}${m.score_breakdown.live_check.cached ? ` (${escapeHtml(t("matches.liveCached"))})` : ""}</p>` : ""}
      </details>
      <div class="match-actions">
        <button class="primary draft-btn" data-match-id="${m.id}" data-title="${escapeHtml(m.program.title)}">${escapeHtml(t("matches.draftBtn"))}</button>
        <button class="ghost detail-btn" data-id="${m.program.id}">${escapeHtml(t("matches.detailsBtn"))}</button>
      </div>
      <p class="meta">${escapeHtml(m.disclaimer)}</p>
    </article>`
    )
    .join("");

  list.querySelectorAll(".detail-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => { e.stopPropagation(); openProgram(btn.dataset.id); });
  });
  list.querySelectorAll(".draft-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      startDraftStream(btn.dataset.matchId, btn.dataset.title);
    });
  });
  document.getElementById("match-subtitle").textContent = t("matches.found", { count: matches.length });
}

async function startDraftStream(matchId, programTitle) {
  switchTab("draft");
  const panel = document.getElementById("draft-panel");
  const stream = document.getElementById("draft-stream");
  const meta = document.getElementById("draft-meta");
  panel.classList.remove("hidden");
  document.getElementById("draft-program-title").textContent = programTitle;
  document.getElementById("draft-company").textContent = t("draft.generating");
  document.getElementById("draft-disclaimer").textContent = "";
  stream.textContent = "";
  meta.textContent = "";
  document.getElementById("draft-subtitle").textContent = t("draft.running");

  try {
    const res = await fetch(`/api/matches/${matchId}/draft/stream`);
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let fullDraft = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const data = JSON.parse(line.slice(6));
        if (data.error) throw new Error(data.error);
        if (data.chunk) stream.textContent += data.chunk;
        if (data.done && data.draft) fullDraft = data.draft;
      }
    }

    if (fullDraft) {
      document.getElementById("draft-company").textContent = fullDraft.project_title || programTitle;
      document.getElementById("draft-disclaimer").textContent = fullDraft.disclaimer || "";
      meta.innerHTML = `<strong>${escapeHtml(t("draft.status"))}:</strong> ${escapeHtml(fullDraft.status)} · 
        <strong>${escapeHtml(t("draft.source"))}:</strong> ${escapeHtml(fullDraft.generated_by || "template")}`;
      if (fullDraft.missing_fields?.length) {
        meta.innerHTML += `<br><strong>${escapeHtml(t("draft.open"))}:</strong> ${fullDraft.missing_fields.map(escapeHtml).join(", ")}`;
      }
      document.getElementById("draft-subtitle").textContent = t("draft.done");
    }
  } catch (err) {
    stream.textContent = t("draft.error", { msg: err.message });
  }
}

function escapeHtml(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

(async function init() {
  applyI18n();
  document.getElementById("lang-select").value = uiLang;
  await loadStats();
  await loadFilters();
  await searchPrograms(1);
})();
