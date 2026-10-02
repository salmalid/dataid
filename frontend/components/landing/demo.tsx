"use client";

import { motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { SectionHeading } from "./agents";
import { BarChart } from "@/components/ui/charts";
import { Badge } from "@/components/ui/primitives";
import { IconCheck, IconSparkle } from "@/components/icons";
import { cn, seriesVar } from "@/lib/utils";

const SCRIPT: {
  role: "user" | "assistant";
  text: string;
  steps?: string[];
  timeline?: { time: string; label: string }[];
}[] = [
  { role: "user", text: "Predict customer churn." },
  {
    role: "assistant",
    text: "Understood. I read the file before touching it — 6,120 rows, 13 columns. The target looks like `churn` (binary, 26.4% positive). Running the pipeline now.",
    steps: [
      "Missing values detected in 3 columns",
      "1,120 duplicate rows removed",
      "`customer_id` dropped — row identifier, no signal",
      "Categorical features encoded",
      "18 features engineered from dates and ratios",
      "14 models trained and ranked",
    ],
    timeline: [
      { time: "09:02", label: "Dataset uploaded" },
      { time: "09:03", label: "Profiling complete" },
      { time: "09:04", label: "Cleaning complete" },
      { time: "09:05", label: "Training started" },
      { time: "09:08", label: "Best model found" },
      { time: "09:09", label: "SHAP generated" },
      { time: "09:10", label: "API deployed" },
    ],
  },
  { role: "user", text: "The classes are very imbalanced." },
  {
    role: "assistant",
    text: "Then accuracy is the wrong objective. I switched the primary metric to PR-AUC, enabled balanced class weights on every estimator that supports them, and tuned the decision threshold on the holdout rather than resampling blindly — recall went from 0.41 to 0.68 at a precision cost of 0.09.",
  },
];

type Series = { label: string; value: number };

type Showcase = {
  available: boolean;
  run_id?: string;
  target?: string;
  best_model?: string;
  metric?: string;
  leaderboard?: Series[];
  drivers?: Series[];
};

/** Numbers below come from a real completed run, or the panels stay empty. */
function useShowcase() {
  const [state, setState] = useState<{ data: Showcase | null; loading: boolean }>({
    data: null,
    loading: true,
  });

  useEffect(() => {
    let cancelled = false;
    fetch("/api/showcase")
      .then((response) => (response.ok ? response.json() : { available: false }))
      .then((data: Showcase) => !cancelled && setState({ data, loading: false }))
      .catch(() => !cancelled && setState({ data: { available: false }, loading: false }));
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}

/** Importance is in target units and can be large; the leaderboard metric is a ratio. */
function formatCompact(value: number) {
  if (Math.abs(value) >= 1000) {
    return new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 })
      .format(value);
  }
  return value.toFixed(Math.abs(value) >= 1 ? 2 : 4);
}

function EmptyPanel({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="rounded-2xl border border-dashed p-6">
      <p className="text-[13px] font-semibold">{title}</p>
      <p className="mt-2 text-[12.5px] text-muted">{hint}</p>
    </div>
  );
}

export function LiveDemo() {
  const { data, loading } = useShowcase();
  const showcase = data?.available ? data : null;
  const leaderboard = showcase?.leaderboard ?? [];
  const drivers = showcase?.drivers ?? [];
  const emptyHint = loading
    ? "Loading the most recent completed run…"
    : "No completed run yet. Upload a dataset and these panels fill with its actual results.";

  return (
    <section id="demo" className="relative py-24 sm:py-32">
      <div className="pointer-events-none absolute inset-0 bg-mesh opacity-40" aria-hidden />
      <div className="relative mx-auto max-w-7xl px-5 lg:px-8">
        <SectionHeading
          eyebrow="How it reads"
          title="Talk to it like a colleague"
          description="No buttons to hunt for. Describe the outcome you want and the right agents pick it up — the interface is a conversation with a visible audit trail behind it. The exchange below is a scripted walkthrough of that interaction; the charts beside it are from a real completed run."
        />

        <div className="mt-14 grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <ChatPanel />
          <div className="space-y-6">
            {leaderboard.length > 0 ? (
              <BarChart
                data={leaderboard}
                title="Model leaderboard"
                subtitle={`Holdout ${showcase?.metric ?? "score"} · run ${showcase?.run_id ?? ""}`}
                formatValue={formatCompact}
              />
            ) : (
              <EmptyPanel title="Model leaderboard" hint={emptyHint} />
            )}
            {drivers.length > 0 ? (
              <BarChart
                data={drivers}
                title={`What drives ${showcase?.target ?? "the target"}`}
                subtitle="Global feature attribution across the holdout set"
                color={seriesVar(6)}
                formatValue={formatCompact}
              />
            ) : (
              <EmptyPanel title="Feature attribution" hint={emptyHint} />
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

function ChatPanel() {
  const [visible, setVisible] = useState(0);
  const [started, setStarted] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const observer = new IntersectionObserver(
      ([entry]) => entry.isIntersecting && setStarted(true),
      { threshold: 0.25 },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!started) return;
    if (visible >= SCRIPT.length) return;
    const timer = window.setTimeout(() => setVisible((value) => value + 1), visible === 0 ? 400 : 1900);
    return () => window.clearTimeout(timer);
  }, [started, visible]);

  return (
    <div ref={ref} className="surface-card overflow-hidden shadow-card dark:shadow-card-dark">
      <div className="flex items-center justify-between border-b px-5 py-3.5">
        <div className="flex items-center gap-2.5">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-gradient">
            <IconSparkle className="h-3.5 w-3.5 text-white" />
          </span>
          <div>
            <p className="text-[13px] font-semibold leading-tight">dataid Assistant</p>
            <p className="text-[11px] text-muted">customer_churn.csv</p>
          </div>
        </div>
        <Badge tone="good" icon={<span className="h-1.5 w-1.5 rounded-full bg-current" />}>
          Ready
        </Badge>
      </div>

      <div className="min-h-[520px] space-y-5 p-5">
        {SCRIPT.slice(0, visible).map((entry, index) => (
          <motion.div
            key={index}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35 }}
            className={cn("flex gap-3", entry.role === "user" && "justify-end")}
          >
            {entry.role === "assistant" && (
              <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-brand-gradient">
                <IconSparkle className="h-3.5 w-3.5 text-white" />
              </span>
            )}
            <div
              className={cn(
                "max-w-[85%] rounded-2xl px-4 py-3 text-[13.5px] leading-relaxed",
                entry.role === "user"
                  ? "bg-brand-gradient text-white"
                  : "bg-black/[0.04] text-secondary dark:bg-white/[0.06]",
              )}
            >
              <p>{entry.text}</p>

              {entry.steps && (
                <ul className="mt-3.5 space-y-1.5">
                  {entry.steps.map((step, stepIndex) => (
                    <motion.li
                      key={step}
                      initial={{ opacity: 0, x: -6 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: 0.35 + stepIndex * 0.28 }}
                      className="flex items-start gap-2 text-[12.5px]"
                    >
                      <IconCheck
                        className="mt-0.5 h-3.5 w-3.5 shrink-0"
                        style={{ color: "var(--status-good)" }}
                      />
                      {step}
                    </motion.li>
                  ))}
                </ul>
              )}

              {entry.timeline && (
                <ol className="mt-4 border-t pt-4">
                  {entry.timeline.map((item, itemIndex) => (
                    <motion.li
                      key={item.time}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: 0.8 + itemIndex * 0.22 }}
                      className="timeline-item relative flex items-center gap-3 pb-3 last:pb-0"
                    >
                      <span className="timeline-rail relative">
                        <span
                          className="block h-2.5 w-2.5 rounded-full ring-4"
                          style={{
                            background: "var(--status-good)",
                            // @ts-expect-error CSS custom property
                            "--tw-ring-color": "var(--surface)",
                          }}
                        />
                      </span>
                      <span className="tnum text-[11.5px] text-muted">{item.time}</span>
                      <span className="text-[12.5px]">{item.label}</span>
                    </motion.li>
                  ))}
                </ol>
              )}
            </div>
          </motion.div>
        ))}

        {started && visible < SCRIPT.length && (
          <div className="flex gap-3">
            <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-brand-gradient">
              <IconSparkle className="h-3.5 w-3.5 text-white" />
            </span>
            <div className="flex items-center gap-1.5 rounded-2xl bg-black/[0.04] px-4 py-3.5 dark:bg-white/[0.06]">
              {[0, 1, 2].map((dot) => (
                <span
                  key={dot}
                  className="h-1.5 w-1.5 animate-pulse rounded-full bg-[color:var(--ink-muted)]"
                  style={{ animationDelay: `${dot * 0.16}s` }}
                />
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="border-t px-5 py-3.5">
        <div className="flex items-center gap-3 rounded-xl border px-3.5 py-2.5 text-[13px] text-muted">
          <span className="flex-1">Ask anything — “find data leakage”, “deploy to Docker”…</span>
          <span className="kbd">⌘K</span>
        </div>
      </div>
    </div>
  );
}
