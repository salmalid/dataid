"""Dependency-free inline SVG charts for the generated report and dashboard.

Mark specs follow the house rules: 2px lines, 4px rounded data-ends anchored to the
baseline, >=8px markers, a 2px surface gap between adjacent fills, recessive grid,
selective direct labels, and a table view beside every chart for the relief rule.
"""
from __future__ import annotations

import html
from typing import Any, Dict, List, Optional, Sequence

from . import palette

FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'


def _esc(text: Any) -> str:
    return html.escape(str(text))


def _fmt(value: float, digits: int = 3) -> str:
    if value is None:
        return "—"
    if abs(value) >= 1000:
        return f"{value:,.0f}"
    return f"{value:.{digits}f}".rstrip("0").rstrip(".") or "0"


def figure(title: str, subtitle: str, body: str, table: str = "") -> str:
    caption = f'<p class="viz-sub">{_esc(subtitle)}</p>' if subtitle else ""
    details = f"""<details class="viz-table">
  <summary>Table view</summary>
  {table}
</details>""" if table else ""
    return f"""<figure class="viz-figure viz-root">
  <figcaption>
    <h3>{_esc(title)}</h3>
    {caption}
  </figcaption>
  {body}
  {details}
</figure>"""


def _table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    head = "".join(f"<th>{_esc(h)}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{_esc(c)}</td>" for c in row) + "</tr>" for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def legend(entries: Sequence[tuple[str, str]]) -> str:
    """Always present for >= 2 series; identity is never carried by color alone."""
    if len(entries) < 2:
        return ""
    items = "".join(
        f'<li><span class="viz-swatch" style="background:{color}"></span>{_esc(label)}</li>'
        for label, color in entries
    )
    return f'<ul class="viz-legend">{items}</ul>'


# ---------------------------------------------------------------- horizontal bars
def bar_chart(items: List[Dict[str, Any]], *, title: str, subtitle: str = "",
              label_key: str = "label", value_key: str = "value",
              color: Optional[str] = None, unit: str = "", max_items: int = 15) -> str:
    items = items[:max_items]
    if not items:
        return figure(title, subtitle, '<p class="viz-empty">No data.</p>')

    values = [float(i[value_key] or 0) for i in items]
    peak = max(abs(v) for v in values) or 1.0
    row_h, gap, label_w, track_w = 26, 2, 210, 340
    height = len(items) * (row_h + gap) + 8
    fill = color or palette.CATEGORICAL_LIGHT[0]

    rows = []
    for idx, (item, value) in enumerate(zip(items, values)):
        y = idx * (row_h + gap)
        width = max(abs(value) / peak * track_w, 2)
        rows.append(f"""
    <text x="{label_w - 10}" y="{y + row_h / 2 + 4}" text-anchor="end"
          class="viz-axis-label">{_esc(item[label_key])[:34]}</text>
    <rect x="{label_w}" y="{y + 3}" width="{width:.2f}" height="{row_h - 6}"
          rx="4" fill="{fill}"><title>{_esc(item[label_key])}: {_fmt(value)}{unit}</title></rect>
    <text x="{label_w + width + 8}" y="{y + row_h / 2 + 4}"
          class="viz-value">{_fmt(value)}{unit}</text>""")

    svg = f"""<svg viewBox="0 0 {label_w + track_w + 90} {height}" width="100%"
       role="img" aria-label="{_esc(title)}" class="viz-svg">
    <line x1="{label_w}" y1="0" x2="{label_w}" y2="{height}" class="viz-baseline" />
    {''.join(rows)}
  </svg>"""

    table = _table(["Item", "Value"], [[i[label_key], _fmt(float(i[value_key] or 0))] for i in items])
    return figure(title, subtitle, svg, table)


# ---------------------------------------------------------------- line / curve
def line_chart(series: List[Dict[str, Any]], *, title: str, subtitle: str = "",
               x_label: str = "", y_label: str = "", reference_diagonal: bool = False) -> str:
    if not series or not any(s.get("points") for s in series):
        return figure(title, subtitle, '<p class="viz-empty">No data.</p>')

    w, h = 560, 320
    pad_l, pad_b, pad_t, pad_r = 52, 40, 16, 20
    plot_w, plot_h = w - pad_l - pad_r, h - pad_t - pad_b

    xs = [p["x"] for s in series for p in s["points"]]
    ys = [p["y"] for s in series for p in s["points"]]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    x_span = (x_max - x_min) or 1.0
    y_span = (y_max - y_min) or 1.0

    def px(x: float) -> float:
        return pad_l + (x - x_min) / x_span * plot_w

    def py(y: float) -> float:
        return pad_t + plot_h - (y - y_min) / y_span * plot_h

    grid = []
    for i in range(5):
        y = pad_t + plot_h * i / 4
        value = y_max - y_span * i / 4
        grid.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{w - pad_r}" y2="{y:.1f}" class="viz-grid" />'
                    f'<text x="{pad_l - 8}" y="{y + 4:.1f}" text-anchor="end" class="viz-axis-label">'
                    f'{_fmt(value, 2)}</text>')

    diagonal = (f'<line x1="{px(x_min)}" y1="{py(y_min)}" x2="{px(x_max)}" y2="{py(y_max)}" '
                f'class="viz-reference" />') if reference_diagonal else ""

    paths, labels, entries = [], [], []
    for i, s in enumerate(series):
        color = palette.series_color(i)
        pts = s["points"]
        d = " ".join(f"{'M' if j == 0 else 'L'}{px(p['x']):.2f},{py(p['y']):.2f}"
                     for j, p in enumerate(pts))
        paths.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2" '
                     f'stroke-linejoin="round" stroke-linecap="round" />')
        entries.append((s.get("name", f"Series {i + 1}"), color))
        if len(series) <= 4 and pts:
            last = pts[-1]
            labels.append(f'<text x="{px(last["x"]) - 4:.1f}" y="{py(last["y"]) - 9:.1f}" '
                          f'text-anchor="end" class="viz-direct-label">{_esc(s.get("name", ""))}</text>')

    svg = f"""<svg viewBox="0 0 {w} {h}" width="100%" role="img"
       aria-label="{_esc(title)}" class="viz-svg">
    {''.join(grid)}
    <line x1="{pad_l}" y1="{pad_t + plot_h}" x2="{w - pad_r}" y2="{pad_t + plot_h}" class="viz-baseline" />
    {diagonal}
    {''.join(paths)}
    {''.join(labels)}
    <text x="{pad_l + plot_w / 2}" y="{h - 6}" text-anchor="middle" class="viz-axis-title">{_esc(x_label)}</text>
    <text x="12" y="{pad_t + plot_h / 2}" text-anchor="middle" class="viz-axis-title"
          transform="rotate(-90 12 {pad_t + plot_h / 2})">{_esc(y_label)}</text>
  </svg>{legend(entries)}"""

    rows = [[s.get("name", ""), len(s["points"]),
             _fmt(min(p["y"] for p in s["points"])), _fmt(max(p["y"] for p in s["points"]))]
            for s in series]
    return figure(title, subtitle, svg, _table(["Series", "Points", "Min", "Max"], rows))


# ---------------------------------------------------------------- histogram
def histogram(bins: Sequence[float], counts: Sequence[int], *, title: str,
              subtitle: str = "", color: Optional[str] = None) -> str:
    if not counts:
        return figure(title, subtitle, '<p class="viz-empty">No data.</p>')
    w, h = 560, 220
    pad_l, pad_b, pad_t = 44, 34, 12
    plot_w, plot_h = w - pad_l - 16, h - pad_t - pad_b
    peak = max(counts) or 1
    slot = plot_w / len(counts)
    fill = color or palette.CATEGORICAL_LIGHT[0]

    bars = []
    for i, count in enumerate(counts):
        bar_h = count / peak * plot_h
        x = pad_l + i * slot
        bars.append(f'<rect x="{x + 1:.2f}" y="{pad_t + plot_h - bar_h:.2f}" '
                    f'width="{max(slot - 2, 1):.2f}" height="{max(bar_h, 1):.2f}" rx="4" '
                    f'fill="{fill}"><title>{_fmt(bins[i], 2) if i < len(bins) else i}: {count}</title></rect>')

    ticks = []
    for i in (0, len(counts) // 2, len(counts) - 1):
        if i < len(bins):
            ticks.append(f'<text x="{pad_l + i * slot + slot / 2:.1f}" y="{h - 14}" '
                         f'text-anchor="middle" class="viz-axis-label">{_fmt(bins[i], 2)}</text>')

    svg = f"""<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="{_esc(title)}" class="viz-svg">
    <line x1="{pad_l}" y1="{pad_t + plot_h}" x2="{w - 16}" y2="{pad_t + plot_h}" class="viz-baseline" />
    <text x="{pad_l - 8}" y="{pad_t + 10}" text-anchor="end" class="viz-axis-label">{peak}</text>
    {''.join(bars)}{''.join(ticks)}
  </svg>"""
    rows = [[_fmt(b, 3), c] for b, c in zip(bins, counts)]
    return figure(title, subtitle, svg, _table(["Bin centre", "Count"], rows))


# ---------------------------------------------------------------- heatmap
def heatmap(columns: Sequence[str], values: Sequence[Sequence[float]], *, title: str,
            subtitle: str = "", diverging: bool = True, max_size: int = 14) -> str:
    columns = list(columns)[:max_size]
    if len(columns) < 2:
        return figure(title, subtitle, '<p class="viz-empty">Not enough numeric columns.</p>')
    values = [list(row)[:max_size] for row in list(values)[:max_size]]

    cell, label_w, label_h = 30, 128, 96
    w = label_w + len(columns) * cell + 12
    h = label_h + len(columns) * cell + 12

    cells = []
    for r, row in enumerate(values):
        for c, value in enumerate(row):
            fill = palette.diverging_color(value, 1.0) if diverging \
                else palette.sequential_color(value, 0, 1)
            cells.append(
                f'<rect x="{label_w + c * cell}" y="{label_h + r * cell}" '
                f'width="{cell - 2}" height="{cell - 2}" rx="3" fill="{fill}">'
                f'<title>{_esc(columns[r])} × {_esc(columns[c])}: {_fmt(value, 2)}</title></rect>'
            )

    y_labels = "".join(
        f'<text x="{label_w - 8}" y="{label_h + i * cell + cell / 2 + 3}" text-anchor="end" '
        f'class="viz-axis-label">{_esc(c)[:18]}</text>' for i, c in enumerate(columns))
    x_labels = "".join(
        f'<text x="{label_w + i * cell + cell / 2}" y="{label_h - 8}" text-anchor="start" '
        f'class="viz-axis-label" transform="rotate(-55 {label_w + i * cell + cell / 2} {label_h - 8})">'
        f'{_esc(c)[:16]}</text>' for i, c in enumerate(columns))

    scale = (f'<g><rect x="{label_w}" y="{h - 6}" width="0" height="0" /></g>')

    svg = f"""<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="{_esc(title)}" class="viz-svg">
    {x_labels}{y_labels}{''.join(cells)}{scale}
  </svg>
  <p class="viz-scale"><span class="viz-scale-swatch" style="background:{palette.DIVERGING['low']}"></span>
     −1 &nbsp;·&nbsp; 0 &nbsp;·&nbsp; +1
     <span class="viz-scale-swatch" style="background:{palette.DIVERGING['high']}"></span></p>"""

    rows = [[columns[r]] + [_fmt(v, 2) for v in row] for r, row in enumerate(values)]
    return figure(title, subtitle, svg, _table([""] + list(columns), rows))


# ---------------------------------------------------------------- confusion matrix
def confusion_matrix(matrix: Sequence[Sequence[int]], labels: Sequence[str], *,
                     title: str = "Confusion matrix", subtitle: str = "") -> str:
    if not matrix:
        return figure(title, subtitle, '<p class="viz-empty">No data.</p>')
    n = len(matrix)
    cell = 74
    pad = 110
    w, h = pad + n * cell + 12, pad + n * cell + 12
    peak = max(max(row) for row in matrix) or 1

    cells = []
    for r, row in enumerate(matrix):
        for c, value in enumerate(row):
            fill = palette.sequential_color(value, 0, peak)
            ink = "#ffffff" if value / peak > 0.55 else palette.CHROME["light"]["text_primary"]
            cells.append(
                f'<rect x="{pad + c * cell}" y="{pad + r * cell}" width="{cell - 2}" '
                f'height="{cell - 2}" rx="4" fill="{fill}" />'
                f'<text x="{pad + c * cell + cell / 2 - 1}" y="{pad + r * cell + cell / 2 + 5}" '
                f'text-anchor="middle" style="fill:{ink};font-weight:600;font-size:13px">{value:,}</text>')

    y_labels = "".join(
        f'<text x="{pad - 10}" y="{pad + i * cell + cell / 2 + 4}" text-anchor="end" '
        f'class="viz-axis-label">{_esc(l)[:14]}</text>' for i, l in enumerate(labels))
    x_labels = "".join(
        f'<text x="{pad + i * cell + cell / 2}" y="{pad - 12}" text-anchor="middle" '
        f'class="viz-axis-label">{_esc(l)[:14]}</text>' for i, l in enumerate(labels))

    svg = f"""<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="{_esc(title)}" class="viz-svg">
    <text x="{pad + n * cell / 2}" y="20" text-anchor="middle" class="viz-axis-title">Predicted</text>
    <text x="18" y="{pad + n * cell / 2}" text-anchor="middle" class="viz-axis-title"
          transform="rotate(-90 18 {pad + n * cell / 2})">Actual</text>
    {x_labels}{y_labels}{''.join(cells)}
  </svg>"""
    rows = [[labels[r]] + [f"{v:,}" for v in row] for r, row in enumerate(matrix)]
    return figure(title, subtitle, svg, _table(["actual \\ predicted"] + list(labels), rows))


# ---------------------------------------------------------------- stat tiles
def stat_tiles(tiles: List[Dict[str, Any]]) -> str:
    cards = []
    for tile in tiles:
        delta = ""
        if tile.get("delta") is not None:
            direction = "up" if tile["delta"] >= 0 else "down"
            arrow = "▲" if direction == "up" else "▼"
            delta = (f'<span class="viz-delta viz-delta-{direction}">{arrow} '
                     f'{_fmt(abs(tile["delta"]), 3)}</span>')
        status = f' data-status="{tile["status"]}"' if tile.get("status") else ""
        cards.append(f"""<div class="viz-tile"{status}>
      <span class="viz-tile-label">{_esc(tile['label'])}</span>
      <span class="viz-tile-value">{_esc(tile['value'])}</span>
      <span class="viz-tile-foot">{_esc(tile.get('caption', ''))} {delta}</span>
    </div>""")
    return f'<div class="viz-tiles viz-root">{"".join(cards)}</div>'


VIZ_CSS = palette.css_variables() + f"""
.viz-root {{ font-family: {FONT}; }}
.viz-figure {{
  margin: 0 0 28px; padding: 20px; border-radius: 14px;
  background: var(--surface-1); border: 1px solid var(--border);
}}
.viz-figure figcaption h3 {{
  margin: 0 0 2px; font-size: 15px; font-weight: 600; color: var(--text-primary);
}}
.viz-sub {{ margin: 0 0 14px; font-size: 13px; color: var(--text-secondary); }}
.viz-svg {{ display: block; max-width: 100%; height: auto; overflow: visible; }}
.viz-grid {{ stroke: var(--grid); stroke-width: 1; }}
.viz-baseline {{ stroke: var(--axis); stroke-width: 1; }}
.viz-reference {{ stroke: var(--axis); stroke-width: 1.5; stroke-dasharray: 5 4; }}
.viz-axis-label {{ font-size: 11px; fill: var(--text-muted); font-variant-numeric: tabular-nums; }}
.viz-axis-title {{ font-size: 11px; fill: var(--text-secondary); font-weight: 500; }}
.viz-direct-label {{ font-size: 11px; fill: var(--text-secondary); font-weight: 600; }}
.viz-value {{ font-size: 11px; fill: var(--text-secondary); font-variant-numeric: tabular-nums; }}
.viz-empty {{ font-size: 13px; color: var(--text-muted); margin: 8px 0; }}
.viz-legend {{
  display: flex; flex-wrap: wrap; gap: 6px 18px; list-style: none;
  margin: 12px 0 0; padding: 0; font-size: 12px; color: var(--text-secondary);
}}
.viz-legend li {{ display: flex; align-items: center; gap: 7px; }}
.viz-swatch {{ width: 10px; height: 10px; border-radius: 3px; display: inline-block; }}
.viz-scale {{ font-size: 11px; color: var(--text-muted); display: flex;
  align-items: center; gap: 8px; margin: 10px 0 0; }}
.viz-scale-swatch {{ width: 26px; height: 8px; border-radius: 3px; display: inline-block; }}
.viz-table {{ margin-top: 14px; font-size: 12px; color: var(--text-secondary); }}
.viz-table summary {{ cursor: pointer; color: var(--text-secondary); }}
.viz-table table {{ border-collapse: collapse; margin-top: 10px; width: 100%; }}
.viz-table th, .viz-table td {{
  text-align: left; padding: 5px 10px; border-bottom: 1px solid var(--grid);
  font-variant-numeric: tabular-nums;
}}
.viz-table th {{ color: var(--text-primary); font-weight: 600; }}
.viz-tiles {{ display: grid; gap: 14px; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); margin-bottom: 28px; }}
.viz-tile {{
  padding: 16px 18px; border-radius: 14px; background: var(--surface-1);
  border: 1px solid var(--border); display: flex; flex-direction: column; gap: 6px;
}}
.viz-tile-label {{ font-size: 12px; color: var(--text-secondary); }}
.viz-tile-value {{ font-size: 26px; font-weight: 650; color: var(--text-primary); line-height: 1.1; }}
.viz-tile-foot {{ font-size: 11px; color: var(--text-muted); }}
.viz-delta-up {{ color: var(--success-text); font-weight: 600; }}
.viz-delta-down {{ color: var(--status-critical); font-weight: 600; }}
.viz-tile[data-status="critical"] {{ border-color: var(--status-critical); }}
.viz-tile[data-status="warning"] {{ border-color: var(--status-warning); }}
"""
