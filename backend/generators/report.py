"""Executive report — Markdown and a self-contained, theme-aware HTML page."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from . import palette, svg
from ..core.utils import format_metric

SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


def _headline_metrics(ctx) -> List[Dict[str, Any]]:
    m = ctx.metrics
    if ctx.task_type.value == "classification":
        pairs = [("Accuracy", "accuracy"), ("F1", "f1"), ("Precision", "precision"),
                 ("Recall", "recall"), ("ROC AUC", "roc_auc"), ("PR AUC", "pr_auc")]
    else:
        pairs = [("R²", "r2"), ("MAE", "mae"), ("RMSE", "rmse"),
                 ("MAPE %", "mape"), ("Explained var.", "explained_variance")]
    out = []
    for label, key in pairs:
        if key in m and isinstance(m[key], (int, float)):
            out.append({"label": label, "value": format_metric(key, float(m[key])),
                        "caption": "holdout"})
    return out


def generate_report_markdown(ctx) -> Path:
    lines: List[str] = []
    add = lines.append

    add(f"# {ctx.target_column} — dataid report")
    add("")
    add(f"**Run** `{ctx.run_id}` · **Task** {ctx.task_type.value} · "
        f"**Generated** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    add("")
    # Omitted entirely when nothing wrote one — the metrics below are the report's substance,
    # and a placeholder sentence under this heading would read as a finding.
    executive_summary = (ctx.explainability.get("business_summary") or "").strip()
    if executive_summary:
        add("## Executive summary")
        add("")
        add(executive_summary)
        add("")

    add("## Headline metrics")
    add("")
    add("| Metric | Value |")
    add("| --- | --- |")
    for tile in _headline_metrics(ctx):
        add(f"| {tile['label']} | {tile['value']} |")
    add("")

    add("## Dataset overview")
    add("")
    profile = ctx.profile
    add(f"- **Rows** {profile.get('rows', 0):,}, **columns** {profile.get('n_columns', 0)}")
    add(f"- **Missing cells** {profile.get('total_missing_cells', 0):,}")
    add(f"- **Duplicate rows** {profile.get('duplicate_rows', 0):,}")
    groups = profile.get("column_groups", {})
    for role in ("numeric", "categorical", "datetime", "identifier", "text"):
        cols = groups.get(role, [])
        if cols:
            add(f"- **{role.title()}** ({len(cols)}): {', '.join(f'`{c}`' for c in cols[:12])}"
                + (" …" if len(cols) > 12 else ""))
    add("")

    add("## What the Data Detective found")
    add("")
    issues = sorted(ctx.issues, key=lambda i: SEVERITY_ORDER.get(i.severity, 3))
    if issues:
        add("| Severity | Category | Column | Finding |")
        add("| --- | --- | --- | --- |")
        for issue in issues[:30]:
            add(f"| {issue.severity} | {issue.category} | `{issue.column or '—'}` | {issue.message} |")
    else:
        add("No blocking issues detected.")
    add("")

    add("## Cleaning")
    add("")
    cleaning = ctx.cleaning_summary
    add(f"Shape `{cleaning.get('shape_before')}` → `{cleaning.get('shape_after')}` "
        f"({cleaning.get('rows_removed', 0):,} rows and "
        f"{cleaning.get('columns_removed', 0)} columns removed).")
    add("")
    for action in cleaning.get("actions", []):
        add(f"- **{action['action']}** — {action['detail']}")
    add("")

    add("## Feature engineering")
    add("")
    features = ctx.feature_summary
    add(f"{features.get('n_created', 0)} derived features; the preprocessor expands the frame to "
        f"**{features.get('n_features_out', 0)}** model-ready columns "
        f"({features.get('train_rows', 0):,} train / {features.get('test_rows', 0):,} holdout).")
    add("")
    created = features.get("created_features", [])
    if created:
        add("Created: " + ", ".join(f"`{c}`" for c in created[:25]) +
            (" …" if len(created) > 25 else ""))
    add("")

    add("## Model comparison")
    add("")
    add(f"Optimised for **{ctx.research.get('primary_metric')}** using "
        f"{ctx.research.get('validation', {}).get('scheme', 'k-fold')} validation.")
    add("")
    for note in ctx.research.get("strategy", []):
        add(f"- {note}")
    add("")
    if ctx.leaderboard is not None:
        base = [c for c in ("rank", "model", "family") if c in ctx.leaderboard.columns]
        metrics = [c for c in ctx.leaderboard.columns
                   if c in ("roc_auc", "pr_auc", "accuracy", "f1", "r2", "rmse", "mae",
                            "cv_mean", "overfit_gap", "fit_seconds")]
        add(ctx.leaderboard[base + metrics].head(20).to_markdown(index=False))
    add("")

    add("## Explainability")
    add("")
    for entry in ctx.explainability.get("global_importance", [])[:12]:
        add(f"- `{entry['feature']}` — {entry['importance']:.5f}")
    add("")
    counterfactuals = [c for c in ctx.explainability.get("counterfactuals", []) if c.get("counterfactual")]
    if counterfactuals:
        add("### Counterfactuals")
        add("")
        for c in counterfactuals:
            cf = c["counterfactual"]
            add(f"- Row {c['index']}: shifting `{cf['feature']}` by {cf['shift_in_std']}σ flips "
                f"`{cf['from_prediction']}` → `{cf['to_prediction']}`.")
        add("")

    if ctx.fairness.get("enabled"):
        add("## Fairness")
        add("")
        add(f"Sliced on `{ctx.fairness['column']}` — max {ctx.fairness['metric']} gap "
            f"**{ctx.fairness['max_gap']}** (verdict: **{ctx.fairness['verdict']}**).")
        add("")

    add("## Deployment")
    add("")
    deployment = ctx.deployment
    add(f"- Bundle `{Path(deployment.get('model_path', '')).name}` "
        f"({deployment.get('model_size_bytes', 0) / 1024:.0f} KB)")
    latency = deployment.get("latency", {})
    if latency:
        add(f"- p50 {latency.get('p50_ms_per_row')} ms/row · p95 {latency.get('p95_ms_per_row')} ms/row "
            f"· {latency.get('throughput_rows_per_sec')} rows/s")
    add(f"- Targets: {', '.join(deployment.get('targets', []))}")
    add("")
    add("```bash")
    add(deployment.get("docker_command", ""))
    add("```")
    add("")

    add("## Monitoring")
    add("")
    drift = ctx.monitoring.get("drift", {})
    add(f"Baseline {ctx.monitoring.get('baseline', {}).get('metric')} = "
        f"{ctx.monitoring.get('baseline', {}).get('value')}. "
        f"Drift status **{drift.get('status', 'unknown')}** (max PSI {drift.get('max_psi', 0)}).")
    add("")
    for alert in ctx.monitoring.get("alerts", []):
        add(f"- **{alert['signal']}** — warn at {alert['warn']}, critical at {alert['critical']}. "
            f"{alert['action']}")
    add("")

    add("## Recommendations")
    add("")
    for rec in _recommendations(ctx):
        add(f"- {rec}")
    add("")

    path = ctx.artifacts_dir / f"report_{ctx.run_id}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _recommendations(ctx) -> List[str]:
    out: List[str] = []
    leakage = [i for i in ctx.issues if i.category == "leakage"]
    if leakage:
        out.append(f"Confirm the {len(leakage)} leakage-flagged column(s) with a domain expert before "
                   "any of these numbers are quoted externally — they were dropped, but the underlying "
                   "collection process may still be leaking.")
    if ctx.leaderboard is not None and "overfit_gap" in ctx.leaderboard.columns:
        gap = float(ctx.leaderboard.iloc[0].get("overfit_gap", 0) or 0)
        if gap > 0.1:
            out.append(f"The winner's train/holdout gap is {gap:.3f}. Add regularisation or reduce "
                       "capacity before production.")
    imbalance = ctx.research.get("imbalance_ratio")
    if imbalance is not None and imbalance < 0.2:
        threshold = ctx.metrics.get("threshold_f1", {})
        if threshold:
            out.append(f"Ship at threshold {threshold.get('threshold')} rather than 0.5 — it lifts F1 to "
                       f"{threshold.get('f1')} on the same model.")
    if ctx.fairness.get("verdict") == "fail":
        out.append(f"Fairness gap on `{ctx.fairness['column']}` exceeds the release bar. Resolve before "
                   "deployment.")
    if ctx.monitoring.get("drift", {}).get("status") != "stable":
        out.append("Holdout already shows distribution movement — schedule the first drift review "
                   "within a week of go-live.")
    out.append("Wire the generated `/metrics` endpoint into your observability stack so the "
               "alert thresholds in this report actually fire.")
    return out


# ---------------------------------------------------------------- HTML
def generate_report_html(ctx) -> Path:
    charts: List[str] = []

    importance = ctx.explainability.get("global_importance", [])
    if importance:
        charts.append(svg.bar_chart(
            [{"label": f["feature"], "value": f["importance"]} for f in importance[:15]],
            title="What drives the model",
            subtitle=f"Top 15 features by {importance[0].get('source', 'importance')} attribution",
        ))

    if ctx.leaderboard is not None and not ctx.leaderboard.empty:
        primary = ctx.research.get("primary_metric", "accuracy")
        key = primary if primary in ctx.leaderboard.columns else (
            "accuracy" if "accuracy" in ctx.leaderboard.columns else "r2")
        rows = ctx.leaderboard[["model", key]].head(12).to_dict("records")
        charts.append(svg.bar_chart(
            [{"label": r["model"], "value": float(r[key] or 0)} for r in rows],
            title="Model leaderboard", subtitle=f"Holdout {key}, best first",
            color=palette.CATEGORICAL_LIGHT[0]))

    if ctx.task_type.value == "classification":
        matrix = ctx.metrics.get("confusion_matrix")
        if matrix:
            charts.append(svg.confusion_matrix(matrix, ctx.metrics.get("labels", []),
                                               subtitle="Counts on the holdout set"))
        roc = ctx.metrics.get("roc_curve")
        if roc:
            charts.append(svg.line_chart(
                [{"name": "ROC", "points": [{"x": p["fpr"], "y": p["tpr"]} for p in roc]}],
                title="ROC curve", subtitle=f"AUC {ctx.metrics.get('roc_auc', 0):.4f}",
                x_label="False positive rate", y_label="True positive rate",
                reference_diagonal=True))
        pr = ctx.metrics.get("pr_curve")
        if pr:
            charts.append(svg.line_chart(
                [{"name": "Precision–recall",
                  "points": [{"x": p["recall"], "y": p["precision"]} for p in pr]}],
                title="Precision–recall curve",
                subtitle=f"Average precision {ctx.metrics.get('pr_auc', 0):.4f}",
                x_label="Recall", y_label="Precision"))
    else:
        residuals = ctx.metrics.get("residual_histogram")
        if residuals:
            charts.append(svg.histogram(residuals["bins"], residuals["counts"],
                                        title="Residual distribution",
                                        subtitle="Centred residuals indicate an unbiased model"))

    matrix = ctx.eda.get("correlation_matrix", {})
    if matrix.get("columns"):
        charts.append(svg.heatmap(matrix["columns"], matrix["values"],
                                  title="Feature correlation",
                                  subtitle="Blue = negative, red = positive, gray = none"))

    drift = ctx.monitoring.get("drift", {}).get("features", [])
    if drift:
        charts.append(svg.bar_chart(
            [{"label": d["feature"], "value": d["psi"]} for d in drift[:12]],
            title="Drift baseline (PSI)",
            subtitle="Holdout vs training reference — above 0.25 triggers a retrain",
            color=palette.STATUS["warning"]))

    tiles = svg.stat_tiles(_headline_metrics(ctx))
    # No narrator configured, or it failed — drop the heading with it rather than print an
    # empty card, which reads as "we looked and found nothing to say".
    _summary_text = (ctx.explainability.get("business_summary") or "").strip()
    summary_block = (f'<h2>Executive summary</h2>\n'
                     f'  <div class="summary-card">{_markdown_lite(_summary_text)}</div>'
                     if _summary_text else "")
    issues = sorted(ctx.issues, key=lambda i: SEVERITY_ORDER.get(i.severity, 3))[:20]
    issue_rows = "".join(
        f'<tr><td><span class="pill pill-{svg._esc(i.severity)}">{svg._esc(i.severity)}</span></td>'
        f'<td>{svg._esc(i.category)}</td><td><code>{svg._esc(i.column or "—")}</code></td>'
        f'<td>{svg._esc(i.message)}</td></tr>' for i in issues)

    leaderboard_html = ""
    if ctx.leaderboard is not None:
        base = [c for c in ("rank", "model", "family") if c in ctx.leaderboard.columns]
        metrics = [c for c in ctx.leaderboard.columns
                   if c in ("roc_auc", "accuracy", "f1", "r2", "rmse", "mae", "cv_mean",
                            "overfit_gap", "fit_seconds")]
        leaderboard_html = ctx.leaderboard[base + metrics].head(20).to_html(
            index=False, border=0, classes="data-table", float_format=lambda v: f"{v:.4f}")

    recommendations = "".join(f"<li>{svg._esc(r)}</li>" for r in _recommendations(ctx))
    actions = "".join(f"<li><strong>{svg._esc(a['action'])}</strong> — {svg._esc(a['detail'])}</li>"
                      for a in ctx.cleaning_summary.get("actions", []))

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{svg._esc(ctx.target_column)} — dataid report</title>
<style>
{svg.VIZ_CSS}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; padding: 0; background: var(--plane); color: var(--text-primary);
  font-family: {svg.FONT}; line-height: 1.6;
}}
.wrap {{ max-width: 1080px; margin: 0 auto; padding: 56px 24px 96px; }}
header.masthead {{ margin-bottom: 40px; }}
.brand {{ font-size: 12px; letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--text-muted); margin-bottom: 10px; }}
h1 {{ font-size: 34px; line-height: 1.2; margin: 0 0 12px; font-weight: 680; }}
.meta {{ color: var(--text-secondary); font-size: 13px; }}
h2 {{ font-size: 20px; margin: 48px 0 14px; font-weight: 640;
  padding-bottom: 8px; border-bottom: 1px solid var(--grid); }}
p, li {{ color: var(--text-secondary); font-size: 14px; }}
code {{ background: var(--surface-1); border: 1px solid var(--border);
  padding: 1px 5px; border-radius: 5px; font-size: 12.5px; }}
pre {{ background: var(--surface-1); border: 1px solid var(--border); border-radius: 12px;
  padding: 16px; overflow-x: auto; font-size: 12.5px; color: var(--text-primary); }}
table.data-table {{ width: 100%; border-collapse: collapse; font-size: 12.5px;
  font-variant-numeric: tabular-nums; }}
table.data-table th, table.data-table td {{
  text-align: left; padding: 7px 11px; border-bottom: 1px solid var(--grid); }}
table.data-table th {{ color: var(--text-primary); font-weight: 600; }}
table.data-table tbody tr:first-child {{ background: color-mix(in srgb, var(--series-1) 8%, transparent); }}
.scroll-x {{ overflow-x: auto; border: 1px solid var(--border); border-radius: 12px;
  background: var(--surface-1); padding: 4px 8px; }}
.pill {{ display: inline-block; padding: 1px 9px; border-radius: 999px;
  font-size: 11px; font-weight: 600; }}
.pill-critical {{ background: color-mix(in srgb, var(--status-critical) 18%, transparent);
  color: var(--status-critical); }}
.pill-warning {{ background: color-mix(in srgb, var(--status-warning) 22%, transparent);
  color: var(--text-primary); }}
.pill-info {{ background: color-mix(in srgb, var(--series-1) 14%, transparent); color: var(--series-1); }}
.chart-grid {{ display: grid; gap: 20px; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); }}
.summary-card {{ background: var(--surface-1); border: 1px solid var(--border);
  border-radius: 14px; padding: 22px 24px; }}
@media (max-width: 720px) {{ .chart-grid {{ grid-template-columns: 1fr; }} h1 {{ font-size: 26px; }} }}
</style>
</head>
<body>
<div class="wrap viz-root">
  <header class="masthead">
    <div class="brand">dataid · automated analysis</div>
    <h1>{svg._esc(ctx.target_column)}</h1>
    <p class="meta">Run <code>{svg._esc(ctx.run_id)}</code> · {svg._esc(ctx.task_type.value)} ·
       winner <strong>{svg._esc(ctx.best_model_name)}</strong> ·
       {datetime.now(timezone.utc).strftime('%d %b %Y %H:%M UTC')}</p>
  </header>

  {summary_block}

  <h2>Headline metrics</h2>
  {tiles}

  <h2>Dataset overview</h2>
  <p>{ctx.profile.get('rows', 0):,} rows × {ctx.profile.get('n_columns', 0)} columns ·
     {ctx.profile.get('total_missing_cells', 0):,} missing cells ·
     {ctx.profile.get('duplicate_rows', 0):,} duplicate rows.</p>

  <h2>What the Data Detective found</h2>
  <div class="scroll-x"><table class="data-table">
    <thead><tr><th>Severity</th><th>Category</th><th>Column</th><th>Finding</th></tr></thead>
    <tbody>{issue_rows or '<tr><td colspan="4">No blocking issues.</td></tr>'}</tbody>
  </table></div>

  <h2>Cleaning &amp; feature engineering</h2>
  <ul>{actions}</ul>
  <p>{ctx.feature_summary.get('n_created', 0)} features derived; the frame expands to
     <strong>{ctx.feature_summary.get('n_features_out', 0)}</strong> model-ready columns.</p>

  <h2>Model comparison</h2>
  <div class="scroll-x">{leaderboard_html}</div>

  <h2>Charts</h2>
  <div class="chart-grid">{''.join(charts)}</div>

  <h2>Deployment</h2>
  <pre>{svg._esc(ctx.deployment.get('docker_command', ''))}</pre>

  <h2>Recommendations</h2>
  <ol>{recommendations}</ol>
</div>
</body>
</html>"""

    path = ctx.artifacts_dir / f"report_{ctx.run_id}.html"
    path.write_text(html_doc, encoding="utf-8")
    return path


def _markdown_lite(text: str) -> str:
    """Just enough Markdown for the narrative blocks: bold, inline code, paragraphs."""
    escaped = svg._esc(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped, flags=re.S)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    return "".join(f"<p>{block.strip()}</p>" for block in escaped.split(chr(10) * 2) if block.strip())
