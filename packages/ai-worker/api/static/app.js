const API = "";
let currentPage = 1;
let currentCompanyId = null;

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

async function loadStats() {
  const stats = await api("/api/stats");
  document.getElementById("stats-line").textContent =
    `${stats.program_count.toLocaleString("de-DE")} Programme · ${stats.top_regions.slice(0, 3).map((r) => r.region).join(", ")} …`;
}

async function loadFilters() {
  const [regions, types] = await Promise.all([
    api("/api/regions"),
    api("/api/funding-types"),
  ]);
  const regionSelects = [document.getElementById("filter-region"), document.getElementById("profile-region")];
  regionSelects.forEach((sel) => {
    regions.forEach((r) => {
      const opt = document.createElement("option");
      opt.value = r;
      opt.textContent = r;
      sel.appendChild(opt);
    });
  });
  types.forEach((t) => {
    const opt = document.createElement("option");
    opt.value = t;
    opt.textContent = t;
    document.getElementById("filter-type").appendChild(opt);
  });
}

function renderPrograms(data) {
  const list = document.getElementById("program-list");
  list.innerHTML = data.items
    .map(
      (p) => `
    <article class="program-card" data-id="${p.id}">
      <h3>${escapeHtml(p.title)}</h3>
      <div class="meta">${escapeHtml(p.region || "—")} · ${escapeHtml(p.provider_name || "Anbieter n/a")}</div>
      <div class="tags">
        ${(p.funding_type || []).slice(0, 3).map((t) => `<span class="tag accent">${escapeHtml(t)}</span>`).join("")}
      </div>
    </article>`
    )
    .join("");
  list.querySelectorAll(".program-card").forEach((card) => {
    card.addEventListener("click", () => openProgram(card.dataset.id));
  });
  const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));
  document.getElementById("page-info").textContent = `Seite ${data.page} / ${totalPages} (${data.total} Treffer)`;
}

async function searchPrograms(page = 1) {
  currentPage = page;
  const q = document.getElementById("search-q").value;
  const region = document.getElementById("filter-region").value;
  const funding_type = document.getElementById("filter-type").value;
  const params = new URLSearchParams({ page, page_size: 12 });
  if (q) params.set("q", q);
  if (region) params.set("region", region);
  if (funding_type) params.set("funding_type", funding_type);
  const data = await api(`/api/programs?${params}`);
  renderPrograms(data);
}

async function openProgram(id) {
  const p = await api(`/api/programs/${id}`);
  const modal = document.getElementById("program-modal");
  document.getElementById("modal-body").innerHTML = `
    <h2>${escapeHtml(p.title)}</h2>
    <div class="meta">${escapeHtml(p.region || "")} · ${escapeHtml(p.provider_name || "")}</div>
    <div class="tags">${(p.funding_type || []).map((t) => `<span class="tag accent">${escapeHtml(t)}</span>`).join("")}</div>
    <div class="body-text">${escapeHtml(p.raw_text.slice(0, 2500))}</div>
    ${p.application_url ? `<p><a href="${escapeHtml(p.application_url)}" target="_blank" rel="noopener">Zur Antragsseite →</a></p>` : ""}
    <small style="color:var(--muted)">${escapeHtml(p.license_attribution)}</small>
  `;
  modal.showModal();
}

document.querySelector(".close-modal").addEventListener("click", () => {
  document.getElementById("program-modal").close();
});

document.getElementById("search-btn").addEventListener("click", () => searchPrograms(1));
document.getElementById("prev-page").addEventListener("click", () => {
  if (currentPage > 1) searchPrograms(currentPage - 1);
});
document.getElementById("next-page").addEventListener("click", () => searchPrograms(currentPage + 1));

function fillForm(data) {
  const form = document.getElementById("company-form");
  Object.entries(data).forEach(([k, v]) => {
    const el = form.elements[k];
    if (el) el.value = v ?? "";
  });
}

document.querySelectorAll(".preset").forEach((btn) => {
  btn.addEventListener("click", () => fillForm(PRESETS[btn.dataset.preset]));
});
document.getElementById("demo-btn").addEventListener("click", () => fillForm(PRESETS.gastro));

document.getElementById("company-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const body = Object.fromEntries(new FormData(form));
  if (body.employees) body.employees = Number(body.employees);
  if (!body.company_size) delete body.company_size;
  const company = await api("/api/companies", { method: "POST", body: JSON.stringify(body) });
  currentCompanyId = company.id;
  document.getElementById("run-match").disabled = false;
  document.getElementById("match-subtitle").textContent =
    `Profil gespeichert: ${company.name} (${company.region})`;
  switchTab("matches");
});

document.getElementById("run-match").addEventListener("click", async () => {
  if (!currentCompanyId) return;
  const matches = await api(`/api/companies/${currentCompanyId}/match`, { method: "POST" });
  renderMatches(matches);
});

function renderMatches(matches) {
  const list = document.getElementById("match-list");
  if (!matches.length) {
    list.innerHTML = `<div class="card">Keine Treffer über Schwellenwert. Profil anpassen und erneut versuchen.</div>`;
    return;
  }
  list.innerHTML = matches
    .map(
      (m) => `
    <article class="match-card" data-id="${m.program.id}">
      <div style="display:flex;justify-content:space-between;gap:1rem;align-items:flex-start">
        <div>
          <h3>${escapeHtml(m.program.title)}</h3>
          <div class="meta">${escapeHtml(m.program.region || "")} · ${escapeHtml(m.program.provider_name || "")}</div>
        </div>
        <div class="score">${m.score}%</div>
      </div>
      <div class="tags">
        ${Object.entries(m.score_breakdown)
          .filter(([k]) => k !== "total")
          .map(([k, v]) => `<span class="tag ${v.ok ? "accent" : ""}">${k}: ${escapeHtml(v.detail || "")}</span>`)
          .join("")}
      </div>
      <p class="meta" style="margin-top:0.75rem">${escapeHtml(m.disclaimer)}</p>
    </article>`
    )
    .join("");
  list.querySelectorAll(".match-card").forEach((card) => {
    card.addEventListener("click", () => openProgram(card.dataset.id));
  });
  document.getElementById("match-subtitle").textContent = `${matches.length} passende Programme gefunden`;
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

(async function init() {
  await loadStats();
  await loadFilters();
  await searchPrograms(1);
})();
