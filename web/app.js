const $ = (id) => document.getElementById(id);
const form = $("prefs-form");
const statusEl = $("status");
const resultsEl = $("results");
const summaryEl = $("summary");
const metaEl = $("meta");
const cardsEl = $("cards");
const submitBtn = $("submit");
const locationSelect = $("location");

function setStatus(text, kind = "loading") {
  statusEl.className = `status ${kind}`;
  statusEl.textContent = text;
  statusEl.classList.remove("hidden");
}

function clearStatus() { statusEl.classList.add("hidden"); }

async function loadLocalities() {
  try {
    const r = await fetch("/api/v1/localities");
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    const list = data.localities || [];
    locationSelect.innerHTML =
      `<option value="">Select a locality…</option>` +
      list.map((l) => `<option value="${escapeHtml(l)}">${escapeHtml(l)}</option>`).join("");
  } catch (e) {
    locationSelect.innerHTML = `<option value="">(failed to load)</option>`;
    setStatus(`Could not load localities: ${e.message}`, "error");
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

function buildPayload(fd) {
  const payload = {
    location: fd.get("location").trim(),
    min_rating: parseFloat(fd.get("min_rating")) || 0,
  };
  const cuisine = fd.get("cuisine").trim();
  if (cuisine) {
    payload.cuisine = cuisine.includes(",")
      ? cuisine.split(",").map((s) => s.trim()).filter(Boolean)
      : cuisine;
  }
  const budget = fd.get("budget_max_inr");
  if (budget !== "" && budget !== null) {
    const n = parseFloat(budget);
    if (!Number.isNaN(n)) payload.budget_max_inr = n;
  }
  const extras = fd.get("extras").trim();
  if (extras) payload.extras = extras;
  return payload;
}

function renderItem(item) {
  const cuisines = (item.cuisines || [])
    .map((c) => `<span class="cuisine-chip">${escapeHtml(c)}</span>`)
    .join("");
  const rating = item.rating != null ? `★ ${item.rating}` : "—";
  const cost = item.cost_display || "—";
  const tier = item.estimated_cost ? ` · ${item.estimated_cost}` : "";
  const locality = item.locality ? escapeHtml(item.locality) : "";
  return `
    <article class="card">
      <div class="card-head">
        <span class="card-rank">#${item.rank}</span>
        <span class="card-name">${escapeHtml(item.name || "")}</span>
        <span class="card-rating">${rating}</span>
      </div>
      <p class="card-meta">${locality} · ${escapeHtml(cost)}${escapeHtml(tier)}</p>
      <div class="card-cuisines">${cuisines}</div>
      <p class="card-explain">${escapeHtml(item.explanation || "")}</p>
    </article>`;
}

async function submit(ev) {
  ev.preventDefault();
  const payload = buildPayload(new FormData(form));
  if (!payload.location) {
    setStatus("Please select a locality first.", "error");
    return;
  }

  resultsEl.classList.add("hidden");
  setStatus("Asking the model… (typically 2–4 seconds)", "loading");
  submitBtn.disabled = true;

  try {
    const t0 = performance.now();
    const r = await fetch("/api/v1/recommend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const elapsed = ((performance.now() - t0) / 1000).toFixed(2);

    if (r.status === 422) {
      const body = await r.json();
      const msg = (body.detail || []).map((e) => `${e.loc.slice(1).join(".")}: ${e.msg}`).join("; ");
      setStatus(`Validation error: ${msg}`, "error");
      return;
    }
    if (!r.ok) {
      setStatus(`HTTP ${r.status}: ${await r.text()}`, "error");
      return;
    }
    const data = await r.json();

    summaryEl.textContent = data.summary || "";
    const m = data.meta || {};
    const parts = [
      `shortlist: ${m.shortlist_size ?? "?"}`,
      `model: ${m.model ?? "?"}`,
      `parse: ${m.parse_method ?? "?"}`,
      `LLM: ${m.llm_called ? "yes" : "no"}`,
      `total: ${elapsed}s`,
    ];
    if (m.filter_reason && m.filter_reason !== "OK") parts.push(`filter: ${m.filter_reason}`);
    metaEl.textContent = parts.join(" · ");

    cardsEl.innerHTML = (data.items || []).map(renderItem).join("") ||
      `<p class="card-meta">No items returned.</p>`;
    resultsEl.classList.remove("hidden");
    clearStatus();
  } catch (e) {
    setStatus(`Network error: ${e.message}`, "error");
  } finally {
    submitBtn.disabled = false;
  }
}

form.addEventListener("submit", submit);
loadLocalities();
