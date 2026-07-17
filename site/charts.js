/* Pick 3 Oracle — hand-rolled SVG / CSS-grid chart builders. No libraries. */
"use strict";

window.Charts = (function () {
  const NS = "http://www.w3.org/2000/svg";

  function svg(tag, attrs) {
    const el = document.createElementNS(NS, tag);
    for (const k in attrs) el.setAttribute(k, attrs[k]);
    return el;
  }

  function txt(x, y, s, attrs) {
    const t = svg("text", Object.assign({
      x: x, y: y, fill: "#5c6680", "font-size": 10,
      "font-family": "ui-monospace, Menlo, Consolas, monospace",
    }, attrs || {}));
    t.textContent = s;
    return t;
  }

  function extent(seriesList) {
    let lo = 0, hi = 0;
    for (const s of seriesList) {
      for (const v of s.points) { if (v < lo) lo = v; if (v > hi) hi = v; }
    }
    if (lo === hi) hi = lo + 1;
    const pad = (hi - lo) * 0.06;
    return [lo - pad, hi + pad];
  }

  function ticks(lo, hi, n) {
    const span = hi - lo;
    const step0 = span / Math.max(1, n);
    const mag = Math.pow(10, Math.floor(Math.log10(step0)));
    let step = mag;
    for (const m of [1, 2, 2.5, 5, 10]) { if (step0 <= m * mag) { step = m * mag; break; } }
    const out = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(Math.round(v * 100) / 100);
    return out;
  }

  /* Multi-series line chart. series: [{points, color, width, dash, opacity, area}] */
  function lineChart(container, opts) {
    const W = opts.width || 760, H = opts.height || 300;
    const L = 48, R = 10, T = 12, B = 24;
    const pw = W - L - R, ph = H - T - B;
    const root = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img" });
    const visible = opts.series.filter(s => s.points && s.points.length);
    const [lo, hi] = extent(visible.length ? visible : [{ points: [0, 1] }]);
    const y = v => T + ph - ((v - lo) / (hi - lo)) * ph;

    for (const tv of ticks(lo, hi, 5)) {
      root.appendChild(svg("line", { x1: L, x2: W - R, y1: y(tv), y2: y(tv), stroke: "#16203a", "stroke-width": 1 }));
      root.appendChild(txt(L - 6, y(tv) + 3, (opts.yFmt || String)(tv), { "text-anchor": "end" }));
    }
    if (lo < 0 && hi > 0) {
      root.appendChild(svg("line", { x1: L, x2: W - R, y1: y(0), y2: y(0), stroke: "#2a3552", "stroke-width": 1.2 }));
    }

    for (const s of visible) {
      const n = s.points.length;
      const x = i => L + (n === 1 ? pw / 2 : (i / (n - 1)) * pw);
      const d = s.points.map((v, i) => (i ? "L" : "M") + x(i).toFixed(1) + " " + y(v).toFixed(1)).join("");
      const attrs = {
        d: d, fill: "none", stroke: s.color, "stroke-width": s.width || 1.6,
        "stroke-linejoin": "round", "stroke-linecap": "round", opacity: s.opacity == null ? 1 : s.opacity,
      };
      if (s.dash) attrs["stroke-dasharray"] = s.dash;
      root.appendChild(svg("path", attrs));
    }
    if (opts.xStart) root.appendChild(txt(L, H - 8, opts.xStart));
    if (opts.xEnd) root.appendChild(txt(W - R, H - 8, opts.xEnd, { "text-anchor": "end" }));
    container.innerHTML = "";
    container.appendChild(root);
  }

  /* Vertical bar chart with optional reference line + per-bar markers. */
  function barChart(container, opts) {
    const W = opts.width || 340, H = opts.height || 170;
    const L = 22, R = 4, T = 8, B = 18;
    const pw = W - L - R, ph = H - T - B;
    const vals = opts.values;
    const n = vals.length;
    let max = Math.max.apply(null, vals.concat([opts.ref || 0]).concat(opts.markers || [0]));
    if (max <= 0) max = 1;
    max *= 1.12;
    const bw = pw / n;
    const root = svg("svg", { viewBox: `0 0 ${W} ${H}` });
    const y = v => T + ph - (v / max) * ph;

    vals.forEach((v, i) => {
      const x = L + i * bw + bw * 0.16;
      root.appendChild(svg("rect", {
        x: x.toFixed(1), y: y(v).toFixed(1), width: (bw * 0.68).toFixed(1),
        height: Math.max(0, ph + T - y(v)).toFixed(1),
        rx: 2, fill: opts.color || "#5b8cff", opacity: 0.85,
      }));
      if (opts.markers && opts.markers[i] != null) {
        const my = y(opts.markers[i]);
        root.appendChild(svg("line", {
          x1: x - bw * 0.06, x2: x + bw * 0.74, y1: my, y2: my,
          stroke: "#f6c453", "stroke-width": 2, "stroke-linecap": "round",
        }));
      }
      root.appendChild(txt(L + i * bw + bw / 2, H - 6, String(opts.labels ? opts.labels[i] : i), { "text-anchor": "middle" }));
    });
    if (opts.ref != null) {
      root.appendChild(svg("line", {
        x1: L, x2: W - R, y1: y(opts.ref), y2: y(opts.ref),
        stroke: "#8b95af", "stroke-width": 1, "stroke-dasharray": "4 4",
      }));
      root.appendChild(txt(W - R, y(opts.ref) - 3, opts.refLabel || "", { "text-anchor": "end", fill: "#8b95af" }));
    }
    container.innerHTML = "";
    container.appendChild(root);
  }

  /* Sum distribution: 28 observed bars + theoretical polyline. */
  function sumDist(container, observed, theoretical) {
    const W = 700, H = 190, L = 26, R = 6, T = 10, B = 20;
    const pw = W - L - R, ph = H - T - B;
    const max = Math.max(Math.max.apply(null, observed), Math.max.apply(null, theoretical)) * 1.12 || 1;
    const n = observed.length;
    const bw = pw / n;
    const y = v => T + ph - (v / max) * ph;
    const root = svg("svg", { viewBox: `0 0 ${W} ${H}` });
    observed.forEach((v, i) => {
      root.appendChild(svg("rect", {
        x: (L + i * bw + bw * 0.14).toFixed(1), y: y(v).toFixed(1),
        width: (bw * 0.72).toFixed(1), height: Math.max(0, ph + T - y(v)).toFixed(1),
        rx: 2, fill: "#5b8cff", opacity: 0.85,
      }));
      if (i % 3 === 0) root.appendChild(txt(L + i * bw + bw / 2, H - 6, String(i), { "text-anchor": "middle" }));
    });
    const d = theoretical.map((v, i) =>
      (i ? "L" : "M") + (L + i * bw + bw / 2).toFixed(1) + " " + y(v).toFixed(1)).join("");
    root.appendChild(svg("path", { d: d, fill: "none", stroke: "#f6c453", "stroke-width": 2, "stroke-linejoin": "round" }));
    container.innerHTML = "";
    container.appendChild(root);
  }

  /* CSS-grid heatmap. grid[r][c] -> number; colorFn(v) -> css color. */
  function heatGrid(container, grid, opts) {
    const rows = grid.length, cols = grid[0].length;
    const wrap = document.createElement("div");
    wrap.className = "heat";
    wrap.style.gridTemplateColumns = `repeat(${cols + 1}, minmax(0, 1fr))`;
    const corner = document.createElement("div");
    corner.className = "hlabel";
    corner.textContent = opts.corner || "";
    wrap.appendChild(corner);
    for (let c = 0; c < cols; c++) {
      const h = document.createElement("div");
      h.className = "hlabel";
      h.textContent = opts.xLabels ? opts.xLabels[c] : c;
      wrap.appendChild(h);
    }
    for (let r = 0; r < rows; r++) {
      const h = document.createElement("div");
      h.className = "hlabel";
      h.textContent = opts.yLabels ? opts.yLabels[r] : r;
      wrap.appendChild(h);
      for (let c = 0; c < cols; c++) {
        const cell = document.createElement("div");
        cell.className = "hcell";
        cell.style.background = opts.colorFn(grid[r][c]);
        if (opts.showValues) cell.textContent = grid[r][c];
        if (opts.titleFn) cell.title = opts.titleFn(r, c, grid[r][c]);
        wrap.appendChild(cell);
      }
    }
    container.innerHTML = "";
    container.appendChild(wrap);
  }

  /* lerp two rgb triples; t in [0,1] */
  function mix(c0, c1, t) {
    const r = Math.round(c0[0] + (c1[0] - c0[0]) * t);
    const g = Math.round(c0[1] + (c1[1] - c0[1]) * t);
    const b = Math.round(c0[2] + (c1[2] - c0[2]) * t);
    return `rgb(${r},${g},${b})`;
  }
  const HOT = [246, 196, 83], COLD = [16, 24, 48];
  const heatColor = t => mix(HOT, COLD, Math.min(1, Math.max(0, t)));

  /* Donut chart via pathLength circles. segments: [{value, color, label}] */
  function donut(container, segments, opts) {
    const size = (opts && opts.size) || 150;
    const r = 42, cx = 60, cy = 60, thick = 15;
    const total = segments.reduce((a, s) => a + s.value, 0) || 1;
    const root = svg("svg", { viewBox: "0 0 120 120", width: size, height: size });
    root.appendChild(svg("circle", { cx: cx, cy: cy, r: r, fill: "none", stroke: "#16203a", "stroke-width": thick }));
    let acc = 0;
    for (const s of segments) {
      const frac = (s.value / total) * 100;
      if (frac <= 0) { continue; }
      const c = svg("circle", {
        cx: cx, cy: cy, r: r, fill: "none", stroke: s.color, "stroke-width": thick,
        pathLength: 100, "stroke-dasharray": `${frac} ${100 - frac}`,
        "stroke-dashoffset": 25 - acc, "stroke-linecap": "butt",
      });
      root.appendChild(c);
      acc += frac;
    }
    if (opts && opts.centerTop) root.appendChild(txt(cx, cy - 1, opts.centerTop, { "text-anchor": "middle", "font-size": 15, fill: "#e9edf7", "font-weight": 700 }));
    if (opts && opts.centerBottom) root.appendChild(txt(cx, cy + 13, opts.centerBottom, { "text-anchor": "middle", "font-size": 8 }));
    container.innerHTML = "";
    container.appendChild(root);
  }

  /* 60-point reward sparkline with a 0.5 baseline. */
  function sparkline(values, opts) {
    const W = 120, H = 26, pad = 2;
    const lo = 0, hi = 1;
    const root = svg("svg", { viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: "none" });
    const y = v => H - pad - ((Math.min(hi, Math.max(lo, v)) - lo) / (hi - lo)) * (H - 2 * pad);
    root.appendChild(svg("line", { x1: 0, x2: W, y1: y(0.5), y2: y(0.5), stroke: "#2a3552", "stroke-width": 1, "stroke-dasharray": "2 3" }));
    const n = values.length;
    const pts = values.map((v, i) => `${(i / Math.max(1, n - 1) * W).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
    root.appendChild(svg("polyline", {
      points: pts, fill: "none", stroke: (opts && opts.color) || "#2fd6c3",
      "stroke-width": 1.4, "stroke-linejoin": "round", "vector-effect": "non-scaling-stroke",
    }));
    return root;
  }

  return { svg, lineChart, barChart, sumDist, heatGrid, heatColor, donut, sparkline, mix };
})();
