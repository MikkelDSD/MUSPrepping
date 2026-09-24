// Coffee preferences: the office coffee machine's drinks, rated per employee.
// Small, self-contained module. app.js only imports and calls these helpers.

const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const RATING_META = {
  favorit: { icon: "❤️", label: "Favorit" },
  kan_lide: { icon: "👍", label: "Kan lide" },
  kan_ikke_lide: { icon: "👎", label: "Kan ikke lide" },
};

function joinDanish(items) {
  if (!items.length) return "";
  if (items.length === 1) return items[0];
  return `${items.slice(0, -1).join(", ")} og ${items[items.length - 1]}`;
}

function coffeeRow(c, rating) {
  const buttons = Object.entries(RATING_META).map(([key, meta]) => {
    const pressed = rating === key;
    return `
      <button type="button" class="coffee-toggle${pressed ? " is-active" : ""}"
              data-coffee="${c.id}" data-rating="${key}" aria-pressed="${pressed}"
              aria-label="${esc(meta.label)} ${esc(c.label)}">${meta.icon}</button>`;
  }).join("");
  return `<li class="coffee-row"><span class="coffee-name">${c.emoji} ${esc(c.label)}</span><span class="coffee-ratings">${buttons}</span></li>`;
}

function coffeeNotes(coffee) {
  if (!coffee.likes_text && !coffee.dislikes_text) {
    return `<p class="muted small">Tilføj kaffeønsker under Rediger.</p>`;
  }
  return `
    ${coffee.likes_text ? `<p class="coffee-note"><strong>Gerne:</strong> ${esc(coffee.likes_text)}</p>` : ""}
    ${coffee.dislikes_text ? `<p class="coffee-note"><strong>Helst ikke:</strong> ${esc(coffee.dislikes_text)}</p>` : ""}`;
}

function coffeeBody(coffee, coffees) {
  return `
    <ul class="coffee-list">${coffees.map((c) => coffeeRow(c, coffee.ratings[c.id])).join("")}</ul>
    ${coffeeNotes(coffee)}`;
}

/** The "☕ Kaffe fra maskinen" profile panel. */
export function renderCoffeeSection(coffee, coffees) {
  return `
    <section class="panel" id="coffee-panel">
      <h2>☕ Kaffe fra maskinen</h2>
      <div id="coffee-body">${coffeeBody(coffee, coffees)}</div>
    </section>`;
}

/** Wires the toggle buttons; re-renders just the body on each response, so a
 * demoted old favourite updates visibly. `handleError` is app.js's own error handler. */
export function bindCoffeeSection(view, api, employeeId, coffees, handleError) {
  const panel = view.querySelector("#coffee-panel");
  if (!panel) return;
  panel.addEventListener("click", async (event) => {
    const btn = event.target.closest("[data-coffee]");
    if (!btn) return;
    const coffeeId = Number(btn.dataset.coffee);
    const rating = btn.dataset.rating;
    const active = btn.getAttribute("aria-pressed") === "true";
    try {
      const profile = await api.post(`/api/employees/${employeeId}/coffees`, {
        coffee_id: coffeeId,
        rating: active ? null : rating,
      });
      document.getElementById("coffee-body").innerHTML = coffeeBody(profile, coffees);
    } catch (err) {
      handleError(err);
    }
  });
}

/** The two free-text inputs for the employee form. */
export function coffeeFormFields(e) {
  return `
    <div class="form-row">
      <label>Kaffe – gerne
        <input name="coffee_likes" value="${esc(e.coffee_likes)}" placeholder="Fx havremælk, ekstra shot">
      </label>
      <label>Kaffe – helst ikke
        <input name="coffee_dislikes" value="${esc(e.coffee_dislikes)}" placeholder="Fx sukker, for varm">
      </label>
    </div>`;
}

/** A small dashboard-card badge for the employee's favourite drink, or "". */
export function coffeeBadge(favoriteCoffee) {
  if (!favoriteCoffee) return "";
  return `<span class="coffee-badge">${favoriteCoffee.emoji} ${esc(favoriteCoffee.label)}</span>`;
}

/** HTML for the "Før samtalen" tip and the guide's "1. Velkomst" section.
 * Pass `employeeId` from the prep page (shows a hint + profile link when nothing
 * is set yet); omit it from the guide (shows nothing in that case). */
export function coffeeTip(firstName, coffee, employeeId) {
  const name = esc(firstName);
  if (coffee.favorite) {
    const parts = [`☕ Hav en ${esc(coffee.favorite.label.toLowerCase())} klar til ${name}, når I sætter jer.`];
    if (coffee.likes_text) parts.push(`Gerne: ${esc(coffee.likes_text)}.`);
    const dislikeBits = [...coffee.dislikes.map((c) => c.label.toLowerCase()), ...(coffee.dislikes_text ? [coffee.dislikes_text] : [])];
    if (dislikeBits.length) parts.push(`Helst ikke: ${esc(dislikeBits.join(", "))}.`);
    return parts.map((p) => `<p>${p}</p>`).join("");
  }
  if (coffee.likes.length) {
    const list = esc(joinDanish(coffee.likes.map((c) => c.label.toLowerCase())));
    return `<p>☕ ${name} kan lide ${list}.</p>`;
  }
  if (employeeId) {
    return `<p>Ved du, hvad ${name} drikker? <a href="#/medarbejder/${employeeId}">Tilføj det på profilen.</a></p>`;
  }
  return "";
}
