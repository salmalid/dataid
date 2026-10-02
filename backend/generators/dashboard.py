"""Standalone interactive dashboard — one self-contained HTML file, no CDN, no build step."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from . import explore, palette, svg
from ..core.utils import coerce_json, format_metric


def generate_dashboard(ctx) -> Path:
    explore_data = explore.build_payload(ctx)
    panels = _panels(ctx, explore_data)
    current = ' aria-current="page"'
    nav = "".join(
        '<button class="tab" data-panel="{id}"{current}>{label}</button>'.format(
            id=p["id"], current=current if i == 0 else "", label=svg._esc(p["label"]))
        for i, p in enumerate(panels))
    sections = "".join(
        f'<section class="panel" id="{p["id"]}"{"" if i == 0 else " hidden"}>{p["html"]}</section>'
        for i, p in enumerate(panels))

    payload = json.dumps(coerce_json({
        "run_id": ctx.run_id,
        "target": ctx.target_column,
        "model": ctx.best_model_name,
        "metrics": {k: v for k, v in ctx.metrics.items() if isinstance(v, (int, float))},
    }), indent=2)

    if explore_data:
        # `</script>` inside the JSON would close the tag early and break the document.
        blob = json.dumps(coerce_json(explore_data), separators=(",", ":")).replace("</", "<\\/")
        explore_script = f'<script id="dataid-explore-data" type="application/json">{blob}</script>'
        explore_engine = f"<script>{explore.EXPLORE_JS}</script>"
    else:
        explore_script = ""
        explore_engine = ""

    doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{svg._esc(ctx.target_column)} — dataid dashboard</title>
<style>
{svg.VIZ_CSS}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--plane); color: var(--text-primary);
  font-family: {svg.FONT}; }}
.shell {{ max-width: 1240px; margin: 0 auto; padding: 32px 22px 80px; }}
header.top {{ display: flex; flex-wrap: wrap; gap: 16px; align-items: baseline;
  justify-content: space-between; margin-bottom: 24px; }}
.kicker {{ font-size: 11px; letter-spacing: 0.16em; text-transform: uppercase;
  color: var(--text-muted); }}
h1 {{ font-size: 28px; margin: 6px 0 0; font-weight: 660; }}
.badge {{ font-size: 12px; color: var(--text-secondary); background: var(--surface-1);
  border: 1px solid var(--border); border-radius: 999px; padding: 5px 13px; }}
nav.tabs {{ display: flex; gap: 4px; overflow-x: auto; border-bottom: 1px solid var(--grid);
  margin-bottom: 26px; padding-bottom: 2px; }}
.tab {{ background: none; border: none; border-bottom: 2px solid transparent; cursor: pointer;
  padding: 10px 15px; font: inherit; font-size: 13.5px; color: var(--text-secondary);
  white-space: nowrap; border-radius: 8px 8px 0 0; }}
.tab:hover {{ color: var(--text-primary); background: color-mix(in srgb, var(--series-1) 7%, transparent); }}
.tab[aria-current="page"] {{ color: var(--text-primary); border-bottom-color: var(--series-1);
  font-weight: 600; }}
.grid {{ display: grid; gap: 20px; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); }}
.card {{ background: var(--surface-1); border: 1px solid var(--border);
  border-radius: 14px; padding: 20px 22px; }}
.card h3 {{ margin: 0 0 6px; font-size: 15px; font-weight: 620; }}
.card p {{ color: var(--text-secondary); font-size: 13.5px; margin: 0 0 12px; }}
table.data-table {{ width: 100%; border-collapse: collapse; font-size: 12.5px;
  font-variant-numeric: tabular-nums; }}
.data-table th, .data-table td {{ text-align: left; padding: 7px 10px;
  border-bottom: 1px solid var(--grid); }}
.data-table th {{ color: var(--text-primary); font-weight: 600; }}
.scroll-x {{ overflow-x: auto; }}
.pill {{ display: inline-block; padding: 1px 9px; border-radius: 999px; font-size: 11px;
  font-weight: 600; }}
.pill-critical {{ background: color-mix(in srgb, var(--status-critical) 18%, transparent);
  color: var(--status-critical); }}
.pill-warning {{ background: color-mix(in srgb, var(--status-warning) 24%, transparent);
  color: var(--text-primary); }}
.pill-info {{ background: color-mix(in srgb, var(--series-1) 14%, transparent); color: var(--series-1); }}
.pill-stable, .pill-pass {{ background: color-mix(in srgb, var(--status-good) 16%, transparent);
  color: var(--status-good); }}
code, pre {{ font-size: 12.5px; }}
pre {{ background: var(--plane); border: 1px solid var(--border); border-radius: 10px;
  padding: 14px; overflow-x: auto; }}
@media (max-width: 760px) {{ .grid {{ grid-template-columns: 1fr; }} }}
{explore.EXPLORE_CSS}
</style>
</head>
<body class="viz-root">
<div class="shell">
  <header class="top">
    <div>
      <div class="kicker">dataid dashboard</div>
      <h1>{svg._esc(ctx.target_column)}</h1>
    </div>
    <div>
      <span class="badge">{svg._esc(ctx.task_type.value)}</span>
      <span class="badge">{svg._esc(ctx.best_model_name)}</span>
      <span class="badge">run {svg._esc(ctx.run_id)}</span>
    </div>
  </header>
  <nav class="tabs" role="tablist">{nav}</nav>
  {sections}
</div>
<script id="dataid-run" type="application/json">{payload}</script>
{explore_script}
<script>
  const tabs = document.querySelectorAll(".tab");
  const panels = document.querySelectorAll(".panel");
  tabs.forEach((tab) => {{
    tab.addEventListener("click", () => {{
      tabs.forEach((t) => t.removeAttribute("aria-current"));
      tab.setAttribute("aria-current", "page");
      panels.forEach((panel) => {{
        panel.hidden = panel.id !== tab.dataset.panel;
      }});
    }});
  }});

  // Hover tooltip layer: every mark carries a <title>, this promotes it to a styled tooltip.
  const tip = document.createElement("div");
  tip.style.cssText = "position:fixed;pointer-events:none;opacity:0;transition:opacity .12s;" +
    "background:var(--text-primary);color:var(--surface-1);padding:6px 10px;border-radius:8px;" +
    "font:500 12px system-ui;z-index:99;white-space:nowrap";
  document.body.appendChild(tip);

  document.addEventListener("mouseover", (event) => {{
    const node = event.target.closest("rect[data-tip], rect, circle, path");
    const label = node && node.querySelector && node.querySelector("title");
    if (!label) return;
    tip.textContent = label.textContent;
    tip.style.opacity = "1";
  }});
  document.addEventListener("mousemove", (event) => {{
    tip.style.left = Math.min(event.clientX + 14, window.innerWidth - tip.offsetWidth - 10) + "px";
    tip.style.top = (event.clientY - 34) + "px";
  }});
  document.addEventListener("mouseout", () => {{ tip.style.opacity = "0"; }});
</script>
{explore_engine}
</body>
</html>"""

    path = ctx.artifacts_dir / f"dashboard_{ctx.run_id}.html"
    path.write_text(doc, encoding="utf-8")
    return path


# ---------------------------------------------------------------- panels
def _panels(ctx, explore_data: Dict[str, Any] | None = None) -> List[Dict[str, str]]:
    panels = []
    if explore_data:
        panels.append({"id": "explore", "label": "Explore", "html": _explore(explore_data)})
    panels += [
        {"id": "overview", "label": "Overview", "html": _overview(ctx)},
        {"id": "data", "label": "Data quality", "html": _data(ctx)},
        {"id": "models", "label": "Models", "html": _models(ctx)},
        {"id": "explain", "label": "Explainability", "html": _explain(ctx)},
        {"id": "fairness", "label": "Fairness", "html": _fairness(ctx)},
        {"id": "deploy", "label": "Deploy", "html": _deploy(ctx)},
        {"id": "monitor", "label": "Monitoring", "html": _monitor(ctx)},
    ]
    return panels


def _explore(data: Dict[str, Any]) -> str:
    """Skeleton only — every number inside is computed in the browser from the embedded rows."""
    categoricals = [f for f in data["fields"] if f["type"] == "categorical"]
    options = "".join(f'<option value="{svg._esc(f["name"])}">{svg._esc(f["name"])}</option>'
                      for f in categoricals)
    picker = (f'<select id="breakdown-field" aria-label="Group by">{options}</select>'
              if options else "")
    unsupervised = data.get("mode") == "unsupervised"
    classification = data["task"] == "classification"
    lead = ("Filter the holdout set and every figure recomputes. No target exists on this run, so "
            "the segments the model discovered are what you slice by."
            if unsupervised else
            "Filter the holdout set and every figure below recomputes.")

    return f"""<p style="margin:0 0 14px;color:var(--text-secondary);font-size:13px">
  {lead} {data['row_count']:,} scored rows,
  {len(data['fields'])} sliceable columns. Click any bar to filter by it.
</p>"""  + f"""
<div class="explore">
  <aside class="slicers" id="explore-slicers" aria-label="Filters"></aside>
  <div>
    <div class="activebar" id="explore-chips"></div>
    <div class="kpis" id="explore-kpis"></div>
    <div class="xgrid">
      <div class="xcard">
        <h3>Breakdown by {picker or "group"}</h3>
        <p class="sub" id="breakdown-note"></p>
        <div id="chart-breakdown"></div>
      </div>
      <div class="xcard">
        <h3>{"Segment sizes" if unsupervised
             else "Class distribution" if classification
             else svg._esc(data["target"]) + " distribution"}</h3>
        <p class="sub">{"How the current selection splits across segments" if unsupervised
                        else "Actual values in the current selection"}</p>
        <div id="chart-distribution"></div>
      </div>
      <div class="xcard">
        <h3>{"Segment composition" if unsupervised
             else "Correct vs incorrect" if classification else "Predicted vs actual"}</h3>
        <p class="sub">{"Click a segment to filter the whole page to it" if unsupervised
                        else "Hit rate in this slice" if classification
                        else "Dashed line is a perfect prediction"}</p>
        <div id="chart-accuracy"></div>
      </div>
      <div class="xcard">
        <h3>{"Residuals" if unsupervised
             else "Confusions" if classification else "Residuals"}</h3>
        <p class="sub">{"Not defined without a target" if unsupervised
                        else "Which classes get mistaken for which" if classification
                        else "Actual minus predicted — should centre on zero"}</p>
        <div id="chart-residuals"></div>
      </div>
    </div>
  </div>
</div>"""


def _tiles(ctx) -> str:
    m = ctx.metrics
    if ctx.task_type.value == "classification":
        pairs = [("Accuracy", "accuracy"), ("F1", "f1"), ("Recall", "recall"),
                 ("Precision", "precision"), ("ROC AUC", "roc_auc")]
    else:
        pairs = [("R²", "r2"), ("MAE", "mae"), ("RMSE", "rmse"), ("MAPE %", "mape")]
    tiles = [{"label": label, "value": format_metric(key, m.get(key)), "caption": "holdout"}
             for label, key in pairs if isinstance(m.get(key), (int, float))]
    tiles.append({"label": "Holdout rows", "value": f"{m.get('holdout_rows', 0):,}",
                  "caption": "never seen in training"})
    return svg.stat_tiles(tiles)


def _overview(ctx) -> str:
    strategy = "".join(f"<li>{svg._esc(s)}</li>" for s in ctx.research.get("strategy", []))
    summary = (ctx.explainability.get("business_summary") or "").strip()
    importance = ctx.explainability.get("global_importance", [])
    chart = svg.bar_chart([{"label": f["feature"], "value": f["importance"]} for f in importance[:10]],
                          title="Top drivers", subtitle="Global feature attribution") if importance else ""
    return f"""{_tiles(ctx)}
<div class="grid">
  <div class="card">
    <h3>Executive summary</h3>
    {_paragraphs(summary) if summary else
     '<p class="muted">No narrator configured for this run — the panels below are computed.</p>'}
  </div>
  <div class="card">
    <h3>Modelling strategy</h3>
    <p>Optimised for <strong>{svg._esc(ctx.research.get('primary_metric', ''))}</strong>.</p>
    <ul>{strategy}</ul>
  </div>
</div>
{chart}"""


def _data(ctx) -> str:
    issues = sorted(ctx.issues, key=lambda i: {"critical": 0, "warning": 1}.get(i.severity, 2))
    rows = "".join(
        f'<tr><td><span class="pill pill-{svg._esc(i.severity)}">{svg._esc(i.severity)}</span></td>'
        f'<td>{svg._esc(i.category)}</td><td><code>{svg._esc(i.column or "—")}</code></td>'
        f'<td>{svg._esc(i.message)}</td></tr>' for i in issues[:40])

    missing = ctx.eda.get("missing_by_column", [])
    missing_chart = svg.bar_chart([{"label": m["column"], "value": m["pct"]} for m in missing[:12]],
                                  title="Missing values", subtitle="Percent null per column",
                                  unit="%", color=palette.STATUS["warning"]) if missing else ""

    matrix = ctx.eda.get("correlation_matrix", {})
    corr_chart = svg.heatmap(matrix["columns"], matrix["values"], title="Correlation",
                             subtitle="Blue negative · gray none · red positive") \
        if matrix.get("columns") else ""

    balance = ctx.eda.get("class_balance", [])
    balance_chart = svg.bar_chart([{"label": b["label"], "value": b["count"]} for b in balance],
                                  title="Class balance", subtitle="Rows per target class",
                                  color=palette.CATEGORICAL_LIGHT[2]) if balance else ""

    actions = "".join(f"<li><strong>{svg._esc(a['action'])}</strong> — {svg._esc(a['detail'])}</li>"
                      for a in ctx.cleaning_summary.get("actions", []))

    return f"""<div class="card" style="margin-bottom:20px">
  <h3>Detective findings</h3>
  <p>{len([i for i in issues if i.severity == 'critical'])} critical ·
     {len([i for i in issues if i.severity == 'warning'])} warnings ·
     {len([i for i in issues if i.severity == 'info'])} informational</p>
  <div class="scroll-x"><table class="data-table">
    <thead><tr><th>Severity</th><th>Category</th><th>Column</th><th>Finding</th></tr></thead>
    <tbody>{rows or '<tr><td colspan="4">Clean dataset.</td></tr>'}</tbody>
  </table></div>
</div>
<div class="card" style="margin-bottom:20px">
  <h3>Cleaning actions applied</h3>
  <ul>{actions or '<li>No changes were required.</li>'}</ul>
</div>
<div class="grid">{missing_chart}{balance_chart}{corr_chart}</div>"""


def _models(ctx) -> str:
    if ctx.leaderboard is None:
        return '<div class="card"><p>No leaderboard available.</p></div>'
    primary = ctx.research.get("primary_metric", "accuracy")
    key = primary if primary in ctx.leaderboard.columns else ctx.leaderboard.columns[-1]
    chart = svg.bar_chart(
        [{"label": r["model"], "value": float(r[key] or 0)}
         for r in ctx.leaderboard[["model", key]].head(14).to_dict("records")],
        title="Leaderboard", subtitle=f"Holdout {key}")

    columns = [c for c in ("rank", "model", "family", "roc_auc", "pr_auc", "accuracy", "f1",
                           "r2", "rmse", "mae", "cv_mean", "cv_std", "overfit_gap",
                           "fit_seconds", "inference_ms_per_row") if c in ctx.leaderboard.columns]
    table = ctx.leaderboard[columns].to_html(index=False, border=0, classes="data-table",
                                             float_format=lambda v: f"{v:.4f}")

    extras = ""
    if ctx.task_type.value == "classification":
        matrix = ctx.metrics.get("confusion_matrix")
        if matrix:
            extras += svg.confusion_matrix(matrix, ctx.metrics.get("labels", []))
        roc = ctx.metrics.get("roc_curve")
        if roc:
            extras += svg.line_chart(
                [{"name": "ROC", "points": [{"x": p["fpr"], "y": p["tpr"]} for p in roc]}],
                title="ROC curve", subtitle=f"AUC {ctx.metrics.get('roc_auc', 0):.4f}",
                x_label="False positive rate", y_label="True positive rate",
                reference_diagonal=True)
        pr = ctx.metrics.get("pr_curve")
        if pr:
            extras += svg.line_chart(
                [{"name": "PR", "points": [{"x": p["recall"], "y": p["precision"]} for p in pr]}],
                title="Precision–recall", subtitle=f"AP {ctx.metrics.get('pr_auc', 0):.4f}",
                x_label="Recall", y_label="Precision")
        calibration = ctx.metrics.get("calibration")
        if calibration:
            extras += svg.line_chart(
                [{"name": "Observed", "points": [{"x": c["predicted"], "y": c["observed"]}
                                                 for c in calibration]}],
                title="Calibration", subtitle="Predicted probability vs observed frequency",
                x_label="Predicted", y_label="Observed", reference_diagonal=True)
    else:
        residual = ctx.metrics.get("residual_histogram")
        if residual:
            extras += svg.histogram(residual["bins"], residual["counts"],
                                    title="Residual distribution",
                                    subtitle="Should be centred on zero")

    return f"""{chart}
<div class="card" style="margin:20px 0">
  <h3>Full leaderboard</h3>
  <p>{len(ctx.leaderboard)} models trained and scored on the same holdout split.</p>
  <div class="scroll-x">{table}</div>
</div>
<div class="grid">{extras}</div>"""


def _explain(ctx) -> str:
    explain = ctx.explainability
    importance = explain.get("global_importance", [])
    chart = svg.bar_chart([{"label": f["feature"], "value": f["importance"]} for f in importance[:20]],
                          title="Global feature importance",
                          subtitle=f"Source: {explain.get('method', 'permutation')}") if importance else ""

    shap = explain.get("shap", {})
    shap_chart = ""
    if shap.get("available"):
        shap_chart = svg.bar_chart(
            [{"label": f["feature"], "value": f["mean_abs_shap"]} for f in shap.get("top_features", [])[:15]],
            title="Mean |SHAP|", subtitle=f"Sampled over {shap.get('sample_size', 0)} holdout rows",
            color=palette.CATEGORICAL_LIGHT[6])
    else:
        shap_chart = (f'<div class="card"><h3>SHAP</h3><p>{svg._esc(shap.get("reason", "unavailable"))}'
                      f'</p></div>')

    pdp = "".join(
        svg.line_chart([{"name": entry["feature"],
                         "points": [{"x": p["x"], "y": p["y"]} for p in entry["points"]]}],
                       title=f"Partial dependence · {entry['feature']}",
                       subtitle="Average prediction as this feature moves",
                       x_label=entry["feature"], y_label="prediction")
        for entry in explain.get("partial_dependence", []))

    local_cards = ""
    for entry in explain.get("local_explanations", [])[:4]:
        rows = "".join(
            f'<tr><td><code>{svg._esc(c["feature"])}</code></td>'
            f'<td>{c["contribution"]:+.4f}</td><td>{svg._esc(c["direction"])}</td></tr>'
            for c in entry["contributions"])
        confidence = f" · confidence {entry['confidence']}" if entry.get("confidence") else ""
        local_cards += f"""<div class="card">
  <h3>Row {entry['index']} — predicted {svg._esc(entry['prediction'])}</h3>
  <p>Actual {svg._esc(entry['actual'])}{confidence}</p>
  <table class="data-table">
    <thead><tr><th>Feature</th><th>Contribution</th><th>Effect</th></tr></thead>
    <tbody>{rows}</tbody></table>
</div>"""

    counterfactuals = "".join(
        f"<li>Row {c['index']}: shifting <code>{svg._esc(c['counterfactual']['feature'])}</code> by "
        f"{c['counterfactual']['shift_in_std']}σ flips "
        f"<strong>{svg._esc(c['counterfactual']['from_prediction'])}</strong> → "
        f"<strong>{svg._esc(c['counterfactual']['to_prediction'])}</strong>.</li>"
        for c in explain.get("counterfactuals", []) if c.get("counterfactual"))

    cf_card = f"""<div class="card" style="margin:20px 0">
  <h3>Counterfactuals</h3>
  <p>The smallest single-feature change that flips the decision.</p>
  <ul>{counterfactuals or '<li>No single-feature flip found within 3 standard deviations.</li>'}</ul>
</div>"""

    return f'<div class="grid">{chart}{shap_chart}</div>{cf_card}<div class="grid">{local_cards}{pdp}</div>'


def _fairness(ctx) -> str:
    fairness = ctx.fairness
    if not fairness.get("enabled"):
        reason = fairness.get("reason", "no sensitive attribute selected")
        return (f'<div class="card"><h3>Fairness</h3><p>{svg._esc(reason[0].upper() + reason[1:])}. '
                f'Pick a sensitive column in project settings to slice performance by group.</p></div>')

    metric = fairness["metric"]
    rows = "".join(
        "<tr>" + "".join(f"<td>{svg._esc(s.get(k, '—'))}</td>"
                         for k in s.keys()) + "</tr>" for s in fairness["slices"])
    headers = "".join(f"<th>{svg._esc(k)}</th>" for k in (fairness["slices"][0].keys()
                                                          if fairness["slices"] else []))
    chart = svg.bar_chart(
        [{"label": s["group"], "value": s.get(metric, 0) or 0} for s in fairness["slices"]],
        title=f"{metric} by {fairness['column']}",
        subtitle=f"Max gap {fairness['max_gap']} — verdict {fairness['verdict']}",
        color=palette.status_color("critical" if fairness["verdict"] == "fail" else "good"))

    return f"""<div class="card" style="margin-bottom:20px">
  <h3>Sliced on <code>{svg._esc(fairness['column'])}</code></h3>
  <p>Verdict <span class="pill pill-{'critical' if fairness['verdict'] == 'fail' else 'stable'}">
     {svg._esc(fairness['verdict'])}</span> · max {svg._esc(metric)} gap {fairness['max_gap']}</p>
  <div class="scroll-x"><table class="data-table"><thead><tr>{headers}</tr></thead>
    <tbody>{rows}</tbody></table></div>
</div>
{chart}"""


def _deploy(ctx) -> str:
    deployment = ctx.deployment
    endpoints = "".join(
        f'<tr><td><code>{svg._esc(e["method"])}</code></td><td><code>{svg._esc(e["path"])}</code></td>'
        f'<td>{svg._esc(e["description"])}</td></tr>' for e in deployment.get("endpoints", []))
    targets = "".join(f'<span class="badge">{svg._esc(t)}</span> '
                      for t in deployment.get("targets", []))
    latency = deployment.get("latency", {})
    tiles = svg.stat_tiles([
        {"label": "p50 latency", "value": f"{latency.get('p50_ms_per_row', 0)} ms", "caption": "per row"},
        {"label": "p95 latency", "value": f"{latency.get('p95_ms_per_row', 0)} ms", "caption": "per row"},
        {"label": "Throughput", "value": f"{latency.get('throughput_rows_per_sec', 0):,.0f}",
         "caption": "rows / second"},
        {"label": "Bundle size", "value": f"{deployment.get('model_size_bytes', 0) / 1024:,.0f} KB",
         "caption": "joblib artifact"},
    ])
    return f"""{tiles}
<div class="card" style="margin-bottom:20px">
  <h3>Endpoints</h3>
  <table class="data-table">
    <thead><tr><th>Method</th><th>Path</th><th>Description</th></tr></thead>
    <tbody>{endpoints}</tbody></table>
</div>
<div class="card" style="margin-bottom:20px">
  <h3>Ship it</h3>
  <pre>{svg._esc(deployment.get('docker_command', ''))}</pre>
  <p style="margin-top:14px">Targets: {targets}</p>
</div>"""


def _monitor(ctx) -> str:
    monitoring = ctx.monitoring
    drift = monitoring.get("drift", {})
    chart = svg.bar_chart(
        [{"label": f["feature"], "value": f["psi"]} for f in drift.get("features", [])[:14]],
        title="Population Stability Index", subtitle="Above 0.10 warn · above 0.25 retrain",
        color=palette.STATUS["warning"]) if drift.get("features") else ""

    alerts = "".join(
        f'<tr><td>{svg._esc(a["signal"])}</td><td>{a["warn"]}</td><td>{a["critical"]}</td>'
        f'<td>{svg._esc(a["action"])}</td></tr>' for a in monitoring.get("alerts", []))
    baseline = monitoring.get("baseline", {})
    schedule = monitoring.get("schedule", {})

    return f"""{svg.stat_tiles([
        {"label": "Baseline " + str(baseline.get("metric", "")), "value": baseline.get("value", "—"),
         "caption": "at release"},
        {"label": "Max PSI", "value": drift.get("max_psi", 0),
         "caption": drift.get("status", "unknown"),
         "status": "critical" if drift.get("status") == "critical"
         else ("warning" if drift.get("status") == "warning" else None)},
        {"label": "Drift check", "value": schedule.get("drift_check", "—"), "caption": "cadence"},
        {"label": "Retrain review", "value": schedule.get("retrain_review", "—"), "caption": "cadence"},
    ])}
<div class="card" style="margin-bottom:20px">
  <h3>Alert rules</h3>
  <table class="data-table">
    <thead><tr><th>Signal</th><th>Warn</th><th>Critical</th><th>Action</th></tr></thead>
    <tbody>{alerts}</tbody></table>
</div>
{chart}"""


def _paragraphs(text: str) -> str:
    from .report import _markdown_lite

    return _markdown_lite(text)
