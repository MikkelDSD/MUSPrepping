// MUSPrepping UI: a hash-routed single page app served by Flask on port 8125.
// Views fetch JSON from the API and render with template literals + innerHTML.
// Anything user-typed goes through esc() before it touches innerHTML.

import { api, ApiError, OfflineError } from "./api.js";

const view = document.getElementById("view");
const MONTHS = ["januar", "februar", "marts", "april", "maj", "juni", "juli", "august",
  "september", "oktober", "november", "december"];
const RING = 113.1; // circumference of the r=18 progress ring

// --- Helpers -----------------------------------------------------------------

const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const firstName = (name) => (name || "").trim().split(/\s+/)[0] || "";

function initials(name) {
  const parts = (name || "").trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  return (parts[0][0] + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}

const todayIso = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

function danishDate(iso) {
  if (!iso) return "";
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return `${d}. ${MONTHS[m - 1]} ${y}`;
}

function daysUntil(iso) {
  if (!iso) return "";
  const days = Math.round((Date.parse(iso.slice(0, 10)) - Date.parse(todayIso())) / 86400000);
  if (days === 0) return "i dag";
  if (days === 1) return "i morgen";
  return days > 0 ? `om ${days} dage` : `for ${-days} dage siden`;
}

const roleLine = (e) => [e.role, e.team].filter(Boolean).map(esc).join(" · ");

let toastTimer;
function toast(message, kind = "success") {
  const el = document.getElementById("toast");
  el.textContent = message;
  el.className = `toast show toast-${kind}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.className = "toast"), 3200);
}

function hearts(anchor) {
  const rect = anchor.getBoundingClientRect();
  for (let i = 0; i < 7; i++) {
    const h = document.createElement("span");
    h.className = "heart";
    h.textContent = ["💛", "🧡", "💚"][i % 3];
    h.style.left = `${rect.left + rect.width / 2 + (Math.random() - 0.5) * 80}px`;
    h.style.top = `${rect.top + window.scrollY}px`;
    h.style.animationDelay = `${i * 70}ms`;
    document.body.appendChild(h);
    setTimeout(() => h.remove(), 1800);
  }
}

function setConnection(ok) {
  const el = document.getElementById("connection");
  el.classList.toggle("is-ok", ok);
  el.classList.toggle("is-off", !ok);
  el.querySelector(".connection-label").textContent = ok ? "Forbundet" : "Ikke forbundet";
}

const go = (hash) => { location.hash = hash; };

function onSubmit(selector, handler) {
  view.querySelectorAll(selector).forEach((form) =>
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      try {
        await handler(Object.fromEntries(new FormData(form)), form);
      } catch (err) {
        handleError(err);
      }
    }));
}

function onClick(selector, handler) {
  view.querySelectorAll(selector).forEach((el) =>
    el.addEventListener("click", async (event) => {
      try {
        await handler(el, event);
      } catch (err) {
        handleError(err);
      }
    }));
}

function handleError(err) {
  if (err instanceof OfflineError) {
    setConnection(false);
    renderOffline();
  } else {
    const message = err.message || "Noget gik galt";
    toast(message[0].toUpperCase() + message.slice(1), "warning");
  }
}

function progressRing(p) {
  return `
    <div class="ring" title="Forberedelse: ${p.done} af ${p.total} trin">
      <svg viewBox="0 0 44 44" aria-hidden="true">
        <circle class="ring-bg" cx="22" cy="22" r="18"/>
        <circle class="ring-fg" cx="22" cy="22" r="18" stroke-dasharray="${(RING * p.percent / 100).toFixed(1)} ${RING}"/>
      </svg>
      <span>${p.done}/${p.total}</span>
    </div>`;
}

// --- Views -------------------------------------------------------------------

async function renderDashboard() {
  const { employees, upcoming } = await api.get("/api/overview");

  const upcomingHtml = upcoming.length ? `
    <section class="panel">
      <h2>Kommende samtaler</h2>
      <ul class="upcoming">
        ${upcoming.map((s) => `
          <li><a href="#/mus/${s.id}">
            <span class="avatar avatar-sm">${esc(initials(s.employee_name))}</span>
            <span class="upcoming-text">
              <strong>${esc(s.employee_name)}</strong>
              <small>${danishDate(s.scheduled_for)} · ${daysUntil(s.scheduled_for)}</small>
            </span>
          </a></li>`).join("")}
      </ul>
    </section>` : "";

  const cards = employees.map((e) => `
    <article class="card employee-card">
      <a class="card-link" href="#/medarbejder/${e.id}" aria-label="Åbn ${esc(e.name)}"></a>
      <div class="card-head">
        <span class="avatar">${esc(initials(e.name))}</span>
        <div>
          <h3>${esc(e.name)}</h3>
          <p class="muted">${roleLine(e)}</p>
        </div>
        ${progressRing(e.progress)}
      </div>
      ${e.strengths.length
        ? `<div class="chips">${e.strengths.slice(0, 4).map((s) => `<span class="chip chip-static">${s.emoji} ${esc(s.label)}</span>`).join("")}</div>`
        : `<p class="muted small">Ingen styrker valgt endnu – hvad er ${esc(firstName(e.name))} særligt god til?</p>`}
      <div class="card-foot">
        ${e.next_mus
          ? `<span>📅 MUS ${danishDate(e.next_mus.scheduled_for)}</span>
             <a class="btn btn-small" href="#/mus/${e.next_mus.id}">Forbered</a>`
          : `<span class="muted">Ingen samtale planlagt</span>`}
      </div>
    </article>`).join("");

  view.innerHTML = `
    <section class="hero">
      <h1>Velkommen tilbage 👋</h1>
      <p>Her er dit hold. Hver samtale er en chance for at fortælle nogen, at de gør en forskel.</p>
    </section>
    ${upcomingHtml}
    <section>
      <h2>Dit hold</h2>
      ${employees.length ? `<div class="card-grid">${cards}</div>` : `
        <div class="empty">
          <p class="empty-emoji">🌻</p>
          <h3>Ingen medarbejdere endnu</h3>
          <p>Tilføj din første medarbejder – eller kør <code>uv run seed</code> for at se nogle eksempler.</p>
          <a class="btn btn-primary" href="#/ny">+ Ny medarbejder</a>
        </div>`}
    </section>`;
}

async function renderEmployeeForm(employeeId) {
  const e = employeeId ? (await api.get(`/api/employees/${employeeId}`)).employee : {};
  const title = employeeId ? `Rediger ${esc(e.name)}` : "Ny medarbejder";

  view.innerHTML = `
    <a class="back" href="${employeeId ? `#/medarbejder/${employeeId}` : "#/"}">← Tilbage</a>
    <section class="panel narrow">
      <h1>${title}</h1>
      <form class="form" id="employee-form">
        <label>Navn
          <input name="name" required value="${esc(e.name)}" placeholder="Fx Sofie Lindberg" autofocus>
        </label>
        <div class="form-row">
          <label>Rolle <input name="role" value="${esc(e.role)}" placeholder="Fx Projektleder"></label>
          <label>Team <input name="team" value="${esc(e.team)}" placeholder="Fx Digital"></label>
        </div>
        <label>Ansat siden <input type="date" name="start_date" value="${esc(e.start_date)}"></label>
        <label>Hvad sætter du særligt pris på ved denne person?
          <textarea name="personal_note" rows="3" placeholder="Et par ord fra hjertet – kun til dig selv.">${esc(e.personal_note)}</textarea>
        </label>
        <div class="form-actions">
          <button class="btn btn-primary" type="submit">${employeeId ? "Gem ændringer" : "Tilføj medarbejder"}</button>
        </div>
      </form>
    </section>`;

  onSubmit("#employee-form", async (data) => {
    const saved = employeeId
      ? await api.put(`/api/employees/${employeeId}`, data)
      : await api.post("/api/employees", data);
    toast(employeeId ? "Ændringerne er gemt." : `${saved.name} er tilføjet. Lad os finde de gode ting frem! ✨`);
    go(`#/medarbejder/${saved.id}`);
  });
}

async function renderEmployee(employeeId) {
  const { employee: e, strengths, selected_strength_ids, highlights, sessions } =
    await api.get(`/api/employees/${employeeId}`);
  const selected = new Set(selected_strength_ids);
  const navn = esc(firstName(e.name));

  const byCategory = {};
  strengths.forEach((s) => (byCategory[s.category] ??= []).push(s));

  view.innerHTML = `
    <a class="back" href="#/">← Oversigt</a>
    <section class="profile-head panel">
      <span class="avatar avatar-lg">${esc(initials(e.name))}</span>
      <div class="profile-info">
        <h1>${esc(e.name)}</h1>
        <p class="muted">${roleLine(e)}${e.start_date ? ` · Ansat siden ${danishDate(e.start_date)}` : ""}</p>
        ${e.personal_note ? `<blockquote class="note">“${esc(e.personal_note)}”</blockquote>` : ""}
      </div>
      <div class="profile-actions">
        <a class="btn" href="#/medarbejder/${e.id}/rediger">Rediger</a>
        <button class="btn btn-ghost" id="delete-employee" type="button">Fjern</button>
      </div>
    </section>

    <div class="two-col">
      <section class="panel">
        <h2>Styrker</h2>
        <p class="muted small">Klik for at vælge, hvad ${navn} er særligt god til. Det bruges i ros-generatoren.</p>
        ${Object.entries(byCategory).map(([category, items]) => `
          <h4 class="chip-category">${esc(category)}</h4>
          <div class="chips">
            ${items.map((s) => `
              <button type="button" class="chip${selected.has(s.id) ? " is-selected" : ""}" data-strength="${s.id}"
                      aria-pressed="${selected.has(s.id)}">${s.emoji} ${esc(s.label)}</button>`).join("")}
          </div>`).join("")}
      </section>

      <section class="panel" id="hoejdepunkter">
        <h2>Højdepunkter</h2>
        <p class="muted small">Konkrete øjeblikke, hvor ${navn} gjorde en forskel. Konkret ros rammer dybest.</p>
        <form class="form form-compact" id="highlight-form">
          <input name="title" placeholder="Fx Reddede kundemødet med en vigtig kunde" required aria-label="Titel">
          <textarea name="description" rows="2" placeholder="Hvad skete der, og hvorfor betød det noget? (valgfrit)" aria-label="Beskrivelse"></textarea>
          <div class="form-row">
            <input type="date" name="happened_on" max="${todayIso()}" aria-label="Dato">
            <button class="btn btn-primary" type="submit">+ Tilføj</button>
          </div>
        </form>
        ${highlights.length ? `
          <ul class="highlight-list">
            ${highlights.map((h) => `
              <li>
                <div>
                  <strong>🌟 ${esc(h.title)}</strong>
                  ${h.description ? `<p>${esc(h.description)}</p>` : ""}
                  ${h.happened_on ? `<small class="muted">${danishDate(h.happened_on)}</small>` : ""}
                </div>
                <button class="icon-btn" type="button" data-delete-highlight="${h.id}" aria-label="Slet">✕</button>
              </li>`).join("")}
          </ul>` : `
          <p class="empty-inline">Ingen højdepunkter endnu. Tænk tilbage: Hvornår blev du sidst glad for noget, ${navn} gjorde?</p>`}
      </section>
    </div>

    <section class="panel">
      <h2>Samtaler</h2>
      <form class="form-inline" id="session-form">
        <label>Planlæg ny MUS <input type="date" name="scheduled_for" required value="${todayIso()}"></label>
        <button class="btn btn-primary" type="submit">Planlæg og forbered →</button>
      </form>
      ${sessions.length ? `
        <ul class="session-list">
          ${sessions.map((s) => `
            <li>
              <span class="status status-${s.status}">${s.status}</span>
              <span>${danishDate(s.scheduled_for)} <small class="muted">(${daysUntil(s.scheduled_for)})</small></span>
              <span class="session-actions">
                <a class="btn btn-small" href="#/mus/${s.id}">Forberedelse</a>
                <a class="btn btn-small btn-ghost" href="#/mus/${s.id}/guide">Samtaleguide</a>
                <button class="icon-btn" type="button" data-delete-session="${s.id}" aria-label="Slet samtale">✕</button>
              </span>
            </li>`).join("")}
        </ul>` : ""}
    </section>`;

  onClick("[data-strength]", async (chip) => {
    const { selected: isOn } = await api.post(`/api/employees/${e.id}/strengths`,
      { strength_id: Number(chip.dataset.strength) });
    chip.classList.toggle("is-selected", isOn);
    chip.setAttribute("aria-pressed", String(isOn));
  });

  onSubmit("#highlight-form", async (data) => {
    await api.post(`/api/employees/${e.id}/highlights`, data);
    toast("Højdepunkt gemt – godt fanget! 🌟");
    await renderEmployee(employeeId);
    document.getElementById("hoejdepunkter").scrollIntoView({ block: "start" });
  });

  onClick("[data-delete-highlight]", async (btn) => {
    if (!confirm("Slet dette højdepunkt?")) return;
    await api.del(`/api/highlights/${btn.dataset.deleteHighlight}`);
    await renderEmployee(employeeId);
  });

  onSubmit("#session-form", async (data) => {
    const session = await api.post(`/api/employees/${e.id}/sessions`, data);
    go(`#/mus/${session.id}`);
  });

  onClick("[data-delete-session]", async (btn) => {
    if (!confirm("Slet denne samtale og forberedelsen?")) return;
    await api.del(`/api/sessions/${btn.dataset.deleteSession}`);
    toast("Samtalen er slettet.", "info");
    await renderEmployee(employeeId);
  });

  onClick("#delete-employee", async () => {
    if (!confirm(`Vil du fjerne ${e.name} og alle noter om vedkommende?`)) return;
    await api.del(`/api/employees/${e.id}`);
    toast(`${e.name} er fjernet.`, "info");
    go("#/");
  });
}

async function renderPrep(sessionId) {
  const [{ session: s, employee: e, strengths, selected_strength_ids, highlights }, tones] =
    await Promise.all([api.get(`/api/sessions/${sessionId}`), api.get("/api/tones")]);
  const selected = new Set(selected_strength_ids);

  view.innerHTML = `
    <a class="back" href="#/medarbejder/${e.id}">← ${esc(e.name)}</a>
    <section class="panel prep-head">
      <span class="avatar avatar-lg">${esc(initials(e.name))}</span>
      <div class="prep-title">
        <h1>MUS med ${esc(e.name)}</h1>
        <div class="form-inline">
          <label>Dato <input type="date" data-field="scheduled_for" value="${esc(s.scheduled_for)}"></label>
          <label>Status
            <select data-field="status">
              <option value="planlagt" ${s.status === "planlagt" ? "selected" : ""}>Planlagt</option>
              <option value="afholdt" ${s.status === "afholdt" ? "selected" : ""}>Afholdt</option>
            </select>
          </label>
        </div>
      </div>
      <a class="btn" href="#/mus/${s.id}/guide">📄 Samtaleguide</a>
    </section>

    <section class="panel step">
      <h2><span class="step-no">1</span> Anerkendelse – hvad vil du fremhæve?</h2>
      <p class="muted small">Styrkerne fra profilen er valgt på forhånd. Vælg de 2–4, der betyder mest lige nu.</p>
      <div class="chips">
        ${strengths.map((st) => `
          <label class="chip chip-check">
            <input type="checkbox" name="strength" value="${st.id}" ${selected.has(st.id) ? "checked" : ""}>
            <span>${st.emoji} ${esc(st.label)}</span>
          </label>`).join("")}
      </div>
      ${highlights.length ? `
        <h4>Højdepunkter</h4>
        <div class="check-list">
          ${highlights.map((h) => `<label><input type="checkbox" name="highlight" value="${h.id}" checked> 🌟 ${esc(h.title)}</label>`).join("")}
        </div>` : `
        <p class="empty-inline">Tip: <a href="#/medarbejder/${e.id}">Tilføj et konkret højdepunkt</a> – det gør rosen meget stærkere.</p>`}
    </section>

    <section class="panel step">
      <h2><span class="step-no">2</span> Ros-generator</h2>
      <div class="tone-picker" role="radiogroup" aria-label="Tone">
        ${tones.map((t) => `
          <label class="tone"><input type="radio" name="tone" value="${t.key}" data-field="tone" ${s.tone === t.key ? "checked" : ""}><span>${esc(t.label)}</span></label>`).join("")}
      </div>
      <div class="button-row">
        <button type="button" class="btn btn-primary" id="generate">✨ Generér ros</button>
        <button type="button" class="btn" id="variant">🔄 Ny variant</button>
      </div>
      <label class="sr-only" for="praise_text">Ros</label>
      <textarea id="praise_text" data-field="praise_text" rows="12" class="praise-text"
        placeholder="Tryk på “Generér ros” – og gør teksten til din egen. Det er dine ord, der tæller.">${esc(s.praise_text)}</textarea>
      <p class="muted small">Tip: Læs teksten højt. Ret til, så det lyder som dig – og tilføj gerne én helt personlig sætning.</p>
    </section>

    <section class="panel step">
      <h2><span class="step-no">3</span> Udvikling og fremtid</h2>
      <div class="form">
        <label>Udviklingsmål for det kommende år
          <textarea data-field="development_goals" rows="4" placeholder="Fx Tage ejerskab for et kundeprojekt fra start til slut">${esc(s.development_goals)}</textarea>
        </label>
        <label>Medarbejderens ønsker (udfyld gerne under samtalen)
          <textarea data-field="employee_wishes" rows="3" placeholder="Kurser, opgaver, arbejdsform …">${esc(s.employee_wishes)}</textarea>
        </label>
        <label>Private noter til dig selv
          <textarea data-field="boss_notes" rows="3" placeholder="Ting du vil huske at spørge ind til">${esc(s.boss_notes)}</textarea>
        </label>
      </div>
    </section>

    <div class="save-bar">
      <span id="save-status" class="muted small">Alt er gemt.</span>
      <button type="button" class="btn btn-primary" id="save">💛 Gem forberedelse</button>
    </div>`;

  // Autosave: every [data-field] change is PATCHed after a short pause.
  const status = document.getElementById("save-status");
  const pending = {};
  let timer;

  const flush = async () => {
    clearTimeout(timer);
    if (!Object.keys(pending).length) return true;
    const payload = { ...pending };
    Object.keys(pending).forEach((k) => delete pending[k]);
    status.textContent = "Gemmer …";
    try {
      await api.patch(`/api/sessions/${sessionId}`, payload);
      status.textContent = "Alt er gemt ✓";
      return true;
    } catch (err) {
      Object.assign(pending, payload, { ...pending });
      status.textContent = "Ikke gemt";
      handleError(err);
      return false;
    }
  };

  const queue = (field, value, delay = 800) => {
    pending[field] = value;
    status.textContent = "Ændringer …";
    clearTimeout(timer);
    timer = setTimeout(flush, delay);
  };

  view.querySelectorAll("[data-field]").forEach((el) => {
    const evt = el.tagName === "TEXTAREA" ? "input" : "change";
    el.addEventListener(evt, () => {
      if (el.type === "radio" && !el.checked) return;
      queue(el.dataset.field, el.value, evt === "input" ? 800 : 0);
    });
  });

  const praiseBox = document.getElementById("praise_text");
  const generate = async () => {
    const checked = (name) => [...view.querySelectorAll(`input[name="${name}"]:checked`)].map((i) => Number(i.value));
    const tone = view.querySelector('input[name="tone"]:checked')?.value;
    if (praiseBox.value.trim() && praiseBox.dataset.generated !== praiseBox.value &&
        !confirm("Vil du erstatte den tekst, du har skrevet?")) return;
    const result = await api.post("/api/praise", {
      employee_id: e.id,
      strength_ids: checked("strength"),
      highlight_ids: checked("highlight"),
      tone,
      seed: Math.floor(Math.random() * 1e9),
    });
    praiseBox.value = result.text;
    praiseBox.dataset.generated = result.text;
    praiseBox.classList.remove("glow");
    void praiseBox.offsetWidth; // restart the animation
    praiseBox.classList.add("glow");
    queue("praise_text", result.text, 0);
  };

  onClick("#generate", generate);
  onClick("#variant", generate);
  onClick("#save", async (btn) => {
    pending.praise_text = praiseBox.value;
    if (await flush()) {
      hearts(btn);
      toast(`Forberedelsen til ${firstName(e.name)} er gemt 💛`);
    }
  });
}

async function renderGuide(sessionId) {
  const { session: s, employee: e, strengths, highlights, questions } = await api.get(`/api/sessions/${sessionId}/guide`);
  const navn = esc(firstName(e.name));

  view.innerHTML = `
    <div class="no-print guide-toolbar">
      <a class="back" href="#/mus/${s.id}">← Tilbage til forberedelsen</a>
      <button type="button" class="btn btn-primary" id="print">🖨️ Udskriv</button>
    </div>
    <article class="guide panel">
      <header>
        <p class="muted">Samtaleguide · ${danishDate(s.scheduled_for)}</p>
        <h1>MUS med ${esc(e.name)}</h1>
        <p class="muted">${roleLine(e)}</p>
      </header>
      <section>
        <h2>1. Velkomst</h2>
        <p>Start roligt. Fortæl, at samtalen handler om ${navn} – om det, der går godt, og om hvor ${navn} gerne vil hen.</p>
      </section>
      <section>
        <h2>2. Anerkendelse</h2>
        ${s.praise_text
          ? `<div class="guide-praise">${s.praise_text.split(/\n\n+/).map((p) => `<p>${esc(p)}</p>`).join("")}</div>`
          : `<p class="empty-inline">Der er endnu ikke skrevet ros. <a href="#/mus/${s.id}">Brug ros-generatoren</a>.</p>`}
        ${strengths.length ? `<div class="chips">${strengths.map((st) => `<span class="chip chip-static">${st.emoji} ${esc(st.label)}</span>`).join("")}</div>` : ""}
        ${highlights.length ? `<ul>${highlights.map((h) => `<li><strong>${esc(h.title)}</strong>${h.description ? ` – ${esc(h.description)}` : ""}</li>`).join("")}</ul>` : ""}
      </section>
      <section>
        <h2>3. Spørgsmål, der åbner samtalen</h2>
        <ol>${questions.map((q) => `<li>${esc(q)}</li>`).join("")}</ol>
      </section>
      <section>
        <h2>4. Udvikling</h2>
        <p><strong>Mål:</strong> ${esc(s.development_goals) || "—"}</p>
        <p><strong>${navn}s ønsker:</strong> ${esc(s.employee_wishes) || "—"}</p>
      </section>
      <section>
        <h2>5. Afslutning</h2>
        <p>Opsummer aftalerne, og slut af med et tak. Husk: Det sidste, der bliver sagt, er det, der bliver husket. 💛</p>
      </section>
    </article>`;

  onClick("#print", () => window.print());
}

function renderOffline() {
  view.innerHTML = `
    <section class="panel narrow offline">
      <p class="empty-emoji">🔌</p>
      <h1>Forbindelsen til MUSPrepping er afbrudt</h1>
      <p>Dine medarbejdere og noter ligger trygt i databasen på din computer – der er ikke gået noget tabt.</p>
      <ol>
        <li>Åbn en terminal i mappen med MUSPrepping.</li>
        <li>Kør <code>uv run start</code>.</li>
        <li>Tryk på <em>Prøv igen</em> herunder.</li>
      </ol>
      <button class="btn btn-primary" id="retry" type="button">Prøv igen</button>
    </section>`;
  document.getElementById("retry").addEventListener("click", route);
}

// --- Router --------------------------------------------------------------------

const routes = [
  [/^#?\/?$/, () => renderDashboard()],
  [/^#\/ny$/, () => renderEmployeeForm(null)],
  [/^#\/medarbejder\/(\d+)$/, (id) => renderEmployee(id)],
  [/^#\/medarbejder\/(\d+)\/rediger$/, (id) => renderEmployeeForm(id)],
  [/^#\/mus\/(\d+)$/, (id) => renderPrep(id)],
  [/^#\/mus\/(\d+)\/guide$/, (id) => renderGuide(id)],
];

async function route() {
  const hash = location.hash || "#/";
  const match = routes.map(([re, fn]) => [hash.match(re), fn]).find(([m]) => m);
  window.scrollTo(0, 0);
  try {
    if (!match) {
      view.innerHTML = `<section class="empty"><p class="empty-emoji">🧭</p><h3>Siden findes ikke</h3><a class="btn" href="#/">Til oversigten</a></section>`;
      return;
    }
    const [m, fn] = match;
    await fn(...m.slice(1));
    setConnection(true);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      view.innerHTML = `<section class="empty"><p class="empty-emoji">🍃</p><h3>${esc(err.message)}</h3><a class="btn" href="#/">Til oversigten</a></section>`;
    } else {
      handleError(err);
    }
  }
}

window.addEventListener("hashchange", route);
route();
