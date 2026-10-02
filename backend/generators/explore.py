"""Row-level data extraction and the client-side engine behind the Explore panel.

The static panels elsewhere in the dashboard render pre-baked SVG: correct, but frozen. This
module embeds the holdout set itself — every row's original feature values alongside its actual
and predicted target — so the browser can re-aggregate on demand. That is what makes slicers,
cross-filtering and drill-down possible in a file with no server and no CDN behind it.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

# Keeping the whole holdout set would make the file unopenable on a large run; this is enough
# rows for every aggregate to stay faithful while the document remains emailable.
MAX_ROWS = 4000
MAX_FIELDS = 24
# Above this many distinct values a column is a label, not something you can slice by.
MAX_CATEGORIES = 30


def build_payload(ctx) -> Optional[Dict[str, Any]]:
    """Column-oriented holdout data plus the field metadata the UI builds slicers from."""
    frame = getattr(ctx, "raw_X_test", None)
    if frame is None or not len(frame) or ctx.best_model is None:
        return None

    unsupervised = ctx.y_test is None or getattr(ctx, "labels_test", None) is not None

    if unsupervised:
        # No target to compare against — the discovered assignment becomes the thing you
        # slice by, which is exactly what a segmentation review needs.
        labels = getattr(ctx, "labels_test", None)
        if labels is None:
            return None
        assigned = np.asarray(labels)
        if len(assigned) != len(frame):
            return None
        actual = predicted = np.asarray([_segment_name(v) for v in assigned])
    else:
        try:
            predicted = np.asarray(ctx.best_model.predict(ctx.X_test))
        except Exception:  # noqa: BLE001 — a dashboard must never take the run down with it
            return None
        actual = np.asarray(ctx.y_test)
        if len(predicted) != len(frame) or len(actual) != len(frame):
            return None

    frame = frame.reset_index(drop=True)
    if len(frame) > MAX_ROWS:
        keep = np.linspace(0, len(frame) - 1, MAX_ROWS).astype(int)
        frame, actual, predicted = frame.iloc[keep], actual[keep], predicted[keep]

    # unsupervised assignments are categorical labels, so they travel as a "classification"
    # payload — the JS then hides the accuracy panels via the `mode` flag below
    categorical_target = unsupervised or ctx.task_type.value == "classification"
    fields: List[Dict[str, Any]] = []
    columns: Dict[str, List[Any]] = {}

    if unsupervised:
        # the assignment itself is the most useful slicer on the page
        segment_values = [_segment_name(v) for v in np.asarray(ctx.labels_test)]
        distinct = sorted(set(segment_values))
        if len(distinct) <= MAX_CATEGORIES:
            fields.append({"name": _SEGMENT_FIELD, "type": "categorical", "values": distinct})
            columns[_SEGMENT_FIELD] = segment_values

    for name in _rank_columns(frame)[:MAX_FIELDS]:
        series = frame[name]
        meta = _describe(str(name), series)
        if meta is None:
            continue
        fields.append(meta)
        columns[str(name)] = _values(series, meta["type"])

    return {
        "task": ctx.task_type.value,
        "mode": "unsupervised" if unsupervised else "supervised",
        "target": _SEGMENT_FIELD if unsupervised else str(ctx.target_column),
        "model": ctx.best_model_name,
        "primary_metric": ctx.research.get("primary_metric", "silhouette"),
        "fields": fields,
        "columns": columns,
        "actual": _target_values(actual, categorical_target),
        "predicted": _target_values(predicted, categorical_target),
        "row_count": int(len(frame)),
    }


_SEGMENT_FIELD = "segment"


def _segment_name(value: Any) -> str:
    """DBSCAN and the outlier detectors both use -1 to mean "not part of the structure"."""
    number = int(value)
    if number < 0:
        return "noise / flagged"
    return f"segment {number}"


def _rank_columns(frame: pd.DataFrame) -> List[str]:
    """Sliceable categoricals first — those are what someone actually wants to filter on."""
    def sort_key(name: str) -> tuple:
        series = frame[name]
        if _is_categorical(series):
            return (0, series.nunique(dropna=True))
        return (1, 0)

    return sorted((str(c) for c in frame.columns), key=sort_key)


def _is_categorical(series: pd.Series) -> bool:
    if series.dtype == object or isinstance(series.dtype, pd.CategoricalDtype):
        return True
    # a small-integer column like `parking` or `stories` slices far better as a category
    return bool(pd.api.types.is_integer_dtype(series) and series.nunique(dropna=True) <= 12)


def _describe(name: str, series: pd.Series) -> Optional[Dict[str, Any]]:
    if _is_categorical(series):
        counts = series.astype("object").where(pd.notna(series), None).value_counts(dropna=True)
        if not len(counts) or len(counts) > MAX_CATEGORIES:
            return None
        return {"name": name, "type": "categorical",
                "values": [str(v) for v in counts.index.tolist()]}

    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().sum() < 2:
        return None
    low, high = float(numeric.min()), float(numeric.max())
    if not np.isfinite(low) or not np.isfinite(high) or low == high:
        return None
    return {"name": name, "type": "numeric", "min": round(low, 6), "max": round(high, 6)}


def _values(series: pd.Series, kind: str) -> List[Any]:
    if kind == "categorical":
        return [None if pd.isna(v) else str(v) for v in series.tolist()]
    numeric = pd.to_numeric(series, errors="coerce")
    return [None if not np.isfinite(v) else round(float(v), 6) for v in numeric.tolist()]


def _target_values(values: np.ndarray, classification: bool) -> List[Any]:
    if classification:
        return [str(v) for v in values.tolist()]
    out: List[Optional[float]] = []
    for v in np.asarray(values, dtype=float).tolist():
        out.append(round(float(v), 6) if np.isfinite(v) else None)
    return out


# --------------------------------------------------------------------------- client
# Plain string, not an f-string: the JS below is full of braces and escaping every one of
# them would make it unreadable and unmaintainable.
EXPLORE_CSS = """
.explore { display: grid; grid-template-columns: 248px minmax(0, 1fr); gap: 22px; align-items: start; }
.slicers { position: sticky; top: 20px; display: flex; flex-direction: column; gap: 14px; }
.slicer { background: var(--surface-1); border: 1px solid var(--border); border-radius: 12px;
  padding: 13px 14px; }
.slicer h4 { margin: 0 0 9px; font-size: 12px; font-weight: 640; letter-spacing: .02em; }
.slicer .opts { display: flex; flex-wrap: wrap; gap: 5px; max-height: 168px; overflow-y: auto; }
.opt { font: inherit; font-size: 11.5px; cursor: pointer; border-radius: 999px; padding: 3px 10px;
  border: 1px solid var(--border); background: transparent; color: var(--text-secondary); }
.opt:hover { border-color: var(--series-1); color: var(--text-primary); }
.opt[aria-pressed="true"] { background: var(--series-1); border-color: var(--series-1); color: #fff;
  font-weight: 600; }
.range { display: flex; align-items: center; gap: 7px; font-size: 11.5px; }
.range input { width: 100%; font: inherit; font-size: 11.5px; padding: 4px 7px; border-radius: 7px;
  border: 1px solid var(--border); background: var(--plane); color: var(--text-primary); }
.activebar { display: flex; flex-wrap: wrap; gap: 7px; align-items: center; margin-bottom: 16px;
  min-height: 30px; }
.chip { display: inline-flex; align-items: center; gap: 7px; font-size: 11.5px; font-weight: 550;
  background: color-mix(in srgb, var(--series-1) 13%, transparent); color: var(--series-1);
  border-radius: 999px; padding: 4px 6px 4px 11px; }
.chip button { background: none; border: none; cursor: pointer; color: inherit; font-size: 14px;
  line-height: 1; padding: 0 3px; }
.reset { font: inherit; font-size: 11.5px; background: none; border: 1px solid var(--border);
  border-radius: 999px; padding: 4px 12px; cursor: pointer; color: var(--text-secondary); }
.reset:hover { color: var(--text-primary); border-color: var(--series-1); }
.xgrid { display: grid; gap: 18px; grid-template-columns: repeat(auto-fit, minmax(330px, 1fr)); }
.xcard { background: var(--surface-1); border: 1px solid var(--border); border-radius: 14px;
  padding: 17px 18px; min-width: 0; }
.xcard h3 { margin: 0 0 3px; font-size: 14px; font-weight: 620; }
.xcard .sub { color: var(--text-muted); font-size: 11.5px; margin: 0 0 12px; }
.xcard select { font: inherit; font-size: 11.5px; padding: 3px 7px; border-radius: 7px;
  border: 1px solid var(--border); background: var(--plane); color: var(--text-primary); }
.kpis { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(148px, 1fr));
  margin-bottom: 18px; }
.kpi { background: var(--surface-1); border: 1px solid var(--border); border-radius: 12px;
  padding: 13px 15px; }
.kpi .lab { font-size: 11px; color: var(--text-muted); text-transform: uppercase;
  letter-spacing: .07em; }
.kpi .val { font-size: 21px; font-weight: 650; margin-top: 3px; font-variant-numeric: tabular-nums; }
.kpi .cap { font-size: 11px; color: var(--text-muted); margin-top: 1px; }
.bar-row { cursor: pointer; }
.bar-row:hover rect { opacity: .78; }
.empty { color: var(--text-muted); font-size: 12.5px; padding: 22px 0; text-align: center; }
@media (max-width: 900px) { .explore { grid-template-columns: 1fr; }
  .slicers { position: static; flex-direction: row; flex-wrap: wrap; }
  .slicer { flex: 1 1 210px; } }
"""


EXPLORE_JS = r"""
(function () {
  var node = document.getElementById("dataid-explore-data");
  if (!node) return;
  var DATA = JSON.parse(node.textContent);
  var NS = "http://www.w3.org/2000/svg";
  var isUnsup = DATA.mode === "unsupervised";
  // an unsupervised assignment has no ground truth, so it is scored like a categorical
  var isClass = isUnsup || DATA.task === "classification";
  var N = DATA.row_count;

  // filters: {field: {type:'categorical', values:[..]} | {type:'numeric', min, max}}
  var filters = {};
  var byField = {};
  DATA.fields.forEach(function (f) { byField[f.name] = f; });

  function activeIndices() {
    var keys = Object.keys(filters);
    var out = [];
    for (var i = 0; i < N; i++) {
      var keep = true;
      for (var k = 0; k < keys.length; k++) {
        var name = keys[k], flt = filters[name], v = DATA.columns[name][i];
        if (flt.type === "categorical") {
          if (v === null || flt.values.indexOf(String(v)) === -1) { keep = false; break; }
        } else {
          if (v === null || v < flt.min || v > flt.max) { keep = false; break; }
        }
      }
      if (keep) out.push(i);
    }
    return out;
  }

  // ------------------------------------------------------------------ maths
  function mean(a) { if (!a.length) return NaN; var s = 0; for (var i=0;i<a.length;i++) s += a[i]; return s / a.length; }

  function regressionStats(idx) {
    var n = 0, sae = 0, sse = 0, sumA = 0;
    for (var j = 0; j < idx.length; j++) {
      var a = DATA.actual[idx[j]], p = DATA.predicted[idx[j]];
      if (a === null || p === null) continue;
      n++; sae += Math.abs(a - p); sse += (a - p) * (a - p); sumA += a;
    }
    if (!n) return { n: 0 };
    var meanA = sumA / n, sst = 0;
    for (var k = 0; k < idx.length; k++) {
      var av = DATA.actual[idx[k]];
      if (av === null) continue;
      sst += (av - meanA) * (av - meanA);
    }
    return { n: n, mae: sae / n, rmse: Math.sqrt(sse / n), meanActual: meanA,
             r2: sst > 0 ? 1 - sse / sst : NaN };
  }

  function classificationStats(idx) {
    var n = 0, correct = 0, counts = {};
    for (var j = 0; j < idx.length; j++) {
      var a = DATA.actual[idx[j]], p = DATA.predicted[idx[j]];
      if (a === null || p === null) continue;
      n++; if (String(a) === String(p)) correct++;
      counts[a] = (counts[a] || 0) + 1;
    }
    return { n: n, accuracy: n ? correct / n : NaN, counts: counts };
  }

  function fmt(v, digits) {
    if (v === null || v === undefined || (typeof v === "number" && !isFinite(v))) return "—";
    if (typeof v !== "number") return String(v);
    var abs = Math.abs(v);
    if (abs >= 1e9) return (v / 1e9).toFixed(2) + "B";
    if (abs >= 1e6) return (v / 1e6).toFixed(2) + "M";
    if (abs >= 1e4) return Math.round(v).toLocaleString();
    return v.toFixed(digits === undefined ? 3 : digits);
  }

  // ------------------------------------------------------------------ svg helpers
  function el(name, attrs, text) {
    var n = document.createElementNS(NS, name);
    for (var k in attrs) if (attrs[k] !== null && attrs[k] !== undefined) n.setAttribute(k, attrs[k]);
    if (text !== undefined) n.textContent = text;
    return n;
  }

  // The palette's custom properties (--series-1, --status-good, ...) are declared on the
  // `.viz-root` element, not on <html> — a bar chart drawn with an unset fill renders black,
  // which is exactly the failure mode this guards against. Resolve once and cache: querying
  // getComputedStyle per bar on a large leaderboard is a measurable amount of layout work.
  var _cssScope = document.querySelector(".viz-root") || document.documentElement;
  var _cssCache = {};
  function css(v) {
    if (!(v in _cssCache)) _cssCache[v] = getComputedStyle(_cssScope).getPropertyValue(v).trim();
    return _cssCache[v];
  }

  function barChart(host, rows, opts) {
    opts = opts || {};
    host.innerHTML = "";
    if (!rows.length) { host.innerHTML = '<p class="empty">No rows match the current filters.</p>'; return; }
    var W = host.clientWidth || 340, rowH = 26, padL = Math.min(150, Math.max(74, W * 0.34));
    var H = rows.length * rowH + 12;
    var svgEl = el("svg", { width: "100%", height: H, viewBox: "0 0 " + W + " " + H,
                            preserveAspectRatio: "xMinYMin meet", role: "img" });
    var max = 0;
    rows.forEach(function (r) { max = Math.max(max, Math.abs(r.value)); });
    if (max === 0) max = 1;
    var avail = W - padL - 58;

    rows.forEach(function (r, i) {
      var y = i * rowH + 4, w = Math.max(1, Math.abs(r.value) / max * avail);
      var g = el("g", { class: opts.clickable ? "bar-row" : null });
      g.appendChild(el("text", { x: padL - 9, y: y + 13, "text-anchor": "end",
                                 "font-size": 11.5, fill: css("--text-secondary") },
                       r.label.length > 22 ? r.label.slice(0, 21) + "…" : r.label));
      var rect = el("rect", { x: padL, y: y + 3, width: w, height: rowH - 11, rx: 3,
                              fill: r.color || css("--series-1") });
      rect.appendChild(el("title", {}, r.label + " · " + fmt(r.value) +
                          (r.count !== undefined ? " (" + r.count + " rows)" : "")));
      g.appendChild(rect);
      g.appendChild(el("text", { x: padL + w + 7, y: y + 13, "font-size": 11,
                                 fill: css("--text-muted") }, fmt(r.value)));
      if (opts.clickable) {
        g.style.cursor = "pointer";
        g.addEventListener("click", function () { opts.onClick(r); });
      }
      svgEl.appendChild(g);
    });
    host.appendChild(svgEl);
  }

  function histogram(host, values, opts) {
    opts = opts || {};
    host.innerHTML = "";
    var clean = values.filter(function (v) { return v !== null && isFinite(v); });
    if (clean.length < 2) { host.innerHTML = '<p class="empty">Not enough rows to plot.</p>'; return; }
    var lo = Math.min.apply(null, clean), hi = Math.max.apply(null, clean);
    if (lo === hi) { hi = lo + 1; }
    var bins = Math.min(26, Math.max(6, Math.round(Math.sqrt(clean.length))));
    var counts = new Array(bins).fill(0), width = (hi - lo) / bins;
    clean.forEach(function (v) {
      var b = Math.min(bins - 1, Math.floor((v - lo) / width));
      counts[b]++;
    });
    var W = host.clientWidth || 340, H = 190, padB = 26, padL = 34;
    var max = Math.max.apply(null, counts) || 1;
    var svgEl = el("svg", { width: "100%", height: H, viewBox: "0 0 " + W + " " + H,
                            preserveAspectRatio: "xMinYMin meet" });
    var innerW = W - padL - 10, innerH = H - padB - 12;
    svgEl.appendChild(el("line", { x1: padL, y1: H - padB, x2: W - 10, y2: H - padB,
                                   stroke: css("--grid") }));
    counts.forEach(function (c, i) {
      var bw = innerW / bins, h = c / max * innerH;
      var rect = el("rect", { x: padL + i * bw + 1, y: H - padB - h, width: Math.max(1, bw - 2),
                              height: h, rx: 2, fill: opts.color || css("--series-1") });
      rect.appendChild(el("title", {}, fmt(lo + i * width) + " – " + fmt(lo + (i + 1) * width) +
                          " · " + c + " rows"));
      svgEl.appendChild(rect);
    });
    [lo, (lo + hi) / 2, hi].forEach(function (v, i) {
      svgEl.appendChild(el("text", { x: padL + i * (innerW / 2), y: H - 8, "font-size": 10,
                                     "text-anchor": i === 0 ? "start" : (i === 2 ? "end" : "middle"),
                                     fill: css("--text-muted") }, fmt(v)));
    });
    svgEl.appendChild(el("text", { x: 4, y: 14, "font-size": 10, fill: css("--text-muted") },
                         max + " max"));
    host.appendChild(svgEl);
  }

  function scatter(host, idx) {
    host.innerHTML = "";
    var pts = [];
    for (var j = 0; j < idx.length; j++) {
      var a = DATA.actual[idx[j]], p = DATA.predicted[idx[j]];
      if (a !== null && p !== null) pts.push([a, p]);
    }
    if (pts.length < 2) { host.innerHTML = '<p class="empty">Not enough rows to plot.</p>'; return; }
    if (pts.length > 1200) {
      var step = pts.length / 1200, thinned = [];
      for (var s = 0; s < pts.length; s += step) thinned.push(pts[Math.floor(s)]);
      pts = thinned;
    }
    var xs = pts.map(function (p) { return p[0]; }), ys = pts.map(function (p) { return p[1]; });
    var lo = Math.min(Math.min.apply(null, xs), Math.min.apply(null, ys));
    var hi = Math.max(Math.max.apply(null, xs), Math.max.apply(null, ys));
    if (lo === hi) hi = lo + 1;
    var W = host.clientWidth || 340, H = 230, pad = 34;
    var svgEl = el("svg", { width: "100%", height: H, viewBox: "0 0 " + W + " " + H,
                            preserveAspectRatio: "xMinYMin meet" });
    function sx(v) { return pad + (v - lo) / (hi - lo) * (W - pad - 12); }
    function sy(v) { return H - pad - (v - lo) / (hi - lo) * (H - pad - 12); }
    svgEl.appendChild(el("line", { x1: sx(lo), y1: sy(lo), x2: sx(hi), y2: sy(hi),
                                   stroke: css("--text-muted"), "stroke-dasharray": "4 4",
                                   "stroke-width": 1 }));
    pts.forEach(function (p) {
      var c = el("circle", { cx: sx(p[0]), cy: sy(p[1]), r: 2.6, fill: css("--series-1"),
                             "fill-opacity": .5 });
      c.appendChild(el("title", {}, "actual " + fmt(p[0]) + " · predicted " + fmt(p[1])));
      svgEl.appendChild(c);
    });
    svgEl.appendChild(el("text", { x: W / 2, y: H - 6, "font-size": 10, "text-anchor": "middle",
                                   fill: css("--text-muted") }, "actual →"));
    host.appendChild(svgEl);
  }

  // ------------------------------------------------------------------ render
  function currentBreakdownField() {
    var sel = document.getElementById("breakdown-field");
    return sel ? sel.value : null;
  }

  function renderKpis(idx) {
    var host = document.getElementById("explore-kpis");
    var tiles = [];
    var pct = N ? (idx.length / N * 100) : 0;
    tiles.push({ lab: "Rows in view", val: idx.length.toLocaleString(),
                 cap: pct.toFixed(0) + "% of holdout" });
    if (isUnsup) {
      // "accuracy" against a label the model invented would be 100% and meaningless
      var counts = {};
      for (var j = 0; j < idx.length; j++) {
        var seg = DATA.actual[idx[j]];
        if (seg !== null) counts[seg] = (counts[seg] || 0) + 1;
      }
      var segs = Object.keys(counts).sort(function (a, b) { return counts[b] - counts[a]; });
      tiles.push({ lab: "Segments here", val: String(segs.length), cap: "in this slice" });
      tiles.push({ lab: "Largest", val: segs.length ? segs[0] : "—",
                   cap: segs.length ? counts[segs[0]] + " rows" : "" });
      var flagged = counts["noise / flagged"] || 0;
      tiles.push({ lab: "Noise / flagged", val: String(flagged),
                   cap: idx.length ? (flagged / idx.length * 100).toFixed(1) + "% of slice" : "" });
      host.innerHTML = "";
      tiles.forEach(function (t) {
        var d = document.createElement("div");
        d.className = "kpi";
        d.innerHTML = '<div class="lab"></div><div class="val"></div><div class="cap"></div>';
        d.querySelector(".lab").textContent = t.lab;
        d.querySelector(".val").textContent = t.val;
        d.querySelector(".cap").textContent = t.cap;
        host.appendChild(d);
      });
      return;
    }
    if (isClass) {
      var cs = classificationStats(idx);
      tiles.push({ lab: "Accuracy", val: isFinite(cs.accuracy) ? (cs.accuracy * 100).toFixed(1) + "%" : "—",
                   cap: "in this slice" });
      var keys = Object.keys(cs.counts).sort(function (a, b) { return cs.counts[b] - cs.counts[a]; });
      tiles.push({ lab: "Most common", val: keys.length ? keys[0] : "—",
                   cap: keys.length ? cs.counts[keys[0]] + " rows" : "" });
      tiles.push({ lab: "Classes present", val: String(keys.length), cap: "in this slice" });
    } else {
      var rs = regressionStats(idx);
      tiles.push({ lab: "Mean actual", val: fmt(rs.meanActual), cap: DATA.target });
      tiles.push({ lab: "MAE", val: fmt(rs.mae), cap: "in this slice" });
      tiles.push({ lab: "R²", val: isFinite(rs.r2) ? rs.r2.toFixed(3) : "—", cap: "in this slice" });
    }
    host.innerHTML = "";
    tiles.forEach(function (t) {
      var d = document.createElement("div");
      d.className = "kpi";
      d.innerHTML = '<div class="lab"></div><div class="val"></div><div class="cap"></div>';
      d.querySelector(".lab").textContent = t.lab;
      d.querySelector(".val").textContent = t.val;
      d.querySelector(".cap").textContent = t.cap;
      host.appendChild(d);
    });
  }

  function renderBreakdown(idx) {
    var field = currentBreakdownField();
    var host = document.getElementById("chart-breakdown");
    var note = document.getElementById("breakdown-note");
    if (!field) { host.innerHTML = '<p class="empty">No categorical column to group by.</p>'; return; }
    var groups = {};
    for (var j = 0; j < idx.length; j++) {
      var i = idx[j], key = DATA.columns[field][i];
      if (key === null) continue;
      if (!groups[key]) groups[key] = [];
      groups[key].push(i);
    }
    var rows = Object.keys(groups).map(function (k) {
      var sub = groups[k];
      var value;
      if (isUnsup) { value = sub.length; }
      else if (isClass) { value = classificationStats(sub).accuracy; }
      else { value = regressionStats(sub).meanActual; }
      return { label: k, value: isFinite(value) ? value : 0, count: sub.length, field: field };
    }).sort(function (a, b) { return b.value - a.value; }).slice(0, 14);

    note.textContent = isUnsup ? "Rows per group — click a bar to filter"
                     : isClass ? "Accuracy per group — click a bar to filter"
                               : "Mean " + DATA.target + " per group — click a bar to filter";
    barChart(host, rows, {
      clickable: true,
      onClick: function (r) { toggleCategory(field, r.label); }
    });
  }

  function renderDistribution(idx) {
    var host = document.getElementById("chart-distribution");
    if (isClass) {
      var cs = classificationStats(idx);
      var rows = Object.keys(cs.counts).map(function (k) {
        return { label: k, value: cs.counts[k] };
      }).sort(function (a, b) { return b.value - a.value; });
      barChart(host, rows, {});
    } else {
      histogram(host, idx.map(function (i) { return DATA.actual[i]; }));
    }
  }

  function renderAccuracyView(idx) {
    var host = document.getElementById("chart-accuracy");
    if (isUnsup) {
      // segment sizes rather than a hit rate — there is nothing to be right or wrong about
      var counts = {};
      for (var j = 0; j < idx.length; j++) {
        var seg = DATA.actual[idx[j]];
        if (seg !== null) counts[seg] = (counts[seg] || 0) + 1;
      }
      var rows = Object.keys(counts).map(function (k) {
        return { label: k, value: counts[k],
                 color: k === "noise / flagged" ? css("--status-warning") : null };
      }).sort(function (a, b) { return b.value - a.value; });
      barChart(host, rows, { clickable: true,
        onClick: function (r) { toggleCategory("segment", r.label); } });
      return;
    }
    if (isClass) {
      var right = 0, wrong = 0;
      for (var j = 0; j < idx.length; j++) {
        var a = DATA.actual[idx[j]], p = DATA.predicted[idx[j]];
        if (a === null || p === null) continue;
        if (String(a) === String(p)) right++; else wrong++;
      }
      barChart(host, [
        { label: "Correct", value: right, color: css("--status-good") },
        { label: "Incorrect", value: wrong, color: css("--status-critical") }
      ], {});
    } else {
      scatter(host, idx);
    }
  }

  function renderResiduals(idx) {
    var host = document.getElementById("chart-residuals");
    if (isUnsup) {
      host.innerHTML = '<p class="empty">No residuals without a target — use the segment ' +
        'slicer to compare groups.</p>';
      return;
    }
    if (isClass) {
      var groups = {};
      for (var j = 0; j < idx.length; j++) {
        var a = DATA.actual[idx[j]], p = DATA.predicted[idx[j]];
        if (a === null || p === null || String(a) === String(p)) continue;
        var key = String(a) + " → " + String(p);
        groups[key] = (groups[key] || 0) + 1;
      }
      var rows = Object.keys(groups).map(function (k) { return { label: k, value: groups[k],
                                                                 color: css("--status-critical") }; })
        .sort(function (a, b) { return b.value - a.value; }).slice(0, 12);
      if (!rows.length) { host.innerHTML = '<p class="empty">No misclassifications in this slice.</p>'; return; }
      barChart(host, rows, {});
    } else {
      var res = [];
      for (var k = 0; k < idx.length; k++) {
        var av = DATA.actual[idx[k]], pv = DATA.predicted[idx[k]];
        if (av !== null && pv !== null) res.push(av - pv);
      }
      histogram(host, res, { color: css("--series-3") });
    }
  }

  function renderChips() {
    var host = document.getElementById("explore-chips");
    host.innerHTML = "";
    var names = Object.keys(filters);
    if (!names.length) {
      var span = document.createElement("span");
      span.className = "empty";
      span.style.padding = "0";
      span.textContent = "No filters — showing the whole holdout set.";
      host.appendChild(span);
      return;
    }
    names.forEach(function (name) {
      var flt = filters[name];
      var label = flt.type === "categorical"
        ? name + ": " + flt.values.join(", ")
        : name + ": " + fmt(flt.min) + " – " + fmt(flt.max);
      var chip = document.createElement("span");
      chip.className = "chip";
      var text = document.createElement("span");
      text.textContent = label.length > 46 ? label.slice(0, 45) + "…" : label;
      chip.appendChild(text);
      var btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = "×";
      btn.setAttribute("aria-label", "Remove filter on " + name);
      btn.addEventListener("click", function () { delete filters[name]; syncSlicers(); render(); });
      chip.appendChild(btn);
      host.appendChild(chip);
    });
    var reset = document.createElement("button");
    reset.type = "button";
    reset.className = "reset";
    reset.textContent = "Reset all";
    reset.addEventListener("click", function () { filters = {}; syncSlicers(); render(); });
    host.appendChild(reset);
  }

  function toggleCategory(field, value) {
    var flt = filters[field];
    if (!flt || flt.type !== "categorical") {
      filters[field] = { type: "categorical", values: [value] };
    } else {
      var at = flt.values.indexOf(value);
      if (at === -1) flt.values.push(value);
      else {
        flt.values.splice(at, 1);
        if (!flt.values.length) delete filters[field];
      }
    }
    syncSlicers();
    render();
  }

  function syncSlicers() {
    document.querySelectorAll(".opt[data-field]").forEach(function (btn) {
      var flt = filters[btn.dataset.field];
      var on = !!flt && flt.type === "categorical" && flt.values.indexOf(btn.dataset.value) !== -1;
      btn.setAttribute("aria-pressed", on ? "true" : "false");
    });
    document.querySelectorAll("input[data-range]").forEach(function (input) {
      var flt = filters[input.dataset.field];
      var f = byField[input.dataset.field];
      if (!flt) { input.value = input.dataset.range === "min" ? f.min : f.max; }
      else { input.value = input.dataset.range === "min" ? flt.min : flt.max; }
    });
  }

  function buildSlicers() {
    var host = document.getElementById("explore-slicers");
    DATA.fields.forEach(function (f) {
      var box = document.createElement("div");
      box.className = "slicer";
      var h = document.createElement("h4");
      h.textContent = f.name;
      box.appendChild(h);

      if (f.type === "categorical") {
        var opts = document.createElement("div");
        opts.className = "opts";
        f.values.forEach(function (v) {
          var b = document.createElement("button");
          b.type = "button";
          b.className = "opt";
          b.textContent = v.length > 16 ? v.slice(0, 15) + "…" : v;
          b.title = v;
          b.dataset.field = f.name;
          b.dataset.value = v;
          b.setAttribute("aria-pressed", "false");
          b.addEventListener("click", function () { toggleCategory(f.name, v); });
          opts.appendChild(b);
        });
        box.appendChild(opts);
      } else {
        var wrap = document.createElement("div");
        wrap.className = "range";
        ["min", "max"].forEach(function (which, i) {
          var input = document.createElement("input");
          input.type = "number";
          input.value = which === "min" ? f.min : f.max;
          input.step = "any";
          input.dataset.field = f.name;
          input.dataset.range = which;
          input.setAttribute("data-range", which);
          input.setAttribute("aria-label", f.name + " " + which);
          input.addEventListener("change", function () {
            var lo = parseFloat(document.querySelector('input[data-field="' + CSS.escape(f.name) +
                     '"][data-range="min"]').value);
            var hi = parseFloat(document.querySelector('input[data-field="' + CSS.escape(f.name) +
                     '"][data-range="max"]').value);
            if (!isFinite(lo)) lo = f.min;
            if (!isFinite(hi)) hi = f.max;
            if (lo <= f.min && hi >= f.max) delete filters[f.name];
            else filters[f.name] = { type: "numeric", min: lo, max: hi };
            render();
          });
          if (i === 1) {
            var dash = document.createElement("span");
            dash.textContent = "–";
            wrap.appendChild(dash);
          }
          wrap.appendChild(input);
        });
        box.appendChild(wrap);
      }
      host.appendChild(box);
    });
  }

  function render() {
    var idx = activeIndices();
    renderChips();
    renderKpis(idx);
    renderBreakdown(idx);
    renderDistribution(idx);
    renderAccuracyView(idx);
    renderResiduals(idx);
  }

  buildSlicers();
  var sel = document.getElementById("breakdown-field");
  if (sel) sel.addEventListener("change", function () { render(); });
  render();

  // charts are sized from clientWidth, so a resize needs a redraw
  var timer = null;
  window.addEventListener("resize", function () {
    clearTimeout(timer);
    timer = setTimeout(render, 180);
  });

  // The palette values in `css()` are cached for speed, but this file has no in-page theme
  // toggle — only the OS-level prefers-color-scheme media query, which browsers apply live.
  // Without this listener, a mid-session OS theme switch would leave every bar, dot and
  // histogram painted in the old palette while the rest of the page updates instantly.
  if (window.matchMedia) {
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () {
      _cssCache = {};
      render();
    });
  }
})();
"""
