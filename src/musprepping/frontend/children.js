// Children: quick-to-look-up names of an employee's kids, for a warm chat opener.
// Small, self-contained ES module. render*/bind* helpers only; app.js just imports
// and calls these.

import { api } from "./api.js";

const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const CURRENT_YEAR = new Date().getFullYear();

async function guard(fn, onError) {
  try {
    await fn();
  } catch (err) {
    onError(err);
  }
}

// "A" / "A og B" / "A, B og C"
function danishList(items) {
  if (!items.length) return "";
  if (items.length === 1) return items[0];
  return `${items.slice(0, -1).join(", ")} og ${items[items.length - 1]}`;
}

function childLine(c) {
  const parts = [esc(c.name)];
  if (c.birth_year) parts.push(`født ${c.birth_year}`);
  if (c.interests) parts.push(esc(c.interests));
  return parts.join(" · ");
}

function childRow(c) {
  return `
    <li data-child="${c.id}">
      <div class="child-view">
        <span>🧸 ${childLine(c)}</span>
        <span class="child-actions">
          <button class="btn btn-small btn-ghost" type="button" data-edit-child="${c.id}">Ret</button>
          <button class="icon-btn" type="button" data-delete-child="${c.id}" aria-label="Slet barn">✕</button>
        </span>
      </div>
      <div class="child-edit" hidden>
        <input class="edit-name" value="${esc(c.name)}" placeholder="Navn" aria-label="Navn">
        <input class="edit-birth-year" type="number" min="1940" max="${CURRENT_YEAR}"
               value="${c.birth_year ?? ""}" placeholder="Født (år)" aria-label="Født år">
        <input class="edit-interests" value="${esc(c.interests)}" placeholder="Interesser" aria-label="Interesser">
        <span class="child-actions">
          <button class="btn btn-small btn-primary" type="button" data-save-child="${c.id}">Gem</button>
          <button class="btn btn-small btn-ghost" type="button" data-cancel-child="${c.id}">Annullér</button>
        </span>
      </div>
    </li>`;
}

// --- Profile panel ---------------------------------------------------------------

export function childrenPanel(children) {
  return `
    <section class="panel" id="boern">
      <h2>🧸 Børn</h2>
      ${children.length
        ? `<ul class="children-list">${children.map(childRow).join("")}</ul>`
        : `<p class="empty-inline">Ingen børn registreret.</p>`}
      <form class="form form-compact" id="child-form">
        <input name="name" placeholder="Navn" required aria-label="Navn">
        <div class="form-row">
          <input name="birth_year" type="number" min="1940" max="${CURRENT_YEAR}" placeholder="Født (år)" aria-label="Født år">
          <input name="interests" placeholder="Interesser, fx fodbold, Minecraft" aria-label="Interesser">
        </div>
        <button class="btn btn-primary" type="submit">+ Tilføj barn</button>
      </form>
    </section>`;
}

/** `onError` is app.js's own error handler (toast, or the offline screen). */
export function bindChildrenPanel(root, employeeId, onChange, onError) {
  const panel = root.querySelector("#boern");
  if (!panel) return;

  const form = panel.querySelector("#child-form");
  if (form) {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const data = Object.fromEntries(new FormData(form));
      guard(async () => {
        await api.post(`/api/employees/${employeeId}/children`, data);
        await onChange();
      }, onError);
    });
  }

  panel.querySelectorAll("[data-edit-child]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const li = btn.closest("li");
      li.querySelector(".child-view").hidden = true;
      li.querySelector(".child-edit").hidden = false;
    });
  });

  panel.querySelectorAll("[data-cancel-child]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const li = btn.closest("li");
      li.querySelector(".child-view").hidden = false;
      li.querySelector(".child-edit").hidden = true;
    });
  });

  panel.querySelectorAll("[data-save-child]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const li = btn.closest("li");
      const childId = btn.dataset.saveChild;
      const data = {
        name: li.querySelector(".edit-name").value,
        birth_year: li.querySelector(".edit-birth-year").value,
        interests: li.querySelector(".edit-interests").value,
      };
      guard(async () => {
        await api.put(`/api/children/${childId}`, data);
        await onChange();
      }, onError);
    });
  });

  panel.querySelectorAll("[data-delete-child]").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (!confirm("Slet dette barn?")) return;
      guard(async () => {
        await api.del(`/api/children/${btn.dataset.deleteChild}`);
        await onChange();
      }, onError);
    });
  });
}

// --- Dashboard ---------------------------------------------------------------

export function childrenDashboardLine(children) {
  if (!children || !children.length) return "";
  return `<p class="muted small children-line">🧸 ${children.map((c) => esc(c.name)).join(", ")}</p>`;
}

export function childrenSearchAttr(employeeName, children) {
  const names = [employeeName, ...(children || []).map((c) => c.name)];
  return esc(names.join(" ").toLowerCase());
}

export function teamSearchBox() {
  return `
    <div class="team-search">
      <input type="search" id="team-search" placeholder="Søg medarbejder eller barn …" aria-label="Søg medarbejder eller barn">
    </div>
    <p id="team-search-empty" class="empty-inline" hidden>Ingen match.</p>`;
}

export function bindTeamSearch(root) {
  const input = root.querySelector("#team-search");
  const grid = root.querySelector("#team-grid");
  const emptyMsg = root.querySelector("#team-search-empty");
  if (!input || !grid) return;
  input.addEventListener("input", () => {
    const q = input.value.trim().toLowerCase();
    let anyVisible = false;
    grid.querySelectorAll(".employee-card").forEach((card) => {
      const match = !q || (card.dataset.search || "").includes(q);
      card.style.display = match ? "" : "none";
      if (match) anyVisible = true;
    });
    if (emptyMsg) emptyMsg.hidden = anyVisible;
  });
}

// --- Tip (prep "Før samtalen" card + guide "1. Velkomst") ------------------------

export function childrenTip(firstName, children) {
  if (!children || !children.length) return "";
  const parts = children.map((c) =>
    c.interests ? `${esc(c.name)} (${esc(c.interests)})` : esc(c.name));
  return `🧸 Spørg gerne ${esc(firstName)} til ${danishList(parts)}.`;
}
