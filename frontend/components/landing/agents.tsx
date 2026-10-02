"use client";

import { motion } from "framer-motion";
import { useState } from "react";
import { cn, seriesVar } from "@/lib/utils";
import {
  IconBroom,
  IconChart,
  IconEye,
  IconFlask,
  IconLayers,
  IconPulse,
  IconRocket,
  IconSearch,
} from "@/components/icons";

export const AGENTS = [
  {
    id: "data_detective",
    name: "Data Detective",
    tagline: "Finds what will hurt you later",
    icon: IconSearch,
    duties: [
      "Missing values and their pattern",
      "Univariate and multivariate outliers",
      "Target leakage — four independent probes",
      "Class imbalance and target skew",
      "Collinearity and redundant columns",
    ],
    detail:
      "Leakage is caught by name semantics, near-perfect correlation, single-feature AUC, and category-to-target purity. Anything that separates the target alone is guilty until proven innocent.",
  },
  {
    id: "data_cleaner",
    name: "Data Cleaner",
    tagline: "Acts on every finding",
    icon: IconBroom,
    duties: [
      "Drops identifiers, constants and leakage suspects",
      "Repairs mis-typed numeric and datetime columns",
      "Imputes, and adds a missingness indicator above 5%",
      "Winsorises at the 1st/99th percentile",
      "Normalises text categories only when it merges variants",
    ],
    detail:
      "Every action is recorded with its reason, so the cleaning step is auditable rather than a black box that quietly changed your data.",
  },
  {
    id: "feature_engineer",
    name: "Feature Engineer",
    tagline: "Extracts signal that was already there",
    icon: IconLayers,
    duties: [
      "Datetime expansion with cyclical encoding",
      "Interaction and ratio features on high-variance columns",
      "Log transforms for skewed distributions",
      "Frequency encoding for high-cardinality categories",
      "One preprocessor fitted on train only",
    ],
    detail:
      "December sits next to January because months are encoded on a circle. The preprocessor is fitted after the split, so the holdout stays honest.",
  },
  {
    id: "ml_researcher",
    name: "ML Researcher",
    tagline: "Frames the problem before solving it",
    icon: IconFlask,
    duties: [
      "Classification vs regression from the target's shape",
      "Picks the primary metric — PR-AUC when imbalanced",
      "Chooses the validation scheme",
      "Shortlists candidates against row and feature counts",
      "Writes the modelling strategy in plain English",
    ],
    detail:
      "Accuracy is not the default objective. On a 1.7% positive rate it optimises PR-AUC, because a model that predicts 'no' every time is 98.3% accurate and worthless.",
  },
  {
    id: "experiment_manager",
    name: "Experiment Manager",
    tagline: "Trains the whole portfolio, not one guess",
    icon: IconChart,
    duties: [
      "Up to 20 models — linear, tree, boosting, kernel, neural",
      "XGBoost, LightGBM and CatBoost when installed",
      "Cross-validation alongside a held-out split",
      "Train/holdout gap reported per model",
      "Randomised search on the winner",
    ],
    detail:
      "Every model is scored on the same holdout with the same preprocessor, so the leaderboard compares models rather than accidents of preprocessing.",
  },
  {
    id: "explainability",
    name: "Explainability Agent",
    tagline: "Turns weights into reasons",
    icon: IconEye,
    duties: [
      "SHAP when available, permutation importance always",
      "LIME-style local surrogate per prediction",
      "Counterfactuals — the smallest flip",
      "Partial dependence for the top drivers",
      "A summary a CEO can read",
    ],
    detail:
      "A counterfactual answers the only question a stakeholder actually asks: what would have had to be different for this to come out the other way?",
  },
  {
    id: "deployment",
    name: "Deployment Agent",
    tagline: "Ships the exact bytes that scored",
    icon: IconRocket,
    duties: [
      "Freezes preprocessor + model into one bundle",
      "Generates a typed FastAPI service",
      "Multi-stage Dockerfile with a healthcheck",
      "Kubernetes, Render, Railway, App Runner, Azure",
      "curl, Python and TypeScript client snippets",
    ],
    detail:
      "No re-implementation between training and serving. The joblib bundle that produced the holdout metrics is the artifact the container loads.",
  },
  {
    id: "monitoring",
    name: "Monitoring Agent",
    tagline: "Knows when the model went stale",
    icon: IconPulse,
    duties: [
      "Captures the training reference distribution",
      "Population Stability Index per feature",
      "Metric decay against the release baseline",
      "Latency and null-rate alerts",
      "Retraining triggers with thresholds",
    ],
    detail:
      "PSI above 0.25 on a driver feature is a retraining trigger, not a discussion. The thresholds ship with the model instead of being invented during an incident.",
  },
];

export function Agents() {
  const [active, setActive] = useState(AGENTS[0].id);
  const agent = AGENTS.find((item) => item.id === active) ?? AGENTS[0];

  return (
    <section id="agents" className="relative py-24 sm:py-32">
      <div className="mx-auto max-w-7xl px-5 lg:px-8">
        <SectionHeading
          eyebrow="Multi-agent architecture"
          title="Not one prompt. Eight specialists."
          description="A single LLM asked to 'do data science' produces plausible-looking code. dataid splits the job into eight agents with narrow responsibilities, each one auditable on its own."
        />

        <div className="mt-14 grid gap-6 lg:grid-cols-[300px_1fr]">
          <div className="scrollbar-none flex gap-2 overflow-x-auto lg:flex-col lg:overflow-visible">
            {AGENTS.map((item, index) => {
              const Icon = item.icon;
              const selected = item.id === active;
              return (
                <button
                  key={item.id}
                  onClick={() => setActive(item.id)}
                  className={cn(
                    "group flex shrink-0 items-center gap-3 rounded-xl border px-3.5 py-3 text-left transition-all focus-ring lg:w-full",
                    selected
                      ? "border-brand-500/40 bg-brand-500/[0.07]"
                      : "hover:bg-black/[0.03] dark:hover:bg-white/[0.05]",
                  )}
                >
                  <span
                    className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg"
                    style={{ background: `color-mix(in srgb, ${seriesVar(index)} 16%, transparent)` }}
                  >
                    <Icon className="h-4.5 w-4.5" style={{ color: seriesVar(index), width: 18, height: 18 }} />
                  </span>
                  <span className="min-w-0">
                    <span className="block whitespace-nowrap text-[13.5px] font-medium">
                      {item.name}
                    </span>
                    <span className="hidden text-[11.5px] text-muted lg:block">{item.tagline}</span>
                  </span>
                </button>
              );
            })}
          </div>

          <motion.div
            key={agent.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35 }}
            className="surface-card p-7 shadow-card dark:shadow-card-dark"
          >
            <div className="flex items-start gap-4">
              <span
                className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl"
                style={{
                  background: `color-mix(in srgb, ${seriesVar(AGENTS.indexOf(agent))} 16%, transparent)`,
                }}
              >
                <agent.icon
                  style={{ color: seriesVar(AGENTS.indexOf(agent)), width: 22, height: 22 }}
                />
              </span>
              <div>
                <h3 className="text-[19px] font-semibold">{agent.name}</h3>
                <p className="mt-0.5 text-[13.5px] text-secondary">{agent.tagline}</p>
              </div>
            </div>

            <ul className="mt-7 grid gap-2.5 sm:grid-cols-2">
              {agent.duties.map((duty) => (
                <li key={duty} className="flex items-start gap-2.5 text-[13.5px] text-secondary">
                  <span
                    className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full"
                    style={{ background: seriesVar(AGENTS.indexOf(agent)) }}
                  />
                  {duty}
                </li>
              ))}
            </ul>

            <p className="mt-7 border-t pt-6 text-[14px] leading-relaxed text-secondary">
              {agent.detail}
            </p>
          </motion.div>
        </div>
      </div>
    </section>
  );
}

export function SectionHeading({
  eyebrow,
  title,
  description,
  align = "center",
}: {
  eyebrow: string;
  title: string;
  description?: string;
  align?: "center" | "left";
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.55 }}
      className={cn("max-w-2xl", align === "center" && "mx-auto text-center")}
    >
      <p className="text-[12px] font-medium uppercase tracking-[0.14em] text-brand-500 dark:text-brand-400">
        {eyebrow}
      </p>
      <h2 className="mt-3 text-[32px] font-semibold leading-[1.14] tracking-[-0.02em] sm:text-[40px]">
        {title}
      </h2>
      {description && (
        <p className="mt-4 text-[16px] leading-relaxed text-secondary">{description}</p>
      )}
    </motion.div>
  );
}
