"use client";

import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { LinkButton } from "@/components/ui/primitives";
import { IconArrowRight, IconBolt, IconCheck, IconSparkle } from "@/components/icons";

const PIPELINE_STEPS = [
  "Reading 42,158 rows × 31 columns",
  "Profiling column types and distributions",
  "Flagging 3 columns with target leakage",
  "Imputing 1,204 missing values",
  "Deriving 18 engineered features",
  "Training 14 candidate models",
  "CatBoost wins — ROC AUC 0.9412",
  "SHAP attribution complete",
  "Container image built · API live",
];

export function Hero() {
  return (
    <section className="relative overflow-hidden pt-32 pb-24 sm:pt-40 sm:pb-32">
      <Backdrop />

      <div className="relative mx-auto max-w-7xl px-5 lg:px-8">
        <div className="grid items-center gap-16 lg:grid-cols-[1.05fr_0.95fr]">
          <div>
            <motion.a
              href="#agents"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="glass inline-flex items-center gap-2 rounded-full py-1.5 pl-1.5 pr-4 text-[12.5px]"
            >
              <span className="rounded-full bg-brand-gradient px-2.5 py-0.5 text-[11px] font-semibold text-white">
                New
              </span>
              <span className="text-secondary">Eight specialised agents, one pipeline</span>
              <IconArrowRight className="h-3.5 w-3.5 text-muted" />
            </motion.a>

            <motion.h1
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.06 }}
              className="mt-7 text-[42px] font-semibold leading-[1.06] tracking-[-0.03em] sm:text-[58px] lg:text-[64px]"
            >
              The AI Operating System
              <br />
              for <span className="gradient-text">Modern Data Scientists</span>
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.14 }}
              className="mt-6 max-w-xl text-[17px] leading-relaxed text-secondary"
            >
              Upload your dataset. Describe your goal. Watch a team of agents profile it, clean it,
              engineer features, train and rank a portfolio of models, explain the winner, and ship
              it as a container — while you read the timeline.
            </motion.p>

            <motion.div
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.22 }}
              className="mt-9 flex flex-wrap items-center gap-3"
            >
              <LinkButton href="/dashboard" size="lg">
                Get started
                <IconArrowRight className="h-4 w-4" />
              </LinkButton>
              <LinkButton href="#demo" size="lg" variant="secondary">
                Watch it run
              </LinkButton>
            </motion.div>

            <motion.ul
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.6, delay: 0.3 }}
              className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-[13px] text-muted"
            >
              {["No API key required", "Runs fully offline", "Open source"].map((item) => (
                <li key={item} className="flex items-center gap-1.5">
                  <IconCheck className="h-3.5 w-3.5" style={{ color: "var(--status-good)" }} />
                  {item}
                </li>
              ))}
            </motion.ul>
          </div>

          <motion.div
            initial={{ opacity: 0, y: 28, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.75, delay: 0.18, ease: [0.22, 1, 0.36, 1] }}
          >
            <TerminalPreview />
          </motion.div>
        </div>

        <LogoStrip />
      </div>
    </section>
  );
}

function Backdrop() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
      <div className="absolute inset-0 bg-mesh opacity-70" />
      <div className="absolute inset-0 bg-grid-light bg-[size:56px_56px] opacity-[0.55] dark:bg-grid-dark" />
      <div className="absolute -left-40 top-10 h-[420px] w-[420px] animate-drift rounded-full bg-brand-500/25 blur-[120px]" />
      <div
        className="absolute -right-32 top-40 h-[380px] w-[380px] animate-drift rounded-full bg-violet-500/20 blur-[120px]"
        style={{ animationDelay: "-6s" }}
      />
      <div className="absolute inset-x-0 bottom-0 h-40 bg-gradient-to-b from-transparent to-[color:var(--page)]" />
    </div>
  );
}

function TerminalPreview() {
  const [visible, setVisible] = useState(0);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setVisible((current) => (current >= PIPELINE_STEPS.length ? 0 : current + 1));
    }, 850);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <div className="glass overflow-hidden rounded-2xl shadow-glow">
      <div className="flex items-center gap-2 border-b px-4 py-3">
        <span className="h-2.5 w-2.5 rounded-full bg-[#ff5f57]" />
        <span className="h-2.5 w-2.5 rounded-full bg-[#febc2e]" />
        <span className="h-2.5 w-2.5 rounded-full bg-[#28c840]" />
        <span className="ml-2 font-mono text-[11.5px] text-muted">dataid · pipeline</span>
        <span className="ml-auto flex items-center gap-1.5 text-[11px] text-muted">
          <span className="relative flex h-1.5 w-1.5">
            <span className="absolute inline-flex h-full w-full animate-pulse-ring rounded-full bg-brand-400" />
            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-brand-500" />
          </span>
          walkthrough
        </span>
      </div>

      <div className="space-y-2.5 px-5 py-5 font-mono text-[12.5px] leading-relaxed">
        <p className="flex items-center gap-2 text-secondary">
          <span className="text-brand-400">$</span>
          <span>dataid run --target churn</span>
        </p>

        {PIPELINE_STEPS.map((step, index) => {
          const done = index < visible;
          const active = index === visible;
          if (index > visible) return null;
          return (
            <p
              key={step}
              className="flex animate-fade-up items-start gap-2.5"
              style={{ color: done ? "var(--ink-secondary)" : "var(--ink)" }}
            >
              {done ? (
                <IconCheck
                  className="mt-0.5 h-3.5 w-3.5 shrink-0"
                  style={{ color: "var(--status-good)" }}
                />
              ) : (
                <IconBolt className="mt-0.5 h-3.5 w-3.5 shrink-0 animate-pulse text-brand-400" />
              )}
              <span className={active ? "font-medium" : ""}>{step}</span>
            </p>
          );
        })}
      </div>

      <div className="flex items-center justify-between border-t px-5 py-3 text-[11.5px]">
        <span className="flex items-center gap-1.5 text-muted">
          <IconSparkle className="h-3.5 w-3.5 text-brand-400" />
          8 agents · 14 models · 11 artifacts
        </span>
        <span className="tnum text-muted">02:47</span>
      </div>
    </div>
  );
}

function LogoStrip() {
  const stack = [
    "scikit-learn", "XGBoost", "LightGBM", "CatBoost", "SHAP",
    "FastAPI", "Docker", "Kubernetes", "pandas", "Next.js",
  ];
  return (
    <div className="relative mt-24 overflow-hidden">
      <p className="mb-6 text-center text-[12px] uppercase tracking-[0.14em] text-muted">
        Built on the stack you already trust
      </p>
      <div className="relative flex overflow-hidden [mask-image:linear-gradient(90deg,transparent,#000_12%,#000_88%,transparent)]">
        <div className="flex animate-marquee gap-12 pr-12">
          {[...stack, ...stack].map((name, index) => (
            <span
              key={`${name}-${index}`}
              className="whitespace-nowrap text-[15px] font-medium text-muted"
            >
              {name}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
