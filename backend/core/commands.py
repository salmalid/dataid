"""Natural-language command router.

Maps free text ("my dataset is very imbalanced", "deploy this to Docker") to a
concrete intent, an agent plan and a real action the backend can execute.

The routing is deterministic; the reply to the user is written by the configured model
against the real project state and the plan that was actually routed. With no model
configured the reply states that plan directly rather than a sentence written in advance.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .llm import narrate


@dataclass
class Intent:
    key: str
    label: str
    patterns: List[str]
    agents: List[str]
    action: str  # what the API should actually do
    steps: List[str]
    params: Dict[str, Any] = field(default_factory=dict)


INTENTS: List[Intent] = [
    Intent(
        key="run_pipeline",
        label="Build the full pipeline",
        patterns=[r"\bpredict\b", r"\bbuild\b.*\b(pipeline|model)\b", r"\btrain\b", r"\brun\b.*\bpipeline\b",
                  r"\bforecast\b", r"\bclassify\b", r"\bkaggle[- ]winning\b", r"\bstart\b.*\banalysis\b"],
        agents=["data_detective", "data_cleaner", "feature_engineer", "ml_researcher",
                "experiment_manager", "explainability", "deployment", "monitoring"],
        action="start_run",
        steps=["Profile the dataset and flag issues", "Clean and repair", "Engineer features",
               "Frame the objective and shortlist models", "Train and rank the portfolio",
               "Explain the winner", "Package for deployment", "Set the monitoring baseline"],
    ),
    Intent(
        key="handle_imbalance",
        label="Handle class imbalance",
        patterns=[r"\bimbalanc", r"\bskewed classes\b", r"\bminority class\b", r"\bsmote\b",
                  r"\bclass weight", r"\brare (event|class)"],
        agents=["ml_researcher", "experiment_manager"],
        action="rerun_with_options",
        params={"balance": True, "primary_metric": "pr_auc"},
        steps=["Switch the primary metric to PR-AUC", "Enable balanced class weights",
               "Compare against SMOTE oversampling", "Tune the decision threshold on the holdout"],
    ),
    Intent(
        key="fix_overfitting",
        label="Reduce overfitting",
        patterns=[r"\boverfit", r"\btrain.*better than.*test\b", r"\bgeneraliz", r"\bmemoriz"],
        agents=["ml_researcher", "experiment_manager"],
        action="rerun_with_options",
        params={"regularize": True, "tune": True},
        steps=["Reduce model capacity", "Add regularisation to the search space",
               "Widen cross-validation to 5 folds", "Report the train/holdout gap per model"],
    ),
    Intent(
        key="improve_recall",
        label="Optimise for recall",
        patterns=[r"\bbetter recall\b", r"\bmore recall\b", r"\bcatch more\b", r"\bfalse negative",
                  r"\bmiss(ing)? (fewer|less)\b", r"\bsensitivity\b"],
        agents=["experiment_manager", "explainability"],
        action="adjust_threshold",
        params={"objective": "recall"},
        steps=["Sweep the decision threshold from 0.05 to 0.95",
               "Pick the point that maximises recall at acceptable precision",
               "Report the precision cost of the change"],
    ),
    Intent(
        key="find_leakage",
        label="Find data leakage",
        patterns=[r"\bleak", r"\btoo good to be true\b", r"\bsuspicious(ly)? (high|good)\b",
                  r"\bcheating\b"],
        agents=["data_detective"],
        action="inspect",
        params={"section": "leakage"},
        steps=["Scan column names for post-outcome semantics",
               "Flag near-perfect correlation with the target",
               "Test single-feature separability", "Check category-to-target purity"],
    ),
    Intent(
        key="explain_prediction",
        label="Explain a prediction",
        patterns=[r"\bexplain\b.*\bprediction\b", r"\bwhy did\b", r"\bshap\b", r"\bfeature importance\b",
                  r"\bto a ceo\b", r"\binterpret"],
        agents=["explainability"],
        action="inspect",
        params={"section": "explainability"},
        steps=["Compute global attribution", "Decompose the individual prediction",
               "Search for the nearest counterfactual", "Translate it into business language"],
    ),
    Intent(
        key="deploy",
        label="Deploy the model",
        patterns=[r"\bdeploy\b", r"\bdocker\b", r"\bship it\b", r"\bproduction\b", r"\bkubernetes\b",
                  r"\baws\b", r"\brender\b", r"\brailway\b", r"\bazure\b", r"\bgenerate an? api\b"],
        agents=["deployment"],
        action="inspect",
        params={"section": "deployment"},
        steps=["Freeze the preprocessor and model into one bundle",
               "Generate the FastAPI service", "Build the container image",
               "Emit Kubernetes, Render, Railway, App Runner and Azure manifests"],
    ),
    Intent(
        key="monitor",
        label="Monitor production",
        patterns=[r"\bmonitor", r"\bdrift\b", r"\balert", r"\bproduction health\b",
                  r"\baccuracy dropped\b", r"\bdegrad", r"\bin production\b",
                  r"\bwatch\b", r"\bpsi\b"],
        agents=["monitoring"],
        action="inspect",
        params={"section": "monitoring"},
        steps=["Capture the reference distribution", "Compute PSI per feature",
               "Compare live metrics against the release baseline", "Fire the alert rules"],
    ),
    Intent(
        key="fairness",
        label="Audit fairness",
        patterns=[r"\bbias\b", r"\bfair", r"\bdiscriminat", r"\bprotected (attribute|group)",
                  r"\bequit"],
        agents=["experiment_manager"],
        action="inspect",
        params={"section": "fairness"},
        steps=["Slice performance by the sensitive attribute",
               "Compute selection rate and TPR parity", "Flag any gap beyond 10 points"],
    ),
    Intent(
        key="generate_notebook",
        label="Generate a notebook",
        patterns=[r"\bnotebook\b", r"\bjupyter\b", r"\bipynb\b"],
        agents=["generators"],
        action="artifact",
        params={"artifact": "notebook"},
        steps=["Rebuild the pipeline as runnable cells", "Interleave narrative markdown",
               "Attach the charts"],
    ),
    Intent(
        key="generate_report",
        label="Generate a report",
        patterns=[r"\breport\b", r"\bexecutive summary\b", r"\bpdf\b", r"\bword\b", r"\bwrite.?up\b"],
        agents=["generators"],
        action="artifact",
        params={"artifact": "report_html"},
        steps=["Assemble the executive summary", "Render the charts",
               "Attach the leaderboard and recommendations"],
    ),
    Intent(
        key="generate_deck",
        label="Generate a deck",
        patterns=[r"\bpowerpoint\b", r"\bslide", r"\bdeck\b", r"\bpptx\b", r"\bpresentation\b"],
        agents=["generators"],
        action="artifact",
        params={"artifact": "deck"},
        steps=["Distil to eight slides", "Lead with the headline metric",
               "Close on the recommendation"],
    ),
    Intent(
        key="generate_dashboard",
        label="Build a dashboard",
        patterns=[r"\bdashboard\b", r"\binteractive\b", r"\bvisuali[sz]"],
        agents=["generators"],
        action="artifact",
        params={"artifact": "dashboard"},
        steps=["Lay out the panels", "Wire the hover layer", "Bundle it as one HTML file"],
    ),
    Intent(
        key="optimize_inference",
        label="Optimise inference",
        patterns=[r"\bfaster\b", r"\blatenc", r"\bcompress\b", r"\bquanti[sz]", r"\bsmaller model\b",
                  r"\binference speed\b", r"\bmobile\b", r"\bspeed up\b",
                  r"\bspeed\b.*\binference\b"],
        agents=["experiment_manager", "deployment"],
        action="inspect",
        params={"section": "latency"},
        steps=["Benchmark every model's per-row latency",
               "Report the accuracy cost of the fastest viable model",
               "Recommend a serving configuration"],
    ),
    Intent(
        key="anomalies",
        label="Find anomalies",
        patterns=[r"\banomal", r"\boutlier", r"\bunusual\b", r"\bweird (rows|records)\b"],
        agents=["data_detective"],
        action="inspect",
        params={"section": "outliers"},
        steps=["IQR scan per numeric column", "Isolation Forest across the joint distribution",
               "Rank rows by anomaly score"],
    ),
    Intent(
        key="compare_runs",
        label="Compare experiments",
        patterns=[r"\bcompare\b.*\b(runs?|experiments?|previous|last)\b", r"\bversus\b", r"\bdiff\b",
                  r"\bregress(ion|ed)\b.*\bmetric"],
        agents=["experiment_manager"],
        action="compare",
        steps=["Align the two leaderboards", "Diff the metrics and the feature set",
               "Attribute the change"],
    ),
]

FALLBACK = Intent(
    key="unknown",
    label="General question",
    patterns=[],
    agents=["ml_researcher"],
    action="answer",
    steps=["Interpret the request against the current run"],
)


def route(message: str) -> Intent:
    text = message.lower().strip()
    best: Optional[Intent] = None
    best_hits = 0
    for intent in INTENTS:
        hits = sum(1 for pattern in intent.patterns if re.search(pattern, text))
        if hits > best_hits:
            best, best_hits = intent, hits
    return best or FALLBACK


def plan_statement(intent: Intent) -> str:
    """The routed plan, stated from the routing data itself.

    Used when no narrator is configured. True by construction — it names the steps the
    agents are actually about to take, rather than a sentence written in advance.
    """
    if intent.steps:
        return f"{intent.label}: " + "; ".join(intent.steps) + "."
    return intent.label


def respond(message: str, context_summary: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    intent = route(message)
    context_summary = context_summary or {}
    known = ", ".join(f"{k}={v}" for k, v in context_summary.items()
                      if v not in (None, "", False)) or "no dataset or completed run yet"
    # The model answers against the real project state and the real routed plan, so it can
    # only describe work the agents are actually queued to do.
    prose = narrate(
        f"User request: {message}\n"
        f"Routed intent: {intent.label}\n"
        f"Agents that will run: {', '.join(intent.agents) or 'none'}\n"
        f"Steps queued: {'; '.join(intent.steps) or 'none'}\n"
        f"Current project state: {known}\n"
        "Reply directly to the user in two or three sentences. Ground every claim in the state "
        "above and do not describe work outside the queued steps.",
        system="You are dataid, a senior data scientist pairing with the user. Be concrete, never "
               "promise work you have not done.",
    )
    return {
        "intent": intent.key,
        "label": intent.label,
        "action": intent.action,
        "params": intent.params,
        "agents": intent.agents,
        "steps": intent.steps,
        "reply": prose.strip() or plan_statement(intent),
        "detail": prose,
        "context": context_summary,
    }


def catalog() -> List[Dict[str, Any]]:
    return [{"key": i.key, "label": i.label, "agents": i.agents, "steps": i.steps} for i in INTENTS]
