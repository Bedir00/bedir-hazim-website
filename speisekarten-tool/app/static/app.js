"use strict";

const state = { clients: [], clientId: null, menus: [], pollTimer: null, previewMode: "print" };
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

async function api(path, options = {}) {
  const res = await fetch(path, options);
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail)) message = body.detail.map((d) => `${(d.loc || []).slice(1).join(".")}: ${d.msg}`).join("\n");
    } catch (_) { /* kein JSON */ }
    throw new Error(message);
  }
  return res.status === 204 ? null : res.json();
}
const jsonBody = (method, data) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });

const STATUS_LABEL = { done: "Fertig", queued: "Wartet", processing: "In Arbeit", error: "Fehler" };
const CHECK_LABEL = { pass: "✓ erfüllt", warn: "! Abweichung", fail: "✗ Verstoß" };
const scoreClass = (s) => (s >= 80 ? "good" : s >= 55 ? "mid" : "bad");
const scoreColor = (s) => `var(--${s >= 80 ? "pass" : s >= 55 ? "warn" : "fail"})`;

// ---------------------------------------------------------------- Status

async function loadStatus() {
  const status = await api("/api/status");
  const banner = $("#banner");
  if (!status.credentials_found) {
    banner.hidden = false;
    banner.textContent =
      "Hinweis: Keine ANTHROPIC_API_KEY-Umgebungsvariable gefunden. Ohne Zugang schlägt die KI-Prüfung fehl (ein über `ant auth login` gespeichertes Profil funktioniert ebenfalls).";
  }
  $("#queue-info").textContent = status.queued ? `${status.queued} in Warteschlange` : "";
}

// ---------------------------------------------------------------- Kunden

async function loadClients() {
  state.clients = await api("/api/clients");
  const list = $("#client-list");
  list.innerHTML = state.clients
    .map((c) => {
      const col = c.ci.colors;
      const avg = c.avg_score != null ? `<span class="score ${scoreClass(c.avg_score)}">${c.avg_score}</span>` : "";
      return `<li data-id="${c.id}" class="${c.id === state.clientId ? "active" : ""}">
        <span><span class="swatches"><i style="background:${col.primary}"></i><i style="background:${col.secondary}"></i><i style="background:${col.accent}"></i></span>
        &nbsp;${esc(c.name)}</span>
        <span class="muted">${c.menu_count || 0} ${avg}</span></li>`;
    })
    .join("");
  $$("li", list).forEach((li) => li.addEventListener("click", () => selectClient(li.dataset.id)));
  $("#empty-state").hidden = state.clients.length > 0 && !!state.clientId;
  if (!state.clientId && state.clients.length) selectClient(state.clients[0].id);
  if (!state.clients.length) {
    $("#empty-state").hidden = false;
    $("#client-view").hidden = true;
  }
}

function currentClient() {
  return state.clients.find((c) => c.id === state.clientId);
}

async function selectClient(id) {
  state.clientId = id;
  $("#empty-state").hidden = true;
  $("#client-view").hidden = false;
  $$("#client-list li").forEach((li) => li.classList.toggle("active", li.dataset.id === id));
  const client = currentClient();
  $("#client-title").textContent = client.name;
  $("#link-client-csv").href = `/api/export/report.csv?client_id=${id}`;
  $("#link-client-zip").href = `/api/export/redesigns.zip?client_id=${id}`;
  renderCiForm(client);
  await loadMenus();
}

async function createClient(name) {
  const client = await api("/api/clients", jsonBody("POST", { ci: { restaurant_name: name } }));
  state.clientId = client.id;
  await loadClients();
  await selectClient(client.id);
  switchTab("ci");
}

// ---------------------------------------------------------------- CI-Formular

const COLOR_FIELDS = [
  ["primary", "Primär"],
  ["secondary", "Sekundär"],
  ["accent", "Akzent"],
  ["background", "Hintergrund"],
  ["text", "Text"],
];

function renderCiForm(client) {
  const ci = client.ci;
  const form = $("#ci-form");
  const opt = (values, current) => values.map((v) => `<option ${v === current ? "selected" : ""}>${esc(v)}</option>`).join("");
  form.innerHTML = `
    <fieldset>
      <legend>Grunddaten</legend>
      <label>Restaurantname <input name="restaurant_name" value="${esc(ci.restaurant_name)}" required></label>
      <label>Claim / Untertitel <input name="tagline" value="${esc(ci.tagline)}"></label>
      <div class="logo-box">
        ${client.logo_path ? `<img src="/api/clients/${client.id}/logo?t=${Date.now()}" alt="Logo">` : '<span class="muted">Kein Logo</span>'}
        <label class="btn ghost small">Logo hochladen<input type="file" id="logo-input" accept=".png,.jpg,.jpeg,.svg,.webp" hidden></label>
        ${client.logo_path ? '<button type="button" class="btn ghost small danger" id="btn-del-logo">Entfernen</button>' : ""}
      </div>
    </fieldset>
    <fieldset>
      <legend>Farben</legend>
      ${COLOR_FIELDS.map(([key, label]) => `
        <div class="color-row"><span>${label}</span>
          <input type="color" data-color="${key}" value="${ci.colors[key]}">
          <input data-color-text="${key}" value="${ci.colors[key]}" pattern="#[0-9A-Fa-f]{6}">
        </div>`).join("")}
      <label>Weitere erlaubte Farben (kommagetrennt) <input name="extra_colors" value="${esc(ci.colors.extra.join(", "))}" placeholder="#AABBCC, #112233"></label>
      <div class="two">
        <label>Farbtoleranz (ΔE) <input type="number" name="color_tolerance" min="1" max="50" step="1" value="${ci.color_tolerance}"></label>
        <label style="align-content:end"><span><input type="checkbox" name="allow_neutrals" ${ci.allow_neutrals ? "checked" : ""}> Weiß/Grau/Schwarz erlaubt</span></label>
      </div>
    </fieldset>
    <fieldset>
      <legend>Typografie & Layout</legend>
      <div class="two">
        <label>Überschriften-Schrift <input name="heading_font" value="${esc(ci.heading_font)}"></label>
        <label>Text-Schrift <input name="body_font" value="${esc(ci.body_font)}"></label>
      </div>
      <label>Weitere erlaubte Schriften (kommagetrennt) <input name="extra_fonts" value="${esc(ci.extra_fonts.join(", "))}"></label>
      <div class="two">
        <label>Layout-Stil <select name="layout_style">${opt(["klassisch", "modern", "minimal"], ci.layout_style)}</select></label>
        <label>Format <select name="page_format">${opt(["A4", "A3", "A5", "Letter"], ci.page_format)}</select></label>
      </div>
      <label>Preisformat <select name="price_format">${opt(["12,50 €", "€ 12,50", "12,50", "12.50 €", "$12.50"], ci.price_format)}</select></label>
    </fieldset>
    <fieldset>
      <legend>Regeln & Tonalität</legend>
      <label>Tonalität <textarea name="tone_of_voice" rows="2" placeholder="z. B. herzlich, bodenständig, du-Ansprache">${esc(ci.tone_of_voice)}</textarea></label>
      <label>CI-Regeln (eine pro Zeile – jede wird einzeln geprüft)
        <textarea name="rules" rows="5" placeholder="Logo oben zentriert mit Schutzzone&#10;Allergenkennzeichnung bei allen Gerichten&#10;Keine Versalien in Gerichtsnamen">${esc(ci.rules.join("\n"))}</textarea></label>
      <label>Fußnote im Redesign <input name="footer_note" value="${esc(ci.footer_note)}" placeholder="z. B. Alle Preise inkl. MwSt."></label>
    </fieldset>
    <div class="row between">
      <button type="button" class="btn ghost small danger" id="btn-del-client">Kunde löschen</button>
      <div class="row">
        <button type="button" class="btn ghost" id="btn-redesign-all" title="Alle fertigen Karten mit der aktuellen CI neu setzen – ohne neue KI-Kosten">Redesigns aktualisieren</button>
        <button class="btn" type="submit">Speichern</button>
      </div>
    </div>
    <div id="ci-msg" class="muted"></div>`;

  $$("[data-color]", form).forEach((input) =>
    input.addEventListener("input", () => { $(`[data-color-text="${input.dataset.color}"]`, form).value = input.value.toUpperCase(); }));
  $$("[data-color-text]", form).forEach((input) =>
    input.addEventListener("input", () => {
      if (/^#[0-9a-f]{6}$/i.test(input.value)) $(`[data-color="${input.dataset.colorText}"]`, form).value = input.value;
    }));
  $("#logo-input", form).addEventListener("change", uploadLogo);
  $("#btn-del-logo", form)?.addEventListener("click", async () => {
    await api(`/api/clients/${client.id}/logo`, { method: "DELETE" });
    await refreshClient();
  });
  $("#btn-del-client", form).addEventListener("click", deleteClient);
  $("#btn-redesign-all", form).addEventListener("click", redesignAll);
  refreshPreview();
}

function readCiForm() {
  const form = $("#ci-form");
  const val = (name) => form.elements[name].value.trim();
  const list = (name) => val(name).split(",").map((s) => s.trim()).filter(Boolean);
  const colors = Object.fromEntries(COLOR_FIELDS.map(([key]) => [key, $(`[data-color-text="${key}"]`, form).value.trim().toUpperCase()]));
  colors.extra = list("extra_colors");
  return {
    restaurant_name: val("restaurant_name"),
    tagline: val("tagline"),
    colors,
    color_tolerance: Number(val("color_tolerance")),
    allow_neutrals: form.elements.allow_neutrals.checked,
    heading_font: val("heading_font"),
    body_font: val("body_font"),
    extra_fonts: list("extra_fonts"),
    layout_style: val("layout_style"),
    page_format: val("page_format"),
    price_format: val("price_format"),
    tone_of_voice: val("tone_of_voice"),
    rules: val("rules").split("\n").map((s) => s.trim()).filter(Boolean),
    footer_note: val("footer_note"),
  };
}

async function saveCi(event) {
  event.preventDefault();
  const msg = $("#ci-msg");
  try {
    await api(`/api/clients/${state.clientId}`, jsonBody("PUT", { ci: readCiForm() }));
    msg.textContent = "Gespeichert. Neue Prüfungen nutzen ab jetzt diese CI.";
    await refreshClient();
  } catch (err) {
    msg.textContent = `Fehler: ${err.message}`;
  }
}

async function refreshClient() {
  await loadClients();
  const client = currentClient();
  $("#client-title").textContent = client.name;
  renderCiForm(client);
}

async function uploadLogo(event) {
  const file = event.target.files[0];
  if (!file) return;
  const data = new FormData();
  data.append("file", file);
  try {
    await api(`/api/clients/${state.clientId}/logo`, { method: "POST", body: data });
    await refreshClient();
  } catch (err) {
    alert(err.message);
  }
}

async function deleteClient() {
  const client = currentClient();
  if (!confirm(`„${client.name}“ inkl. aller Karten und Redesigns löschen?`)) return;
  await api(`/api/clients/${client.id}`, { method: "DELETE" });
  state.clientId = null;
  await loadClients();
}

async function redesignAll() {
  const button = $("#btn-redesign-all");
  button.disabled = true;
  try {
    await api(`/api/clients/${state.clientId}`, jsonBody("PUT", { ci: readCiForm() }));
    const result = await api(`/api/clients/${state.clientId}/redesign`, { method: "POST" });
    $("#ci-msg").textContent = `${result.updated} Redesign(s) mit der aktuellen CI neu gesetzt.`;
  } catch (err) {
    $("#ci-msg").textContent = `Fehler: ${err.message}`;
  } finally {
    button.disabled = false;
  }
}

function refreshPreview() {
  $("#ci-preview").src = `/api/clients/${state.clientId}/preview?mode=${state.previewMode}&t=${Date.now()}`;
}

// ---------------------------------------------------------------- Speisekarten

async function loadMenus() {
  if (!state.clientId) return;
  state.menus = await api(`/api/menus?client_id=${state.clientId}`);
  renderMenus();
  const busy = state.menus.some((m) => m.status === "queued" || m.status === "processing");
  clearTimeout(state.pollTimer);
  if (busy) state.pollTimer = setTimeout(() => { loadMenus(); loadStatus(); }, 2500);
  else loadClients();
}

function renderMenus() {
  const status = $("#filter-status").value;
  const sort = $("#sort").value;
  let menus = state.menus.filter((m) => !status || m.status === status);
  if (sort !== "new") {
    const dir = sort === "score-asc" ? 1 : -1;
    menus = [...menus].sort((a, b) => ((a.score ?? 101) - (b.score ?? 101)) * dir);
  }
  const done = state.menus.filter((m) => m.status === "done");
  const avg = done.length ? Math.round(done.reduce((s, m) => s + (m.score || 0), 0) / done.length) : null;
  $("#client-stats").textContent =
    `${state.menus.length} Karten · ${done.length} fertig` + (avg != null ? ` · Ø CI-Score ${avg}` : "");

  $("#menu-rows").innerHTML = menus.length
    ? menus.map((m) => `
      <tr data-id="${m.id}">
        <td class="source" title="${esc(m.source)}"><span class="kind">${m.source_type}</span>${esc(m.source)}</td>
        <td><span class="pill ${m.status}">${STATUS_LABEL[m.status]}${m.stage && m.status !== "done" ? ` · ${esc(m.stage)}` : ""}</span>
            ${m.error ? `<div class="muted" style="font-size:12px">${esc(m.error)}</div>` : ""}</td>
        <td>${m.score != null ? `<span class="score ${scoreClass(m.score)}">${m.score}</span><span class="bar"><i style="width:${m.score}%;background:${scoreColor(m.score)}"></i></span>` : "–"}</td>
        <td>${m.fails != null ? `<span style="color:var(--fail);font-weight:700">${m.fails}</span> <span class="muted">/ ${m.warns} Warnungen</span>` : ""}</td>
        <td class="row end">
          ${m.status === "done" ? `<a class="btn ghost small" href="/api/menus/${m.id}/files/redesign.pdf?download=true" onclick="event.stopPropagation()">PDF</a>` : ""}
          <button class="btn ghost small" data-action="reprocess" data-id="${m.id}">Neu prüfen</button>
          <button class="btn ghost small danger" data-action="delete" data-id="${m.id}">✕</button>
        </td>
      </tr>`).join("")
    : `<tr><td colspan="5" class="muted">Noch keine Karten – oben Dateien oder URLs hinzufügen.</td></tr>`;

  $$("#menu-rows tr[data-id]").forEach((tr) => tr.addEventListener("click", () => openMenu(tr.dataset.id)));
  $$("#menu-rows [data-action]").forEach((btn) =>
    btn.addEventListener("click", async (event) => {
      event.stopPropagation();
      const id = btn.dataset.id;
      if (btn.dataset.action === "delete") {
        if (!confirm("Karte und Ergebnisse löschen?")) return;
        await api(`/api/menus/${id}`, { method: "DELETE" });
      } else {
        await api(`/api/menus/${id}/reprocess`, { method: "POST" });
      }
      loadMenus();
    }));
}

async function uploadMenus(event) {
  event.preventDefault();
  const files = $("#file-input").files;
  const urls = $("#url-input").value;
  if (!files.length && !urls.trim()) return;
  const data = new FormData();
  for (const file of files) data.append("files", file);
  data.append("urls", urls);
  const button = $("#btn-upload");
  button.disabled = true;
  button.textContent = "Lade hoch …";
  try {
    const result = await api(`/api/clients/${state.clientId}/menus`, { method: "POST", body: data });
    if (result.rejected.length) alert("Nicht übernommen:\n" + result.rejected.map((r) => `${r.source}: ${r.reason}`).join("\n"));
    $("#file-input").value = "";
    $("#url-input").value = "";
    $("#file-count").textContent = "";
    await loadMenus();
  } catch (err) {
    alert(err.message);
  } finally {
    button.disabled = false;
    button.textContent = "Prüfen starten";
  }
}

// ---------------------------------------------------------------- Detailansicht

async function openMenu(id) {
  const menu = await api(`/api/menus/${id}`);
  const dialog = $("#dlg-menu");
  $("#menu-title").textContent = menu.source;
  const box = $("#menu-detail");
  if (!menu.report) {
    box.innerHTML = `<p class="muted">${menu.status === "error" ? esc(menu.error) : "Noch in Bearbeitung …"}</p>`;
    dialog.showModal();
    return;
  }
  const r = menu.report;
  const order = { fail: 0, warn: 1, pass: 2 };
  const checks = [...r.checks].sort((a, b) => order[a.status] - order[b.status]);
  const pages = r.pages.map((p) => `<img src="/api/menus/${id}/files/${p}" alt="${p}" loading="lazy">`).join("");
  const usage = r.usage ? `${r.model} · ${r.usage.input_tokens + r.usage.cache_read_input_tokens + r.usage.cache_creation_input_tokens} Input- / ${r.usage.output_tokens} Output-Tokens` : "";

  box.innerHTML = `
    <div class="summary-box card">
      <div class="big-score score ${scoreClass(r.score)}">${r.score}</div>
      <div><strong>CI-Score</strong><p style="margin:4px 0 0">${esc(r.summary)}</p><div class="muted" style="font-size:12px">${esc(usage)}</div></div>
    </div>
    ${menu.redesign_notes.length ? `<div class="notes">${menu.redesign_notes.map(esc).join("<br>")}</div>` : ""}
    <div class="row">
      <a class="btn" href="/api/menus/${id}/files/redesign.pdf?download=true">Redesign als PDF</a>
      <a class="btn ghost" href="/api/menus/${id}/files/redesign-web.html" target="_blank">Web-Karte öffnen</a>
      <a class="btn ghost" href="/api/menus/${id}/files/redesign-web.html?download=true">Web-Karte (HTML)</a>
      <a class="btn ghost" href="/api/menus/${id}/original" target="_blank">Original</a>
      <button class="btn ghost" id="btn-rerender">Redesign neu setzen</button>
    </div>
    <div class="detail-grid">
      <div>
        <h3 style="margin-bottom:8px">Prüfpunkte (${checks.filter((c) => c.status === "fail").length} Verstöße, ${checks.filter((c) => c.status === "warn").length} Warnungen)</h3>
        <div class="checks">
          ${checks.map((c) => `
            <div class="check ${c.status}">
              <div class="cat">${esc(c.category)} · ${c.source === "automatisch" ? "gemessen" : "KI-Bewertung"}</div>
              <div class="head"><span>${esc(c.criterion)}</span><span>${CHECK_LABEL[c.status]}</span></div>
              <p>${esc(c.finding)}</p>
              ${c.status !== "pass" ? `<p class="rec">→ ${esc(c.recommendation)}</p>` : ""}
            </div>`).join("")}
        </div>
      </div>
      <div class="compare">
        <figure><figcaption>Vorher</figcaption><div class="pages">${pages}</div></figure>
        <figure><figcaption>Nachher (Redesign)</figcaption><iframe src="/api/menus/${id}/files/redesign-druck.html?t=${Date.now()}" title="Redesign"></iframe></figure>
      </div>
    </div>
    <details>
      <summary>Gemessene Farben</summary>
      <div class="palette" style="margin-top:8px">
        ${r.dominant_colors.map((d) => `<span class="chip ${d.in_ci ? "" : "off"}" title="ΔE ${d.delta_e}"><i style="background:${d.hex}"></i>${d.hex} · ${Math.round(d.share * 100)} %${d.in_ci ? "" : " ✗"}</span>`).join("")}
      </div>
      <p class="muted">Erkannte Schriften: ${esc(r.observed_fonts.join(", ") || "–")}</p>
    </details>
    <details>
      <summary>Erfassten Inhalt korrigieren</summary>
      <p class="muted">Gerichte, Preise oder Rubriken anpassen (JSON) – das Redesign wird danach neu gesetzt, ohne neue KI-Prüfung.</p>
      <textarea id="content-json" rows="16" style="font-family:ui-monospace,monospace;font-size:12px">${esc(JSON.stringify(r.menu, null, 2))}</textarea>
      <div class="row end" style="margin-top:8px"><span id="content-msg" class="muted"></span><button class="btn" id="btn-save-content">Speichern & neu setzen</button></div>
    </details>`;

  $("#btn-rerender").addEventListener("click", async () => {
    await api(`/api/menus/${id}/redesign`, { method: "POST" });
    openMenu(id);
  });
  $("#btn-save-content").addEventListener("click", async () => {
    try {
      const content = JSON.parse($("#content-json").value);
      await api(`/api/menus/${id}/content`, jsonBody("PUT", content));
      openMenu(id);
    } catch (err) {
      $("#content-msg").textContent = `Fehler: ${err.message}`;
    }
  });
  if (!dialog.open) dialog.showModal();
}

// ---------------------------------------------------------------- Allgemein

function switchTab(name) {
  $$(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  $$(".tab-panel").forEach((p) => (p.hidden = p.dataset.panel !== name));
  if (name === "ci") refreshPreview();
}

function init() {
  $$(".tab").forEach((t) => t.addEventListener("click", () => switchTab(t.dataset.tab)));
  $("#ci-form").addEventListener("submit", async (event) => { await saveCi(event); refreshPreview(); });
  $$(".seg-btn").forEach((b) => b.addEventListener("click", () => {
    state.previewMode = b.dataset.preview;
    $$(".seg-btn").forEach((x) => x.classList.toggle("active", x === b));
    refreshPreview();
  }));

  const openNew = () => { $("#new-client-form").reset(); $("#dlg-client").showModal(); };
  $("#btn-new-client").addEventListener("click", openNew);
  $("#btn-new-client-2").addEventListener("click", openNew);
  $("#dlg-client").addEventListener("close", async () => {
    if ($("#dlg-client").returnValue !== "ok") return;
    const name = $("#new-client-form").elements.restaurant_name.value.trim();
    if (name) createClient(name).catch((err) => alert(err.message));
  });

  $("#btn-import").addEventListener("click", () => { $("#import-result").textContent = ""; $("#dlg-import").showModal(); });
  $("#import-form").addEventListener("submit", async (event) => {
    if (event.submitter?.value !== "ok") return;
    event.preventDefault();
    const form = event.target;
    const data = new FormData();
    data.append("text", form.elements.text.value);
    if (form.elements.file.files[0]) data.append("file", form.elements.file.files[0]);
    try {
      const result = await api("/api/import-urls", { method: "POST", body: data });
      $("#import-result").innerHTML = `${result.created.length} Karte(n) in die Warteschlange gestellt.` +
        (result.rejected.length ? `<br>Übersprungen:<br>${result.rejected.map((r) => `Zeile ${r.line}: ${esc(r.reason)}`).join("<br>")}` : "");
      await loadClients();
      await loadMenus();
    } catch (err) {
      $("#import-result").textContent = `Fehler: ${err.message}`;
    }
  });

  $("#btn-close-menu").addEventListener("click", () => $("#dlg-menu").close());
  $("#upload-form").addEventListener("submit", uploadMenus);
  $("#filter-status").addEventListener("change", renderMenus);
  $("#sort").addEventListener("change", renderMenus);
  $("#btn-reprocess-all").addEventListener("click", async () => {
    if (!confirm("Alle Karten dieses Kunden erneut mit KI prüfen? (verursacht API-Kosten)")) return;
    await api(`/api/clients/${state.clientId}/reprocess`, { method: "POST" });
    loadMenus();
  });
  $("#btn-retry-errors").addEventListener("click", async () => {
    await api(`/api/clients/${state.clientId}/reprocess?only_errors=true`, { method: "POST" });
    loadMenus();
  });

  const zone = $("#dropzone");
  const input = $("#file-input");
  const showCount = () => ($("#file-count").textContent = input.files.length ? `${input.files.length} Datei(en) ausgewählt` : "");
  input.addEventListener("change", showCount);
  ["dragenter", "dragover"].forEach((e) => zone.addEventListener(e, (ev) => { ev.preventDefault(); zone.classList.add("drag"); }));
  ["dragleave", "drop"].forEach((e) => zone.addEventListener(e, (ev) => { ev.preventDefault(); zone.classList.remove("drag"); }));
  zone.addEventListener("drop", (ev) => { input.files = ev.dataTransfer.files; showCount(); });

  loadStatus();
  loadClients();
}

init();
