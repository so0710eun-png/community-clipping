// 커뮤니티 이슈 클리핑 — 화면 동작 (posts.json을 읽어 목록을 그림)
const TABS = { all: "전체", saved: "★ 저장" };
const store = (() => { try { return window.localStorage; } catch { return null; } })();
const remember = (k, v) => { try { store && store.setItem(k, v); } catch {} };
const recall = (k, d) => { try { return (store && store.getItem(k)) || d; } catch { return d; } };

const state = {
  posts: [], names: {}, sourcesInfo: {}, hidden: {},
  tab: recall("tab", "all"),
  source: recall("source", "ALL"),
  sort: recall("sort", "heat"),
  period: recall("period", "24"),
  showLow: recall("showLow", "0") === "1",
  q: "",
};

// ── 저장(별표): 이 브라우저에만 보관 ─────────────────────────
const loadSaved = () => { try { return JSON.parse(recall("saved", "{}")) || {}; } catch { return {}; } };
let saved = loadSaved();
const persistSaved = () => remember("saved", JSON.stringify(saved));
const SAVE_FIELDS = ["id", "source", "board", "title", "url", "views", "likes", "comments", "published"];
function toggleSave(id) {
  if (saved[id]) delete saved[id];
  else {
    const p = state.posts.find((x) => x.id === id);
    if (!p) return;
    saved[id] = Object.fromEntries(SAVE_FIELDS.map((k) => [k, p[k]]));
    saved[id].savedAt = new Date().toISOString();
  }
  persistSaved();
  render();
}
const savedList = () => Object.values(saved).sort((a, b) => b.savedAt.localeCompare(a.savedAt));

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const highlight = (text, q) => {
  const safe = esc(text);
  if (!q) return safe;
  const re = new RegExp(esc(q).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi");
  return safe.replace(re, (m) => `<mark>${m}</mark>`);
};
const fmtTime = (iso) => {
  const diff = (Date.now() - new Date(iso)) / 36e5;
  if (diff < 1) return `${Math.max(1, Math.floor(diff * 60))}분 전`;
  if (diff < 24) return `${Math.floor(diff)}시간 전`;
  return new Date(iso).toLocaleDateString("ko-KR", { month: "short", day: "numeric" });
};
const fmtN = (n) => (n >= 10000 ? `${(n / 10000).toFixed(1)}만` : (n || 0).toLocaleString("ko-KR"));
const srcName = (s) => state.names[s] || s;

const inPeriod = (p) => Date.now() - new Date(p.published) <= Number(state.period) * 36e5;
const inSource = (p) => state.source === "ALL" || p.source === state.source;
const matches = (p) => {
  if (!state.q) return true;
  return [p.title, p.board, srcName(p.source)].join(" ").toLowerCase().includes(state.q.toLowerCase());
};

function groupStories(list) {
  const map = new Map();
  for (const p of list) {
    const key = p.cluster || p.id;
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(p);
  }
  return [...map.values()].map((items) => {
    items.sort((x, y) => (y.pct || 0) - (x.pct || 0));
    const latest = items.reduce((m, x) => (x.published > m ? x.published : m), items[0].published);
    return { main: items[0], others: items.slice(1), latest, heat: items[0].heat || 0, score: items[0].score || 1 };
  });
}

function storiesFor(tab) {
  if (tab === "saved") {
    return savedList().filter((p) => inSource(p) && matches(p))
      .map((p) => ({ main: p, others: [], latest: p.published, heat: 0, score: 0, savedAt: p.savedAt }));
  }
  return groupStories(state.posts.filter((p) => inSource(p) && inPeriod(p) && matches(p) && (state.showLow || !p.low)));
}

function clippingText() {
  return savedList().map((p, i) =>
    `${i + 1}. [${srcName(p.source)}${p.board ? "·" + p.board : ""}] ${p.title}\n` +
    `   조회 ${fmtN(p.views)} · 추천 ${fmtN(p.likes)} · 댓글 ${fmtN(p.comments)} (${new Date(p.published).toLocaleString("ko-KR")})\n` +
    `   ${p.url}`).join("\n\n");
}

function renderHeader() {
  const info = Object.entries(state.sourcesInfo).map(([k, v]) =>
    v.ok ? esc(v.name) : `<span class="bad">${esc(v.name)}(수집 실패)</span>`).join(" · ");
  const hiddenN = Object.values(state.hidden).reduce((a, b) => a + b, 0);
  $("#status").innerHTML = `${info}${hiddenN ? ` · 걸러낸 글 ${hiddenN}건` : ""}`;
}

function renderTabs() {
  $("#tabs").innerHTML = Object.entries(TABS).map(([code, label]) =>
    `<button role="tab" data-t="${code}" class="${state.tab === code ? "on" : ""}" aria-selected="${state.tab === code}">
      ${label}<span class="n">${storiesFor(code).length}</span></button>`).join("");
  const srcs = { ALL: "모든 커뮤니티", ...state.names };
  $("#sources").innerHTML = Object.entries(srcs).map(([code, label]) =>
    `<button data-s="${code}" class="${state.source === code ? "on" : ""}">${esc(label)}</button>`).join("");
}

function card({ main: p, others, score, savedAt }) {
  const q = state.q;
  const on = !!saved[p.id];
  return `<article class="card">
    <div class="meta"><span class="src">${esc(srcName(p.source))}</span>${p.board ? `<span>${highlight(p.board, q)}</span>` : ""}
      <time datetime="${esc(p.published)}">${fmtTime(p.published)}</time>
      <span>조회 ${fmtN(p.views)} · 추천 ${fmtN(p.likes)} · 댓글 ${fmtN(p.comments)}</span>
      <button class="star ${on ? "on" : ""}" data-save="${esc(p.id)}" aria-pressed="${on}" title="${on ? "저장 취소" : "저장하기"}">${on ? "★" : "☆"}</button></div>
    <h2><a href="${esc(p.url)}" target="_blank" rel="noopener noreferrer">${highlight(p.title, q)}</a></h2>
    ${score ? `<div class="score s${score}" title="화제성">${score}<small>화제</small></div>` : ""}
    ${savedAt ? `<p class="saved-note">${new Date(savedAt).toLocaleString("ko-KR", { dateStyle: "medium", timeStyle: "short" })} 저장</p>` : ""}
    ${p.reason && !savedAt ? `<p class="reason">${esc(p.reason)}</p>` : ""}
    ${others.length ? `<details class="related"><summary>같은 이야기 ${others.length}건 더 보기</summary><ul>${
      others.map((o) => `<li><span class="src">${esc(srcName(o.source))}</span> ·
        <a href="${esc(o.url)}" target="_blank" rel="noopener noreferrer">${highlight(o.title, q)}</a>
        <span class="status">조회 ${fmtN(o.views)} · 댓글 ${fmtN(o.comments)}</span></li>`).join("")
    }</ul></details>` : ""}
  </article>`;
}

function renderList() {
  const isSaved = state.tab === "saved";
  const stories = storiesFor(state.tab);
  if (!isSaved) {
    stories.sort(state.sort === "heat"
      ? (a, b) => b.heat - a.heat || b.latest.localeCompare(a.latest)
      : (a, b) => b.latest.localeCompare(a.latest));
  }
  const nPosts = stories.reduce((n, s) => n + 1 + s.others.length, 0);
  $("#count").textContent = isSaved ? `저장한 글 ${stories.length}건` : `이야기 ${stories.length}개 · 글 ${nPosts}건`;
  if (!stories.length) {
    $("#list").innerHTML = `<p class="empty">${isSaved ? "아직 저장한 글이 없습니다. 카드의 ☆를 눌러 저장하세요." : "조건에 맞는 글이 없습니다."}</p>`;
    return;
  }
  const toolbar = isSaved ? `<div class="toolbar"><button id="copyClip">📋 클리핑 복사</button><button id="clearSaved">모두 지우기</button></div>` : "";
  $("#list").innerHTML = toolbar + stories.map(card).join("");
}

function render() { renderHeader(); renderTabs(); renderList(); }

function bind() {
  $("#tabs").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-t]");
    if (b) { state.tab = b.dataset.t; remember("tab", state.tab); render(); }
  });
  $("#sources").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-s]");
    if (b) { state.source = b.dataset.s; remember("source", state.source); render(); }
  });
  $("#list").addEventListener("click", async (e) => {
    const star = e.target.closest("button[data-save]");
    if (star) { toggleSave(star.dataset.save); return; }
    if (e.target.id === "copyClip") {
      const text = clippingText();
      try { await navigator.clipboard.writeText(text); e.target.textContent = "✅ 복사됨"; }
      catch { window.prompt("아래 내용을 복사하세요 (Ctrl+C)", text); }
      return;
    }
    if (e.target.id === "clearSaved" && window.confirm("저장한 글을 모두 지울까요?")) {
      saved = {}; persistSaved(); render();
    }
  });
  document.querySelectorAll(".seg button").forEach((b) => {
    b.classList.toggle("on", b.dataset.sort === state.sort);
    b.addEventListener("click", () => {
      state.sort = b.dataset.sort; remember("sort", state.sort);
      document.querySelectorAll(".seg button").forEach((x) => x.classList.toggle("on", x === b));
      renderList();
    });
  });
  const period = $("#period");
  period.value = state.period;
  period.addEventListener("change", () => { state.period = period.value; remember("period", state.period); render(); });
  const low = $("#showLow");
  low.checked = state.showLow;
  low.addEventListener("change", () => { state.showLow = low.checked; remember("showLow", low.checked ? "1" : "0"); render(); });
  let t;
  $("#q").addEventListener("input", (e) => {
    clearTimeout(t);
    t = setTimeout(() => { state.q = e.target.value.trim(); render(); }, 150);
  });
}

async function init() {
  bind();
  try {
    const res = await fetch("posts.json", { cache: "no-cache" });
    const data = await res.json();
    state.posts = data.posts || [];
    state.sourcesInfo = data.sources || {};
    state.hidden = data.hidden || {};
    state.names = Object.fromEntries(Object.entries(state.sourcesInfo).map(([k, v]) => [k, v.name]));
    if (data.updated) {
      $("#updated").textContent = `· 마지막 갱신 ${new Date(data.updated).toLocaleString("ko-KR", { dateStyle: "medium", timeStyle: "short" })}`;
    }
  } catch {
    $("#list").innerHTML = `<p class="empty">데이터를 불러오지 못했습니다.</p>`;
    return;
  }
  render();
}

init();
