# dataid

**The AI Operating System for Data Scientists.**
From raw data to production in minutes.

Upload a dataset, describe your goal, and eight specialised agents profile it, clean it, engineer
features, train and rank a portfolio of models, explain the winner, package it as a container, and
set up its monitoring baseline — streaming every step into a live timeline.

dataid runs **fully offline with no API key**. An LLM is optional and only ever improves the prose;
it never touches a number, a model or an artifact.

---

## Quickstart

Requires Python 3.11+ and Node.js 20+. Create a virtual environment before installing.
On Windows, use `py -3.11 -m venv .venv`, then `.venv\Scripts\Activate.ps1`.
On macOS/Linux, use `python3 -m venv .venv`, then `source .venv/bin/activate`.

```bash
# 1. Backend
pip install -r requirements.txt          # or requirements-core.txt for the minimum set
python scripts/make_sample_data.py       # writes five demo datasets to sample_data/
uvicorn backend.api.main:app --port 8000

# 2. Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Open <http://localhost:3000>. The Next.js dev server proxies `/api/*` to the backend, so everything
runs on one origin.

Prefer one command? `python scripts/dev.py` starts both.

The frontend build uses system fonts and requires no Google Fonts download.

### Verification

```bash
pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
cd frontend
npm ci
npm run build
```

Tests cover raw-input prediction parity, generated serving APIs, per-record validation,
holdout isolation, uploads, authentication, model promotion, and all six task families.
The pipeline smoke tests use small real estimators and generate the four document formats.
GitHub Actions runs these checks after the project is put in a GitHub repository.

Evaluation scope: the leaderboard uses the holdout to choose a winner, and cross-validation
operates on the transformed training matrix. For an unbiased final performance estimate,
evaluate the chosen bundle on an additional untouched dataset. Forecast metrics describe
rolling one-step-ahead prediction, not recursive multi-step forecasting.

### Workspace access

The default is a local, single-workspace application. To require authentication, set:

```dotenv
DATAID_REQUIRE_API_KEY=true
DATAID_ADMIN_TOKEN=<a-long-random-secret-you-generate>
```

Restart the backend, open **Settings → Workspace access**, and connect with the admin token.
Create scoped keys on the API Keys page, then use those keys for browser sessions or
`Authorization: Bearer <key>` for programmatic access. Revocation applies to browser sessions
too. Tokens are stored in HttpOnly cookies for browser access and hashed in the key registry.
Use HTTPS when hosting remotely. This is one shared workspace, without per-user tenant isolation.

Run the control plane with **one Uvicorn worker**: its run queue and live event bus are in-process.
Runs interrupted by a restart are marked failed and can be started again. Generated model
services are separate and may use multiple workers. Registry production promotion controls
serving; without a production model, the latest successful run is used.

> **Do not run the backend with `--reload` while executing pipelines.** The Deployment agent
> writes a generated `app.py` into `storage/runs/<id>/deploy/`; uvicorn's file watcher reads that
> as a source change and restarts the server mid-run, killing the executor thread and dropping
> the SSE stream behind the live timeline. `--reload-dir backend` does not reliably contain it.
> `scripts/dev.py` leaves reload off by default; pass `--reload` only when editing backend code.

---

## What actually happens on a run

```
ProjectContext  ──┬──▶ Data Detective       profile, issues, EDA
                  ├──▶ Data Cleaner         repaired frame, cleaning log
                  ├──▶ Feature Engineer     preprocessor, train/holdout split
                  ├──▶ ML Researcher        objective, metric, model shortlist
                  ├──▶ Experiment Manager   leaderboard, winner, metrics
                  ├──▶ Explainability       SHAP, LIME, counterfactuals, PDP
                  ├──▶ Deployment           bundle, FastAPI service, container
                  └──▶ Monitoring           reference distribution, drift, alerts
                            │
                            └──▶ EventBus ──▶ SSE ──▶ live timeline
```

Agents do **not** message each other through a model. They mutate one typed `ProjectContext` and
emit events, which is why the timeline is real and the run is reproducible.

### The eight agents

| Agent | Responsibility |
| --- | --- |
| **Data Detective** | Missing values, outliers (IQR + Isolation Forest), **target leakage via four independent probes**, class imbalance, collinearity |
| **Data Cleaner** | Drops identifiers/constants/leakage suspects, repairs types, imputes with a missingness indicator, winsorises, normalises categories |
| **Feature Engineer** | Datetime expansion with cyclical encoding, interactions and ratios, log transforms, frequency encoding, the fitted preprocessor |
| **ML Researcher** | Task framing across six families, primary metric (PR-AUC when imbalanced, MASE for forecasts, NDCG for ranking, silhouette for clustering), validation scheme, model shortlist sized to the data |
| **Experiment Manager** | Trains up to 20 candidates, cross-validates, ranks the leaderboard, reports the train/holdout gap, tunes the winner |
| **Explainability** | SHAP when available, permutation importance always, LIME-style local surrogates, counterfactuals, partial dependence, a plain-English summary |
| **Deployment** | Freezes preprocessor + model into one joblib bundle, generates a FastAPI service, Dockerfile, compose, K8s, Render, Railway, App Runner, Azure |
| **Monitoring** | Captures the training reference distribution, computes PSI per feature, defines metric-decay and latency alerts with thresholds |

Leakage detection is the part worth reading: it combines name semantics, near-perfect correlation
with the target, single-feature AUC separability, and category-to-target purity. In the bundled
`fraud_detection.csv` it finds the planted `chargeback_resolved_date` column and drops it before
training.

---

## Choosing the task

Six task families, picked on the run form. Leave it on auto-detect and dataid infers
classification or regression from the target, exactly as before.

| Task | Needs | What changes |
| --- | --- | --- |
| **Classification** | target | Stratified split, PR-AUC when imbalanced |
| **Regression** | target | Random split, R² |
| **Forecasting** | target + **time column** | Chronological split — never shuffled. Lag, rolling and difference features on the target. Rolling-origin CV. Scored on MAE, sMAPE and **MASE against the naive forecast** |
| **Clustering** | *nothing* | No target at all. Sweeps the cluster count and ranks by holdout silhouette, so choosing k *is* the experiment. Returns a profile of what distinguishes each segment |
| **Anomaly detection** | *nothing* | Sweeps contamination. Scored on how far the flagged population separates from the rest; supply a label and precision/recall are reported too |
| **Ranking** | target + **group column** | Whole query groups held out together. NDCG, MAP and MRR averaged per query |

The two unsupervised families are why `target_column` is optional throughout: `requires_target()`
in `backend/core/context.py` is the single check, and agents branch on the **task family**
(supervised / unsupervised / temporal / ranking) rather than on the task itself.

```python
Pipeline("customers.csv", task_type="clustering").run()                  # no target
Pipeline("txns.csv", task_type="anomaly", target_column="is_fraud").run()  # label optional
Pipeline("sales.csv", task_type="forecasting",
         target_column="demand", time_column="date").run()
Pipeline("results.csv", task_type="ranking",
         target_column="relevance", group_column="query_id").run()
```

Three details worth knowing, because each is a trap:

- **A forecast is never shuffled.** The holdout is the most recent slice. A random split lets the
  model train on Thursday to predict Wednesday, which inflates every metric and cannot happen in
  production.
- **Lag features are what make a forecast a forecast.** Every one is `shift(≥1)`, so a row only
  ever sees strictly earlier observations. On a trending series they take MASE from 9.3 to 0.80 —
  from nine times worse than doing nothing, to beating it.
- **The ranking group column is held out of the features.** Left in, the model learns "query q17
  scores high" instead of what makes an item relevant, and the holdout's unseen query ids make
  that knowledge worthless.

---

## Choosing what gets generated

The run form has an **Outputs to generate** picker — report, dashboard, deck, notebook. The model
is always trained and packaged; these are the documents written alongside it. Unticking everything
is legal and means "train and register, write no documents", which is the fastest way to iterate on
a model you are not ready to present.

The catalog is served from `/api/agents`, so the checkboxes cannot drift from what the pipeline can
actually produce. From Python it is the `artifacts` argument:

```python
Pipeline("data.csv", target_column="churn", artifacts=["report", "dashboard"]).run()
Pipeline("data.csv", target_column="churn", artifacts=[]).run()   # model only
```

---

## Generated artifacts

Every successful run writes to `storage/runs/<run_id>/`:

| File | What it is |
| --- | --- |
| `dataid_<id>.ipynb` | A **runnable** notebook that reproduces the pipeline, with narrative markdown and charts |
| `report_<id>.html` | Self-contained report — executive summary, findings, leaderboard, inline SVG charts |
| `report_<id>.md` | The same report as Markdown |
| `deck_<id>.pptx` | Eight-slide executive deck (falls back to an HTML deck without `python-pptx`) |
| `dashboard_<id>.html` | Interactive multi-panel dashboard with slicers and cross-filtering, one file, no CDN |
| `deployment.zip` | Complete, portable deployment directory |
| `deploy/model.joblib` | The frozen preprocessor + model bundle |
| `deploy/app.py` | Generated FastAPI service — `/predict`, `/predict/batch`, `/health`, `/schema`, `/metrics` |
| `deploy/Dockerfile` | Container image, non-root user, healthcheck |
| `deploy/k8s-deployment.yaml` | Deployment + Service + HorizontalPodAutoscaler |
| `deploy/{render,railway,apprunner,azure-container-app}.*` | Platform manifests |
| `deploy/CLIENTS.md` | curl, Python and TypeScript call examples |
| `monitoring_reference.json` | Reference distribution, drift status and alert rules |

Ship it:

```bash
cd storage/runs/<run_id>/deploy
docker build -t dataid/model . && docker run -p 8080:8080 dataid/model
curl localhost:8080/schema     # the exact columns /predict requires — all of them
```

The bytes that scored on holdout are the bytes the container loads — the preprocessor and the model
are the fitted objects, not a re-implementation of them.

The bundle now includes a fitted feature recipe. Both prediction APIs replay cleaning,
missingness flags, clipping, text normalisation, datetime expansion, interactions, ratios,
log transforms and frequency encoding before calling the frozen preprocessor and model.
Statistics and feature choices are learned from training rows after the holdout is reserved.
The control-plane API and generated service share the same inference runtime.

For ordinary tasks, send raw retained columns. `GET /api/projects/<project_id>/schema`
(or `/schema` on the generated service) lists required fields and an example payload.
Every record is checked separately, including records in a batch. Absent keys return 400;
explicit nulls use the fitted missing-value handling.

Forecasting is evaluated as rolling one-step-ahead prediction with observed past targets.
It additionally requires the history columns listed in `history_columns` (lags, rolling
statistics, differences and elapsed periods). A stateless request cannot reconstruct those
from a single future row. Models without `predict`, such as DBSCAN, are marked as unable
to serve unseen rows; choose a model with online inference for deployment.

Download **Complete deployment** from the run's artifacts to get `deployment.zip`, including
all runtime files, the fitted model, schema, pinned model-library versions and manifests.
Extract it before running Docker. Existing bundles remain readable but retain their old
engineered-input contract; re-run a project to get raw-input serving.

---

## Natural-language commands

The chat routes free text to a concrete intent, an agent plan and a real action:

| You say | What happens |
| --- | --- |
| *"Predict customer churn"* | Starts the full pipeline |
| *"My dataset is very imbalanced"* | Switches to PR-AUC, enables class weights, tunes the threshold |
| *"My model is overfitting"* | Cuts capacity, adds regularisation, widens CV |
| *"I want better recall"* | Sweeps the decision threshold instead of retraining |
| *"Find data leakage"* | Runs the four leakage probes |
| *"Explain this prediction to a CEO"* | Local attribution rewritten without jargon |
| *"Deploy this to Docker"* | Surfaces the packaged container and manifests |
| *"Build a dashboard"* | Regenerates the self-contained dashboard |

Sixteen intents in total — see `backend/core/commands.py`.

---

## Using it from Python

The pipeline is importable; HTTP is optional.

```python
from backend.core.orchestrator import Pipeline, understand_dataset

# what the AI reads from a file before anything runs
print(understand_dataset("sample_data/customer_churn.csv")["problem_statement"])

result = Pipeline(
    "sample_data/customer_churn.csv",
    target_column="churn",
    sensitive_column="gender",   # enables the fairness audit
    tune=True,
).run()

print(result["best_model"], result["metrics"]["roc_auc"])
print(result["artifacts"])
```

---

## Optional: a real LLM

The default provider is `none`. Every metric, ranking, feature attribution and drift figure is
computed by an agent and reported either way — a provider adds written analysis on top of those
numbers, and its absence removes the prose rather than substituting a stand-in for it. Every
alternative below is free to start — Hugging Face is the one that meters past a small included
credit. Copy `.env.example` to `.env` and fill one in; `.env` is gitignored and loaded
automatically, so nothing needs exporting.

```bash
DATAID_LLM_PROVIDER=nvidia                 # free credits — build.nvidia.com
NVIDIA_API_KEY=nvapi-...
DATAID_NVIDIA_MODEL=nvidia/nemotron-3-ultra-550b-a55b

DATAID_LLM_PROVIDER=huggingface            # one token, every served open-weights model
HF_TOKEN=hf_...                            # huggingface.co/settings/tokens
DATAID_HF_MODEL=moonshotai/Kimi-K3

DATAID_LLM_PROVIDER=gemini                 # free tier — aistudio.google.com/apikey
GEMINI_API_KEY=...

DATAID_LLM_PROVIDER=groq                   # free tier — console.groq.com/keys
GROQ_API_KEY=...

DATAID_LLM_PROVIDER=openrouter             # free-tier models — openrouter.ai/keys
OPENROUTER_API_KEY=...

DATAID_LLM_PROVIDER=ollama                 # free, local, no key
# ollama serve && ollama pull llama3.1
```

Real env vars always win over `.env`, so `DATAID_LLM_PROVIDER=groq python -m uvicorn ...` still
overrides the file for a single run.

**Failure is never fatal, and never papered over.** A provider that cannot be constructed (no
key) disables narration at startup; one that fails mid-run — a rate limit, a 503, a dropped
connection — omits that section, so the prose is lost but the pipeline, the metrics and the
artifacts are untouched. Sections with nothing written are dropped rather than filled, so an
absent narrator is visible instead of being disguised as a short analysis. Transient statuses are
retried twice with backoff; a bad key or a retired model fails immediately rather than burning
the retry budget.

### Model notes

`gemini-2.5-flash` is the default. Gemini 3.x models (`gemini-3.6-flash` and friends) spend part
of the completion budget on hidden reasoning tokens, so dataid sends `reasoning_effort: low` for
them and floors `max_tokens` at 2048 — without that the narration comes back cut mid-sentence
with `finish_reason="length"`. Raise `DATAID_LLM_MIN_MAX_TOKENS` if you still see truncation.

The `huggingface` provider is the Inference Providers router, which is why a 2.8-trillion-parameter
model is three lines of config rather than a hardware problem: HF forwards the call to whichever
partner (Together, Fireworks, Baseten, DeepInfra, Featherless) currently serves the weights, and
dataid only ever sees an OpenAI-compatible endpoint. `moonshotai/Kimi-K3` is the default there.

Do not try to load K3 through `transformers` locally. It is 2.8T parameters — the checkpoint alone
is well over a terabyte, and the `image-text-to-text` pipeline on its model card is the wrong shape
for this project anyway: dataid narrates numbers, and never sends an image to a model.

K3 reasons on every call and exposes no switch to turn that off, so thinking and prose come out of
one completion budget — and the ordinary 2048 floor is **not** enough. A short leaderboard summary
fits (~370 reasoning tokens), but the explainability prompt spends the whole 2048 thinking and the
narration lands truncated with `finish_reason="length"`. Thinking models therefore get
`DATAID_HF_REASONING_BUDGET` (8192) instead, gated on the model name exactly as the NVIDIA client
gates its own, so a non-thinking model served through the same router keeps the ordinary floor.
`max_tokens` is a ceiling rather than a target, so the larger budget costs nothing on a short answer.

When a model does spend its entire budget reasoning, the reply carries `content: null` with the
partial answer stranded in `reasoning_content`. The client salvages that rather than discarding it,
which is why a misconfigured budget degrades to cut-off prose instead of to silence.

On NVIDIA build the default is `nvidia/nemotron-3-ultra-550b-a55b`, a reasoning model. Thinking is
gated **per model**, which matters more than it sounds:

- The `nemotron-3` family requires `enable_thinking` + `reasoning_budget`. Sent to a model served
  without a reasoning config (`meta/llama-3.3-70b-instruct`), those same parameters return
  `HTTP 500: thinking_token_budget is set but reasoning_config is not configured`. 500 is a
  retryable status here, so sending them blindly burns both retries and silently drops the run to
  the offline narrator. `DATAID_NVIDIA_THINKING=auto` matches on the model name; `on`/`off` force it.
- Reasoning tokens share the completion budget, so thinking models get `DATAID_NVIDIA_REASONING_BUDGET`
  (8192) rather than the 2048 floor. When a model spends the whole budget thinking it returns an
  empty `content`, and dataid falls back to its `reasoning_content` rather than dropping the prose.
- The 550B model runs on shared free-tier capacity and intermittently returns
  `503 ResourceExhausted: Worker local total request limit reached`. That is retried with backoff;
  set `DATAID_NVIDIA_MODEL=meta/llama-3.3-70b-instruct` if you hit it often.

---

## Project layout

```
backend/
  core/         context, config, LLM, events, metrics, utils, store, orchestrator, commands
  agents/       the eight agents + the model zoo
  generators/   notebook, report, deck, dashboard, deploy templates, chart palette + SVG
  api/          FastAPI control plane, schemas, background run executor
frontend/
  app/          landing page + dashboard routes
  components/   landing sections, dashboard panels, UI primitives, chart components
  lib/          typed API client, shared types, formatters
scripts/        sample-data generator, dev launcher
sample_data/    five deliberately imperfect demo datasets
storage/        SQLite database, uploads, run artifacts (git-ignored)
```

### Enterprise scaffolding

Workspaces, versioned runs, a **model registry** with staging/production promotion, **scoped API
keys** (only a SHA-256 hash is stored — the token is shown once), and an **append-only audit log**.

---

## Data visualization

Charts follow one method across the Python-generated artifacts and the React frontend, sharing a
single validated palette (`backend/generators/palette.py` ↔ `frontend/app/globals.css`):

- Categorical hues are assigned in fixed slot order and never cycled
- Sequential encoding is one hue light→dark; diverging is blue ↔ **neutral gray** ↔ red
- Never a dual-axis chart
- A legend whenever there are ≥ 2 series; a table view on every chart
- Dark mode re-steps the same hues for the dark surface rather than inverting

The palette passes colour-vision-deficiency separation, lightness-band, chroma and contrast checks
in both light and dark modes.

### The Explore panel

The generated dashboard opens on **Explore**, which is a BI-style view rather than a picture of
one. The holdout set travels inside the file — each row's original feature values next to its
actual and predicted target — so the browser re-aggregates on demand:

- **Slicers** down the left: chips for every categorical column, min/max inputs for numeric ones
- **Cross-filtering**: click any bar and it becomes a filter; click it again to remove it
- **KPI tiles and all four charts recompute** against the current selection, not the whole set
- **Active filters** show as removable chips, with a reset

Charts are drawn by ~19 KB of dependency-free JavaScript, so the file stays openable offline with
no CDN and no build step. Row-level data is capped at 4,000 rows and 24 columns
(`backend/generators/explore.py`) to keep the document emailable — a 1,200-row classification run
lands around 300 KB. The remaining tabs stay pre-rendered SVG, since they describe the run as a
whole rather than a slice of it.

---

## Notes

- Optional dependencies (`xgboost`, `lightgbm`, `catboost`, `shap`, `python-pptx`, `openpyxl`,
  `pyarrow`) all degrade gracefully. `/api/health` reports what is actually installed.
- Uploads are stored under a generated filename, so a hostile filename cannot escape the upload
  directory; artifact downloads are path-checked against the run directory.
- Pricing on the landing page is illustrative — dataid is an open-source portfolio project and
  nothing is billed.
