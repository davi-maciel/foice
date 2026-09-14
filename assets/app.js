/* FOICE — banco de problemas (vanilla JS, sem build) */
(function () {
  "use strict";
  const D = window.FOICE;
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const norm = (s) => String(s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const STAR = "★";

  if (!D) { document.body.innerHTML = '<p style="padding:40px;font-family:sans-serif">Não foi possível carregar <code>data/problems.js</code>.</p>'; return; }

  // ------------------------------------------------------------------ data prep
  const topics = D.topics;
  const topicLabel = Object.fromEntries(topics.map((t) => [t.id, t.label]));
  const lists = Object.fromEntries(D.lists.map((l) => [l.id, l]));
  const listOrder = Object.fromEntries(D.lists.map((l, i) => [l.id, i]));
  D.lists.forEach((l) => { l.authorName = D.authors[l.author]; l.topics = {}; });
  D.problems.forEach((p, i) => {
    const l = lists[p.list];
    p.L = l; p.year = l.year; p.authorName = l.authorName; p.authorId = l.author;
    p.displayTitle = p.title || `Problema ${p.label}`;
    p.hay = norm([p.title, p.text, p.authorName, l.label, l.year, topicLabel[p.topic], p.source].filter(Boolean).join(" \n "));
    p.hayTitle = norm(p.title || "");
    p.idx = i;
    l.topics[p.topic] = (l.topics[p.topic] || 0) + 1;
  });
  const byId = Object.fromEntries(D.problems.map((p) => [p.id, p]));
  const groupSize = {};
  D.problems.forEach((p) => { if (p.group) groupSize[p.group] = (groupSize[p.group] || 0) + 1; });
  D.problems.forEach((p) => { p.similar = p.similar || []; p.versions = p.group ? groupSize[p.group] : 1; });
  const simLabel = (score) => (score >= 0.75 ? "praticamente igual" : "mesma ideia");
  const authorsSorted = Object.entries(D.authors).map(([id, name]) => ({ id, name, n: D.problems.filter((p) => p.authorId === id).length }))
    .sort((a, b) => a.name.localeCompare(b.name, "pt"));
  const years = [...new Set(D.lists.map((l) => l.year))].sort((a, b) => b - a);

  // ------------------------------------------------------------------ solved (localStorage)
  const store = {
    key: "foice:solved",
    read() { try { return JSON.parse(localStorage.getItem(this.key) || "{}"); } catch { return {}; } },
    write(v) { try { localStorage.setItem(this.key, JSON.stringify(v)); } catch { /* private mode */ } },
  };
  let solved = store.read();
  const isSolved = (id) => !!solved[id];
  function toggleSolved(id) {
    if (solved[id]) delete solved[id]; else solved[id] = Date.now();
    store.write(solved);
    $$(`[data-id="${id}"]`).forEach((el) => {
      el.classList.toggle("solved", isSolved(id));
      const b = $(".solve", el); if (b) { b.setAttribute("aria-pressed", String(isSolved(id))); b.lastChild.textContent = isSolved(id) ? " Resolvido" : " Marcar resolvido"; }
    });
    if (state.open === id) renderPanelSolved();
    renderProgress();
    if (state.hideSolved) render();
  }

  // ------------------------------------------------------------------ state <-> URL hash
  const state = { view: "problemas", q: "", topic: "", year: "", author: "", list: "", diff: "", sort: "recentes", hideSolved: false, open: null, shown: 72 };
  const HASH_KEYS = { q: "q", topic: "t", year: "y", author: "a", list: "l", diff: "d", sort: "s", view: "v", open: "p" };
  function readHash() {
    const h = location.hash.replace(/^#\/?/, "");
    const sp = new URLSearchParams(h);
    Object.assign(state, { view: "problemas", q: "", topic: "", year: "", author: "", list: "", diff: "", sort: "recentes", open: null });
    for (const [k, hk] of Object.entries(HASH_KEYS)) if (sp.has(hk)) state[k] = sp.get(hk);
    state.hideSolved = sp.get("hs") === "1";
    if (!["problemas", "listas"].includes(state.view)) state.view = "problemas";
    if (!["recentes", "antigos", "dificuldade", "repetidos", "aleatorio", "relevancia"].includes(state.sort)) state.sort = "recentes";
  }
  function writeHash() {
    const sp = new URLSearchParams();
    for (const [k, hk] of Object.entries(HASH_KEYS)) {
      const v = state[k];
      if (v && !(k === "view" && v === "problemas") && !(k === "sort" && v === "recentes")) sp.set(hk, v);
    }
    if (state.hideSolved) sp.set("hs", "1");
    const s = sp.toString().replace(/%2C/g, ",");
    history.replaceState(null, "", s ? "#" + s : location.pathname + location.search);
  }

  // ------------------------------------------------------------------ filtering + ranking
  let seed = Date.now() % 100000;
  function rng(i) { const x = Math.sin(i * 9301 + seed * 49297) * 233280; return x - Math.floor(x); }
  function tokens() { return norm(state.q).split(/\s+/).filter(Boolean); }
  function matches(p, toks) { return toks.every((t) => p.hay.includes(t)); }
  function score(p, toks) {
    let s = 0;
    for (const t of toks) {
      if (p.hayTitle.includes(t)) s += 6;
      if (p.hayTitle === t) s += 6;
      let i = -1, c = 0; while ((i = p.hay.indexOf(t, i + 1)) !== -1 && c < 8) c++;
      s += c;
    }
    if (toks.length > 1 && p.hay.includes(toks.join(" "))) s += 4;
    return s;
  }
  function baseFilter(p, { skipTopic = false } = {}) {
    if (!skipTopic && state.topic && p.topic !== state.topic) return false;
    if (state.year && String(p.year) !== state.year) return false;
    if (state.author && p.authorId !== state.author) return false;
    if (state.list && p.list !== state.list) return false;
    if (state.diff) {
      if (state.diff === "any" && !p.stars) return false;
      if (state.diff !== "any" && (p.stars || 0) !== Number(state.diff) && !(state.diff === "3" && (p.stars || 0) >= 3)) return false;
    }
    if (state.hideSolved && isSolved(p.id)) return false;
    return true;
  }
  function filtered() {
    const toks = tokens();
    let arr = D.problems.filter((p) => baseFilter(p) && (toks.length === 0 || matches(p, toks)));
    const sort = toks.length && state.sort === "recentes" ? "relevancia" : state.sort;
    const byList = (a, b) => (listOrder[a.list] - listOrder[b.list]) || (a.n - b.n);
    if (sort === "relevancia") arr.sort((a, b) => score(b, toks) - score(a, toks) || b.year - a.year || byList(a, b));
    else if (sort === "recentes") arr.sort((a, b) => b.year - a.year || byList(a, b));
    else if (sort === "antigos") arr.sort((a, b) => a.year - b.year || byList(a, b));
    else if (sort === "dificuldade") arr.sort((a, b) => (a.stars || 9) - (b.stars || 9) || b.year - a.year || byList(a, b));
    else if (sort === "repetidos") arr.sort((a, b) => b.versions - a.versions || b.year - a.year || byList(a, b));
    else if (sort === "aleatorio") arr.sort((a, b) => rng(a.idx) - rng(b.idx));
    return arr;
  }
  let current = [];

  // ------------------------------------------------------------------ rendering helpers
  function highlight(text, toks) {
    if (!toks.length) return esc(text);
    const plain = String(text); const n = norm(plain);
    // build a map from normalized index to original index (NFD strips only combining marks, so lengths differ)
    const map = []; let j = 0;
    for (let i = 0; i < plain.length; i++) { const nf = plain[i].normalize("NFD").replace(/[̀-ͯ]/g, ""); for (let k = 0; k < nf.length; k++) map[j++] = i; }
    map[j] = plain.length;
    const ranges = [];
    for (const t of toks) { let i = -1; while ((i = n.indexOf(t, i + 1)) !== -1) ranges.push([map[i], map[i + t.length] ?? plain.length]); }
    ranges.sort((a, b) => a[0] - b[0]);
    let out = "", pos = 0;
    for (const [a, b] of ranges) { if (a < pos) continue; out += esc(plain.slice(pos, a)) + '<mark class="mark">' + esc(plain.slice(a, b)) + "</mark>"; pos = b; }
    return out + esc(plain.slice(pos));
  }
  function snippet(p, toks) {
    const t = p.text || "";
    if (!toks.length) return t.slice(0, 220);
    const n = norm(t); let best = -1;
    for (const tk of toks) { const i = n.indexOf(tk); if (i !== -1 && (best === -1 || i < best)) best = i; }
    if (best <= 60) return t.slice(0, 220);
    const start = Math.max(0, t.lastIndexOf(" ", best - 50));
    return "…" + t.slice(start + 1, start + 220);
  }
  const starsHtml = (p) => p.stars ? `<span class="stars" title="dificuldade indicada pelo autor">${STAR.repeat(p.stars)}</span>` : "";
  const versionsHtml = (p) => p.versions > 1 ? `<span class="versions" title="este problema aparece em ${p.versions} listas">${p.versions} versões</span>` : "";
  const pdfHref = (p, page) => `${p.L.file}#page=${page || p.page}`;
  function cardHtml(p, toks) {
    const title = p.title ? highlight(p.title, toks) : `<span class="num">Problema ${esc(p.label)}</span>`;
    const probNo = p.title ? ` · problema ${esc(p.label)}` : "";
    const src = p.source ? ` · <span title="fonte citada na lista">${esc(p.source)}</span>` : "";
    return `<article class="card${isSolved(p.id) ? " solved" : ""}${state.open === p.id ? " active" : ""}" data-id="${p.id}" tabindex="0" role="button" aria-label="${esc(p.displayTitle)}">
      <div class="tags"><span>${esc(topicLabel[p.topic])}</span>${versionsHtml(p)}${starsHtml(p)}</div>
      <h3 class="title">${title}</h3>
      <div class="meta"><b>${esc(p.authorName)}</b> · ${esc(p.L.label)}${probNo} · ${p.year} · p.&nbsp;${p.page}${src}</div>
      <p class="snippet">${highlight(snippet(p, toks), toks)}</p>
      <div class="foot">
        <a class="open" href="${pdfHref(p)}" target="_blank" rel="noopener" title="Abrir o PDF na página ${p.page}">Abrir PDF <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M7 17 17 7M9 7h8v8"/></svg></a>
        <button class="solve" aria-pressed="${isSolved(p.id)}" title="Marcar como resolvido"><i>✓</i>${isSolved(p.id) ? " Resolvido" : " Marcar resolvido"}</button>
      </div></article>`;
  }

  // ------------------------------------------------------------------ render
  const els = {};
  function render() {
    writeHash();
    $$("nav.views button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.view === state.view)));
    els.problemas.hidden = state.view !== "problemas";
    els.listas.hidden = state.view !== "listas";
    if (state.view === "problemas") { renderChips(); renderSubfilters(); renderGrid(); }
    else renderLists();
    renderProgress();
  }
  function renderChips() {
    const counts = {}; let total = 0;
    const toks = tokens();
    for (const p of D.problems) if (baseFilter(p, { skipTopic: true }) && (!toks.length || matches(p, toks))) { counts[p.topic] = (counts[p.topic] || 0) + 1; total++; }
    els.chips.innerHTML = `<button class="chip all" aria-pressed="${!state.topic}" data-topic="">Todos <b>${total}</b></button>` +
      topics.map((t) => `<button class="chip" aria-pressed="${state.topic === t.id}" data-topic="${t.id}">${esc(t.label)} <b>${counts[t.id] || 0}</b></button>`).join("");
  }
  function renderSubfilters() {
    els.year.innerHTML = `<option value="">Todos os anos</option>` + years.map((y) => `<option value="${y}" ${String(y) === state.year ? "selected" : ""}>${y}</option>`).join("");
    els.author.innerHTML = `<option value="">Todos os autores</option>` + authorsSorted.map((a) => `<option value="${a.id}" ${a.id === state.author ? "selected" : ""}>${esc(a.name)} (${a.n})</option>`).join("");
    els.diff.value = state.diff; els.sort.value = state.sort;
    els.hide.checked = state.hideSolved;
    [els.year, els.author, els.diff].forEach((s) => s.classList.toggle("active", !!s.value));
    els.sort.classList.toggle("active", state.sort !== "recentes");
    const relevOpt = $('option[value="relevancia"]', els.sort); relevOpt.hidden = !state.q;
    if (state.q && state.sort === "recentes") els.sort.value = "relevancia";
    const any = state.q || state.topic || state.year || state.author || state.list || state.diff || state.hideSolved;
    els.reset.hidden = !any;
    els.listTag.hidden = !state.list;
    if (state.list && lists[state.list]) els.listTag.innerHTML = `Lista: <b>${esc(lists[state.list].authorName)} — ${esc(lists[state.list].label)} (${lists[state.list].year})</b> <button class="x" title="remover filtro">✕</button>`;
  }
  function renderGrid() {
    const toks = tokens();
    current = filtered();
    const n = current.length;
    const what = state.q ? `para <b>“${esc(state.q)}”</b>` : "";
    els.count.innerHTML = `<b>${n}</b> ${n === 1 ? "problema" : "problemas"} ${what}`;
    const shown = current.slice(0, state.shown);
    let html = shown.map((p) => cardHtml(p, toks)).join("");
    if (!n) html = `<div class="empty"><h3>Nada por aqui.</h3><p>Nenhum problema bate com esses filtros. Tente outra palavra${state.hideSolved ? ", mostre os resolvidos" : ""} ou <button class="btn sm" id="emptyReset">limpe os filtros</button>.</p></div>`;
    else if (n > shown.length) html += `<div class="more"><button class="btn" id="moreBtn">Mostrar mais ${Math.min(72, n - shown.length)} de ${n - shown.length} restantes</button></div>`;
    els.grid.innerHTML = html;
  }
  function renderProgress() {
    const total = D.problems.length; const done = Object.keys(solved).filter((id) => D.problems.some((p) => p.id === id)).length;
    els.progress.innerHTML = `<span>${done} de ${total} resolvidos</span><span class="bar" role="progressbar" aria-valuenow="${done}" aria-valuemax="${total}"><i style="width:${(100 * done / total).toFixed(1)}%"></i></span>`;
  }
  function renderLists() {
    const byYear = {};
    for (const l of D.lists) (byYear[l.year] ||= []).push(l);
    els.years.innerHTML = years.map((y) => {
      const ls = byYear[y]; const byAuthor = {};
      for (const l of ls) (byAuthor[l.author] ||= []).push(l);
      const np = ls.reduce((s, l) => s + l.problems, 0);
      const na = Object.keys(byAuthor).length;
      return `<section class="year"><h2>${y}</h2><p class="yhint">${na} ${na === 1 ? "autor" : "autores"} · ${ls.length} ${ls.length === 1 ? "lista" : "listas"} · ${np} problemas</p>
        <div class="authors">${Object.entries(byAuthor).map(([a, al]) => {
          const tot = al.reduce((s, l) => s + l.problems, 0);
          return `<div class="author"><h3>${esc(D.authors[a])}</h3>${al.length > 1 ? `<div class="sum">${tot} problemas em ${al.length} listas</div>` : ""}
            <div class="lists">${al.map((l) => `<div class="lrow"><button class="lmain" data-list="${l.id}" title="Ver os problemas desta lista"><span class="lname">${esc(l.label)}</span><span class="lmeta">${l.problems} ${l.problems === 1 ? "problema" : "problemas"}</span></button><a class="lpdf" href="${l.file}" target="_blank" rel="noopener" title="Abrir o PDF">PDF ↗</a></div>`).join("")}</div></div>`;
        }).join("")}</div></section>`;
    }).join("");
  }
  function fmtDate(d) {
    const m = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
    const [y, mo, day] = d.split("-"); return (day ? `${Number(day)} ` : "") + m[Number(mo) - 1] + " " + y;
  }

  // ------------------------------------------------------------------ detail panel
  const isDesktop = () => matchMedia("(min-width: 1100px)").matches;
  function openDetail(id, { scroll = false } = {}) {
    const p = D.problems.find((x) => x.id === id); if (!p) return;
    const prev = state.open; state.open = id; writeHash();
    if (prev) $$(`[data-id="${prev}"]`).forEach((el) => el.classList.remove("active"));
    $$(`[data-id="${id}"]`).forEach((el) => el.classList.add("active"));
    const i = current.findIndex((x) => x.id === id);
    $(".ptags", els.panel).innerHTML = `<span>${esc(topicLabel[p.topic])}</span>${versionsHtml(p)}${starsHtml(p)}`;
    $("h2", els.panel).textContent = p.displayTitle;
    $(".pmeta", els.panel).innerHTML = `<b>${esc(p.authorName)}</b> · ${esc(p.L.label)} · ${p.year} · ${p.title ? `problema ${esc(p.label)} · ` : ""}página ${p.page} de ${p.L.pages}${p.source ? ` · fonte: ${esc(p.source)}` : ""}`;
    $(".statement", els.panel).innerHTML = `<p>${esc(p.text || "(sem texto extraído — veja o PDF)")}${p.text && p.text.length >= 900 ? "…" : ""}</p><small>Texto extraído automaticamente do PDF; fórmulas e figuras só aparecem direito no PDF.</small>`;
    $("#openPdf", els.panel).href = pdfHref(p);
    $("#openPdf", els.panel).lastElementChild.textContent = ` Abrir PDF na p. ${p.page}`;
    const gab = $("#openGab", els.panel);
    if (p.L.gabaritoPage) { gab.hidden = false; gab.href = pdfHref(p, p.L.gabaritoPage); gab.lastElementChild.textContent = ` Gabarito (p. ${p.L.gabaritoPage})`; } else gab.hidden = true;
    $("#prevBtn", els.panel).disabled = i <= 0; $("#nextBtn", els.panel).disabled = i === -1 || i >= current.length - 1;
    $("#posInfo", els.panel).textContent = i === -1 ? "" : `${i + 1} / ${current.length}`;
    renderPanelSolved();
    renderSimilar(p);
    const frame = $("iframe", els.panel);
    if (isDesktop()) { const src = `${p.L.file}#page=${p.page}&navpanes=0&view=FitH`; if (frame.getAttribute("src") !== src) frame.setAttribute("src", src); }
    els.panel.setAttribute("open", ""); els.scrim.setAttribute("open", ""); document.body.classList.add("panel-open");
    if (scroll) { const card = $(`.card[data-id="${id}"]`); if (card) card.scrollIntoView({ block: "center", behavior: "smooth" }); }
  }
  function renderSimilar(p) {
    const near = (p.similar || []).map((s) => ({ q: byId[s.id], score: s.score })).filter((x) => x.q);
    els.similar.hidden = !near.length;
    if (!near.length) { els.similar.innerHTML = ""; return; }
    els.similar.innerHTML = `<h3>Problemas parecidos <b>${near.length}</b></h3>
      <ul>${near.map(({ q, score }) => `<li><button class="simrow" data-open="${esc(q.id)}" title="Abrir este problema">
        <span class="simtitle">${esc(q.displayTitle)}</span>
        <span class="simmeta">${esc(q.authorName)} · ${esc(q.L.label)} · ${q.year}${q.title ? ` · problema ${esc(q.label)}` : ""}</span>
        <span class="simtag">${simLabel(score)}</span></button></li>`).join("")}</ul>
      <small>Comparação automática dos enunciados: o mesmo problema costuma voltar em outro ano, às vezes com outro título.</small>`;
  }
  function renderPanelSolved() {
    const b = $("#panelSolve", els.panel); const on = isSolved(state.open);
    b.setAttribute("aria-pressed", String(on)); b.lastChild.textContent = on ? " Resolvido" : " Marcar como resolvido";
  }
  function closeDetail() {
    if (state.open) $$(`[data-id="${state.open}"]`).forEach((el) => el.classList.remove("active"));
    state.open = null; writeHash();
    els.panel.removeAttribute("open"); els.scrim.removeAttribute("open"); document.body.classList.remove("panel-open");
    $("iframe", els.panel).setAttribute("src", "about:blank");
  }
  function nav(delta) {
    const i = current.findIndex((x) => x.id === state.open); if (i === -1) return;
    const j = i + delta; if (j < 0 || j >= current.length) return;
    if (j >= state.shown) { state.shown = j + 24; renderGrid(); }
    openDetail(current[j].id, { scroll: true });
  }
  function random() {
    let pool = current.filter((p) => !isSolved(p.id)); if (!pool.length) pool = current; if (!pool.length) return toast("Nenhum problema com esses filtros.");
    const p = pool[Math.floor(Math.random() * pool.length)];
    const j = current.indexOf(p); if (j >= state.shown) { state.shown = j + 24; renderGrid(); }
    openDetail(p.id, { scroll: true });
  }
  let toastT; function toast(msg) { els.toast.textContent = msg; els.toast.classList.add("show"); clearTimeout(toastT); toastT = setTimeout(() => els.toast.classList.remove("show"), 2200); }

  // ------------------------------------------------------------------ wire up
  function init() {
    Object.assign(els, { problemas: $("#viewProblemas"), listas: $("#viewListas"), chips: $("#chips"), year: $("#fYear"), author: $("#fAuthor"), diff: $("#fDiff"), sort: $("#fSort"), hide: $("#fHide"), reset: $("#resetBtn"), listTag: $("#listTag"), count: $("#count"), grid: $("#grid"), progress: $("#progress"), years: $("#years"), panel: $("#panel"), scrim: $("#scrim"), toast: $("#toast"), q: $("#q"), similar: $("#similar") });
    readHash();
    els.q.value = state.q; $(".search").classList.toggle("has-q", !!state.q);
    $("#statTotal").textContent = D.problems.length; $("#statLists").textContent = D.lists.length; $("#statAuthors").textContent = Object.keys(D.authors).length;
    $("#statYears").textContent = `${Math.min(...years)}–${Math.max(...years)}`;
    render();
    if (state.open) openDetail(state.open, { scroll: true });

    let qt; els.q.addEventListener("input", () => { clearTimeout(qt); qt = setTimeout(() => { state.q = els.q.value.trim(); state.shown = 72; $(".search").classList.toggle("has-q", !!state.q); render(); }, 120); });
    $(".search .clear").addEventListener("click", () => { els.q.value = ""; state.q = ""; $(".search").classList.remove("has-q"); render(); els.q.focus(); });
    els.chips.addEventListener("click", (e) => { const b = e.target.closest(".chip"); if (!b) return; state.topic = b.dataset.topic === state.topic ? "" : b.dataset.topic; state.shown = 72; render(); });
    els.year.addEventListener("change", () => { state.year = els.year.value; state.shown = 72; render(); });
    els.author.addEventListener("change", () => { state.author = els.author.value; state.list = ""; state.shown = 72; render(); });
    els.diff.addEventListener("change", () => { state.diff = els.diff.value; state.shown = 72; render(); });
    els.sort.addEventListener("change", () => { state.sort = els.sort.value; if (state.sort === "aleatorio") seed = Date.now() % 100000; render(); });
    els.hide.addEventListener("change", () => { state.hideSolved = els.hide.checked; render(); });
    const resetAll = () => { Object.assign(state, { q: "", topic: "", year: "", author: "", list: "", diff: "", sort: "recentes", hideSolved: false, shown: 72 }); els.q.value = ""; $(".search").classList.remove("has-q"); render(); };
    els.reset.addEventListener("click", resetAll);
    els.listTag.addEventListener("click", (e) => { if (e.target.closest(".x")) { state.list = ""; render(); } });
    $$("nav.views button").forEach((b) => b.addEventListener("click", () => { state.view = b.dataset.view; render(); window.scrollTo({ top: 0 }); }));
    $("#randomBtn").addEventListener("click", random);
    els.grid.addEventListener("click", (e) => {
      if (e.target.closest("#moreBtn")) { state.shown += 72; renderGrid(); return; }
      if (e.target.closest("#emptyReset")) { resetAll(); return; }
      const card = e.target.closest(".card"); if (!card) return;
      if (e.target.closest(".solve")) { toggleSolved(card.dataset.id); return; }
      if (e.target.closest("a.open")) return;   // let the link open the PDF
      openDetail(card.dataset.id);
    });
    els.grid.addEventListener("keydown", (e) => { const card = e.target.closest(".card"); if (card && e.target === card && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); openDetail(card.dataset.id); } });
    els.years.addEventListener("click", (e) => { const b = e.target.closest("button[data-list]"); if (!b) return; const l = lists[b.dataset.list]; Object.assign(state, { view: "problemas", list: l.id, author: "", year: "", topic: "", q: "", shown: 72 }); els.q.value = ""; render(); window.scrollTo({ top: 0 }); });
    $("#closeBtn").addEventListener("click", closeDetail); els.scrim.addEventListener("click", closeDetail);
    $("#prevBtn").addEventListener("click", () => nav(-1)); $("#nextBtn").addEventListener("click", () => nav(1));
    els.similar.addEventListener("click", (e) => { const b = e.target.closest("[data-open]"); if (b) openDetail(b.dataset.open, { scroll: true }); });
    $("#panelSolve").addEventListener("click", () => toggleSolved(state.open));
    $("#panelRandom").addEventListener("click", random);
    document.addEventListener("keydown", (e) => {
      const typing = /^(INPUT|SELECT|TEXTAREA)$/.test(document.activeElement?.tagName);
      if (e.key === "Escape") { if (state.open) closeDetail(); else if (typing) document.activeElement.blur(); return; }
      if (typing) return;
      if (e.key === "/") { e.preventDefault(); els.q.focus(); els.q.select(); }
      else if (e.key === "r" && !e.metaKey && !e.ctrlKey) random();
      else if (state.open && (e.key === "ArrowRight" || e.key === "j")) nav(1);
      else if (state.open && (e.key === "ArrowLeft" || e.key === "k")) nav(-1);
    });
    window.addEventListener("hashchange", () => { const before = JSON.stringify(state); readHash(); if (JSON.stringify(state) !== before) { els.q.value = state.q; render(); if (state.open) openDetail(state.open); else closeDetail(); } });
  }
  document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", init) : init();
})();
