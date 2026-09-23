const $ = (id) => document.getElementById(id);

// ---- wire up controls ----
$("budget").oninput = () => ($("budgetVal").textContent = $("budget").value);
$("seatPref").oninput = () => ($("seatVal").textContent = $("seatPref").value);
$("btnSpotify").onclick = () => (location.href = "/connect/spotify");
$("btnYtm").onclick = importYtm;
$("btnGo").onclick = go;

const today = new Date();
const plus90 = new Date(Date.now() + 90 * 864e5);
$("startDate").value = today.toISOString().slice(0, 10);
$("endDate").value = plus90.toISOString().slice(0, 10);

// taste imported from connected sources, keyed by lowercase name
let importedTaste = {};

init();

async function init() {
  const params = new URLSearchParams(location.search);
  if (params.get("spotify_error")) showError("Spotify connect failed: " + params.get("spotify_error"));

  const status = await fetch("/api/status").then((r) => r.json());
  renderBadges(status);

  const taste = await fetch("/api/taste").then((r) => r.json());
  if (taste.artists?.length) {
    importedTaste = Object.fromEntries(taste.artists.map((a) => [a.name.toLowerCase(), a]));
    $("artists").value = taste.artists.map((a) => a.name).join("\n");
  }
}

function renderBadges(status) {
  const defs = [
    ["ticketmaster", "Ticketmaster API"],
    ["seatgeek", "SeatGeek API"],
    ["spotify", "Spotify"],
    ["ytmusic", "YouTube Music"],
  ];
  let html = defs
    .map(([k, label]) => `<span class="badge ${status[k] ? "on" : ""}">${label} ${status[k] ? "✓" : "–"}</span>`)
    .join("");
  if (status.demo_mode)
    html += `<span class="badge" style="color:var(--warn);border-color:var(--warn)">demo mode — synthetic events (add API keys in .env)</span>`;
  $("providerBadges").innerHTML = html;
}

async function importYtm() {
  const r = await fetch("/api/import/ytmusic", { method: "POST" });
  if (!r.ok) return showError((await r.json()).detail);
  await init();
}

function collectArtists() {
  return $("artists")
    .value.split("\n")
    .map((s) => s.trim())
    .filter(Boolean)
    .map((name) => importedTaste[name.toLowerCase()] || { name, affinity: 0.8, source: "manual" });
}

async function go() {
  hideError();
  const artists = collectArtists();
  if (!artists.length) return showError("Add at least one artist.");

  $("btnGo").disabled = true;
  $("btnGo").textContent = "Scouting…";
  try {
    const r = await fetch("/api/recommend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        artists,
        city: $("city").value.trim(),
        start_date: $("startDate").value,
        end_date: $("endDate").value,
        budget: +$("budget").value,
        seat_pref: +$("seatPref").value,
        weekend_pref: $("weekendPref").checked,
      }),
    });
    if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
    render(await r.json());
  } catch (e) {
    showError(e.message);
  } finally {
    $("btnGo").disabled = false;
    $("btnGo").textContent = "Find my concerts";
  }
}

function render(data) {
  const box = $("results");
  if (!data.recommendations.length) {
    box.innerHTML = `<p class="muted">No concerts found (considered ${data.considered_events} events). Try a wider date range, another city, or more artists.</p>`;
  } else {
    box.innerHTML = data.recommendations.map(card).join("");
  }
  renderTrace(data.trace);
}

function card(rec) {
  const ev = rec.event;
  const s = rec.score;
  const date = new Date(ev.date + "T12:00:00");
  const when = date.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric", year: "numeric" });
  const price =
    ev.min_price != null
      ? `$${Math.round(ev.min_price)}<small> from</small>`
      : `<small>price TBA</small>`;

  const seg = (w, cls) => `<span class="${cls}" style="width:${(w * 100).toFixed(1)}%"></span>`;
  const bar =
    seg(0.4 * s.affinity, "s-aff") + seg(0.3 * s.price_value, "s-price") +
    seg(0.15 * s.date_fit, "s-date") + seg(0.15 * s.seat_value, "s-seat");

  const tags = [];
  if (rec.cheapest_of_run && rec.run_dates.length > 1) tags.push(`<span class="tag best">cheapest night of ${rec.run_dates.length}</span>`);
  if (ev.min_price != null && ev.min_price > +$("budget").value) tags.push(`<span class="tag">over budget</span>`);

  const alts = (ev.also_on || [])
    .map((a) => `<a class="buy alt" href="${a.url}" target="_blank" rel="noopener">also on ${a.provider}${a.min_price ? ` · $${Math.round(a.min_price)}` : ""}</a>`)
    .join("");

  return `<div class="card">
    <div class="top">
      <div>
        <h3>${esc(ev.artist)} <span class="muted">· ${esc(ev.title !== ev.artist ? ev.title : "")}</span></h3>
        <div class="when">${when}${ev.time ? " · " + ev.time : ""} — ${esc(ev.venue)}, ${esc(ev.city)} ${tags.join(" ")}</div>
      </div>
      <div class="price">${price}</div>
    </div>
    <div class="scorebar">${bar}</div>
    <div class="legend">
      <span><span class="dot s-aff"></span>taste ${pct(s.affinity)}</span>
      <span><span class="dot s-price"></span>price ${pct(s.price_value)}</span>
      <span><span class="dot s-date"></span>date ${pct(s.date_fit)}</span>
      <span><span class="dot s-seat"></span>seats ${pct(s.seat_value)}</span>
      <span>· total ${(s.total * 100).toFixed(0)}</span>
    </div>
    <ul class="reasons">${rec.reasons.map((r) => `<li>${esc(r)}</li>`).join("")}</ul>
    <div class="cardfoot">
      <a class="buy" href="${ev.url}" target="_blank" rel="noopener">Buy on ${ev.provider} →</a>
      ${alts}
      ${rec.picked_tier ? `<span class="muted" style="font-size:12px">suggested: ${esc(rec.picked_tier.name)} · $${Math.round(rec.picked_tier.price)}</span>` : ""}
    </div>
  </div>`;
}

function renderTrace(trace) {
  $("traceBox").classList.remove("hidden");
  $("trace").innerHTML = trace
    .map(
      (t) => `<div class="step">
        <div class="stage">${esc(t.stage)}</div>
        <div>${esc(t.summary)}</div>
        ${t.detail.length ? `<div class="detail">${t.detail.map(esc).join("\n")}</div>` : ""}
      </div>`
    )
    .join("");
}

const pct = (x) => `${Math.round(x * 100)}`;
const esc = (s) =>
  String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function showError(msg) {
  $("error").textContent = msg;
  $("error").classList.remove("hidden");
}
function hideError() {
  $("error").classList.add("hidden");
}
