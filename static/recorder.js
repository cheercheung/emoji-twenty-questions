/* 对局录制：记下每次状态变化，结束后把整个过程按时间轴压缩，逐帧画到 9:16 画布，交给后端 ffmpeg 编码成 20 秒 MP4 */
const Recorder = (() => {
  const W = 1080, H = 1920, FPS = 30;
  const SECONDS = 20;       // 成片总时长
  const PLAY_SECONDS = 16;  // 前 16 秒加速回放全过程，其余时间停在结果画面
  const FRAMES = FPS * SECONDS;
  const BATCH = 30;         // 每次上传多少帧

  const C = { bg: "#f7f6f2", card: "#ecebe6", inset: "#e2e1db", ink: "#161513", muted: "#8a877f", line: "#dcdad3", err: "#b3261e", mark: "#6f6c65" };
  const SANS = 'system-ui, -apple-system, "PingFang SC", "Noto Sans SC", sans-serif';
  const MONO = 'ui-monospace, "SF Mono", Menlo, Consolas, monospace';
  const EMOJI = '"Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji", sans-serif';
  const font = (size, weight = 400, family = SANS) => `${weight} ${size}px ${family}`;

  // 版面（像素）
  const L = 72, R = 1008;                  // 卡片内容左右边界
  const ROWS_TOP = 272, ROWS_BOTTOM = 1300;
  const TXT_X = L + 174, TXT_W = 558, LINE_H = 40, ROW_PAD = 13;

  // ---------- 记录 ----------
  const create = () => ({ t0: performance.now(), snaps: [], done: false });
  const snap = (rec, game) => rec.snaps.push({ t: performance.now() - rec.t0, game: JSON.parse(JSON.stringify(game)) });

  // ---------- 文字 ----------
  const wrapCache = new Map();
  function wrap(ctx, text, maxW, maxLines) {
    const key = `${ctx.font}|${text}`;
    if (wrapCache.has(key)) return wrapCache.get(key);
    // 中日韩逐字可断行，其余按单词断行
    const toks = String(text).match(/[⺀-鿿＀-￯]|\s+|[^\s⺀-鿿＀-￯]+/g) || [];
    const fits = (s) => ctx.measureText(s).width <= maxW;
    let lines = [], cur = "";
    for (const tok of toks) {
      if (fits(cur + tok)) { cur += tok; continue; }
      if (cur.trim()) lines.push(cur.trimEnd());
      cur = /^\s+$/.test(tok) ? "" : tok;
    }
    if (cur.trim()) lines.push(cur.trimEnd());
    if (lines.length > maxLines) {
      lines = lines.slice(0, maxLines);
      let last = lines[maxLines - 1];
      while (last && !fits(last + "…")) last = last.slice(0, -1);
      lines[maxLines - 1] = last + "…";
    }
    if (!lines.length) lines = [""];
    wrapCache.set(key, lines);
    return lines;
  }

  function text(ctx, s, x, y, f, color, align = "left") {
    ctx.font = f;
    ctx.fillStyle = color;
    ctx.textAlign = align;
    ctx.fillText(s, x, y);
  }

  function hline(ctx, y, color = C.line, width = 2) {
    ctx.fillStyle = color;
    ctx.fillRect(L, y, R - L, width);
  }

  const secs = (ms) => ((ms || 0) / 1000).toFixed(1);
  const clock = (ms) => {
    const s = Math.floor(ms / 1000);
    return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
  };
  const money = (x) => `$${(x || 0).toFixed(x >= 1 ? 2 : 3)}`;
  const tokens = (n) => (n >= 1000 ? `${(n / 1000).toFixed(1)}k` : `${n || 0}`);
  const dots = (f) => ".".repeat(1 + (Math.floor(f / 8) % 3));

  // ---------- 单帧 ----------
  function paint(ctx, rec, f, env) {
    const { t, modelOf, emojiName } = env;
    const snaps = rec.snaps;
    const total = Math.max(snaps[snaps.length - 1].t, 1); // 真实总时长（毫秒）
    const vt = f / FPS;
    const real = Math.min(vt / PLAY_SECONDS, 1) * total;
    let g = snaps[0].game;
    for (const s of snaps) {
      if (s.t > real) break;
      g = s.game;
    }
    const playing = g.status === "playing" || g.status === "error";
    const gm = modelOf(g.model), jm = modelOf(g.judgeModel);

    ctx.textBaseline = "alphabetic";
    ctx.fillStyle = C.bg;
    ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = C.card;
    ctx.beginPath();
    ctx.roundRect(28, 28, W - 56, 1784, 36);
    ctx.fill();

    // --- 头部：模型、状态、真实用时与加速倍数 ---
    const st = { playing: "running", error: "running", won: "solved", lost: "failed" }[g.status];
    text(ctx, t("guessEyebrow").toUpperCase(), L, 104, font(22, 500, MONO), C.muted);
    text(ctx, `● ${t(st).toUpperCase()}`, R, 104, font(22, 500, MONO), playing ? C.muted : g.status === "lost" ? C.err : C.ink, "right");
    text(ctx, gm.label, L, 184, font(68, 700), C.ink);
    text(ctx, `${clock(real)} · ${(total / 1000 / PLAY_SECONDS).toFixed(1)}×`, R, 184, font(26, 500, MONO), C.muted, "right");
    text(ctx, `Judge · ${jm.label}`, L, 236, font(24, 400, MONO), C.muted);
    text(ctx, `${t("turn")} ${g.turnsUsed} / ${g.maxTurns}`, R, 236, font(24, 400, MONO), C.muted, "right");
    hline(ctx, ROWS_TOP - 2);

    // --- 提问记录：放不下时向上滚动，始终露出最新一行 ---
    const rows = g.history.map((h) => {
      const isAsk = h.action === "ask";
      return {
        n: h.turn,
        action: h.action,
        text: isAsk ? h.text : `${h.text.replace(/\uFE0F/g, "")}\uFE0F ${emojiName(h.text)}?`, // 补上变体选择符，保证按彩色 emoji 画
        yes: isAsk ? h.answer === "yes" : !!h.correct,
        ms: `${secs((h.modelMs || 0) + (h.answerMs || 0))} s`,
      };
    });
    if (g.status === "playing" && g.pending) rows.push({ n: g.turnsUsed + 1, action: "ask", text: g.pending.text, ms: dots(f) });
    else if (g.status === "playing") rows.push({ n: g.turnsUsed + 1, wait: t("thinking").replace(/…$/, "") + dots(f) });

    ctx.font = font(30);
    for (const r of rows) {
      r.lines = r.wait ? [r.wait] : wrap(ctx, r.text, TXT_W, 2);
      r.h = r.lines.length * LINE_H + ROW_PAD * 2;
    }
    const rowsH = rows.reduce((a, r) => a + r.h, 0);
    let y = ROWS_TOP - Math.max(0, rowsH - (ROWS_BOTTOM - ROWS_TOP));

    ctx.save();
    ctx.beginPath();
    ctx.rect(0, ROWS_TOP, W, ROWS_BOTTOM - ROWS_TOP);
    ctx.clip();
    for (const r of rows) {
      const base = y + ROW_PAD + 30;
      text(ctx, String(r.n), L + 30, base, font(22, 400, MONO), C.muted, "right");
      if (r.wait) {
        text(ctx, r.wait, TXT_X, base, font(26), C.muted);
      } else {
        ctx.fillStyle = C.inset;
        ctx.beginPath();
        ctx.roundRect(L + 46, y + ROW_PAD + 2, 112, 36, 8);
        ctx.fill();
        text(ctx, `${r.action}()`, L + 102, base - 3, font(21, 400, MONO), r.action === "guess" ? C.ink : C.muted, "center");
        r.lines.forEach((line, i) => text(ctx, line, TXT_X, base + i * LINE_H, font(30), C.ink));
        if (r.yes !== undefined) text(ctx, r.yes ? "Yes" : "No", R - 112, base, font(28, r.yes ? 700 : 400), r.yes ? C.ink : C.muted, "right");
        text(ctx, r.ms, R, base, font(22, 400, MONO), C.muted, "right");
      }
      hline(ctx, y + r.h - 2);
      y += r.h;
    }
    ctx.restore();

    // --- 答案：结束前遮住，结束后弹出 ---
    if (playing) {
      text(ctx, "🙈", W / 2, 1490, font(160, 400, EMOJI), C.ink, "center");
      text(ctx, t("hidden"), W / 2, 1580, font(26), C.muted, "center");
    } else {
      const p = Math.min(Math.max((vt - PLAY_SECONDS) / 0.4, 0), 1);
      const scale = 0.6 + 0.4 * (1 - (1 - p) ** 3);
      ctx.save();
      ctx.translate(W / 2, 1430);
      ctx.scale(scale, scale);
      text(ctx, `${g.secretEmoji}\uFE0F`, 0, 70, font(200, 400, EMOJI), C.ink, "center");
      ctx.restore();
      text(ctx, g.secretName || "", W / 2, 1580, font(44, 700), C.ink, "center");
      text(ctx, g.status === "won" ? t("won", g.turnsUsed) : t("lost", g.maxTurns), W / 2, 1626, font(26), C.muted, "center");
    }

    // --- 合计 ---
    hline(ctx, 1660);
    const s = (g.stats && g.stats.total) || {};
    const cells = [
      [t("colCalls"), `${s.calls || 0}`],
      [t("colTime"), `${secs(s.ms)}s`],
      [t("colCost"), money(s.cost)],
      [t("colTokens"), tokens((s.inputTokens || 0) + (s.outputTokens || 0))],
    ];
    cells.forEach(([label, value], i) => {
      const x = L + (i * (R - L)) / cells.length;
      text(ctx, label.toUpperCase(), x, 1706, font(20, 500, MONO), C.muted);
      text(ctx, value, x, 1776, font(58, 700), C.ink);
    });

    // --- 卡片外：左下应用名，右下水印 ---
    text(ctx, t("appName"), 28 + 8, 1874, font(24, 400, MONO), C.muted);
    text(ctx, t("watermark"), W - 28 - 8, 1874, font(30, 600), C.mark, "right");
  }

  // ---------- 导出 ----------
  async function call(path, opts) {
    const res = await fetch(path, { method: "POST", ...opts });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : `HTTP ${res.status}`);
    return data;
  }

  // 逐帧渲染并上传；返回 { url, filename }。onProgress 收到 0..1
  async function render(rec, env, onProgress = () => {}) {
    const canvas = document.createElement("canvas");
    canvas.width = W;
    canvas.height = H;
    const ctx = canvas.getContext("2d");
    const { id } = await call("/api/recordings", {
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ label: rec.snaps[0].game.model, fps: FPS, frames: FRAMES }),
    });
    let batch = [];
    for (let f = 0; f < FRAMES; f++) {
      paint(ctx, rec, f, env);
      batch.push(await new Promise((ok) => canvas.toBlob(ok, "image/jpeg", 0.92)));
      if (batch.length === BATCH || f === FRAMES - 1) {
        // JPEG 直接首尾相接，后端原样喂给 ffmpeg
        await call(`/api/recordings/${id}/frames`, { headers: { "Content-Type": "application/octet-stream" }, body: new Blob(batch) });
        batch = [];
        onProgress((f + 1) / FRAMES);
      }
    }
    return call(`/api/recordings/${id}/finish`);
  }

  return { create, snap, render, paint, W, H, FRAMES };
})();
