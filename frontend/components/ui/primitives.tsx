"use client";

import Link from "next/link";
import { forwardRef, type ButtonHTMLAttributes, type HTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ Button */
type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "subtle";
type ButtonSize = "sm" | "md" | "lg";

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary:
    "bg-brand-gradient text-white shadow-glow hover:brightness-110 active:brightness-95 border-transparent",
  secondary:
    "bg-surface border hairline hover:bg-brand-50 dark:hover:bg-white/[0.06] text-[color:var(--ink)]",
  ghost: "border-transparent hover:bg-black/[0.04] dark:hover:bg-white/[0.06] text-secondary",
  danger: "border-transparent bg-[color:var(--status-critical)] text-white hover:brightness-110",
  subtle:
    "border-transparent bg-black/[0.045] dark:bg-white/[0.07] text-[color:var(--ink)] hover:bg-black/[0.08] dark:hover:bg-white/[0.11]",
};

const BUTTON_SIZES: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-[13px] gap-1.5 rounded-lg",
  md: "h-10 px-4 text-sm gap-2 rounded-xl",
  lg: "h-12 px-6 text-[15px] gap-2.5 rounded-xl",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant = "primary", size = "md", loading, children, disabled, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cn(
        "inline-flex items-center justify-center border font-medium transition-all focus-ring",
        "disabled:cursor-not-allowed disabled:opacity-55",
        BUTTON_VARIANTS[variant],
        BUTTON_SIZES[size],
        className,
      )}
      {...props}
    >
      {loading && <Spinner className="h-3.5 w-3.5" />}
      {children}
    </button>
  );
});

export function LinkButton({
  href,
  className,
  variant = "primary",
  size = "md",
  children,
}: {
  href: string;
  className?: string;
  variant?: ButtonVariant;
  size?: ButtonSize;
  children: ReactNode;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "inline-flex items-center justify-center border font-medium transition-all focus-ring",
        BUTTON_VARIANTS[variant],
        BUTTON_SIZES[size],
        className,
      )}
    >
      {children}
    </Link>
  );
}

/* ------------------------------------------------------------------ Card */
export function Card({
  className,
  children,
  ...props
}: HTMLAttributes<HTMLDivElement> & { children: ReactNode }) {
  return (
    <div className={cn("surface-card shadow-card dark:shadow-card-dark", className)} {...props}>
      {children}
    </div>
  );
}

export function CardHeader({
  title,
  subtitle,
  action,
  className,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex items-start justify-between gap-4 px-5 pt-5", className)}>
      <div className="min-w-0">
        <h3 className="text-[15px] font-semibold leading-tight">{title}</h3>
        {subtitle && <p className="mt-1 text-[13px] text-secondary">{subtitle}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

/* ------------------------------------------------------------------ Badge */
type Tone = "neutral" | "brand" | "good" | "warning" | "serious" | "critical";

const TONES: Record<Tone, string> = {
  neutral: "bg-black/[0.05] dark:bg-white/[0.08] text-secondary",
  brand: "bg-brand-500/12 text-brand-600 dark:text-brand-300",
  good: "bg-[color:var(--status-good)]/14 text-[color:var(--success-text)]",
  warning: "bg-[color:var(--status-warning)]/22 text-[color:var(--ink)]",
  serious: "bg-[color:var(--status-serious)]/20 text-[color:var(--ink)]",
  critical: "bg-[color:var(--status-critical)]/16 text-[color:var(--status-critical)]",
};

/** Status tones always ship with a label — colour never carries the meaning alone. */
export function Badge({
  tone = "neutral",
  icon,
  children,
  className,
}: {
  tone?: Tone;
  icon?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5",
        "text-[11px] font-medium leading-5",
        TONES[tone],
        className,
      )}
    >
      {icon}
      {children}
    </span>
  );
}

/* ------------------------------------------------------------------ Spinner */
export function Spinner({ className }: { className?: string }) {
  return (
    <svg className={cn("animate-spin", className)} viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="3" opacity="0.25" />
      <path
        d="M21 12a9 9 0 0 0-9-9"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
      />
    </svg>
  );
}

/* ------------------------------------------------------------------ Skeleton */
export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton rounded-lg", className)} aria-hidden />;
}

export function SkeletonCard() {
  return (
    <Card className="p-5">
      <Skeleton className="h-4 w-1/3" />
      <Skeleton className="mt-3 h-3 w-2/3" />
      <Skeleton className="mt-6 h-28 w-full" />
    </Card>
  );
}

/* ------------------------------------------------------------------ Empty */
export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed px-6 py-16 text-center">
      {icon && <div className="mb-4 text-muted">{icon}</div>}
      <p className="text-[15px] font-semibold">{title}</p>
      {description && <p className="mt-1.5 max-w-md text-[13px] text-secondary">{description}</p>}
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}

/* ------------------------------------------------------------------ Field */
export function Field({
  label,
  hint,
  children,
  htmlFor,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
  htmlFor?: string;
}) {
  return (
    <label className="block" htmlFor={htmlFor}>
      <span className="mb-1.5 block text-[13px] font-medium">{label}</span>
      {children}
      {hint && <span className="mt-1.5 block text-[12px] text-muted">{hint}</span>}
    </label>
  );
}

const CONTROL =
  "w-full rounded-xl border bg-surface px-3.5 py-2.5 text-sm transition-colors focus-ring " +
  "placeholder:text-[color:var(--ink-muted)] disabled:opacity-55";

export const Input = forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...props }, ref) {
    return <input ref={ref} className={cn(CONTROL, className)} {...props} />;
  },
);

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(function Textarea({ className, ...props }, ref) {
  return <textarea ref={ref} className={cn(CONTROL, "resize-none", className)} {...props} />;
});

export const Select = forwardRef<
  HTMLSelectElement,
  React.SelectHTMLAttributes<HTMLSelectElement>
>(function Select({ className, children, ...props }, ref) {
  return (
    <select ref={ref} className={cn(CONTROL, "cursor-pointer pr-9", className)} {...props}>
      {children}
    </select>
  );
});

/* ------------------------------------------------------------------ Toggle */
export function Toggle({
  checked,
  onChange,
  label,
  description,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
  description?: string;
}) {
  return (
    <div className="flex items-start justify-between gap-6">
      <div className="min-w-0">
        <p className="text-[13px] font-medium">{label}</p>
        {description && <p className="mt-0.5 text-[12px] text-secondary">{description}</p>}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative h-6 w-11 shrink-0 rounded-full border transition-colors focus-ring",
          checked ? "bg-brand-gradient border-transparent" : "bg-black/[0.08] dark:bg-white/[0.12]",
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 h-4.5 w-4.5 rounded-full bg-white shadow transition-transform",
            "h-[18px] w-[18px]",
            checked ? "translate-x-[22px]" : "translate-x-[3px]",
          )}
        />
      </button>
    </div>
  );
}

/* ------------------------------------------------------------------ Tabs */
export function Tabs({
  tabs,
  active,
  onChange,
  className,
}: {
  tabs: { id: string; label: string; count?: number }[];
  active: string;
  onChange: (id: string) => void;
  className?: string;
}) {
  return (
    <div
      role="tablist"
      className={cn("scrollbar-none flex gap-1 overflow-x-auto border-b", className)}
    >
      {tabs.map((tab) => {
        const selected = tab.id === active;
        return (
          <button
            key={tab.id}
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(tab.id)}
            className={cn(
              "relative whitespace-nowrap rounded-t-lg px-3.5 py-2.5 text-[13.5px] transition-colors focus-ring",
              selected
                ? "font-semibold text-[color:var(--ink)]"
                : "text-secondary hover:bg-black/[0.03] dark:hover:bg-white/[0.05]",
            )}
          >
            {tab.label}
            {tab.count !== undefined && (
              <span className="ml-1.5 tnum text-[11px] text-muted">{tab.count}</span>
            )}
            {selected && (
              <span className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-brand-gradient" />
            )}
          </button>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------ Table */
export function DataTable<T extends Record<string, unknown>>({
  columns,
  rows,
  highlightFirst,
  emptyMessage = "Nothing to show.",
}: {
  columns: { key: string; header: string; align?: "left" | "right"; render?: (row: T) => ReactNode }[];
  rows: T[];
  highlightFirst?: boolean;
  emptyMessage?: string;
}) {
  if (!rows.length) {
    return <p className="px-5 py-8 text-center text-[13px] text-muted">{emptyMessage}</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[12.5px] tnum">
        <thead>
          <tr className="border-b">
            {columns.map((column) => (
              <th
                key={column.key}
                className={cn(
                  "whitespace-nowrap px-4 py-2.5 font-semibold",
                  column.align === "right" ? "text-right" : "text-left",
                )}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr
              key={index}
              className={cn(
                "border-b last:border-0 transition-colors hover:bg-black/[0.02] dark:hover:bg-white/[0.03]",
                highlightFirst && index === 0 && "bg-brand-500/[0.06]",
              )}
            >
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={cn(
                    "whitespace-nowrap px-4 py-2.5",
                    column.align === "right" ? "text-right" : "text-left",
                  )}
                >
                  {column.render ? column.render(row) : String(row[column.key] ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
