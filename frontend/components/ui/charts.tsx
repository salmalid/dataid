"use client";

/**
 * Chart primitives.
 *
 * Colour rules enforced here, not left to callers:
 *  - categorical hues are assigned in fixed slot order and never cycled past 8
 *  - sequential encoding is one hue, light -> dark
 *  - diverging is blue <-> neutral gray <-> red, never a hue at the midpoint
 *  - a legend is rendered whenever there are >= 2 series; one series is named by the title
 *  - every chart carries a table view, which is also the relief for the light-mode
 *    sub-3:1 contrast slots
 */

import { useId, useMemo, useState, type ReactNode } from "react";
import { cn, formatNumber, seriesVar, truncate } from "@/lib/utils";

const AXIS = "fill-[color:var(--viz-label)] text-[10.5px] tnum";

/* ------------------------------------------------------------------ shell */
export function Figure({
  title,
  subtitle,
  legend,
  table,
  className,
  children,
}: {
  title: string;
  subtitle?: string;
  legend?: { label: string; color: string }[];
  table?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  const [showTable, setShowTable] = useState(false);
  return (
    <figure
      className={cn(
        "surface-card overflow-hidden p-5 shadow-card dark:shadow-card-dark",
        className,
      )}
    >
      <figcaption className="mb-4 flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h3 className="text-[14.5px] font-semibold leading-tight">{title}</h3>
          {subtitle && <p className="mt-1 text-[12.5px] text-secondary">{subtitle}</p>}
        </div>
        {table && (
          <button
            type="button"
            onClick={() => setShowTable((value) => !value)}
            className="shrink-0 rounded-lg px-2 py-1 text-[11.5px] text-secondary transition-colors hover:bg-black/[0.04] focus-ring dark:hover:bg-white/[0.06]"
          >
            {showTable ? "Chart" : "Table"}
          </button>
        )}
      </figcaption>

      {showTable && table ? (
        <div className="max-h-80 overflow-auto">{table}</div>
      ) : (
        <div className="overflow-x-auto">{children}</div>
      )}

      {legend && legend.length >= 2 && !showTable && (
        <ul className="mt-4 flex flex-wrap gap-x-5 gap-y-1.5 text-[12px] text-secondary">
          {legend.map((entry) => (
            <li key={entry.label} className="flex items-center gap-2">
              <span
                className="h-2.5 w-2.5 rounded-[3px]"
                style={{ background: entry.color }}
                aria-hidden
              />
              {entry.label}
            </li>
          ))}
        </ul>
      )}
    </figure>
  );
}

function MiniTable({
  headers,
  rows,
}: {
  headers: string[];
  rows: (string | number)[][];
}) {
  return (
    <table className="w-full text-[12px] tnum">
      <thead className="sticky top-0 bg-surface">
        <tr className="border-b">
          {headers.map((header) => (
            <th key={header} className="px-3 py-2 text-left font-semibold">
              {header}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, index) => (
          <tr key={index} className="border-b last:border-0">
            {row.map((cell, cellIndex) => (
              <td key={cellIndex} className="px-3 py-1.5 text-secondary">
                {typeof cell === "number" ? formatNumber(cell, 4) : cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/* ------------------------------------------------------------------ bars */
export interface BarDatum {
  label: string;
  value: number;
}

export function BarChart({
  data,
  title,
  subtitle,
  color,
  unit = "",
  max = 15,
  formatValue,
  className,
}: {
  data: BarDatum[];
  title: string;
  subtitle?: string;
  color?: string;
  unit?: string;
  max?: number;
  formatValue?: (value: number) => string;
  className?: string;
}) {
  const items = data.slice(0, max);
  const peak = Math.max(...items.map((item) => Math.abs(item.value)), 1e-9);
  const fill = color ?? seriesVar(0);
  const format = formatValue ?? ((value: number) => formatNumber(value, 4));

  const rowHeight = 26;
  const gap = 2;
  const labelWidth = 168;
  const trackWidth = 300;
  const height = items.length * (rowHeight + gap) + 6;

  if (!items.length) return <Figure title={title} subtitle={subtitle}>{<Empty />}</Figure>;

  return (
    <Figure
      title={title}
      subtitle={subtitle}
      className={className}
      table={
        <MiniTable
          headers={["Item", "Value"]}
          rows={items.map((item) => [item.label, item.value])}
        />
      }
    >
      <svg
        viewBox={`0 0 ${labelWidth + trackWidth + 78} ${height}`}
        className="w-full"
        style={{ minWidth: 420 }}
        role="img"
        aria-label={title}
      >
        <line
          x1={labelWidth}
          y1={0}
          x2={labelWidth}
          y2={height}
          stroke="var(--viz-axis)"
          strokeWidth={1}
        />
        {items.map((item, index) => {
          const y = index * (rowHeight + gap);
          const width = Math.max((Math.abs(item.value) / peak) * trackWidth, 2);
          return (
            <g key={`${item.label}-${index}`} className="group">
              <rect
                x={0}
                y={y}
                width={labelWidth + trackWidth + 78}
                height={rowHeight}
                fill="transparent"
                className="group-hover:fill-black/[0.03] dark:group-hover:fill-white/[0.05]"
              />
              <text x={labelWidth - 10} y={y + rowHeight / 2 + 4} textAnchor="end" className={AXIS}>
                {truncate(item.label, 26)}
              </text>
              <rect
                x={labelWidth}
                y={y + 3}
                width={width}
                height={rowHeight - 6}
                rx={4}
                fill={fill}
              >
                <title>{`${item.label}: ${format(item.value)}${unit}`}</title>
              </rect>
              <text
                x={labelWidth + width + 8}
                y={y + rowHeight / 2 + 4}
                className="fill-[color:var(--ink-secondary)] text-[10.5px] tnum"
              >
                {format(item.value)}
                {unit}
              </text>
            </g>
          );
        })}
      </svg>
    </Figure>
  );
}

/* ------------------------------------------------------------------ line */
export interface Series {
  name: string;
  points: { x: number; y: number }[];
}

export function LineChart({
  series,
  title,
  subtitle,
  xLabel,
  yLabel,
  referenceDiagonal,
  className,
}: {
  series: Series[];
  title: string;
  subtitle?: string;
  xLabel?: string;
  yLabel?: string;
  referenceDiagonal?: boolean;
  className?: string;
}) {
  const id = useId();
  const [hover, setHover] = useState<{ x: number; y: number; label: string } | null>(null);

  const bounds = useMemo(() => {
    const xs = series.flatMap((s) => s.points.map((p) => p.x));
    const ys = series.flatMap((s) => s.points.map((p) => p.y));
    if (!xs.length) return null;
    const xMin = Math.min(...xs);
    const xMax = Math.max(...xs);
    const yMin = Math.min(...ys);
    const yMax = Math.max(...ys);
    return {
      xMin,
      xMax,
      yMin,
      yMax,
      xSpan: xMax - xMin || 1,
      ySpan: yMax - yMin || 1,
    };
  }, [series]);

  if (!bounds) return <Figure title={title} subtitle={subtitle}>{<Empty />}</Figure>;

  const width = 520;
  const height = 300;
  const padding = { left: 50, right: 22, top: 14, bottom: 38 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;

  const px = (x: number) => padding.left + ((x - bounds.xMin) / bounds.xSpan) * plotWidth;
  const py = (y: number) => padding.top + plotHeight - ((y - bounds.yMin) / bounds.ySpan) * plotHeight;

  const legend = series.map((s, index) => ({ label: s.name, color: seriesVar(index) }));

  return (
    <Figure
      title={title}
      subtitle={subtitle}
      legend={legend}
      className={className}
      table={
        <MiniTable
          headers={["Series", "Points", "Min y", "Max y"]}
          rows={series.map((s) => [
            s.name,
            s.points.length,
            Math.min(...s.points.map((p) => p.y)),
            Math.max(...s.points.map((p) => p.y)),
          ])}
        />
      }
    >
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full"
        style={{ minWidth: 420 }}
        role="img"
        aria-label={title}
        onMouseLeave={() => setHover(null)}
      >
        {[0, 1, 2, 3, 4].map((step) => {
          const y = padding.top + (plotHeight * step) / 4;
          const value = bounds.yMax - (bounds.ySpan * step) / 4;
          return (
            <g key={step}>
              <line
                x1={padding.left}
                y1={y}
                x2={width - padding.right}
                y2={y}
                stroke="var(--viz-grid)"
                strokeWidth={1}
              />
              <text x={padding.left - 8} y={y + 4} textAnchor="end" className={AXIS}>
                {value.toFixed(2)}
              </text>
            </g>
          );
        })}

        <line
          x1={padding.left}
          y1={padding.top + plotHeight}
          x2={width - padding.right}
          y2={padding.top + plotHeight}
          stroke="var(--viz-axis)"
        />

        {referenceDiagonal && (
          <line
            x1={px(bounds.xMin)}
            y1={py(bounds.yMin)}
            x2={px(bounds.xMax)}
            y2={py(bounds.yMax)}
            stroke="var(--viz-axis)"
            strokeWidth={1.5}
            strokeDasharray="5 4"
          />
        )}

        {series.map((s, index) => (
          <path
            key={`${id}-${s.name}`}
            d={s.points
              .map((point, i) => `${i === 0 ? "M" : "L"}${px(point.x).toFixed(2)},${py(point.y).toFixed(2)}`)
              .join(" ")}
            fill="none"
            stroke={seriesVar(index)}
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ))}

        {/* crosshair hit layer — bigger target than the marks themselves */}
        {series[0]?.points.map((point, index) => (
          <rect
            key={index}
            x={px(point.x) - 6}
            y={padding.top}
            width={12}
            height={plotHeight}
            fill="transparent"
            onMouseEnter={() =>
              setHover({
                x: px(point.x),
                y: py(point.y),
                label: `${xLabel ?? "x"} ${point.x.toFixed(3)} · ${yLabel ?? "y"} ${point.y.toFixed(3)}`,
              })
            }
          />
        ))}

        {hover && (
          <g pointerEvents="none">
            <line
              x1={hover.x}
              y1={padding.top}
              x2={hover.x}
              y2={padding.top + plotHeight}
              stroke="var(--viz-axis)"
              strokeWidth={1}
            />
            <circle cx={hover.x} cy={hover.y} r={5} fill={seriesVar(0)} stroke="var(--surface)" strokeWidth={2} />
            <text
              x={Math.min(hover.x + 10, width - 150)}
              y={padding.top + 14}
              className="fill-[color:var(--ink)] text-[11px] font-medium tnum"
            >
              {hover.label}
            </text>
          </g>
        )}

        {xLabel && (
          <text
            x={padding.left + plotWidth / 2}
            y={height - 6}
            textAnchor="middle"
            className="fill-[color:var(--ink-secondary)] text-[10.5px]"
          >
            {xLabel}
          </text>
        )}
        {yLabel && (
          <text
            x={12}
            y={padding.top + plotHeight / 2}
            textAnchor="middle"
            transform={`rotate(-90 12 ${padding.top + plotHeight / 2})`}
            className="fill-[color:var(--ink-secondary)] text-[10.5px]"
          >
            {yLabel}
          </text>
        )}
      </svg>
    </Figure>
  );
}

/* ------------------------------------------------------------------ histogram */
export function Histogram({
  bins,
  counts,
  title,
  subtitle,
  color,
  className,
}: {
  bins: number[];
  counts: number[];
  title: string;
  subtitle?: string;
  color?: string;
  className?: string;
}) {
  if (!counts.length) return <Figure title={title} subtitle={subtitle}>{<Empty />}</Figure>;

  const width = 520;
  const height = 210;
  const padding = { left: 44, bottom: 32, top: 12, right: 14 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const peak = Math.max(...counts, 1);
  const slot = plotWidth / counts.length;
  const fill = color ?? seriesVar(0);

  return (
    <Figure
      title={title}
      subtitle={subtitle}
      className={className}
      table={
        <MiniTable
          headers={["Bin centre", "Count"]}
          rows={bins.map((bin, index) => [bin, counts[index] ?? 0])}
        />
      }
    >
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" style={{ minWidth: 380 }} role="img" aria-label={title}>
        <text x={padding.left - 8} y={padding.top + 9} textAnchor="end" className={AXIS}>
          {peak}
        </text>
        <line
          x1={padding.left}
          y1={padding.top + plotHeight}
          x2={width - padding.right}
          y2={padding.top + plotHeight}
          stroke="var(--viz-axis)"
        />
        {counts.map((count, index) => {
          const barHeight = (count / peak) * plotHeight;
          return (
            <rect
              key={index}
              x={padding.left + index * slot + 1}
              y={padding.top + plotHeight - barHeight}
              width={Math.max(slot - 2, 1)}
              height={Math.max(barHeight, 1)}
              rx={4}
              fill={fill}
              className="transition-opacity hover:opacity-80"
            >
              <title>{`${bins[index]?.toFixed(3) ?? index}: ${count}`}</title>
            </rect>
          );
        })}
        {[0, Math.floor(counts.length / 2), counts.length - 1].map((index) =>
          bins[index] === undefined ? null : (
            <text
              key={index}
              x={padding.left + index * slot + slot / 2}
              y={height - 12}
              textAnchor="middle"
              className={AXIS}
            >
              {bins[index].toFixed(2)}
            </text>
          ),
        )}
      </svg>
    </Figure>
  );
}

/* ------------------------------------------------------------------ heatmap */
const SEQUENTIAL = [
  "#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5",
  "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b",
];

export function sequentialColor(value: number, min = 0, max = 1): string {
  if (max <= min) return SEQUENTIAL[6];
  const t = Math.max(0, Math.min(1, (value - min) / (max - min)));
  return SEQUENTIAL[Math.round(t * (SEQUENTIAL.length - 1))];
}

function mix(a: string, b: string, t: number): string {
  const parse = (hex: string) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
  const [ar, ag, ab] = parse(a);
  const [br, bg, bb] = parse(b);
  const to = (x: number) => Math.round(x).toString(16).padStart(2, "0");
  return `#${to(ar + (br - ar) * t)}${to(ag + (bg - ag) * t)}${to(ab + (bb - ab) * t)}`;
}

/** Blue (negative) ↔ neutral gray ↔ red (positive). Gray midpoint reads as "nothing". */
export function divergingColor(value: number, scale = 1, dark = false): string {
  const neutral = dark ? "#383835" : "#f0efec";
  const t = Math.max(-1, Math.min(1, value / (scale || 1)));
  if (Math.abs(t) < 0.08) return neutral;
  return mix(neutral, t > 0 ? "#d03b3b" : "#2a78d6", Math.abs(t));
}

export function Heatmap({
  columns,
  values,
  title,
  subtitle,
  className,
}: {
  columns: string[];
  values: number[][];
  title: string;
  subtitle?: string;
  className?: string;
}) {
  const size = Math.min(columns.length, 14);
  const cols = columns.slice(0, size);
  const grid = values.slice(0, size).map((row) => row.slice(0, size));

  if (cols.length < 2) return <Figure title={title} subtitle={subtitle}>{<Empty />}</Figure>;

  const cell = 30;
  const labelWidth = 120;
  const labelHeight = 88;
  const width = labelWidth + cols.length * cell + 10;
  const height = labelHeight + cols.length * cell + 10;

  return (
    <Figure
      title={title}
      subtitle={subtitle}
      className={className}
      table={
        <MiniTable
          headers={["", ...cols]}
          rows={grid.map((row, index) => [cols[index], ...row])}
        />
      }
    >
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" style={{ minWidth: 420 }} role="img" aria-label={title}>
        {cols.map((column, index) => (
          <text
            key={`x-${column}`}
            x={labelWidth + index * cell + cell / 2}
            y={labelHeight - 8}
            className={AXIS}
            transform={`rotate(-55 ${labelWidth + index * cell + cell / 2} ${labelHeight - 8})`}
          >
            {truncate(column, 14)}
          </text>
        ))}
        {cols.map((column, index) => (
          <text
            key={`y-${column}`}
            x={labelWidth - 8}
            y={labelHeight + index * cell + cell / 2 + 3}
            textAnchor="end"
            className={AXIS}
          >
            {truncate(column, 15)}
          </text>
        ))}
        {grid.map((row, r) =>
          row.map((value, c) => (
            <rect
              key={`${r}-${c}`}
              x={labelWidth + c * cell}
              y={labelHeight + r * cell}
              width={cell - 2}
              height={cell - 2}
              rx={3}
              fill={divergingColor(value)}
              className="transition-opacity hover:opacity-75"
            >
              <title>{`${cols[r]} × ${cols[c]}: ${value.toFixed(3)}`}</title>
            </rect>
          )),
        )}
      </svg>
      <div className="mt-3 flex items-center gap-2 text-[11px] text-muted">
        <span className="h-2 w-7 rounded" style={{ background: "#2a78d6" }} />
        −1
        <span className="h-2 w-7 rounded" style={{ background: "var(--viz-grid)" }} />0
        <span className="h-2 w-7 rounded" style={{ background: "#d03b3b" }} />
        +1
      </div>
    </Figure>
  );
}

/* ------------------------------------------------------------------ confusion */
export function ConfusionMatrix({
  matrix,
  labels,
  title = "Confusion matrix",
  subtitle,
  className,
}: {
  matrix: number[][];
  labels: string[];
  title?: string;
  subtitle?: string;
  className?: string;
}) {
  if (!matrix.length) return <Figure title={title} subtitle={subtitle}>{<Empty />}</Figure>;

  const n = matrix.length;
  const cell = 68;
  const pad = 96;
  const width = pad + n * cell + 10;
  const height = pad + n * cell + 10;
  const peak = Math.max(...matrix.flat(), 1);

  return (
    <Figure
      title={title}
      subtitle={subtitle}
      className={className}
      table={
        <MiniTable
          headers={["actual \\ predicted", ...labels]}
          rows={matrix.map((row, index) => [labels[index] ?? index, ...row])}
        />
      }
    >
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" style={{ minWidth: 340 }} role="img" aria-label={title}>
        <text x={pad + (n * cell) / 2} y={18} textAnchor="middle" className="fill-[color:var(--ink-secondary)] text-[10.5px]">
          Predicted
        </text>
        <text
          x={16}
          y={pad + (n * cell) / 2}
          textAnchor="middle"
          transform={`rotate(-90 16 ${pad + (n * cell) / 2})`}
          className="fill-[color:var(--ink-secondary)] text-[10.5px]"
        >
          Actual
        </text>
        {labels.map((label, index) => (
          <text key={`p-${label}`} x={pad + index * cell + cell / 2} y={pad - 10} textAnchor="middle" className={AXIS}>
            {truncate(label, 11)}
          </text>
        ))}
        {labels.map((label, index) => (
          <text key={`a-${label}`} x={pad - 10} y={pad + index * cell + cell / 2 + 4} textAnchor="end" className={AXIS}>
            {truncate(label, 12)}
          </text>
        ))}
        {matrix.map((row, r) =>
          row.map((value, c) => {
            const intensity = value / peak;
            return (
              <g key={`${r}-${c}`}>
                <rect
                  x={pad + c * cell}
                  y={pad + r * cell}
                  width={cell - 2}
                  height={cell - 2}
                  rx={4}
                  fill={sequentialColor(value, 0, peak)}
                />
                <text
                  x={pad + c * cell + cell / 2 - 1}
                  y={pad + r * cell + cell / 2 + 5}
                  textAnchor="middle"
                  className="text-[12.5px] font-semibold tnum"
                  fill={intensity > 0.55 ? "#ffffff" : "var(--ink)"}
                >
                  {formatNumber(value)}
                </text>
              </g>
            );
          }),
        )}
      </svg>
    </Figure>
  );
}

/* ------------------------------------------------------------------ tiles */
export function StatTile({
  label,
  value,
  caption,
  delta,
  tone,
  className,
}: {
  label: string;
  value: ReactNode;
  caption?: string;
  delta?: number;
  tone?: "good" | "warning" | "serious" | "critical";
  className?: string;
}) {
  return (
    <div
      className={cn(
        "surface-card p-4 shadow-card dark:shadow-card-dark",
        tone && "border-l-2",
        className,
      )}
      style={tone ? { borderLeftColor: `var(--status-${tone})` } : undefined}
    >
      <p className="text-[12px] text-secondary">{label}</p>
      <p className="mt-1.5 text-[26px] font-semibold leading-none">{value}</p>
      <p className="mt-2 flex items-center gap-2 text-[11.5px] text-muted">
        {caption}
        {delta !== undefined && (
          <span
            className="font-semibold"
            style={{
              color: delta >= 0 ? "var(--success-text)" : "var(--status-critical)",
            }}
          >
            {delta >= 0 ? "▲" : "▼"} {Math.abs(delta).toFixed(3)}
          </span>
        )}
      </p>
    </div>
  );
}

function Empty() {
  return <p className="py-8 text-center text-[13px] text-muted">Not enough data to plot.</p>;
}
