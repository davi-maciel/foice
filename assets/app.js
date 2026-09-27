/* FOICE — banco de problemas (vanilla JS, sem build) */
(function () {
  "use strict";
  const D = window.FOICE;
  const CROPS = window.FOICE_CROPS || {};
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const norm = (s) => String(s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const STAR = "★";
  const labelText = (p) => /^\d/.test(p.label) ? `problema ${p.label}` : p.label;

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
  const state = { view: "problemas", q: "", topic: "", year: "", author: "", list: "", diff: "", sort: "recentes", hideSolved: false, open: null, shown: 72, group: "" };
  const HASH_KEYS = { q: "q", topic: "t", year: "y", author: "a", list: "l", diff: "d", sort: "s", view: "v", open: "p", group: "g" };
  function readHash() {
    const h = location.hash.replace(/^#\/?/, "");
    const sp = new URLSearchParams(h);
    Object.assign(state, { view: "problemas", q: "", topic: "", year: "", author: "", list: "", diff: "", sort: "recentes", open: null, group: "" });
    for (const [k, hk] of Object.entries(HASH_KEYS)) if (sp.has(hk)) state[k] = sp.get(hk);
    state.hideSolved = sp.get("hs") === "1";
    if (!["problemas", "listas", "repetidos"].includes(state.view)) state.view = "problemas";
    if (!["recentes", "antigos", "dificuldade", "aleatorio", "relevancia"].includes(state.sort)) state.sort = "recentes";
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
  // filtros com várias escolhas: guardados como "a,b,c" (também assim na URL)
  const sel = (k) => new Set(String(state[k] || "").split(",").filter(Boolean));
  const setSel = (k, set) => { state[k] = [...set].join(","); };
  const diffKey = (p) => String(Math.min(p.stars || 0, 3));   // 0 = sem indicação, 3 = três ou mais
  function baseFilter(p, { skipTopic = false } = {}) {
    if (!skipTopic && state.topic && !sel("topic").has(p.topic)) return false;
    if (state.year && !sel("year").has(String(p.year))) return false;
    if (state.author && !sel("author").has(p.authorId)) return false;
    if (state.list && p.list !== state.list) return false;
    if (state.diff && !sel("diff").has(diffKey(p))) return false;
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
  const versionsHtml = (p) => p.versions > 1 ? `<button class="versions" data-group="${esc(p.group)}" title="Ver as ${p.versions} versões deste problema">${p.versions} versões</button>` : "";
  const pdfHref = (p, page) => `${p.L.file}#page=${page || p.page}`;
  function cardHtml(p, toks) {
    const title = p.title ? highlight(p.title, toks) : `<span class="num">Problema ${esc(p.label)}</span>`;
    const probNo = p.title ? ` · ${esc(labelText(p))}` : "";
    return `<article class="card${isSolved(p.id) ? " solved" : ""}${state.open === p.id ? " active" : ""}" data-id="${p.id}" tabindex="0" role="button" aria-label="${esc(p.displayTitle)}">
      <div class="tags"><span>${esc(topicLabel[p.topic])}</span>${starsHtml(p)}</div>
      <h3 class="title">${title}</h3>
      <div class="meta"><span><b>${esc(p.authorName)}</b> · ${esc(p.L.label)}${probNo} · ${p.year} ${versionsHtml(p)}</span></div>
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
    els.repetidos.hidden = state.view !== "repetidos";
    if (state.view === "problemas") { renderChips(); renderSubfilters(); renderGrid(); }
    else if (state.view === "listas") renderLists();
    else renderGroups();
    renderProgress();
  }
  function renderChips() {
    const counts = {}; let total = 0;
    const toks = tokens();
    for (const p of D.problems) if (baseFilter(p, { skipTopic: true }) && (!toks.length || matches(p, toks))) { counts[p.topic] = (counts[p.topic] || 0) + 1; total++; }
    const ts = sel("topic");
    els.chips.innerHTML = `<button class="chip all" aria-pressed="${!ts.size}" data-topic="">Todos <b>${total}</b></button>` +
      topics.map((t) => `<button class="chip" aria-pressed="${ts.has(t.id)}" data-topic="${t.id}">${esc(t.label)} <b>${counts[t.id] || 0}</b></button>`).join("");
  }
  function renderSubfilters() {
    renderFilterToggle();
    renderMsel(els.year, "year", years.map((y) => ({ v: String(y), label: String(y) })), "Todos os anos", (n) => `${n} anos`);
    renderMsel(els.author, "author", authorsSorted.map((a) => ({ v: a.id, label: a.name, n: a.n })), "Todos os autores", (n) => `${n} autores`);
    renderMsel(els.diff, "diff", [{ v: "1", label: "★ fácil" }, { v: "2", label: "★★ médio" }, { v: "3", label: "★★★ difícil" }, { v: "0", label: "sem indicação" }], "Qualquer dificuldade", (n) => `${n} dificuldades`);
    els.sort.value = state.sort;
    els.hide.checked = state.hideSolved;

    els.sort.classList.toggle("active", state.sort !== "recentes");
    const relevOpt = $('option[value="relevancia"]', els.sort); relevOpt.hidden = !state.q;
    if (state.q && state.sort === "recentes") els.sort.value = "relevancia";
    const any = state.q || state.topic || state.year || state.author || state.list || state.diff || state.hideSolved;
    els.reset.hidden = !any;
    els.listTag.hidden = !state.list;
    if (state.list && lists[state.list]) els.listTag.innerHTML = `Lista: <b>${esc(lists[state.list].authorName)} — ${esc(lists[state.list].label)} (${lists[state.list].year})</b> <button class="x" title="remover filtro">✕</button>`;
  }
  // ---- filtros no celular: botão "Filtros" abre uma gaveta de baixo para cima
  function renderFilterToggle() {
    const n = ["year", "author", "diff", "topic"].reduce((a, k) => a + sel(k).size, 0) + (state.list ? 1 : 0) + (state.hideSolved ? 1 : 0);
    $(".ftcount").textContent = n ? String(n) : "";
    const total = current.length || D.problems.length;
    $("#fApply").textContent = `Ver ${total} ${total === 1 ? "problema" : "problemas"}`;
  }
  function setFiltersOpen(open) {
    const f = $("#filters"); f.classList.toggle("open", open);
    $("#fToggle").setAttribute("aria-expanded", String(open));
    document.body.classList.toggle("filters-open", open);
  }
  function renderMsel(el, key, opts, allLabel, manyLabel) {
    const chosen = sel(key);
    const one = opts.find((o) => chosen.has(o.v));
    $("summary", el).textContent = !chosen.size ? allLabel : chosen.size === 1 && one ? one.label : manyLabel(chosen.size);
    el.classList.toggle("active", chosen.size > 0);
    const menu = $(".menu", el);
    const html = (chosen.size ? `<button type="button" class="mclear" data-key="${key}">limpar</button>` : "") +
      opts.map((o) => `<label class="mopt"><input type="checkbox" data-key="${key}" value="${esc(o.v)}" ${chosen.has(o.v) ? "checked" : ""}> <span>${esc(o.label)}</span>${o.n ? ` <b>${o.n}</b>` : ""}</label>`).join("");
    if (menu.dataset.html !== html) { const st = menu.scrollTop; menu.innerHTML = html; menu.dataset.html = html; menu.scrollTop = st; }
  }
  function renderGrid() {
    const toks = tokens();
    current = filtered();
    if ($("#fApply")) renderFilterToggle();
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
  const groups = (() => {
    const by = {};
    for (const p of D.problems) if (p.group) (by[p.group] ||= []).push(p);
    return Object.entries(by).map(([id, members]) => {
      members.sort((a, b) => a.year - b.year || listOrder[a.list] - listOrder[b.list] || a.n - b.n);
      const titled = members.filter((m) => m.title);
      const topic = Object.entries(members.reduce((c, m) => (c[m.topic] = (c[m.topic] || 0) + 1, c), {})).sort((a, b) => b[1] - a[1])[0][0];
      return { id, members, title: (titled[0] || members[0]).displayTitle, topic, years: [...new Set(members.map((m) => m.year))] };
    }).sort((a, b) => b.members.length - a.members.length || a.members[0].year - b.members[0].year || a.title.localeCompare(b.title, "pt"));
  })();
  function renderGroups() {
    const np = groups.reduce((s, g) => s + g.members.length, 0);
    $("#groupsHint").innerHTML = `<b>${np} problemas</b> em <b>${groups.length} grupos</b>. Problemas que voltaram em outra lista, às vezes com outro título ou mais itens. A comparação é automática, feita sobre os enunciados, e pode errar.`;
    els.groups.innerHTML = groups.map((g) => `<article class="grp${state.group === g.id ? " focus" : ""}" id="grp-${esc(g.id)}">
      <header><h3>${esc(g.title)}</h3><span class="gmeta">${esc(topicLabel[g.topic])} · ${g.members.length} versões · ${g.years.join(", ")}</span></header>
      <div class="lists">${g.members.map((m) => `<div class="lrow${isSolved(m.id) ? " solved" : ""}" data-id="${m.id}"><button class="lmain" data-open="${m.id}" title="Abrir este problema">
        <span class="lname">${esc(m.displayTitle)}</span><span class="lmeta">${esc(m.authorName)} · ${esc(m.L.label)} · ${m.year}${m.title ? ` · ${esc(labelText(m))}` : ""}</span></button>
        <a class="lpdf" href="${pdfHref(m)}" target="_blank" rel="noopener" title="Abrir o PDF na página ${m.page}">PDF ↗</a></div>`).join("")}</div></article>`).join("");
    if (state.group) { const el = $(`#grp-${state.group}`); if (el) requestAnimationFrame(() => el.scrollIntoView({ block: "start", behavior: "smooth" })); }
  }
  function goToGroup(gid) {
    state.view = "repetidos"; state.group = gid; render();
    setTimeout(() => { state.group = ""; writeHash(); $$(".grp.focus").forEach((el) => el.classList.remove("focus")); }, 2500);
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
    // ao navegar com o teclado, o foco (e seu contorno vermelho) acompanha o cartão aberto
    const ae = document.activeElement;
    if (ae && ae.classList && ae.classList.contains("card") && ae.dataset.id !== id) {
      const nc = $(`.card[data-id="${id}"]`); if (nc) nc.focus({ preventScroll: true });
    }
    const i = current.findIndex((x) => x.id === id);
    $("h2", els.panel).textContent = p.displayTitle;
    $(".pmeta", els.panel).innerHTML = `<b>${esc(p.authorName)}</b> · ${esc(p.L.label)} · ${p.year} · ${p.title ? `${esc(labelText(p))} · ` : ""}<span class="ptopic">${esc(topicLabel[p.topic])}</span>${p.stars ? " " + starsHtml(p) : ""}${p.versions > 1 ? " " + versionsHtml(p) : ""}`;
    $("#openPdf", els.panel).href = pdfHref(p);
    $("#openPdf", els.panel).lastElementChild.textContent = " Abrir PDF";
    const gab = $("#openGab", els.panel);
    if (p.L.gabaritoPage) { gab.hidden = false; gab.href = pdfHref(p, p.L.gabaritoPage); gab.lastElementChild.textContent = " Gabarito"; } else gab.hidden = true;
    els.panel.classList.toggle("no-gab", !p.L.gabaritoPage);
    $("#prevBtn", els.panel).disabled = i <= 0; $("#nextBtn", els.panel).disabled = i === -1 || i >= current.length - 1;
    $("#posInfo", els.panel).textContent = i === -1 ? "" : `${i + 1} / ${current.length}`;
    renderPanelSolved();
    renderSimilar(p);
    const frame = $("iframe", els.panel), crop = $(".cropimg", els.panel);
    if (CROPS[p.id]) {
      const [w, h, pt, scale] = CROPS[p.id];
      // mostra o recorte no tamanho em que o texto do PDF fica com ~16px, como o texto do site
      crop.src = `data/crops/${p.id}.png`; crop.width = w; crop.height = h; crop.hidden = false;
      const cssW = (pt && scale) ? Math.round((w / scale) * (16 / pt)) : 560;
      crop.style.width = `${cssW + 44}px`;   // inclui as margens laterais (box-sizing: border-box); no celular cai para 100%
      // o painel abraça o recorte (imagem + margens), entre 460px e 60% da janela
      const pw = Math.max(460, Math.min(cssW + 46, Math.round(window.innerWidth * 0.6), 780));
      document.documentElement.style.setProperty("--panel-w", `${pw}px`);
      frame.hidden = true; if (frame.getAttribute("src") !== "about:blank") frame.setAttribute("src", "about:blank");
      els.panel.classList.add("has-crop");
    } else {
      crop.hidden = true; crop.removeAttribute("src"); frame.hidden = false; els.panel.classList.remove("has-crop");
      document.documentElement.style.removeProperty("--panel-w");
      if (isDesktop()) { const src = `${p.L.file}#page=${p.page}&navpanes=0&view=FitH`; if (frame.getAttribute("src") !== src) frame.setAttribute("src", src); }
    }
    $(".pbody", els.panel).scrollTop = 0;
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
        <span class="simmeta">${esc(q.authorName)} · ${esc(q.L.label)} · ${q.year}${q.title ? ` · ${esc(labelText(q))}` : ""}</span>
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
  // "Sortear" embaralha a lista inteira (ordem aleatória) e abre o primeiro problema não resolvido;
  // a partir daí "próximo"/"anterior" e "Sortear outro" andam por essa ordem embaralhada.
  function random({ reshuffle = false } = {}) {
    if (state.sort !== "aleatorio" || reshuffle || !state.open) {
      state.sort = "aleatorio"; seed = Math.floor(Math.random() * 100000); state.shown = 72; render();
      if (!current.length) return toast("Nenhum problema com esses filtros.");
      const first = current.find((p) => !isSolved(p.id)) || current[0];
      window.scrollTo({ top: 0 });
      return openDetail(first.id, { scroll: true });
    }
    const i = current.findIndex((x) => x.id === state.open);
    for (let k = 1; k <= current.length; k++) {
      const q = current[(i + k) % current.length];
      if (!isSolved(q.id) || k === current.length) {
        const j = current.indexOf(q); if (j >= state.shown) { state.shown = j + 24; renderGrid(); }
        return openDetail(q.id, { scroll: true });
      }
    }
  }
  let toastT; function toast(msg) { els.toast.textContent = msg; els.toast.classList.add("show"); clearTimeout(toastT); toastT = setTimeout(() => els.toast.classList.remove("show"), 2200); }

  // ------------------------------------------------------------------ wire up
  function init() {
    Object.assign(els, { problemas: $("#viewProblemas"), listas: $("#viewListas"), chips: $("#chips"), year: $("#fYear"), author: $("#fAuthor"), diff: $("#fDiff"), sort: $("#fSort"), hide: $("#fHide"), reset: $("#resetBtn"), listTag: $("#listTag"), count: $("#count"), grid: $("#grid"), progress: $("#progress"), years: $("#years"), panel: $("#panel"), scrim: $("#scrim"), toast: $("#toast"), q: $("#q"), similar: $("#similar"), repetidos: $("#viewRepetidos"), groups: $("#groups") });
    readHash();
    els.q.value = state.q; $(".search").classList.toggle("has-q", !!state.q);
    render();
    if (state.open) openDetail(state.open, { scroll: true });

    let qt; els.q.addEventListener("input", () => { clearTimeout(qt); qt = setTimeout(() => { state.q = els.q.value.trim(); state.shown = 72; $(".search").classList.toggle("has-q", !!state.q); render(); }, 120); });
    $(".search .clear").addEventListener("click", () => { els.q.value = ""; state.q = ""; $(".search").classList.remove("has-q"); render(); els.q.focus(); });
    els.chips.addEventListener("click", (e) => {
      const b = e.target.closest(".chip"); if (!b) return;
      const t = b.dataset.topic, ts = sel("topic");
      if (!t) ts.clear(); else if (ts.has(t)) ts.delete(t); else ts.add(t);
      setSel("topic", ts); state.shown = 72; render();
    });
    [els.year, els.author, els.diff].forEach((el) => {
      el.addEventListener("change", (e) => {
        const cb = e.target.closest("input[type=checkbox]"); if (!cb) return;
        const k = cb.dataset.key, set = sel(k);
        if (cb.checked) set.add(cb.value); else set.delete(cb.value);
        setSel(k, set); if (k === "author") state.list = ""; state.shown = 72; render();
      });
      el.addEventListener("click", (e) => { const c = e.target.closest(".mclear"); if (c) { e.preventDefault(); state[c.dataset.key] = ""; state.shown = 72; render(); } });
      el.addEventListener("toggle", () => { if (el.open) [els.year, els.author, els.diff].forEach((o) => { if (o !== el) o.open = false; }); });
    });
    document.addEventListener("click", (e) => { if (!e.target.closest(".msel")) [els.year, els.author, els.diff].forEach((o) => { o.open = false; }); });
    els.sort.addEventListener("change", () => { state.sort = els.sort.value; if (state.sort === "aleatorio") seed = Date.now() % 100000; render(); });
    els.hide.addEventListener("change", () => { state.hideSolved = els.hide.checked; render(); });
    const resetAll = () => { Object.assign(state, { q: "", topic: "", year: "", author: "", list: "", diff: "", sort: "recentes", hideSolved: false, shown: 72 }); els.q.value = ""; $(".search").classList.remove("has-q"); render(); };
    els.reset.addEventListener("click", resetAll);
    els.listTag.addEventListener("click", (e) => { if (e.target.closest(".x")) { state.list = ""; render(); } });
    $$("nav.views button").forEach((b) => b.addEventListener("click", () => { state.view = b.dataset.view; render(); window.scrollTo({ top: 0 }); }));
    $("#randomBtn").addEventListener("click", () => random({ reshuffle: true }));
    els.grid.addEventListener("click", (e) => {
      if (e.target.closest("#moreBtn")) { state.shown += 72; renderGrid(); return; }
      if (e.target.closest("#emptyReset")) { resetAll(); return; }
      const card = e.target.closest(".card"); if (!card) return;
      if (e.target.closest(".solve")) { toggleSolved(card.dataset.id); return; }
      if (e.target.closest(".versions")) { closeDetail(); goToGroup(e.target.closest(".versions").dataset.group); return; }
      if (e.target.closest("a.open")) return;   // let the link open the PDF
      openDetail(card.dataset.id);
    });
    els.grid.addEventListener("keydown", (e) => { const card = e.target.closest(".card"); if (card && e.target === card && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); openDetail(card.dataset.id); } });
    els.years.addEventListener("click", (e) => { const b = e.target.closest("button[data-list]"); if (!b) return; const l = lists[b.dataset.list]; Object.assign(state, { view: "problemas", list: l.id, author: "", year: "", topic: "", q: "", shown: 72 }); els.q.value = ""; render(); window.scrollTo({ top: 0 }); });
    $("#closeBtn").addEventListener("click", closeDetail); els.scrim.addEventListener("click", closeDetail);
    $("#prevBtn").addEventListener("click", () => nav(-1)); $("#nextBtn").addEventListener("click", () => nav(1));
    els.similar.addEventListener("click", (e) => { const b = e.target.closest("[data-open]"); if (b) openDetail(b.dataset.open, { scroll: true }); });
    $(".pmeta", els.panel).addEventListener("click", (e) => { const b = e.target.closest(".versions"); if (b) { closeDetail(); goToGroup(b.dataset.group); } });
    els.groups.addEventListener("click", (e) => { const b = e.target.closest("[data-open]"); if (b) openDetail(b.dataset.open); });
    $("#panelSolve").addEventListener("click", () => toggleSolved(state.open));
    $("#panelRandom").addEventListener("click", random);
    document.addEventListener("keydown", (e) => {
      const typing = /^(INPUT|SELECT|TEXTAREA)$/.test(document.activeElement?.tagName);
      if (e.key === "Escape" && $("#filters").classList.contains("open")) { setFiltersOpen(false); return; }
      if (e.key === "Escape" && [els.year, els.author, els.diff].some((o) => o.open)) { [els.year, els.author, els.diff].forEach((o) => { o.open = false; }); return; }
      if (e.key === "Escape") { if (state.open) closeDetail(); else if (typing) document.activeElement.blur(); return; }
      if (typing) return;
      if (e.key === "/") { e.preventDefault(); els.q.focus(); els.q.select(); }
      else if (e.key === "r" && !e.metaKey && !e.ctrlKey) random();
      else if (state.open && (e.key === "ArrowRight" || e.key === "j")) nav(1);
      else if (state.open && (e.key === "ArrowLeft" || e.key === "k")) nav(-1);
    });
    $("#fToggle").addEventListener("click", () => setFiltersOpen(!$("#filters").classList.contains("open")));
    ["#fClose", "#fScrim", "#fApply"].forEach((q) => $(q).addEventListener("click", () => setFiltersOpen(false)));
    const toTop = $("#toTop");
    const onScroll = () => { toTop.hidden = window.scrollY < 600; };
    window.addEventListener("scroll", onScroll, { passive: true }); onScroll();
    toTop.addEventListener("click", () => {
      if (matchMedia("(prefers-reduced-motion: reduce)").matches) { window.scrollTo(0, 0); return; }
      const y0 = window.scrollY, t0 = performance.now(), dur = Math.min(600, 250 + y0 / 12);
      let started = false;
      const step = (t) => { started = true; const k = Math.min(1, (t - t0) / dur); window.scrollTo(0, Math.round(y0 * Math.pow(1 - k, 3))); if (k < 1) requestAnimationFrame(step); };
      requestAnimationFrame(step);
      setTimeout(() => { if (!started) window.scrollTo(0, 0); }, 200);   // sem quadros de animação (aba em segundo plano), pula direto
    });
    window.addEventListener("hashchange", () => { const before = JSON.stringify(state); readHash(); if (JSON.stringify(state) !== before) { els.q.value = state.q; render(); if (state.open) openDetail(state.open); else closeDetail(); } });
  }
  document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", init) : init();
})();
