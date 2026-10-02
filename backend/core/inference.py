"""Portable inference runtime, copied into each deployment without project imports.

Recipes contain fitted constants, never statistics recomputed from a request batch.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def prepare_frame(bundle, records):
    columns = bundle["input_columns"]
    if not records:
        raise ValueError("records must not be empty")
    for index, record in enumerate(records):
        missing = [c for c in columns if c not in record]
        if missing:
            raise ValueError(f"record {index}: missing required columns {missing}; send null to impute")
    df = pd.DataFrame(records, columns=columns).replace({None: np.nan})
    return apply_operations(df, bundle.get("feature_recipe", {}).get("operations", []))


def apply_operations(df, operations):
    df = df.copy()
    for op in operations:
        kind, col = op["kind"], op["column"]
        if kind == "numeric":
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(r"[,$%\s]", "", regex=True), errors="coerce")
        elif kind == "datetime":
            df[col] = pd.to_datetime(df[col], errors="coerce", format="mixed")
        elif kind == "indicator":
            df[op["output"]] = df[col].isna().astype(int)
        elif kind == "fill":
            df[col] = df[col].fillna(op["value"])
        elif kind == "clip":
            df[col] = df[col].clip(op["low"], op["high"])
        elif kind == "text":
            df[col] = df[col].astype("string").str.strip()
            if op["lower"]:
                df[col] = df[col].str.lower()
            df[col] = df[col].astype(object).where(df[col].notna(), np.nan)
        elif kind == "datepart":
            s = df[col].dt
            part = op["part"]
            if part == "is_weekend":
                values = (s.dayofweek >= 5).astype(int)
            elif part == "days_since_epoch":
                values = (df[col] - pd.Timestamp("1970-01-01")).dt.days
            elif part == "month_sin":
                values = np.sin(2 * np.pi * s.month / 12)
            elif part == "month_cos":
                values = np.cos(2 * np.pi * s.month / 12)
            else:
                values = getattr(s, part)
            df[op["output"]] = values.astype(float)
        elif kind == "product":
            df[op["output"]] = df[col] * df[op["other"]]
        elif kind == "ratio":
            df[op["output"]] = (df[col] / df[op["other"]].replace(0, np.nan)).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        elif kind == "log":
            df[op["output"]] = np.log1p(df[col])
        elif kind == "frequency":
            df[op["output"]] = df[col].map(op["values"]).astype(float).fillna(0.0)
        else:
            raise ValueError(f"Unknown feature operation: {kind}")
    return df


def score_records(bundle, records):
    model = bundle["model"]
    if not hasattr(model, "predict"):
        raise ValueError("This model cannot predict unseen rows without refitting")
    features = bundle["preprocessor"].transform(prepare_frame(bundle, records))
    predictions = model.predict(features)
    probabilities = None
    if bundle["task_type"] == "classification" and hasattr(model, "predict_proba"):
        probabilities = model.predict_proba(features)
        classes = [str(c) for c in model.classes_]
    out = []
    for i, prediction in enumerate(predictions):
        entry = {"prediction": prediction.item() if hasattr(prediction, "item") else prediction}
        if probabilities is not None:
            entry["probabilities"] = {c: round(float(p), 6) for c, p in zip(classes, probabilities[i])}
            entry["confidence"] = round(float(max(probabilities[i])), 6)
        out.append(entry)
    return out
