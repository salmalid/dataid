"""Validated chart palette, shared by every generated artifact.

Data encoding uses these hues only. The dataid brand gradient (indigo/violet) is
UI chrome and never carries a data value.

Validated with the dataviz palette checker: all checks pass in both modes on the
adjacent pairlist. Light mode carries a sub-3:1 contrast WARN on aqua/yellow/magenta,
so every chart that uses those slots ships direct labels or an accompanying table.
"""
from __future__ import annotations

from typing import Dict, List

# Slot order is the CVD-safety mechanism — assign in order, never cycle.
CATEGORICAL_LIGHT: List[str] = [
    "#2a78d6",  # 1 blue
    "#eb6834",  # 2 orange
    "#1baf7a",  # 3 aqua
    "#eda100",  # 4 yellow
    "#e87ba4",  # 5 magenta
    "#008300",  # 6 green
    "#4a3aa7",  # 7 violet
    "#e34948",  # 8 red
]
CATEGORICAL_DARK: List[str] = [
    "#3987e5", "#d95926", "#199e70", "#c98500",
    "#d55181", "#008300", "#9085e9", "#e66767",
]

# Scatter / heatmap / small-multiple forms need all-pairs separation — capped at 3.
ALL_PAIRS_CAP = 3

SEQUENTIAL_BLUE: List[str] = [
    "#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec",
    "#5598e7", "#3987e5", "#2a78d6", "#256abf", "#1c5cab",
    "#184f95", "#104281", "#0d366b",
]

DIVERGING = {"low": "#2a78d6", "mid_light": "#f0efec", "mid_dark": "#383835", "high": "#d03b3b"}

STATUS: Dict[str, str] = {
    "good": "#0ca30c",
    "warning": "#fab219",
    "serious": "#ec835a",
    "critical": "#d03b3b",
}

CHROME = {
    "light": {
        "surface": "#fcfcfb",
        "plane": "#f9f9f7",
        "text_primary": "#0b0b0b",
        "text_secondary": "#52514e",
        "muted": "#898781",
        "grid": "#e1e0d9",
        "axis": "#c3c2b7",
        "border": "rgba(11,11,11,0.10)",
        "success_text": "#006300",
    },
    "dark": {
        "surface": "#1a1a19",
        "plane": "#0d0d0d",
        "text_primary": "#ffffff",
        "text_secondary": "#c3c2b7",
        "muted": "#898781",
        "grid": "#2c2c2a",
        "axis": "#383835",
        "border": "rgba(255,255,255,0.10)",
        "success_text": "#0ca30c",
    },
}


def series_color(index: int, mode: str = "light") -> str:
    ramp = CATEGORICAL_DARK if mode == "dark" else CATEGORICAL_LIGHT
    return ramp[index % len(ramp)]


def sequential_color(value: float, vmin: float = 0.0, vmax: float = 1.0) -> str:
    """Map a magnitude onto the single-hue blue ramp."""
    if vmax <= vmin:
        return SEQUENTIAL_BLUE[len(SEQUENTIAL_BLUE) // 2]
    t = max(0.0, min(1.0, (value - vmin) / (vmax - vmin)))
    return SEQUENTIAL_BLUE[round(t * (len(SEQUENTIAL_BLUE) - 1))]


def diverging_color(value: float, scale: float = 1.0, mode: str = "light") -> str:
    """Blue (negative) ↔ neutral gray ↔ red (positive). Never a hue at the midpoint."""
    t = max(-1.0, min(1.0, value / scale if scale else 0.0))
    neutral = DIVERGING["mid_dark"] if mode == "dark" else DIVERGING["mid_light"]
    if abs(t) < 0.08:
        return neutral
    pole = DIVERGING["high"] if t > 0 else DIVERGING["low"]
    return _mix(neutral, pole, abs(t))


def status_color(level: str) -> str:
    return STATUS.get(level, STATUS["good"])


def _mix(a: str, b: str, t: float) -> str:
    ar, ag, ab = _rgb(a)
    br, bg, bb = _rgb(b)
    return "#{:02x}{:02x}{:02x}".format(
        round(ar + (br - ar) * t), round(ag + (bg - ag) * t), round(ab + (bb - ab) * t)
    )


def _rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def css_variables() -> str:
    """Emit the role tokens for both modes, toggle-aware."""
    def block(mode: str) -> str:
        c = CHROME[mode]
        ramp = CATEGORICAL_DARK if mode == "dark" else CATEGORICAL_LIGHT
        series = "\n".join(f"  --series-{i + 1}: {hexv};" for i, hexv in enumerate(ramp))
        return f"""  color-scheme: {mode};
  --surface-1: {c['surface']};
  --plane: {c['plane']};
  --text-primary: {c['text_primary']};
  --text-secondary: {c['text_secondary']};
  --text-muted: {c['muted']};
  --grid: {c['grid']};
  --axis: {c['axis']};
  --border: {c['border']};
  --success-text: {c['success_text']};
  --status-good: {STATUS['good']};
  --status-warning: {STATUS['warning']};
  --status-serious: {STATUS['serious']};
  --status-critical: {STATUS['critical']};
{series}"""

    return f""".viz-root {{
{block('light')}
}}
@media (prefers-color-scheme: dark) {{
  :root:where(:not([data-theme="light"])) .viz-root {{
{block('dark')}
  }}
}}
:root[data-theme="dark"] .viz-root {{
{block('dark')}
}}"""
