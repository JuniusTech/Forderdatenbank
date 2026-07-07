const API = "";
let currentPage = 1;
let currentCompanyId = null;
let lastMatches = [];

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
  const [regions, types] = await Promise.all([api("/api/regions"), api("/api/funding-types")]);
  [document.getElementById("filter-region"), document.getElementById("profile-region")].forEach((sel) => {
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
      <div class="tags">${(p.funding_type || []).slice(0, 3).map((t) => `<span class="tag accent">${escapeHtml(t)}</span>`).join("")}</div>
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
  const params = new URLSearchParams({ page, page_size: 12 });
  const q = document.getElementById("search-q").value;
  const region = document.getElementById("filter-region").value;
  const funding_type = document.getElementById("filter-type").value;
  if (q) params.set("q", q);
  if (region) params.set("region", region);
  if (funding_type) params.set("funding_type", funding_type);
  renderPrograms(await api(`/api/programs?${params}`));
}

async function openProgram(id) {
  const p = await api(`/api/programs/${id}`);
  document.getElementById("modal-body").innerHTML = `
    <h2>${escapeHtml(p.title)}</h2>
    <div class="meta">${escapeHtml(p.region || "")} · ${escapeHtml(p.provider_name || "")}</div>
    <div class="tags">${(p.funding_type || []).map((t) => `<span class="tag accent">${escapeHtml(t)}</span>`).join("")}</div>
    <div class="body-text">${escapeHtml(p.raw_text.slice(0, 2500))}</div>
    ${p.application_url ? `<p><a href="${escapeHtml(p.application_url)}" target="_blank" rel="noopener">Zur Antragsseite →</a></p>` : ""}
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
  document.getElementById("match-subtitle").textContent = `Profil gespeichert: ${company.name} (${company.region})`;
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
    document.getElementById("match-list").innerHTML = `<div class="card">Fehler: ${escapeHtml(err.message)}</div>`;
  } finally {
    loading.classList.add("hidden");
  }
});

function renderMatches(matches) {
  const list = document.getElementById("match-list");
  if (!matches.length) {
    list.innerHTML = `<div class="card">Keine Treffer. Profil anpassen oder andere Region wählen.</div>`;
    return;
  }
  list.innerHTML = matches
    .map(
      (m) => `
    <article class="match-card">
      <div style="display:flex;justify-content:space-between;gap:1rem;align-items:flex-start">
        <div>
          <h3>${escapeHtml(m.program.title)}</h3>
          <div class="meta">${escapeHtml(m.program.region || "")} · ${escapeHtml(m.program.provider_name || "")}</div>
          ${m.estimated_amount_range ? `<div class="meta">${escapeHtml(m.estimated_amount_range)}</div>` : ""}
        </div>
        <div class="score">${m.score}%</div>
      </div>
      <details class="why-box" open>
        <summary>Warum passend?</summary>
        <div class="tags">
          ${(m.matched_terms || []).map((t) => `<span class="tag accent">${escapeHtml(t)}</span>`).join("")}
          ${Object.entries(m.score_breakdown)
            .filter(([k]) => !["total"].includes(k))
            .map(([k, v]) => `<span class="tag">${escapeHtml(k)}: ${escapeHtml(v.detail || "")}</span>`)
            .join("")}
        </div>
      </details>
      <div class="match-actions">
        <button class="primary draft-btn" data-match-id="${m.id}" data-title="${escapeHtml(m.program.title)}">Entwurf erstellen</button>
        <button class="ghost detail-btn" data-id="${m.program.id}">Details</button>
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
  document.getElementById("match-subtitle").textContent = `${matches.length} passende Programme (Beraterprüfung erforderlich)`;
}

async function startDraftStream(matchId, programTitle) {
  switchTab("draft");
  const panel = document.getElementById("draft-panel");
  const stream = document.getElementById("draft-stream");
  const meta = document.getElementById("draft-meta");
  panel.classList.remove("hidden");
  document.getElementById("draft-program-title").textContent = programTitle;
  document.getElementById("draft-company").textContent = "Entwurf wird generiert…";
  document.getElementById("draft-disclaimer").textContent = "";
  stream.textContent = "";
  meta.textContent = "";
  document.getElementById("draft-subtitle").textContent = "KI-/Regelbasiertes Entwurfsmodul läuft…";

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
      meta.innerHTML = `<strong>Status:</strong> ${escapeHtml(fullDraft.status)} · 
        <strong>Quelle:</strong> ${escapeHtml(fullDraft.generated_by || "template")}`;
      if (fullDraft.missing_fields?.length) {
        meta.innerHTML += `<br><strong>Offen:</strong> ${fullDraft.missing_fields.map(escapeHtml).join(", ")}`;
      }
      document.getElementById("draft-subtitle").textContent = "ENTWURF — nicht zur Einreichung freigegeben";
    }
  } catch (err) {
    stream.textContent = `Fehler beim Entwurf: ${err.message}`;
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
  await loadStats();
  await loadFilters();
  await searchPrograms(1);
})();
