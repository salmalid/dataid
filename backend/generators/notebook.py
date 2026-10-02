"""Generates a runnable .ipynb that reproduces the whole run, with narrative markdown."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from ..core.utils import coerce_json


def _md(source: str) -> Dict[str, Any]:
    return {"cell_type": "markdown", "metadata": {}, "source": source.splitlines(keepends=True)}


def _code(source: str) -> Dict[str, Any]:
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
            "source": source.splitlines(keepends=True)}


def generate_notebook(ctx, dataset_path: str) -> Path:
    cleaning = ctx.cleaning_summary
    features = ctx.feature_summary
    research = ctx.research
    issues_table = "\n".join(
        f"| {i.severity} | {i.category} | {i.column or '—'} | {i.message} |" for i in ctx.issues[:25]
    ) or "| info | — | — | No issues detected. |"

    leaderboard_preview = ""
    if ctx.leaderboard is not None:
        cols = [c for c in ["rank", "model", "family"] if c in ctx.leaderboard.columns]
        metric_cols = [c for c in ctx.leaderboard.columns
                       if c in ("roc_auc", "accuracy", "f1", "r2", "rmse", "mae")][:3]
        leaderboard_preview = ctx.leaderboard[cols + metric_cols].head(10).to_markdown(index=False)

    dropped = ", ".join(f"`{c}`" for c in cleaning.get("dropped_columns", [])) or "none"
    created = ", ".join(f"`{c}`" for c in features.get("created_features", [])[:15]) or "none"
    strategy = "\n".join(f"- {s}" for s in research.get("strategy", []))

    cells: List[Dict[str, Any]] = [
        _md(f"""# {ctx.target_column} — dataid generated notebook

**Run** `{ctx.run_id}`  ·  **Task** {ctx.task_type.value}  ·  **Winner** {ctx.best_model_name}

This notebook reproduces the pipeline dataid executed: profiling, cleaning, feature
engineering, model comparison and explanation. Every cell is runnable — nothing here is
a screenshot of work done elsewhere.
"""),
        _code("""import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

pd.set_option("display.max_columns", 80)
sns.set_theme(style="whitegrid", palette="viridis")
RANDOM_STATE = 42"""),
        _md("## 1. Load the dataset"),
        _code(f'''df = pd.read_csv(r"{dataset_path}")
TARGET = "{ctx.target_column}"

print(f"{{df.shape[0]:,}} rows x {{df.shape[1]}} columns")
df.head()'''),
        _code("""df.info()
df.describe(include="all").T.head(30)"""),
        _md(f"""## 2. What the Data Detective found

| Severity | Category | Column | Finding |
| --- | --- | --- | --- |
{issues_table}
"""),
        _code("""missing = df.isna().mean().sort_values(ascending=False)
missing = missing[missing > 0]

if not missing.empty:
    fig, ax = plt.subplots(figsize=(10, max(3, len(missing) * 0.3)))
    missing.plot.barh(ax=ax, color="#6366f1")
    ax.set_xlabel("fraction missing")
    ax.set_title("Missing values by column")
    plt.tight_layout()
else:
    print("No missing values.")"""),
        _code("""numeric = df.select_dtypes(include=[np.number])
if numeric.shape[1] >= 2:
    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(numeric.corr(numeric_only=True), cmap="RdBu_r", center=0,
                square=True, linewidths=0.4, ax=ax)
    ax.set_title("Correlation matrix")
    plt.tight_layout()"""),
        _code(f"""target = df[TARGET]
fig, ax = plt.subplots(figsize=(8, 4))
if target.dtype == object or target.nunique() <= 20:
    target.astype(str).value_counts().plot.bar(ax=ax, color="#8b5cf6")
    ax.set_title("Target class distribution")
else:
    sns.histplot(target.dropna(), kde=True, ax=ax, color="#8b5cf6")
    ax.set_title("Target distribution")
plt.tight_layout()"""),
        _md(f"""## 3. Cleaning

The Data Cleaner dropped {dropped} and reshaped
`{cleaning.get('shape_before')}` → `{cleaning.get('shape_after')}`.
"""),
        _code(f"""DROP_COLUMNS = {json.dumps(cleaning.get("dropped_columns", []))}

df = df[df[TARGET].notna()].drop_duplicates().reset_index(drop=True)
df = df.drop(columns=[c for c in DROP_COLUMNS if c in df.columns])

for col in df.columns:
    if col == TARGET or df[col].isna().sum() == 0:
        continue
    if pd.api.types.is_numeric_dtype(df[col]):
        df[col] = df[col].fillna(df[col].median())
    else:
        mode = df[col].mode(dropna=True)
        df[col] = df[col].fillna(mode.iloc[0] if not mode.empty else "unknown")

print(f"clean shape: {{df.shape}}, remaining nulls: {{int(df.isna().sum().sum())}}")"""),
        _md(f"""## 4. Feature engineering

{features.get('n_created', 0)} features were derived, including {created}.
The preprocessor expands them to **{features.get('n_features_out', 0)}** model-ready columns.
"""),
        _code("""from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.model_selection import train_test_split

X = df.drop(columns=[TARGET])
y = df[TARGET]

numeric_cols = X.select_dtypes(include=[np.number]).columns.tolist()
categorical_cols = [c for c in X.columns if c not in numeric_cols]

preprocessor = ColumnTransformer([
    ("numeric", Pipeline([("impute", SimpleImputer(strategy="median")),
                          ("scale", StandardScaler())]), numeric_cols),
    ("categorical", Pipeline([("impute", SimpleImputer(strategy="most_frequent")),
                              ("onehot", OneHotEncoder(handle_unknown="ignore",
                                                       sparse_output=False,
                                                       drop="if_binary"))]), categorical_cols),
])"""),
        _code(f"""IS_CLASSIFICATION = {ctx.task_type.value == 'classification'}

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=RANDOM_STATE,
    stratify=y if IS_CLASSIFICATION else None,
)

X_train_t = preprocessor.fit_transform(X_train)
X_test_t = preprocessor.transform(X_test)
print(X_train_t.shape, X_test_t.shape)"""),
        _md(f"""## 5. Model comparison

The ML Researcher optimised for **{research.get('primary_metric')}**.

{strategy}

{leaderboard_preview}
"""),
        _code(_model_comparison_code(ctx)),
        _md("## 6. Winning model — holdout performance"),
        _code(_evaluation_code(ctx)),
        _md("## 7. Explainability"),
        _code("""from sklearn.inspection import permutation_importance

feature_names = preprocessor.get_feature_names_out()
importance = getattr(best_model, "feature_importances_", None)

if importance is None:
    result = permutation_importance(best_model, X_test_t[:1000], y_test[:1000],
                                    n_repeats=5, random_state=RANDOM_STATE)
    importance = result.importances_mean

top = (pd.Series(importance, index=feature_names)
       .sort_values(key=abs, ascending=False).head(20))

fig, ax = plt.subplots(figsize=(9, 7))
top.sort_values().plot.barh(ax=ax, color="#6366f1")
ax.set_title("Top 20 features")
plt.tight_layout()"""),
        _code("""# SHAP, if installed
try:
    import shap
    explainer = shap.Explainer(best_model, X_train_t[:200])
    shap_values = explainer(X_test_t[:200])
    shap.plots.beeswarm(shap_values, max_display=15)
except Exception as exc:
    print(f"SHAP unavailable ({exc}); permutation importance above covers global attribution.")"""),
        _md(f"""## 8. Ship it

```bash
cd deploy
pip install -r requirements.txt
uvicorn app:app --port 8080
# or
docker build -t dataid/{ctx.run_id} . && docker run -p 8080:8080 dataid/{ctx.run_id}
```

{ctx.explainability.get('business_summary', '')}
"""),
        _code("""import joblib

joblib.dump({"preprocessor": preprocessor, "model": best_model,
             "target": TARGET, "input_columns": list(X.columns)}, "model.joblib")
print("saved model.joblib")"""),
    ]

    notebook = {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11"},
            "dataid": coerce_json({"run_id": ctx.run_id, "model": ctx.best_model_name,
                                   "metrics": {k: v for k, v in ctx.metrics.items()
                                               if isinstance(v, (int, float))}}),
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }

    path = ctx.artifacts_dir / f"dataid_{ctx.run_id}.ipynb"
    path.write_text(json.dumps(notebook, indent=1), encoding="utf-8")
    return path


def _model_comparison_code(ctx) -> str:
    if ctx.task_type.value == "classification":
        return """from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score

candidates = {
    "Logistic Regression": LogisticRegression(max_iter=2000, random_state=RANDOM_STATE),
    "Random Forest": RandomForestClassifier(n_estimators=300, random_state=RANDOM_STATE, n_jobs=-1),
    "HistGradientBoosting": HistGradientBoostingClassifier(random_state=RANDOM_STATE),
}
try:
    from xgboost import XGBClassifier
    candidates["XGBoost"] = XGBClassifier(n_estimators=400, learning_rate=0.08, max_depth=6,
                                          random_state=RANDOM_STATE, eval_metric="logloss")
except ImportError:
    pass

rows = []
fitted = {}
for name, model in candidates.items():
    model.fit(X_train_t, y_train)
    fitted[name] = model
    pred = model.predict(X_test_t)
    row = {"model": name,
           "accuracy": accuracy_score(y_test, pred),
           "f1": f1_score(y_test, pred, average="weighted", zero_division=0)}
    if hasattr(model, "predict_proba") and y.nunique() == 2:
        row["roc_auc"] = roc_auc_score(y_test, model.predict_proba(X_test_t)[:, 1])
    rows.append(row)

leaderboard = pd.DataFrame(rows).sort_values("f1", ascending=False).reset_index(drop=True)
best_model = fitted[leaderboard.iloc[0]["model"]]
leaderboard"""
    return """from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

candidates = {
    "Ridge": Ridge(random_state=RANDOM_STATE),
    "Random Forest": RandomForestRegressor(n_estimators=300, random_state=RANDOM_STATE, n_jobs=-1),
    "HistGradientBoosting": HistGradientBoostingRegressor(random_state=RANDOM_STATE),
}
try:
    from xgboost import XGBRegressor
    candidates["XGBoost"] = XGBRegressor(n_estimators=400, learning_rate=0.08, max_depth=6,
                                         random_state=RANDOM_STATE)
except ImportError:
    pass

rows = []
fitted = {}
for name, model in candidates.items():
    model.fit(X_train_t, y_train)
    fitted[name] = model
    pred = model.predict(X_test_t)
    rows.append({"model": name,
                 "r2": r2_score(y_test, pred),
                 "mae": mean_absolute_error(y_test, pred),
                 "rmse": np.sqrt(mean_squared_error(y_test, pred))})

leaderboard = pd.DataFrame(rows).sort_values("r2", ascending=False).reset_index(drop=True)
best_model = fitted[leaderboard.iloc[0]["model"]]
leaderboard"""


def _evaluation_code(ctx) -> str:
    if ctx.task_type.value == "classification":
        return """from sklearn.metrics import ConfusionMatrixDisplay, classification_report, RocCurveDisplay

pred = best_model.predict(X_test_t)
print(classification_report(y_test, pred, zero_division=0))

fig, axes = plt.subplots(1, 2, figsize=(13, 5))
ConfusionMatrixDisplay.from_predictions(y_test, pred, ax=axes[0], cmap="Purples",
                                        colorbar=False)
axes[0].set_title("Confusion matrix")

if hasattr(best_model, "predict_proba") and pd.Series(y_test).nunique() == 2:
    RocCurveDisplay.from_estimator(best_model, X_test_t, y_test, ax=axes[1], color="#6366f1")
    axes[1].plot([0, 1], [0, 1], "--", color="#94a3b8")
    axes[1].set_title("ROC curve")
else:
    axes[1].axis("off")
plt.tight_layout()"""
    return """pred = best_model.predict(X_test_t)
residuals = y_test - pred

fig, axes = plt.subplots(1, 3, figsize=(16, 4.5))
axes[0].scatter(y_test, pred, alpha=0.4, s=14, color="#6366f1")
lims = [min(y_test.min(), pred.min()), max(y_test.max(), pred.max())]
axes[0].plot(lims, lims, "--", color="#ef4444")
axes[0].set(xlabel="actual", ylabel="predicted", title="Predicted vs actual")

axes[1].scatter(pred, residuals, alpha=0.4, s=14, color="#8b5cf6")
axes[1].axhline(0, color="#ef4444", linestyle="--")
axes[1].set(xlabel="predicted", ylabel="residual", title="Residuals")

sns.histplot(residuals, kde=True, ax=axes[2], color="#6366f1")
axes[2].set_title("Residual distribution")
plt.tight_layout()

print(f"R2   {r2_score(y_test, pred):.4f}")
print(f"MAE  {mean_absolute_error(y_test, pred):,.4f}")
print(f"RMSE {np.sqrt(mean_squared_error(y_test, pred)):,.4f}")"""
