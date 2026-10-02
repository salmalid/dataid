"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { useState } from "react";
import { SectionHeading } from "./agents";
import { Logo } from "./nav";
import { Badge, Button, Card, Input, LinkButton } from "@/components/ui/primitives";
import {
  IconAlert,
  IconArrowRight,
  IconBolt,
  IconBook,
  IconChart,
  IconCheck,
  IconDatabase,
  IconDocker,
  IconEye,
  IconFile,
  IconGithub,
  IconKey,
  IconPulse,
  IconRocket,
  IconShield,
  IconSparkle,
  IconTerminal,
  IconUpload,
} from "@/components/icons";
import { cn, seriesVar } from "@/lib/utils";

/* ================================================================== how it works */
const STEPS = [
  {
    title: "Upload a dataset",
    body: "CSV, TSV, Excel, Parquet or JSON. dataid reads it before you configure anything and tells you what it thinks the problem is.",
    icon: IconUpload,
  },
  {
    title: "Confirm the goal",
    body: "It proposes a target column with a confidence score and its reasoning, flags likely leakage, and estimates how long the run will take.",
    icon: IconSparkle,
  },
  {
    title: "Watch the agents work",
    body: "Eight agents run in sequence, each streaming progress into a timeline that reads like a CI pipeline — not a spinner.",
    icon: IconBolt,
  },
  {
    title: "Ship the result",
    body: "A notebook, a report, a deck, a dashboard, a FastAPI service and a container image — generated, not templated.",
    icon: IconRocket,
  },
];

export function HowItWorks() {
  return (
    <section id="how" className="relative border-t py-24 sm:py-32">
      <div className="mx-auto max-w-7xl px-5 lg:px-8">
        <SectionHeading
          eyebrow="How it works"
          title="Four steps. No configuration files."
          description="The gap between a CSV on your desktop and a monitored model behind an endpoint is usually weeks of glue work. This closes it."
        />

        <div className="mt-16 grid gap-x-8 gap-y-12 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((step, index) => {
            const Icon = step.icon;
            return (
              <motion.div
                key={step.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-60px" }}
                transition={{ duration: 0.5, delay: index * 0.08 }}
                className="relative"
              >
                {index < STEPS.length - 1 && (
                  <div
                    className="absolute left-[52px] top-6 hidden h-px w-[calc(100%-30px)] lg:block"
                    style={{
                      background:
                        "linear-gradient(90deg, var(--hairline), transparent)",
                    }}
                    aria-hidden
                  />
                )}
                <div className="flex items-center gap-3">
                  <span className="flex h-11 w-11 items-center justify-center rounded-xl border bg-surface">
                    <Icon className="h-5 w-5 text-brand-500 dark:text-brand-400" />
                  </span>
                  <span className="tnum text-[12px] font-medium text-muted">
                    0{index + 1}
                  </span>
                </div>
                <h3 className="mt-5 text-[16px] font-semibold">{step.title}</h3>
                <p className="mt-2 text-[13.5px] leading-relaxed text-secondary">{step.body}</p>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

/* ================================================================== features */
const FEATURES = [
  {
    icon: IconDatabase,
    title: "Dataset understanding",
    body: "Before a single model runs it reports the shape, the likely target with its reasoning, leakage candidates, sensitive attributes and a time estimate.",
    span: "lg:col-span-2",
    demo: "understanding" as const,
  },
  {
    icon: IconChart,
    title: "20-model portfolio",
    body: "Linear, tree, ensemble, boosting, kernel and neural candidates — all scored on the same holdout with the same preprocessor.",
  },
  {
    icon: IconEye,
    title: "Explainability that lands",
    body: "SHAP, permutation importance, LIME-style local surrogates, counterfactuals, partial dependence — plus a summary written for a non-technical reader.",
  },
  {
    icon: IconShield,
    title: "Fairness auditing",
    body: "Slice performance by any sensitive attribute. Selection-rate and TPR parity are reported next to the headline metric, and a 10-point gap blocks release.",
  },
  {
    icon: IconFile,
    title: "Artifacts, generated",
    body: "A runnable notebook, an HTML and Markdown report, a PowerPoint deck, a self-contained dashboard, service code and a Dockerfile.",
    span: "lg:col-span-2",
    demo: "artifacts" as const,
  },
  {
    icon: IconPulse,
    title: "Drift and decay monitoring",
    body: "The training distribution is captured as a reference. PSI per feature, metric decay against the release baseline, and thresholds that ship with the model.",
  },
  {
    icon: IconDocker,
    title: "One-click packaging",
    body: "Multi-stage Dockerfile, compose file, Kubernetes manifests with an HPA, and configs for Render, Railway, App Runner and Azure Container Apps.",
  },
  {
    icon: IconKey,
    title: "Enterprise scaffolding",
    body: "Workspaces, project versioning, a model registry with promotion stages, scoped API keys and an append-only audit log.",
  },
];

export function Features() {
  return (
    <section id="features" className="relative border-t py-24 sm:py-32">
      <div className="mx-auto max-w-7xl px-5 lg:px-8">
        <SectionHeading
          eyebrow="Capabilities"
          title="Everything between the CSV and the endpoint"
          description="Each capability is a real code path in the repository, not a roadmap item on a marketing page."
        />

        <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((feature, index) => {
            const Icon = feature.icon;
            return (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 18 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-50px" }}
                transition={{ duration: 0.45, delay: (index % 3) * 0.06 }}
                className={cn("group", feature.span)}
              >
                <Card className="h-full p-6 transition-colors hover:border-brand-500/35">
                  <span
                    className="flex h-10 w-10 items-center justify-center rounded-xl"
                    style={{
                      background: `color-mix(in srgb, ${seriesVar(index)} 15%, transparent)`,
                    }}
                  >
                    <Icon style={{ color: seriesVar(index), width: 19, height: 19 }} />
                  </span>
                  <h3 className="mt-4 text-[15.5px] font-semibold">{feature.title}</h3>
                  <p className="mt-2 text-[13.5px] leading-relaxed text-secondary">{feature.body}</p>
                  {feature.demo === "understanding" && <UnderstandingPreview />}
                  {feature.demo === "artifacts" && <ArtifactPreview />}
                </Card>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function UnderstandingPreview() {
  return (
    <div className="mt-5 rounded-xl border bg-black/[0.02] p-4 font-mono text-[12px] leading-relaxed dark:bg-white/[0.03]">
      <p className="text-muted">employees.csv</p>
      <p className="mt-2 text-secondary">
        <span className="text-brand-400">→</span> 42,158 rows · 31 columns
      </p>
      <p className="text-secondary">
        <span className="text-brand-400">→</span> Problem: Employee Attrition Prediction
      </p>
      <p className="text-secondary">
        <span className="text-brand-400">→</span> Target: <span className="text-[color:var(--ink)]">attrition</span>{" "}
        <span className="text-muted">(confidence 0.86)</span>
      </p>
      <p style={{ color: "var(--status-critical)" }}>
        <span>⚠</span> Leakage: exit_date, settlement_amount
      </p>
      <p className="text-secondary">
        <span className="text-brand-400">→</span> Recommended: CatBoost, LightGBM, XGBoost
      </p>
      <p className="text-muted">Estimated completion: 3 min</p>
    </div>
  );
}

// What a run writes, by type. Sizes and filenames depend on the dataset, so they are not
// quoted here — the real ones appear on the run's artifacts panel once it completes.
const ARTIFACTS = [
  { name: "Notebook", format: ".ipynb", tone: 0 },
  { name: "Report", format: ".html + .md", tone: 1 },
  { name: "Slide deck", format: ".pptx", tone: 2 },
  { name: "Dashboard", format: ".html", tone: 3 },
  { name: "Inference service", format: "app.py", tone: 4 },
  { name: "Container image", format: "Dockerfile", tone: 6 },
];

function ArtifactPreview() {
  return (
    <ul className="mt-5 grid gap-2 sm:grid-cols-2">
      {ARTIFACTS.map((artifact) => (
        <li
          key={artifact.name}
          className="flex items-center gap-2.5 rounded-lg border px-3 py-2 text-[12px]"
        >
          <IconFile style={{ color: seriesVar(artifact.tone), width: 14, height: 14 }} />
          <span className="min-w-0 flex-1 truncate">{artifact.name}</span>
          <span className="shrink-0 font-mono text-muted">{artifact.format}</span>
        </li>
      ))}
    </ul>
  );
}

/* ================================================================== examples */
const EXAMPLES = [
  {
    name: "Customer Churn",
    task: "Classification",
    rows: "6,120",
    metric: "ROC AUC 0.941",
    model: "CatBoost",
    highlight: "Threshold tuning lifted recall from 0.41 to 0.68.",
    tone: 0,
  },
  {
    name: "Fraud Detection",
    task: "Classification",
    rows: "9,180",
    metric: "PR AUC 0.612",
    model: "LightGBM",
    highlight: "Caught a leakage column that inflated AUC to 0.99.",
    tone: 1,
  },
  {
    name: "House Prices",
    task: "Regression",
    rows: "5,100",
    metric: "R² 0.918",
    model: "XGBoost",
    highlight: "Neighbourhood premium was the third strongest driver.",
    tone: 2,
  },
  {
    name: "Heart Disease",
    task: "Classification",
    rows: "3,264",
    metric: "F1 0.812",
    model: "HistGradientBoosting",
    highlight: "Fairness slice on sex showed a 3-point gap — passing.",
    tone: 6,
  },
  {
    name: "Titanic",
    task: "Classification",
    rows: "1,414",
    metric: "Accuracy 0.834",
    model: "Random Forest",
    highlight: "Small-sample run: CV weighted above the single holdout.",
    tone: 4,
  },
];

export function ExampleProjects() {
  return (
    <section id="examples" className="relative border-t py-24 sm:py-32">
      <div className="mx-auto max-w-7xl px-5 lg:px-8">
        <SectionHeading
          eyebrow="Example projects"
          title="Five datasets ship with it"
          description="Each one is deliberately imperfect — missing values, duplicates, identifier columns, outliers, and in two cases a planted leakage column, so the Detective has something real to find."
        />

        <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {EXAMPLES.map((example, index) => (
            <motion.div
              key={example.name}
              initial={{ opacity: 0, y: 18 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.45, delay: (index % 3) * 0.07 }}
            >
              <Card className="group h-full p-5 transition-all hover:-translate-y-0.5 hover:border-brand-500/35">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="text-[15px] font-semibold">{example.name}</h3>
                    <p className="mt-0.5 text-[12px] text-muted">
                      {example.task} · {example.rows} rows
                    </p>
                  </div>
                  <span
                    className="h-2 w-2 shrink-0 rounded-full"
                    style={{ background: seriesVar(example.tone) }}
                    aria-hidden
                  />
                </div>

                <p className="mt-5 tnum text-[22px] font-semibold">{example.metric}</p>
                <p className="mt-1 text-[12.5px] text-secondary">won by {example.model}</p>

                <p className="mt-5 border-t pt-4 text-[12.5px] leading-relaxed text-secondary">
                  {example.highlight}
                </p>
              </Card>
            </motion.div>
          ))}

          <motion.div
            initial={{ opacity: 0, y: 18 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.45, delay: 0.2 }}
          >
            <Link
              href="/dashboard"
              className="flex h-full flex-col items-center justify-center rounded-2xl border border-dashed px-6 py-10 text-center transition-colors hover:border-brand-500/50 hover:bg-brand-500/[0.04]"
            >
              <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-gradient">
                <IconArrowRight className="h-5 w-5 text-white" />
              </span>
              <p className="mt-4 text-[14.5px] font-semibold">Bring your own</p>
              <p className="mt-1.5 text-[12.5px] text-secondary">
                Drop a CSV and get the same treatment
              </p>
            </Link>
          </motion.div>
        </div>
      </div>
    </section>
  );
}

/* ================================================================== pricing */
const PLANS = [
  {
    name: "Free",
    price: "$0",
    cadence: "forever",
    description: "Everything needed to run the full pipeline locally.",
    features: [
      "Unlimited local projects",
      "All 8 agents",
      "20-model portfolio",
      "Notebook, report and deck export",
      "Docker packaging",
      "Community support",
    ],
    cta: "Start free",
  },
  {
    name: "Team",
    price: "$49",
    cadence: "per seat / month",
    description: "Shared workspaces and the governance layer.",
    features: [
      "Everything in Free",
      "Shared workspaces and roles",
      "Model registry with promotion",
      "Scoped API keys",
      "Audit log export",
      "Drift alerting via webhook",
      "Priority support",
    ],
    cta: "Start trial",
    featured: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    cadence: "annual",
    description: "For teams with a compliance department.",
    features: [
      "Everything in Team",
      "Self-hosted or VPC deployment",
      "SSO / SAML and SCIM",
      "Custom agent definitions",
      "Fairness policy enforcement",
      "SLA and dedicated support",
    ],
    cta: "Talk to us",
  },
];

export function Pricing() {
  return (
    <section id="pricing" className="relative border-t py-24 sm:py-32">
      <div className="mx-auto max-w-7xl px-5 lg:px-8">
        <SectionHeading
          eyebrow="Pricing"
          title="Free where it matters"
          description="The engine is open source and runs entirely on your machine with no API key. Paid tiers add the collaboration and governance layer."
        />

        <div className="mt-14 grid gap-5 lg:grid-cols-3">
          {PLANS.map((plan, index) => (
            <motion.div
              key={plan.name}
              initial={{ opacity: 0, y: 18 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.45, delay: index * 0.07 }}
            >
              <Card
                className={cn(
                  "relative flex h-full flex-col p-7",
                  plan.featured && "border-brand-500/45 shadow-glow",
                )}
              >
                {plan.featured && (
                  <span className="absolute -top-3 left-7 rounded-full bg-brand-gradient px-3 py-1 text-[11px] font-semibold text-white">
                    Most popular
                  </span>
                )}
                <h3 className="text-[15px] font-semibold">{plan.name}</h3>
                <p className="mt-4 flex items-baseline gap-2">
                  <span className="text-[38px] font-semibold leading-none tracking-tight">
                    {plan.price}
                  </span>
                  <span className="text-[12.5px] text-muted">{plan.cadence}</span>
                </p>
                <p className="mt-3 text-[13px] text-secondary">{plan.description}</p>

                <ul className="mt-7 flex-1 space-y-2.5">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-start gap-2.5 text-[13px] text-secondary">
                      <IconCheck
                        className="mt-0.5 h-3.5 w-3.5 shrink-0"
                        style={{ color: "var(--status-good)" }}
                      />
                      {feature}
                    </li>
                  ))}
                </ul>

                <LinkButton
                  href="/dashboard"
                  variant={plan.featured ? "primary" : "secondary"}
                  className="mt-8 w-full"
                >
                  {plan.cta}
                </LinkButton>
              </Card>
            </motion.div>
          ))}
        </div>

        <p className="mt-8 text-center text-[12.5px] text-muted">
          Pricing shown for portfolio demonstration — dataid is an open-source project, nothing is
          billed.
        </p>
      </div>
    </section>
  );
}

/* ================================================================== architecture */
const LAYERS = [
  {
    label: "Interface",
    items: ["Next.js 14 App Router", "Tailwind design system", "Server-sent event timeline", "Command palette"],
    tone: 0,
  },
  {
    label: "Control plane",
    items: ["FastAPI", "SQLite / WAL persistence", "Bounded run executor", "Model registry & audit log"],
    tone: 6,
  },
  {
    label: "Agent layer",
    items: ["8 agents on one shared context", "In-process event bus", "Natural-language intent router", "Graceful degradation"],
    tone: 2,
  },
  {
    label: "Compute",
    items: ["scikit-learn pipelines", "XGBoost / LightGBM / CatBoost", "SHAP & permutation importance", "joblib artifact bundles"],
    tone: 1,
  },
];

export function Architecture() {
  return (
    <section id="architecture" className="relative border-t py-24 sm:py-32">
      <div className="mx-auto max-w-7xl px-5 lg:px-8">
        <SectionHeading
          eyebrow="Architecture"
          title="Four layers, one shared context"
          description="Agents don't message each other through a model. They mutate a single typed context object and emit events — which is why the timeline is real and the run is reproducible."
        />

        <div className="mt-14 space-y-3">
          {LAYERS.map((layer, index) => (
            <motion.div
              key={layer.label}
              initial={{ opacity: 0, x: -16 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.45, delay: index * 0.08 }}
            >
              <Card className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center">
                <div className="flex items-center gap-3 sm:w-52 sm:shrink-0">
                  <span
                    className="h-8 w-1 rounded-full"
                    style={{ background: seriesVar(layer.tone) }}
                    aria-hidden
                  />
                  <span className="text-[14.5px] font-semibold">{layer.label}</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {layer.items.map((item) => (
                    <span
                      key={item}
                      className="rounded-lg border px-2.5 py-1 text-[12px] text-secondary"
                    >
                      {item}
                    </span>
                  ))}
                </div>
              </Card>
            </motion.div>
          ))}
        </div>

        <Card className="mt-8 overflow-x-auto p-6">
          <pre className="font-mono text-[12px] leading-relaxed text-secondary">{`ProjectContext  ──┬──▶ DataDetective     profile, issues, eda
                  ├──▶ DataCleaner       df, cleaning_summary
                  ├──▶ FeatureEngineer   X_train/X_test, preprocessor
                  ├──▶ MLResearcher      research (metric, shortlist)
                  ├──▶ ExperimentManager leaderboard, best_model, metrics
                  ├──▶ Explainability    global + local attribution
                  ├──▶ Deployment        bundle, service, container
                  └──▶ Monitoring        reference, drift, alerts
                            │
                            └──▶ EventBus ──▶ SSE ──▶ live timeline`}</pre>
        </Card>
      </div>
    </section>
  );
}

/* ================================================================== docs */
const DOC_SECTIONS = [
  {
    title: "Quickstart",
    icon: IconTerminal,
    body: "Install, generate the sample datasets, start both servers.",
    code: `pip install -r requirements.txt
python scripts/make_sample_data.py
uvicorn backend.api.main:app --reload --port 8000

cd frontend && npm install && npm run dev`,
  },
  {
    title: "Run from Python",
    icon: IconBook,
    body: "The pipeline is importable — no HTTP required.",
    code: `from backend.core.orchestrator import Pipeline

result = Pipeline(
    "sample_data/customer_churn.csv",
    target_column="churn",
    sensitive_column="gender",
).run()

print(result["best_model"], result["metrics"]["roc_auc"])`,
  },
  {
    title: "Score the deployed model",
    icon: IconDocker,
    body: "Every run emits a container that serves the exact bundle.",
    code: `cd storage/runs/<run_id>/deploy
docker build -t dataid/model .
docker run -p 8080:8080 dataid/model

curl -X POST localhost:8080/predict \\
  -H 'Content-Type: application/json' \\
  -d '{"record": {"tenure_months": 3}}'`,
  },
  {
    title: "Use a real LLM",
    icon: IconSparkle,
    body: "Optional. The pipeline's numbers never depend on it.",
    code: `# free, local
export DATAID_LLM_PROVIDER=ollama
ollama pull llama3.1

# or a free-tier hosted model
export DATAID_LLM_PROVIDER=groq
export GROQ_API_KEY=...`,
  },
];

export function Docs() {
  const [active, setActive] = useState(0);
  const section = DOC_SECTIONS[active];
  const Icon = section.icon;

  return (
    <section id="docs" className="relative border-t py-24 sm:py-32">
      <div className="mx-auto max-w-7xl px-5 lg:px-8">
        <SectionHeading
          eyebrow="Documentation"
          title="Running in under two minutes"
          description="No Docker required to try it, no API key required to use it, no cloud account required at all."
        />

        <div className="mt-14 grid gap-6 lg:grid-cols-[280px_1fr]">
          <div className="scrollbar-none flex gap-2 overflow-x-auto lg:flex-col">
            {DOC_SECTIONS.map((item, index) => (
              <button
                key={item.title}
                onClick={() => setActive(index)}
                className={cn(
                  "flex shrink-0 items-center gap-3 rounded-xl border px-4 py-3 text-left transition-all focus-ring lg:w-full",
                  index === active
                    ? "border-brand-500/40 bg-brand-500/[0.07]"
                    : "hover:bg-black/[0.03] dark:hover:bg-white/[0.05]",
                )}
              >
                <item.icon className="h-4 w-4 shrink-0 text-brand-500 dark:text-brand-400" />
                <span className="whitespace-nowrap text-[13.5px] font-medium">{item.title}</span>
              </button>
            ))}
          </div>

          <Card className="overflow-hidden">
            <div className="flex items-center gap-3 border-b px-5 py-4">
              <Icon className="h-4.5 w-4.5 text-brand-500 dark:text-brand-400" style={{ width: 18, height: 18 }} />
              <div>
                <h3 className="text-[14.5px] font-semibold">{section.title}</h3>
                <p className="text-[12.5px] text-secondary">{section.body}</p>
              </div>
            </div>
            <pre className="overflow-x-auto bg-black/[0.02] p-5 font-mono text-[12.5px] leading-relaxed text-secondary dark:bg-white/[0.03]">
              {section.code}
            </pre>
          </Card>
        </div>
      </div>
    </section>
  );
}

/* ================================================================== testimonials */
/* ================================================================== CTA + contact */
export function Contact() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);

  return (
    <section id="contact" className="relative border-t py-24 sm:py-32">
      <div className="pointer-events-none absolute inset-0 bg-mesh opacity-50" aria-hidden />
      <div className="relative mx-auto max-w-4xl px-5 text-center lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
        >
          <h2 className="text-[34px] font-semibold leading-[1.12] tracking-[-0.02em] sm:text-[44px]">
            From raw data to production
            <br />
            <span className="gradient-text">in minutes</span>
          </h2>
          <p className="mx-auto mt-5 max-w-xl text-[16px] text-secondary">
            Open the app and drop a CSV. Nothing to configure, no account, no key.
          </p>

          <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
            <LinkButton href="/dashboard" size="lg">
              Open dataid
              <IconArrowRight className="h-4 w-4" />
            </LinkButton>
            <a
              href="https://github.com"
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex h-12 items-center justify-center gap-2.5 rounded-xl border bg-surface px-6 text-[15px] font-medium transition-colors hover:bg-black/[0.03] focus-ring dark:hover:bg-white/[0.05]"
            >
              <IconGithub className="h-4 w-4" />
              Star on GitHub
            </a>
          </div>

          <form
            onSubmit={(event) => {
              event.preventDefault();
              setSent(true);
            }}
            className="mx-auto mt-12 flex max-w-md flex-col gap-2.5 sm:flex-row"
          >
            <Input
              type="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@company.com"
              aria-label="Email address"
              className="flex-1"
            />
            <Button type="submit" size="md" variant={sent ? "secondary" : "primary"}>
              {sent ? "Thanks — you're on the list" : "Get product updates"}
            </Button>
          </form>
          <p className="mt-3 text-[12px] text-muted">
            Demo form — nothing is transmitted or stored.
          </p>
        </motion.div>
      </div>
    </section>
  );
}

/* ================================================================== footer */
const FOOTER_LINKS = [
  {
    heading: "Product",
    links: [
      { label: "How it works", href: "#how" },
      { label: "Agents", href: "#agents" },
      { label: "Live demo", href: "#demo" },
      { label: "Pricing", href: "#pricing" },
    ],
  },
  {
    heading: "Developers",
    links: [
      { label: "Documentation", href: "#docs" },
      { label: "Architecture", href: "#architecture" },
      { label: "API reference", href: "/api/docs" },
      { label: "GitHub", href: "https://github.com" },
    ],
  },
  {
    heading: "Workspace",
    links: [
      { label: "Dashboard", href: "/dashboard" },
      { label: "Model registry", href: "/dashboard/registry" },
      { label: "Audit log", href: "/dashboard/audit" },
      { label: "Settings", href: "/dashboard/settings" },
    ],
  },
];

export function Footer() {
  return (
    <footer className="border-t py-14">
      <div className="mx-auto max-w-7xl px-5 lg:px-8">
        <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-[1.4fr_repeat(3,1fr)]">
          <div>
            <Logo />
            <p className="mt-4 max-w-xs text-[13px] leading-relaxed text-secondary">
              The AI operating system for data scientists. Open source, runs locally, no API key
              required.
            </p>
            <div className="mt-5 flex gap-2">
              <a
                href="https://github.com"
                target="_blank"
                rel="noreferrer noopener"
                aria-label="GitHub"
                className="flex h-9 w-9 items-center justify-center rounded-lg border transition-colors hover:bg-black/[0.04] dark:hover:bg-white/[0.06]"
              >
                <IconGithub className="h-4 w-4" />
              </a>
            </div>
          </div>

          {FOOTER_LINKS.map((group) => (
            <div key={group.heading}>
              <p className="text-[12px] font-semibold uppercase tracking-[0.1em] text-muted">
                {group.heading}
              </p>
              <ul className="mt-4 space-y-2.5">
                {group.links.map((link) => (
                  <li key={link.label}>
                    <Link
                      href={link.href}
                      className="text-[13.5px] text-secondary transition-colors hover:text-[color:var(--ink)]"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-12 flex flex-col items-center justify-between gap-4 border-t pt-7 sm:flex-row">
          <p className="text-[12.5px] text-muted">
            © {new Date().getFullYear()} dataid. A portfolio project.
          </p>
          <p className="flex items-center gap-2 text-[12.5px] text-muted">
            <span
              className="h-1.5 w-1.5 rounded-full"
              style={{ background: "var(--status-good)" }}
            />
            All systems operational
          </p>
        </div>
      </div>
    </footer>
  );
}
