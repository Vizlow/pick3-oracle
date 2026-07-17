/* Pick 3 Oracle — dashboard logic. Vanilla JS, zero external requests. */
"use strict";

const REPO_URL = "https://github.com/Vizlow/pick3-oracle";

/* ---------------------------------------------------------------- helpers */
const $ = (sel, root) => (root || document).querySelector(sel);

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}

const fmtMoney = v => (v < 0 ? "-$" : "$") + Math.abs(v).toFixed(2);
const fmtMoneyAxis = v => (v < 0 ? "-$" : "$") + Math.round(Math.abs(v));
const fmtPct = (x, d) => (100 * x).toFixed(d == null ? 1 : d) + "%";
const sameCombo = (a, b) => a[0] === b[0] && a[1] === b[1] && a[2] === b[2];
const boxEq = (a, b) => String(a.slice().sort()) === String(b.slice().sort());
const PERIOD_NAME = { mid: "Midday", eve: "Evening" };

const TACTIC_ACRONYMS = { vtrac: "VTRAC", ttt: "TTT", hl: "HL", eo: "EO", sld: "SLD", pi: "Pi" };
function tacticName(key) {
  return key.split("_").map(w => TACTIC_ACRONYMS[w] || w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
}

function ballRow(combo, size, extraCls) {
  const row = el("span", "balls" + (size === "ball-xs" ? " balls-xs" : "") + (extraCls ? " " + extraCls : ""));
  for (const d of combo) row.appendChild(el("span", "ball " + size, String(d)));
  return row;
}

function fmtDrawDate(dateStr) {
  return new Intl.DateTimeFormat("en-US", { weekday: "short", month: "short", day: "numeric", timeZone: "UTC" })
    .format(new Date(dateStr + "T12:00:00Z"));
}

function splitDrawId(did) {
  return { date: did.slice(0, 10), period: did.slice(11) };
}

/* ------------------------------------------------- America/New_York time */
const ET_FMT = new Intl.DateTimeFormat("en-US", {
  timeZone: "America/New_York", hourCycle: "h23",
  year: "numeric", month: "2-digit", day: "2-digit",
  hour: "2-digit", minute: "2-digit", second: "2-digit",
});

function etParts(date) {
  const p = {};
  for (const part of ET_FMT.formatToParts(date)) p[part.type] = part.value;
  return p;
}

/* Epoch ms of an ET wall-clock time (converges across the EDT/EST offset). */
function etWallToEpoch(dateStr, hh, mm) {
  const want = Date.parse(`${dateStr}T${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}:00Z`);
  let guess = want;
  for (let i = 0; i < 3; i++) {
    const p = etParts(new Date(guess));
    const shown = Date.parse(`${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}:${p.second}Z`);
    if (shown === want) break;
    guess += want - shown;
  }
  return guess;
}

const DRAW_HM = { mid: [14, 30], eve: [22, 30] };
function drawEpoch(dateStr, period) {
  const hm = DRAW_HM[period];
  return etWallToEpoch(dateStr, hm[0], hm[1]);
}

/* Countdown: draws daily at 14:30 & 22:30 ET. */
function tickCountdown() {
  const p = etParts(new Date());
  const sec = (+p.hour) * 3600 + (+p.minute) * 60 + (+p.second);
  const MID = 14 * 3600 + 30 * 60, EVE = 22 * 3600 + 30 * 60;
  let label, remain;
  if (sec < MID) { label = "Midday 2:30 PM ET"; remain = MID - sec; }
  else if (sec < EVE) { label = "Evening 10:30 PM ET"; remain = EVE - sec; }
  else { label = "Midday 2:30 PM ET (tomorrow)"; remain = 86400 - sec + MID; }
  const h = Math.floor(remain / 3600), m = Math.floor((remain % 3600) / 60), s = remain % 60;
  $("#next-draw-label").textContent = label;
  $("#countdown-clock").textContent =
    `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

/* ---------------------------------------------------------------- fetch */
async function fetchJSON(name, optional) {
  try {
    const res = await fetch(`data/${name}?v=${Date.now()}`);
    if (!res.ok) throw new Error(`${name}: HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    if (optional) return null; // e.g. community.json may simply not exist yet
    throw err;
  }
}

/* ---------------------------------------------------------------- header */
function renderHeader(draws) {
  const dt = new Date(draws.updated_at);
  const s = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York", month: "short", day: "numeric",
    hour: "numeric", minute: "2-digit",
  }).format(dt);
  $("#updated-at").textContent = `data updated ${s} ET`;
}

/* --------------------------------------------------------------- NOW panel */
function renderNow(pred, community) {
  const { date, period } = splitDrawId(pred.draw_id);
  const lbl = $("#now-draw-label");
  lbl.innerHTML = "";
  lbl.append("5 picks for the ");
  lbl.appendChild(el("strong", null, `${PERIOD_NAME[period] || period} draw`));
  lbl.append(` · ${fmtDrawDate(date)} · `);
  lbl.appendChild(el("span", "mono", pred.draw_id));

  const row = $("#pick-row");
  row.innerHTML = "";
  pred.picks.forEach((pick, i) => {
    const card = el("div", "pick-card");
    const isTop = i === 0;
    card.appendChild(ballRow(pick, isTop ? "ball-lg" : "ball-md", isTop ? "top-pick-balls" : ""));
    card.appendChild(el("span", "pick-tag" + (isTop ? "" : " alt"), isTop ? "★ Top pick" : `#${i + 1}`));
    row.appendChild(card);
  });

  const pairs = $("#pairs-line");
  pairs.innerHTML = "";
  for (const [name, pr] of [["Front pair", pred.pairs.front], ["Back pair", pred.pairs.back]]) {
    const b = el("span", "pair-block");
    b.appendChild(el("span", null, name));
    b.appendChild(ballRow(pr, "ball-sm"));
    pairs.appendChild(b);
  }

  // Lock line. prediction.lock is optional — pipeline may attach {sha, committed_at, hours_before_draw}.
  const lock = pred.lock || null;
  const sha = lock && lock.sha ? lock.sha : null;
  let hrs = lock && lock.hours_before_draw != null ? lock.hours_before_draw : null;
  if (hrs == null && pred.generated_at) {
    hrs = Math.round((drawEpoch(date, period) - Date.parse(pred.generated_at)) / 36000) / 100;
  }
  const line = $("#lock-line");
  line.innerHTML = "";
  line.append("🔒 locked ");
  const a = el("a", null, sha ? sha.slice(0, 7) : "commit pending");
  a.href = sha ? `${REPO_URL}/commit/${sha}` : "#";
  if (sha) { a.target = "_blank"; a.rel = "noopener"; }
  line.appendChild(a);
  if (hrs != null) line.append(` · ${hrs} hrs before draw`);

  const tl = $("#tactics-line");
  tl.innerHTML = "";
  tl.append("Top tactics behind the top pick: ");
  (pred.explain && pred.explain.top_tactics_for_top_pick || []).forEach((k, i) => {
    if (i) tl.append(" ");
    tl.appendChild(el("span", "t", tacticName(k)));
  });
  tl.append(` · engine v${pred.engine_version}`);

  const cl = $("#community-line");
  if (community) {
    const n = (community.picks || community.entries || []).length;
    cl.textContent = `Community: ${n} member pick${n === 1 ? "" : "s"} loaded for this draw`;
  } else {
    cl.textContent = "Community picks: none published for this draw";
  }
}

/* --------------------------------------------------------------- scoreboard */
const SCORE_METRICS = [
  ["any_straight", "Any pick · Straight"],
  ["any_box", "Any pick · Box"],
  ["top_box", "Top pick · Box"],
  ["front_pair", "Top pick · Front pair"],
  ["back_pair", "Top pick · Back pair"],
  ["control_any_box", "Random control · Box"],
];

function renderScoreboard(stats) {
  const live = stats.scoreboard.live;
  const grid = $("#score-grid");
  grid.innerHTML = "";
  for (const [key, label] of SCORE_METRICS) {
    const m = live[key];
    if (!m) continue;
    const isControl = key === "control_any_box";
    const card = el("div", "score-card" + (isControl ? " control" : m.hits > 0 ? " hit" : ""));
    card.appendChild(el("div", "metric", label));
    card.appendChild(el("div", "big", String(m.hits)));
    const vs = el("div", "vs");
    if (m.baseline != null) {
      const beat = m.rate > m.baseline;
      const rateSpan = el("span", beat ? "beat" : "under", fmtPct(m.rate));
      vs.appendChild(rateSpan);
      vs.append(` vs ${fmtPct(m.baseline)} expected`);
    } else {
      vs.append(`${fmtPct(m.rate)} observed`);
    }
    card.appendChild(vs);
    const nLine = el("div", "n", `n = ${live.n_draws} live draws`);
    if (live.n_draws < 200) nLine.appendChild(el("span", "badge-small-sample", "small sample"));
    card.appendChild(nLine);
    grid.appendChild(card);
  }
}

/* --------------------------------------------------------------- P&L */
const SERIES_META = {
  all_box: { label: "All-5 Box", color: "#5b8cff" },
  all_straight: { label: "All-5 Straight", color: "#b18cff" },
  sb_top: { label: "Straight/Box top", color: "#2fd6c3" },
  pairs_mix: { label: "Pairs mix", color: "#ff8a5b" },
  random_control: { label: "Random control", color: "#8b95af", dash: "6 4" },
  house_edge_ref: { label: "House-edge ref", color: "#ff6371", dash: "2 4" },
};

function renderPnl(stats) {
  const pnl = stats.pnl;
  const keys = pnl.structures.concat(["random_control", "house_edge_ref"]);
  const hidden = new Set();
  $("#pnl-headline").textContent = `headline: ${SERIES_META[pnl.headline].label}`;

  function draw() {
    const series = [];
    for (const key of keys) {
      if (hidden.has(key)) continue;
      const meta = SERIES_META[key] || { label: key, color: "#8b95af" };
      const width = key === pnl.headline ? 3 : 1.6;
      const bt = pnl.backtest.series[key], lv = pnl.live.series[key];
      if (bt) series.push({ points: bt, color: meta.color, width, dash: meta.dash, opacity: 0.28 });
      if (lv) series.push({ points: lv, color: meta.color, width, dash: meta.dash });
    }
    Charts.lineChart($("#pnl-chart"), {
      series, height: 300, yFmt: fmtMoneyAxis,
      xStart: pnl.live.labels[0], xEnd: pnl.live.labels[pnl.live.labels.length - 1],
    });
  }

  const legend = $("#pnl-legend");
  legend.innerHTML = "";
  for (const key of keys) {
    const meta = SERIES_META[key] || { label: key, color: "#8b95af" };
    const item = el("span", "legend-item" + (key === pnl.headline ? " headline" : ""));
    const sw = el("span", "swatch");
    sw.style.borderTopColor = meta.color;
    if (meta.dash) sw.style.borderTopStyle = "dashed";
    item.appendChild(sw);
    item.append(meta.label);
    item.addEventListener("click", () => {
      hidden.has(key) ? hidden.delete(key) : hidden.add(key);
      item.classList.toggle("off", hidden.has(key));
      draw();
    });
    legend.appendChild(item);
  }
  draw();

  const tbody = $("#pnl-summary tbody");
  tbody.innerHTML = "";
  for (const key of pnl.structures.concat(["random_control"])) {
    const s = pnl.summary[key];
    if (!s) continue;
    const tr = el("tr");
    tr.appendChild(el("td", null, (SERIES_META[key] || { label: key }).label));
    const cells = [
      [fmtMoney(s.stake), ""],
      [fmtMoney(s.won), ""],
      [fmtMoney(s.net), s.net >= 0 ? "pos" : "neg"],
      [fmtPct(s.roi), s.roi >= 0 ? "pos" : "neg"],
      [fmtPct(s.win_rate), ""],
      [String(s.max_losing_streak), ""],
      [s.max_drawdown > 0 ? "-" + fmtMoney(s.max_drawdown).replace("$", "$") : fmtMoney(0), s.max_drawdown > 0 ? "neg" : ""],
    ];
    for (const [textVal, cls] of cells) tr.appendChild(el("td", ("num " + cls).trim(), textVal));
    tbody.appendChild(tr);
  }
}

/* --------------------------------------------------------------- ledger */
function badgeCell(grade) {
  const cell = el("td");
  let any = false;
  const add = (cls, label) => { cell.appendChild(el("span", "badge " + cls, label)); any = true; };
  if (grade.straight_hit) add("badge-str", "STR");
  if (grade.box_hit && grade.box_hit.pick_index != null) add("badge-box", "BOX");
  if (grade.top_pick && grade.top_pick.one_off) add("badge-oneoff", "1-OFF");
  if (grade.pair_hits && grade.pair_hits.front) add("badge-pair", "F-PAIR");
  if (grade.pair_hits && grade.pair_hits.back) add("badge-pair", "B-PAIR");
  if (!any) cell.appendChild(el("span", null, "—")).style.color = "var(--faint)";
  return cell;
}

function ledgerRow(entry) {
  const tr = el("tr");
  const { period } = splitDrawId(entry.draw_id);

  const idCell = el("td");
  idCell.appendChild(el("div", "mono", entry.draw_id));
  idCell.appendChild(el("span", "chip " + (entry.mode === "live" ? "chip-live" : "chip-bt"),
    entry.mode === "live" ? "LIVE" : "BT"));
  tr.appendChild(idCell);

  const perCell = el("td");
  perCell.appendChild(el("span", "chip " + (period === "mid" ? "chip-mid" : "chip-eve"), period.toUpperCase()));
  tr.appendChild(perCell);

  const picksCell = el("td");
  const wrap = el("div", "ledger-picks");
  const result = entry.result;
  entry.prediction.picks.forEach(pick => {
    let cls = "pick-group";
    if (sameCombo(pick, result)) cls += " win-straight";
    else if (boxEq(pick, result)) cls += " win-box";
    const g = el("span", cls);
    g.appendChild(ballRow(pick, "ball-xs"));
    wrap.appendChild(g);
  });
  picksCell.appendChild(wrap);
  tr.appendChild(picksCell);

  const resCell = el("td");
  resCell.appendChild(ballRow(result, "ball-sm", "result-balls"));
  for (const b of resCell.querySelectorAll(".ball")) b.classList.add("result-ball");
  tr.appendChild(resCell);

  tr.appendChild(badgeCell(entry.grade));

  const wonCell = el("td");
  const mini = el("div", "won-mini");
  for (const [tag, key] of [["S", "all_straight"], ["B", "all_box"], ["SB", "sb_top"], ["P", "pairs_mix"]]) {
    const won = entry.pnl[key].won;
    mini.appendChild(el("span", null, tag));
    mini.appendChild(el("span", "w" + (won > 0 ? " pos" : ""), won > 0 ? fmtMoney(won) : "·"));
  }
  wonCell.appendChild(mini);
  tr.appendChild(wonCell);

  const lockCell = el("td");
  const sha = entry.lock && entry.lock.sha;
  if (sha) {
    const a = el("a", "mono", sha.slice(0, 7));
    a.href = `${REPO_URL}/commit/${sha}`;
    a.target = "_blank";
    a.rel = "noopener";
    a.title = `committed ${entry.lock.hours_before_draw} hrs before draw`;
    lockCell.appendChild(a);
  } else {
    lockCell.appendChild(el("span", null, "—")).style.color = "var(--faint)";
  }
  tr.appendChild(lockCell);
  return tr;
}

function renderLedger(ledger) {
  const entries = ledger.entries.slice().reverse(); // newest first
  $("#ledger-count").textContent = `${entries.length} graded draws`;
  const tbody = $("#ledger-table tbody");
  const btn = $("#ledger-more");
  let shown = 0;
  const CHUNK = 50;
  function more() {
    const next = entries.slice(shown, shown + CHUNK);
    for (const e of next) tbody.appendChild(ledgerRow(e));
    shown += next.length;
    btn.hidden = shown >= entries.length;
  }
  btn.addEventListener("click", more);
  more();
}

/* --------------------------------------------------------------- charts */
const DIGITS = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"];

function renderCharts(stats) {
  const c = stats.charts;
  $("#charts-window").textContent = `window: last ${c.window} draws`;

  // Positional frequency — 3 bar groups vs the 10% line.
  const row = $("#chart-posfreq");
  row.innerHTML = "";
  c.positional_freq.forEach((values, p) => {
    const cell = el("div", "freq-cell");
    const holder = el("div");
    cell.appendChild(holder);
    cell.appendChild(el("div", "cap", `Position ${p + 1}`));
    row.appendChild(cell);
    const total = values.reduce((a, b) => a + b, 0);
    Charts.barChart(holder, { values, labels: DIGITS, color: "#5b8cff", ref: total / 10, refLabel: "10%" });
  });

  // Digit skips with median markers.
  Charts.barChart($("#chart-skips"), {
    values: c.digit_skips.any, labels: DIGITS, color: "#2fd6c3",
    markers: c.digit_skips.median_any, width: 340, height: 170,
  });

  // Pairs heatmaps with front/split/back tabs.
  const kinds = ["front", "split", "back"];
  const maxSkip = Math.max.apply(null, kinds.map(k => Math.max.apply(null, c.pairs_heat[k].map(r => Math.max.apply(null, r)))));
  $("#pairs-max-label").textContent = String(maxSkip);
  const tabs = $("#pairs-tabs");
  tabs.innerHTML = "";
  function showPairs(kind) {
    for (const b of tabs.children) b.classList.toggle("active", b.dataset.kind === kind);
    Charts.heatGrid($("#chart-pairs"), c.pairs_heat[kind], {
      xLabels: DIGITS, yLabels: DIGITS, corner: kind === "back" ? "2·3" : kind === "split" ? "1·3" : "1·2",
      colorFn: v => Charts.heatColor(maxSkip ? v / maxSkip : 0),
      titleFn: (r, cc, v) => `${kind} pair ${r}-${cc} · ${v} draws out`,
      showValues: false,
    });
  }
  for (const kind of kinds) {
    const b = el("button", "tab", kind);
    b.dataset.kind = kind;
    b.addEventListener("click", () => showPairs(kind));
    tabs.appendChild(b);
  }
  showPairs("front");

  // VTRAC mini-heatmaps.
  const vt = c.vtrac;
  const vMaxSkip = Math.max.apply(null, vt.pos_skips.map(r => Math.max.apply(null, r))) || 1;
  Charts.heatGrid($("#chart-vtrac-skips"), vt.pos_skips, {
    xLabels: ["v1", "v2", "v3", "v4", "v5"], yLabels: ["P1", "P2", "P3"], corner: "",
    colorFn: v => Charts.heatColor(v / vMaxSkip), showValues: true,
    titleFn: (r, cc, v) => `pos ${r + 1} vtrac ${cc + 1} · ${v} draws out`,
  });
  const vMaxFreq = Math.max.apply(null, vt.freq30.map(r => Math.max.apply(null, r))) || 1;
  Charts.heatGrid($("#chart-vtrac-freq"), vt.freq30, {
    xLabels: ["v1", "v2", "v3", "v4", "v5"], yLabels: ["P1", "P2", "P3"], corner: "",
    colorFn: v => Charts.heatColor(1 - v / vMaxFreq), showValues: true,
    titleFn: (r, cc, v) => `pos ${r + 1} vtrac ${cc + 1} · ${v} hits in 30`,
  });
  const last = $("#vtrac-last");
  last.innerHTML = "";
  last.append("Last draw vtrac:");
  last.appendChild(ballRow(vt.last, "ball-xs"));

  // Sum distribution.
  Charts.sumDist($("#chart-sums"), c.sum_dist.observed, c.sum_dist.theoretical);

  // Structure donut vs 72/27/1.
  const obs = c.structure.observed;
  const totalStruct = obs.single + obs.double + obs.triple;
  const segs = [
    { label: "Single", value: obs.single, color: "#5b8cff" },
    { label: "Double", value: obs.double, color: "#b18cff" },
    { label: "Triple", value: obs.triple, color: "#f6c453" },
  ];
  Charts.donut($("#chart-structure"), segs, { centerTop: String(totalStruct), centerBottom: "draws" });
  const legend = $("#structure-legend");
  legend.innerHTML = "";
  segs.forEach((s, i) => {
    const line = el("div");
    const sw = el("span", "sw");
    sw.style.background = s.color;
    line.appendChild(sw);
    const obsPct = totalStruct ? (100 * s.value / totalStruct).toFixed(1) : "0.0";
    line.append(`${s.label}: ${s.value} (${obsPct}%) · expected ${c.structure.expected_pct[i]}%`);
    legend.appendChild(line);
  });
}

/* --------------------------------------------------------------- tactics */
function renderTactics(weights) {
  const p = weights.params;
  $("#tactics-params").textContent = `α=${p.alpha} · τ=${p.tau} · floor=${p.floor_frac}`;
  const rows = $("#tactic-rows");
  rows.innerHTML = "";
  const keys = Object.keys(weights.tactics).sort((a, b) => weights.tactics[b].weight - weights.tactics[a].weight);
  const maxDev = Math.max(0.05, Math.max.apply(null, keys.map(k => Math.abs(weights.tactics[k].ewma - 0.5))));

  keys.forEach((key, i) => {
    const t = weights.tactics[key];
    const rowEl = el("div", "tactic-row");
    rowEl.appendChild(el("span", "rank", String(i + 1)));

    const name = el("span", "tname", tacticName(key));
    name.appendChild(el("span", "seen", `${t.draws_seen} draws seen`));
    rowEl.appendChild(name);

    const barWrap = el("div");
    const bar = el("div", "ewma-bar");
    bar.appendChild(el("div", "mid"));
    const dev = t.ewma - 0.5;
    const fill = el("div", "fill " + (dev >= 0 ? "up" : "down"));
    fill.style.width = `${Math.min(1, Math.abs(dev) / maxDev) * 48}%`;
    bar.appendChild(fill);
    barWrap.appendChild(bar);
    barWrap.appendChild(el("span", "ewma-val", `ewma ${t.ewma.toFixed(3)}`));
    rowEl.appendChild(barWrap);

    rowEl.appendChild(el("span", "tweight", fmtPct(t.weight)));

    const sparkWrap = el("div", "tspark");
    sparkWrap.appendChild(Charts.sparkline(t.spark, { color: dev >= 0 ? "#2fd6c3" : "#ff6371" }));
    rowEl.appendChild(sparkWrap);
    rows.appendChild(rowEl);
  });
}

/* --------------------------------------------------------------- boot */
async function boot() {
  tickCountdown();
  setInterval(tickCountdown, 1000);
  const [draws, prediction, ledger, weights, stats, community] = await Promise.all([
    fetchJSON("draws.json"),
    fetchJSON("prediction.json"),
    fetchJSON("ledger.json"),
    fetchJSON("weights.json"),
    fetchJSON("stats.json"),
    fetchJSON("community.json", true), // optional — 404 is fine
  ]);
  renderHeader(draws);
  renderNow(prediction, community);
  renderScoreboard(stats);
  renderPnl(stats);
  renderLedger(ledger);
  renderCharts(stats);
  renderTactics(weights);
}

boot().catch(err => {
  console.error(err);
  $("#load-error").hidden = false;
});
