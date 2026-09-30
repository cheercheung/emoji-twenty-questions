/* Emoji 二十问 前端：自动单局，三列（Guess / Judge / Question log）+ overview */
const $ = (id) => document.getElementById(id);
const api = async (path, opts = {}) => {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : `HTTP ${res.status}`);
  return data;
};
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

const I18N = {
  zh: {
    appName: "Emoji 二十问",
    guesserModel: "Guess 模型",
    judgeModel: "Judge 模型",
    secretEmoji: "隐藏 emoji",
    random: "随机",
    start: "开始",
    record: "录制视频（结束后自动生成 20 秒 9:16 MP4）",
    rendering: (p) => `正在生成视频… ${p}%`,
    download: "下载视频",
    watermark: "开源产品来自：林悅己",
    videoFailed: "视频生成失败：",
    hint: "Judge 只看到隐藏 emoji 和当前问题，并且只能回答 Yes 或 No。Guess 模型永远看不到答案。",
    guessEyebrow: "Guess · 猜测模型",
    judgeEyebrow: "Judge · 裁判模型",
    logEyebrow: "Question log",
    turn: "回合",
    thinking: "思考中…",
    judging: "回答中…",
    running: "进行中",
    solved: "已猜中",
    failed: "未猜中",
    error: "出错",
    won: (n) => `第 ${n} 回合猜中`,
    lost: (n) => `${n} 回合用完，没有猜中`,
    hidden: "答案在对局结束后公布",
    callFailed: "模型调用失败",
    again: "再来一局",
    retry: "重试",
    giveUp: "放弃这局",
    overview: "Overview",
    colModel: "模型",
    colCalls: "调用",
    colTime: "用时",
    colTokens: "Tokens",
    colCost: "花费",
    rowGuess: "Guess",
    rowJudge: "Judge",
    rowTotal: "Total",
    costNote: "花费是 EvoLink 的真实扣费：每次调用前后查询 /v1/credits 取差值，美元按 1 credit ≈ $0.0147 折算。",
    estNote: (n) => `其中 ${n} 次调用没取到真实扣费，按 token 单价估算。`,
    checkTip: "猜测由后端规则直接判定，不调用 Judge 模型",
    noKey: "尚未配置 EVOLINK_API_KEY：请在 .env 中填入密钥，然后重启服务。",
    initFailed: "初始化失败：",
  },
  en: {
    appName: "Emoji Twenty Questions",
    guesserModel: "Guess model",
    judgeModel: "Judge model",
    secretEmoji: "Secret emoji",
    random: "Random",
    start: "Start",
    record: "Record video (a 20-second 9:16 MP4 is made when the game ends)",
    rendering: (p) => `Rendering video… ${p}%`,
    download: "Download video",
    watermark: "Opensourced by Cheer Lin",
    videoFailed: "Video failed: ",
    hint: "The judge sees only the secret emoji and the current question, and may answer only Yes or No. The guess model never sees the answer.",
    guessEyebrow: "Guess model",
    judgeEyebrow: "Judge model",
    logEyebrow: "Question log",
    turn: "Turn",
    thinking: "thinking…",
    judging: "answering…",
    running: "Running",
    solved: "Solved",
    failed: "Not solved",
    error: "Error",
    won: (n) => `Solved on turn ${n}`,
    lost: (n) => `All ${n} turns used, not solved`,
    hidden: "The answer is revealed when the game ends",
    callFailed: "Model call failed",
    again: "Play again",
    retry: "Retry",
    giveUp: "Abandon game",
    overview: "Overview",
    colModel: "Model",
    colCalls: "Calls",
    colTime: "Time",
    colTokens: "Tokens",
    colCost: "Cost",
    rowGuess: "Guess",
    rowJudge: "Judge",
    rowTotal: "Total",
    costNote: "Cost is what EvoLink actually charged: the difference in /v1/credits before and after each call, converted at 1 credit ≈ $0.0147.",
    estNote: (n) => `${n} call(s) could not be read from billing and were estimated from token prices.`,
    checkTip: "Guesses are checked by a backend rule, not by the judge model",
    noKey: "EVOLINK_API_KEY is not set. Add it to .env and restart the server.",
    initFailed: "Failed to initialise: ",
  },
};

let lang = "zh";
try { lang = localStorage.getItem("lang") === "en" ? "en" : "zh"; } catch (_) {}
const t = (k, ...a) => (typeof I18N[lang][k] === "function" ? I18N[lang][k](...a) : I18N[lang][k]);

let META = null;
let EMOJIS = [];
const state = { game: null, running: false, rec: null };

// ---------- 格式化 ----------
const secs = (ms) => (ms == null ? "—" : (ms / 1000).toFixed(1));
const rowMs = (ms) => (ms == null ? "—" : `${secs(ms)} s`);
const bigSecs = (ms) => `${secs(ms || 0)}<small>s</small>`;
const money = (x) => `$${(x || 0).toFixed(x >= 1 ? 2 : 4)}`;
const tokens = (n) => (n >= 1000 ? `${(n / 1000).toFixed(1)}<small>k</small>` : `${n || 0}`);
const modelOf = (id) => META.models.find((x) => x.id === id) || { id, label: id };
const emojiName = (e) => (EMOJIS.find((x) => x.emoji.replace(/️/g, "") === e) || {}).name || "";

// ---------- 语言 ----------
function applyLang() {
  document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
  document.querySelectorAll("[data-i18n]").forEach((el) => (el.textContent = t(el.dataset.i18n)));
  document.querySelectorAll(".lang button").forEach((b) => b.classList.toggle("active", b.dataset.lang === lang));
  const first = $("emoji").querySelector("option");
  if (first) first.textContent = t("random");
  $("title").textContent = t("appName");
  if (META) {
    $("banner").textContent = t("noKey");
    if (state.game) draw();
    else document.title = t("appName");
  }
}

// ---------- 初始化 ----------
async function init() {
  [META, { emojis: EMOJIS }] = await Promise.all([api("/api/models"), api("/api/emojis")]);
  if (!META.apiKeyConfigured) $("banner").classList.remove("hidden");
  const opts = META.models.map((m) => `<option value="${m.id}">${esc(m.label)} (${m.id})</option>`).join("");
  $("model").innerHTML = opts;
  $("judge").innerHTML = opts;
  $("judge").value = META.defaultJudge;
  $("emoji").innerHTML = `<option value=""></option>` + EMOJIS.map((e) => `<option value="${e.emoji}">${e.emoji} ${esc(e.name)}</option>`).join("");
  document.querySelectorAll(".lang button").forEach((b) =>
    b.addEventListener("click", () => {
      lang = b.dataset.lang;
      try { localStorage.setItem("lang", lang); } catch (_) {}
      applyLang();
    })
  );
  $("start").onclick = start;
  applyLang();
  // ?autostart=1：打开页面即用默认选项开始一局（演示 / 截图用）
  if (new URLSearchParams(location.search).get("autostart")) start();
}

// ---------- 渲染 ----------
const chip = (action) => `<span class="chip ${action}">${action}()</span>`;
const yn = (yes) => `<span class="yn ${yes ? "yes" : "no"}">${yes ? "Yes" : "No"}</span>`;
const spin = `<span class="spinner"></span>`;

function draw() {
  const g = state.game;
  const playing = g.status === "playing";
  const gm = modelOf(g.model);
  const jm = modelOf(g.judgeModel);
  document.title = `${t("appName")} · ${gm.label} / ${jm.label}`;

  $("guess-name").textContent = gm.label;
  $("guess-id").textContent = gm.id;
  $("judge-name").textContent = jm.label;
  $("judge-id").textContent = jm.id;
  $("turns").textContent = g.turnsUsed;
  $("max").textContent = g.maxTurns;

  // --- 轨迹：每行 = 序号 · 动作 · 内容 · Yes/No · Guess 用时 · Judge 用时 · 合计 ---
  const rows = g.history.map((h) => {
    const isAsk = h.action === "ask";
    const yes = isAsk ? h.answer === "yes" : !!h.correct;
    const text = isAsk ? esc(h.text) : `${esc(h.text)} ${esc(emojiName(h.text))}?`;
    // 猜测由后端规则直接判定，不调用 Judge，所以 Judge 用时为空
    const judgeMs = isAsk ? rowMs(h.answerMs) : `<span title="${esc(t("checkTip"))}">—</span>`;
    const cost = (h.guessCost || 0) + (h.judgeCost || 0);
    const costTip = `Guess ${money(h.guessCost)} + Judge ${money(h.judgeCost)}`;
    return `<li><span class="n">${h.turn}</span>${chip(h.action)}<span class="txt">${text}</span>${yn(yes)}
      <span class="ms">${rowMs(h.modelMs)}</span><span class="ms">${judgeMs}</span><span class="ms tot">${rowMs((h.modelMs || 0) + (h.answerMs || 0))}</span><span class="ms cost" title="${costTip}">${money(cost)}</span></li>`;
  });
  const next = g.turnsUsed + 1;
  if (playing && g.pending) {
    const p = g.pending; // Guess 已提问，等 Judge 回答
    rows.push(`<li><span class="n">${next}</span>${chip("ask")}<span class="txt">${esc(p.text)}</span><span class="yn"></span>
      <span class="ms">${rowMs(p.modelMs)}</span><span class="ms">${spin}</span><span class="ms tot"></span><span class="ms cost"></span></li>`);
  } else if (playing) {
    rows.push(`<li><span class="n">${next}</span><span class="chip-h"></span><span class="txt wait">${spin}${t("thinking")}</span></li>`);
  }
  $("rows").innerHTML = rows.join("");

  // --- 状态 ---
  const st = { playing: "running", won: "solved", lost: "failed", error: "error" }[g.status];
  $("status").className = `status ${playing ? "running" : g.status}`;
  $("status").textContent = t(st);

  // --- 答案 ---
  const reveal = $("reveal");
  if (g.status === "won" || g.status === "lost") {
    reveal.innerHTML = `<div class="big">${g.secretEmoji}</div><div class="name">${esc(g.secretName || "")}</div>
      <div class="verdict">${g.status === "won" ? t("won", g.turnsUsed) : t("lost", g.maxTurns)}</div>
      <div class="btns"><button class="ghost" id="_again">${t("again")}</button></div>`;
    $("_again").onclick = reset;
  } else if (g.status === "error") {
    reveal.innerHTML = `<div class="big">⚠️</div><div class="name">${t("callFailed")}</div><div class="err">${esc(g.error)}</div>
      <div class="btns"><button class="ghost" id="_retry">${t("retry")}</button><button class="ghost" id="_again">${t("giveUp")}</button></div>`;
    $("_retry").onclick = retry;
    $("_again").onclick = reset;
  } else {
    reveal.innerHTML = `<div class="big">🙈</div><div class="verdict">${t("hidden")}</div>`;
  }

  // --- overview：Guess / Judge / Total 三行 ---
  const s = g.stats || { guess: {}, judge: {}, total: {} };
  const row = (cls, role, m, d) => `<tr class="${cls}"><td class="role">${role}</td>
    <td class="model">${m ? `<b>${esc(m.label)}</b><span>${esc(m.id)}</span>` : ""}</td>
    <td class="num">${d.calls || 0}</td>
    <td class="num">${bigSecs(d.ms)}</td>
    <td class="num">${tokens((d.inputTokens || 0) + (d.outputTokens || 0))}</td>
    <td class="num">${money(d.cost)}<span>${(d.credits || 0).toFixed(4)} credits</span></td></tr>`;
  $("overview-rows").innerHTML = row("", t("rowGuess"), gm, s.guess) + row("", t("rowJudge"), jm, s.judge) + row("total", t("rowTotal"), null, s.total);
  const est = s.total.estimatedCalls || 0;
  $("cost-note").textContent = t("costNote") + (est ? " " + t("estNote", est) : "");
  record();
}

// ---------- 录制 ----------
// 每次重绘记一张快照；对局结束后自动导出视频
function record() {
  const rec = state.rec;
  if (!rec || rec.done) return;
  Recorder.snap(rec, state.game);
  if (state.game.status === "won" || state.game.status === "lost") {
    rec.done = true;
    exportVideo(rec);
  }
}

async function exportVideo(rec) {
  const box = $("video");
  const mine = () => state.rec === rec; // 期间没有重开或放弃
  box.innerHTML = `<p class="hint">${spin} <span id="_vp">${t("rendering", 0)}</span></p>`;
  try {
    const v = await Recorder.render(rec, { t, modelOf, emojiName }, (p) => {
      if (mine()) $("_vp").textContent = t("rendering", Math.round(p * 100));
    });
    if (!mine()) return;
    box.innerHTML = `<video src="${v.url}" controls autoplay muted loop playsinline></video>
      <div class="btns"><a class="ghost" href="${v.url}" download="${esc(v.filename)}">${t("download")}</a></div>
      <p class="hint">recordings/${esc(v.filename)}</p>`;
  } catch (e) {
    if (mine()) box.innerHTML = `<p class="err">${t("videoFailed")}${esc(e.message)}</p>`;
  }
}

// ---------- 对局流程 ----------
async function start() {
  $("setup").classList.add("hidden");
  $("game").classList.remove("hidden");
  state.game = { status: "playing", turnsUsed: 0, maxTurns: META.maxTurns, history: [], pending: null, model: $("model").value, judgeModel: $("judge").value };
  state.running = true;
  state.rec = $("record").checked ? Recorder.create() : null;
  $("video").innerHTML = "";
  draw();
  try {
    state.game = await api("/api/games", {
      method: "POST",
      body: { model: $("model").value, mode: "auto", judgeModel: $("judge").value, secretEmoji: $("emoji").value || null, language: lang },
    });
  } catch (e) {
    state.game = { ...state.game, status: "error", error: e.message };
  }
  draw();
  await loop();
}

// 每次 auto-step 只做一件事：Judge 回答，或 Guess 给出下一动作
async function loop() {
  while (state.running && state.game.status === "playing") {
    const id = state.game.id;
    let next;
    try {
      next = await api(`/api/games/${id}/auto-step`, { method: "POST", body: { language: lang } });
    } catch (e) {
      next = { ...state.game, status: "error", error: e.message };
    }
    if (!state.game || state.game.id !== id) return; // 已放弃或开了新局
    state.game = next;
    draw();
  }
}

async function retry() {
  const g = state.game;
  if (!g.id) return reset();
  state.game = { ...g, status: "playing", error: null };
  draw();
  try {
    state.game = await api(`/api/games/${g.id}/next`, { method: "POST" });
  } catch (e) {
    state.game = { ...g, status: "error", error: e.message };
  }
  draw();
  await loop();
}

function reset() {
  state.running = false;
  state.game = null;
  state.rec = null;
  $("video").innerHTML = "";
  $("game").classList.add("hidden");
  $("setup").classList.remove("hidden");
  document.title = t("appName");
}

init().catch((e) => {
  $("banner").textContent = I18N[lang].initFailed + e.message;
  $("banner").classList.remove("hidden");
});
