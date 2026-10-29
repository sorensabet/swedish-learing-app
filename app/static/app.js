const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const store = {
  get(key, fallback) {
    try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; }
  },
  set(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch {}
  },
};

const state = {
  tab: store.get("tab", "nouns"),
  item: null,
  graded: null,
  params: {},
};

const NOUN_LABELS = { gender: "en/ett", def_sg: "bestämd singular", indef_pl: "obestämd plural", def_pl: "bestämd plural" };
const VERB_LABELS = {
  translation: "English", imperative: "imperativ", infinitive: "infinitiv", present: "presens",
  preterite: "preteritum", supine: "supinum", group: "grupp",
};
const MODE_NAMES = { nouns: "Substantiv", verbs: "Verb", cloze: "Adjektiv & adverb", translate: "Översätt" };

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: opts.body && !(opts.body instanceof FormData) ? { "Content-Type": "application/json" } : {},
    ...opts,
    body: opts.body && !(opts.body instanceof FormData) ? JSON.stringify(opts.body) : opts.body,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

function pct(x) {
  return x == null ? "–" : `${Math.round(x * 100)}%`;
}

function renderSummary(s) {
  if (!s) { $("#summary").textContent = ""; return; }
  $("#summary").textContent =
    `${s.learned} learned · ${s.in_progress} in progress · ${s.total - s.seen - s.excluded} new · accuracy ${pct(s.accuracy)}`;
}

function statusBadge(status, kind) {
  if (kind === "new" || !status || !status.attempts) return `<span class="badge">new</span>`;
  return `<span class="badge">${status.correct}/${status.attempts} correct · streak ${status.streak}</span>`;
}

function input(field, opts = {}) {
  const cls = opts.short ? "short" : "";
  return `<div class="cell"><input type="text" data-field="${field}" class="${cls}" autocomplete="off" autocapitalize="off" spellcheck="false" placeholder="${esc(opts.placeholder || "")}"></div>`;
}

function renderNoun(card) {
  return `
    <p class="meta">#${card.rank} by frequency ${statusBadge(state.item.status, state.item.kind)}</p>
    <p class="word">${esc(card.word)}</p>
    <p class="gloss">${esc(card.translations.join(", "))}</p>
    <table class="forms">
      <tr><th></th><th>obestämd</th><th>bestämd</th></tr>
      <tr><th>singular</th>
        <td><div class="inline-pair">${input("gender", { short: true, placeholder: "en/ett" })}<span>${esc(card.word)}</span></div></td>
        <td>${input("def_sg")}</td></tr>
      <tr><th>plural</th>
        <td>${card.has_plural ? input("indef_pl") : "<span class='meta'>no plural</span>"}</td>
        <td>${card.has_plural ? input("def_pl") : ""}</td></tr>
    </table>`;
}

function renderVerb(card) {
  const promptStyle = store.get("verbPrompt", "random");
  const rows = Object.entries(VERB_LABELS).map(([field, label]) => {
    if (field === "imperative" && !card.has_imperative) {
      return `<label>${label}</label><span class="meta">no imperative</span>`;
    }
    const ph = field === "group" ? "1, 2, 3 or 4" : "";
    return `<label>${label}</label>${input(field, { placeholder: ph })}`;
  }).join("");
  return `
    <p class="meta">#${card.rank} by frequency ${statusBadge(state.item.status, state.item.kind)}
      ${card.deponent ? '<span class="badge">deponent</span>' : ""}
      ${promptStyle === "random" ? `<span class="badge">shown: ${esc(card.prompt_slot)}</span>` : ""}</p>
    <p class="word">${esc(card.word)}</p>
    <div class="fields" style="margin-top:12px">${rows}</div>`;
}

function renderCloze(card) {
  const html = card.segments.map(seg => {
    if (seg.text !== undefined) return esc(seg.text);
    const width = Math.max(seg.base.length + 3, 6);
    return `<span class="blank"><input type="text" data-field="${seg.blank}" style="width:${width}ch" autocomplete="off" autocapitalize="off" spellcheck="false"><span class="base">${esc(seg.base)}</span></span>`;
  }).join("");
  return `
    <p class="meta">${esc(card.topic)} ${statusBadge(state.item.status, state.item.kind)}</p>
    <div class="paragraph">${html}</div>`;
}

function renderTranslate(card) {
  const to = card.direction === "sv2en" ? "English" : "Swedish";
  return `
    <p class="meta">${card.direction === "sv2en" ? "Swedish → English" : "English → Swedish"} ${statusBadge(state.item.status, state.item.kind)}</p>
    <p class="word">${esc(card.word)}</p>
    <div class="fields" style="margin-top:12px"><label>${to}</label>${input("answer")}</div>`;
}

const RENDERERS = { nouns: renderNoun, verbs: renderVerb, cloze: renderCloze, translate: renderTranslate };

function setActions(buttons) {
  $("#actions").innerHTML = "";
  for (const [label, handler, ghost] of buttons) {
    const b = document.createElement("button");
    b.textContent = label;
    if (ghost) b.className = "ghost";
    b.addEventListener("click", handler);
    $("#actions").appendChild(b);
  }
}

function query(params) {
  const q = new URLSearchParams(params).toString();
  return q ? `?${q}` : "";
}

async function loadNext() {
  state.graded = null;
  $("#feedback").innerHTML = "";
  const params = { ...state.params };
  if (state.tab === "verbs") params.prompt = store.get("verbPrompt", "random");
  if (state.tab === "translate" && !params.deck) {
    $("#card").innerHTML = `<p>Upload a CSV with Swedish/English pairs to start.</p>`;
    setActions([]);
    renderSummary(null);
    return;
  }
  const data = await api(`/api/${state.tab}/next${query(params)}`);
  renderSummary(data.summary);
  if (data.done) {
    state.item = null;
    $("#card").innerHTML = `<p>Nothing left to practise here. Everything is learned!</p>`;
    setActions([]);
    return;
  }
  state.item = data;
  $("#card").innerHTML = RENDERERS[state.tab](data.card);
  const first = $("#card input");
  if (first) first.focus();
  setActions([
    ["Check", submit],
    ["I already know this", markKnown, true],
    ["Skip (bad item)", exclude, true],
  ]);
}

function collectAnswers() {
  const answers = {};
  for (const el of $$("#card input[data-field]")) answers[el.dataset.field] = el.value;
  return answers;
}

function showExpected(el, res) {
  el.classList.add(res.correct ? "ok" : "bad");
  el.readOnly = true;
  if (!res.correct) {
    const div = document.createElement("div");
    div.className = "expected";
    div.textContent = `→ ${res.expected}`;
    el.closest(".blank, .cell").appendChild(div);
  }
}

async function submit() {
  if (!state.item || state.graded) return;
  const data = await api(`/api/${state.tab}/answer`, {
    method: "POST",
    body: { item_id: state.item.item_id, answers: collectAnswers(), params: state.params },
  });
  state.graded = data;
  for (const [field, res] of Object.entries(data.fields)) {
    const el = $(`#card input[data-field="${field}"]`);
    if (el) showExpected(el, res);
  }
  let html = `<p class="verdict ${data.all_correct ? "ok" : "bad"}">${data.all_correct ? "Rätt!" : "Inte riktigt."}`;
  if (data.status.learned) html += " Marked as learned.";
  html += `</p>`;
  if (state.tab === "verbs") {
    const exp = data.fields;
    html += `<p class="meta">${esc(exp.infinitive.expected)} · ${esc(exp.present.expected)} · ${esc(exp.preterite.expected)} · ${esc(exp.supine.expected)}
      — group ${esc(exp.group.expected)} — ${esc(exp.translation.expected)}</p>`;
  }
  if (state.tab === "nouns") {
    const f = data.fields;
    const forms = [`${f.gender.expected} ${state.item.card.word}`, f.def_sg.expected];
    if (f.indef_pl) forms.push(f.indef_pl.expected, f.def_pl.expected);
    html += `<p class="meta">${esc(forms.join(" · "))}</p>`;
  }
  if (state.tab === "cloze") {
    const rules = Object.values(data.fields).filter(r => !r.correct);
    if (rules.length) {
      html += `<ul class="rules">${rules.map(r => `<li><b>${esc(r.expected)}</b> (${esc(r.base)}): ${esc(r.rule)}</li>`).join("")}</ul>`;
    }
  }
  $("#feedback").innerHTML = html;
  const buttons = [["Next", loadNext]];
  if (!data.all_correct) buttons.push(["I was right", override, true]);
  setActions(buttons);
  $("#actions button").focus();
}

async function override() {
  const data = await api(`/api/${state.tab}/override`, {
    method: "POST", body: { item_id: state.item.item_id, params: state.params },
  });
  $$("#card input.bad").forEach(el => { el.classList.replace("bad", "ok"); });
  $$("#card .expected").forEach(el => el.remove());
  $("#feedback .verdict").className = "verdict ok";
  $("#feedback .verdict").textContent = `Counted as correct.${data.status.learned ? " Marked as learned." : ""}`;
  setActions([["Next", loadNext]]);
  $("#actions button").focus();
}

async function markKnown() {
  await api(`/api/${state.tab}/known`, { method: "POST", body: { item_id: state.item.item_id, params: state.params } });
  loadNext();
}

async function exclude() {
  await api(`/api/${state.tab}/exclude`, { method: "POST", body: { item_id: state.item.item_id, params: state.params } });
  loadNext();
}

document.addEventListener("keydown", e => {
  if (e.key !== "Enter" || ["progress"].includes(state.tab)) return;
  if (e.target.closest("#toolbar")) return;
  e.preventDefault();
  if (state.graded) loadNext();
  else if (state.item) submit();
});

async function refreshDecks(selectId) {
  const decks = await api("/api/decks");
  const sel = $("#deck-select");
  sel.innerHTML = decks.map(d => `<option value="${d.id}">${esc(d.name)} (${d.size})</option>`).join("");
  const wanted = selectId ?? store.get("deck", null);
  if (decks.some(d => String(d.id) === String(wanted))) sel.value = wanted;
  state.params.deck = sel.value || undefined;
  if (!state.params.deck) delete state.params.deck;
  store.set("deck", state.params.deck ?? null);
  return decks;
}

async function setupTranslateToolbar() {
  $("#toolbar").appendChild($("#translate-toolbar").content.cloneNode(true));
  const dir = $("#direction-select");
  dir.value = store.get("direction", "both");
  state.params.direction = dir.value;
  dir.addEventListener("change", () => { state.params.direction = dir.value; store.set("direction", dir.value); loadNext(); });
  $("#deck-select").addEventListener("change", e => { state.params.deck = e.target.value; store.set("deck", e.target.value); loadNext(); });
  $("#delete-deck").addEventListener("click", async () => {
    if (!state.params.deck || !confirm("Delete this deck and its progress?")) return;
    await api(`/api/decks/${state.params.deck}`, { method: "DELETE" });
    await refreshDecks();
    loadNext();
  });
  $("#upload-form").addEventListener("submit", async e => {
    e.preventDefault();
    try {
      const res = await api("/api/decks", { method: "POST", body: new FormData(e.target) });
      e.target.reset();
      await refreshDecks(res.id);
      loadNext();
    } catch (err) {
      alert(err.message);
    }
  });
  await refreshDecks();
}

function setupVerbToolbar() {
  const v = store.get("verbPrompt", "random");
  $("#toolbar").innerHTML = `
    <div class="toolbar-row"><label>Show
      <select id="verb-prompt">
        <option value="random">a random form (present, past or supine)</option>
        <option value="infinitive">the infinitive</option>
      </select></label></div>`;
  $("#verb-prompt").value = v;
  $("#verb-prompt").addEventListener("change", e => { store.set("verbPrompt", e.target.value); loadNext(); });
}

async function renderProgress() {
  const decks = await api("/api/decks");
  const options = [
    ["nouns", "Substantiv"], ["verbs", "Verb"], ["cloze", "Adjektiv & adverb"],
    ...decks.map(d => [`translate:${d.id}`, `Översätt: ${d.name}`]),
  ];
  const current = store.get("progressMode", "nouns");
  $("#toolbar").innerHTML = `<div class="toolbar-row"><label>Mode <select id="progress-mode">
    ${options.map(([v, l]) => `<option value="${esc(v)}">${esc(l)}</option>`).join("")}</select></label></div>`;
  const sel = $("#progress-mode");
  sel.value = options.some(o => o[0] === current) ? current : "nouns";
  sel.addEventListener("change", () => { store.set("progressMode", sel.value); renderProgress(); });

  const [mode, deck] = sel.value.split(":");
  const params = deck ? { deck, direction: "both" } : {};
  const data = await api(`/api/${mode}/stats${query(params)}`);
  const s = data.summary;
  const tiles = [
    [s.total, "items"], [s.learned, "learned"], [s.in_progress, "in progress"],
    [s.attempts, "attempts"], [pct(s.accuracy), "accuracy"],
  ];
  const labels = mode === "nouns" ? NOUN_LABELS : mode === "verbs" ? VERB_LABELS : {};
  const rows = data.items
    .sort((a, b) => (a.status === "learning" ? 0 : 1) - (b.status === "learning" ? 0 : 1) || (a.accuracy ?? 1) - (b.accuracy ?? 1))
    .map(r => {
      const weak = Object.entries(r.fields)
        .filter(([, acc]) => acc < 1)
        .sort((a, b) => a[1] - b[1])
        .slice(0, 3)
        .map(([f, acc]) => `${esc(labels[f] || (mode === "cloze" ? `blank ${+f + 1}` : f))} ${pct(acc)}`)
        .join(", ");
      const action = r.status === "learning"
        ? `<button class="ghost" data-known="${esc(r.item_id)}">Mark learned</button>`
        : `<button class="ghost" data-relearn="${esc(r.item_id)}">Practise again</button>`;
      return `<tr><td>${esc(r.label)}</td><td>${r.status}</td><td>${r.correct}/${r.attempts}</td>
        <td>${pct(r.accuracy)}</td><td>${weak}</td><td>${action}</td></tr>`;
    }).join("");
  $("#summary").innerHTML = "";
  $("#card").innerHTML = `
    <div class="tiles">${tiles.map(([n, l]) => `<div class="tile"><div class="n">${n}</div><div class="l">${l}</div></div>`).join("")}</div>
    <div class="stats-wrap"><table class="stats">
      <tr><th>Item</th><th>Status</th><th>Correct</th><th>Accuracy</th><th>Weakest parts</th><th></th></tr>
      ${rows || `<tr><td colspan="6" class="meta">Nothing practised yet.</td></tr>`}
    </table></div>`;
  for (const b of $$("[data-known]")) b.addEventListener("click", async () => {
    await api(`/api/${mode}/known`, { method: "POST", body: { item_id: b.dataset.known, params } });
    renderProgress();
  });
  for (const b of $$("[data-relearn]")) b.addEventListener("click", async () => {
    await api(`/api/${mode}/relearn`, { method: "POST", body: { item_id: b.dataset.relearn, params } });
    renderProgress();
  });
  $("#feedback").innerHTML = "";
  setActions([]);
}

async function switchTab(tab) {
  state.tab = tab;
  state.item = null;
  state.graded = null;
  state.params = {};
  store.set("tab", tab);
  $$("#tabs button").forEach(b => b.classList.toggle("active", b.dataset.tab === tab));
  $("#toolbar").innerHTML = "";
  $("#card").innerHTML = "";
  $("#feedback").innerHTML = "";
  if (tab === "progress") return renderProgress();
  if (tab === "translate") await setupTranslateToolbar();
  if (tab === "verbs") setupVerbToolbar();
  loadNext();
}

$$("#tabs button").forEach(b => b.addEventListener("click", () => switchTab(b.dataset.tab)));
switchTab(state.tab);
