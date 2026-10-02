"""Generate the five demo datasets dataid ships with.

    python scripts/make_sample_data.py

Each one is deliberately imperfect — missing values, duplicates, an id column,
outliers, and in two cases a planted leakage column — so the Data Detective has
something real to find.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "sample_data"
OUT.mkdir(parents=True, exist_ok=True)
RNG = np.random.default_rng(42)


def _dirty(df: pd.DataFrame, missing_cols: list[str], dup_frac: float = 0.02) -> pd.DataFrame:
    for col in missing_cols:
        mask = RNG.random(len(df)) < RNG.uniform(0.03, 0.16)
        df.loc[mask, col] = np.nan
    duplicates = df.sample(int(len(df) * dup_frac), random_state=7)
    return pd.concat([df, duplicates], ignore_index=True).sample(frac=1, random_state=1).reset_index(drop=True)


def customer_churn(n: int = 6000) -> pd.DataFrame:
    tenure = RNG.integers(1, 72, n)
    monthly = RNG.normal(70, 25, n).clip(15, 160)
    contract = RNG.choice(["month-to-month", "one year", "two year"], n, p=[0.55, 0.25, 0.20])
    support_calls = RNG.poisson(1.4, n)
    payment = RNG.choice(["card", "bank transfer", "electronic check", "mailed check"], n)

    logit = (-0.045 * tenure + 0.018 * monthly + 0.42 * support_calls
             + np.where(contract == "month-to-month", 1.3, -0.5)
             + np.where(payment == "electronic check", 0.6, 0) - 2.1)
    churn = (RNG.random(n) < 1 / (1 + np.exp(-logit))).astype(int)

    df = pd.DataFrame({
        "customer_id": [f"CUS{i:06d}" for i in range(n)],
        "tenure_months": tenure,
        "monthly_charges": monthly.round(2),
        "total_charges": (monthly * tenure).round(2),
        "contract_type": contract,
        "payment_method": payment,
        "support_calls": support_calls,
        "has_fiber": RNG.choice([0, 1], n, p=[0.55, 0.45]),
        "streaming_services": RNG.integers(0, 5, n),
        "signup_date": pd.to_datetime("2019-01-01") + pd.to_timedelta(RNG.integers(0, 1800, n), "D"),
        "region": RNG.choice(["north", "south", "east", "west"], n),
        "gender": RNG.choice(["female", "male"], n),
        "churn": churn,
    })
    return _dirty(df, ["total_charges", "payment_method", "streaming_services"])


def fraud_detection(n: int = 9000) -> pd.DataFrame:
    amount = np.abs(RNG.lognormal(3.4, 1.25, n)).round(2)
    hour = RNG.integers(0, 24, n)
    distance = np.abs(RNG.normal(22, 40, n)).round(1)
    prior_fraud = RNG.choice([0, 1], n, p=[0.97, 0.03])

    logit = (0.0022 * amount + 0.011 * distance + 1.9 * prior_fraud
             + np.where((hour < 5) | (hour > 22), 1.1, 0) - 5.2)
    fraud = (RNG.random(n) < 1 / (1 + np.exp(-logit))).astype(int)

    df = pd.DataFrame({
        "transaction_id": [f"TXN{i:07d}" for i in range(n)],
        "amount": amount,
        "hour_of_day": hour,
        "distance_from_home_km": distance,
        "merchant_category": RNG.choice(
            ["grocery", "electronics", "travel", "fuel", "restaurant", "online"], n),
        "card_type": RNG.choice(["credit", "debit", "prepaid"], n, p=[0.5, 0.42, 0.08]),
        "prior_fraud_flag": prior_fraud,
        "account_age_days": RNG.integers(20, 4000, n),
        "device_trust_score": RNG.uniform(0, 1, n).round(3),
        # planted leakage: only populated after the case is adjudicated
        "chargeback_resolved_date": np.where(
            fraud == 1,
            (pd.to_datetime("2024-01-01") + pd.to_timedelta(RNG.integers(0, 300, n), "D")).astype(str),
            None),
        "is_fraud": fraud,
    })
    return _dirty(df, ["device_trust_score", "merchant_category"])


def house_prices(n: int = 5000) -> pd.DataFrame:
    sqft = RNG.normal(1900, 750, n).clip(420, 6800)
    bedrooms = RNG.integers(1, 7, n)
    bathrooms = RNG.integers(1, 5, n)
    age = RNG.integers(0, 95, n)
    quality = RNG.integers(1, 11, n)
    garage = RNG.integers(0, 4, n)
    neighborhood = RNG.choice(["riverside", "downtown", "hillcrest", "eastwood", "oldtown"], n)
    premium = pd.Series(neighborhood).map(
        {"riverside": 92000, "downtown": 61000, "hillcrest": 128000,
         "eastwood": 24000, "oldtown": 0}).to_numpy()

    price = (sqft * 148 + bedrooms * 9200 + bathrooms * 14500 - age * 830
             + quality * 15200 + garage * 8600 + premium
             + RNG.normal(0, 26000, n)).clip(48000, None).round(0)

    df = pd.DataFrame({
        "listing_id": [f"LST{i:06d}" for i in range(n)],
        "square_feet": sqft.round(0),
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "year_built": 2024 - age,
        "quality_score": quality,
        "garage_spaces": garage,
        "neighborhood": neighborhood,
        "lot_size_sqft": (sqft * RNG.uniform(1.4, 4.2, n)).round(0),
        "has_pool": RNG.choice([0, 1], n, p=[0.82, 0.18]),
        "last_sold_date": pd.to_datetime("2015-01-01") + pd.to_timedelta(RNG.integers(0, 3200, n), "D"),
        "sale_price": price,
    })
    return _dirty(df, ["lot_size_sqft", "garage_spaces", "quality_score"])


def heart_disease(n: int = 3200) -> pd.DataFrame:
    age = RNG.integers(28, 82, n)
    cholesterol = RNG.normal(215, 48, n).clip(110, 460)
    resting_bp = RNG.normal(132, 19, n).clip(85, 205)
    max_hr = (208 - 0.7 * age + RNG.normal(0, 14, n)).clip(70, 205)
    chest_pain = RNG.choice(["typical", "atypical", "non-anginal", "asymptomatic"], n)

    logit = (0.055 * age + 0.007 * cholesterol + 0.019 * resting_bp - 0.031 * max_hr
             + np.where(chest_pain == "asymptomatic", 1.35, -0.3) - 4.4)
    disease = (RNG.random(n) < 1 / (1 + np.exp(-logit))).astype(int)

    df = pd.DataFrame({
        "patient_id": [f"PT{i:06d}" for i in range(n)],
        "age": age,
        "sex": RNG.choice(["female", "male"], n),
        "chest_pain_type": chest_pain,
        "resting_bp": resting_bp.round(0),
        "cholesterol": cholesterol.round(0),
        "fasting_blood_sugar": RNG.choice([0, 1], n, p=[0.85, 0.15]),
        "max_heart_rate": max_hr.round(0),
        "exercise_angina": RNG.choice([0, 1], n, p=[0.67, 0.33]),
        "st_depression": np.abs(RNG.normal(1.0, 1.1, n)).round(2),
        "smoker": RNG.choice([0, 1], n, p=[0.72, 0.28]),
        "heart_disease": disease,
    })
    return _dirty(df, ["cholesterol", "st_depression", "resting_bp"])


def titanic(n: int = 1400) -> pd.DataFrame:
    pclass = RNG.choice([1, 2, 3], n, p=[0.22, 0.24, 0.54])
    sex = RNG.choice(["female", "male"], n, p=[0.36, 0.64])
    age = RNG.normal(29, 14, n).clip(0.5, 80)
    fare = np.where(pclass == 1, RNG.normal(88, 55, n),
                    np.where(pclass == 2, RNG.normal(21, 11, n), RNG.normal(13, 9, n))).clip(3, 520)

    logit = (np.where(sex == "female", 2.4, -0.9) - 0.55 * pclass - 0.018 * age + 0.004 * fare + 0.6)
    survived = (RNG.random(n) < 1 / (1 + np.exp(-logit))).astype(int)

    df = pd.DataFrame({
        "passenger_id": np.arange(1, n + 1),
        "pclass": pclass,
        "sex": sex,
        "age": age.round(1),
        "siblings_spouses": RNG.poisson(0.5, n),
        "parents_children": RNG.poisson(0.4, n),
        "fare": fare.round(2),
        "embarked": RNG.choice(["S", "C", "Q"], n, p=[0.72, 0.19, 0.09]),
        "cabin_deck": RNG.choice(["A", "B", "C", "D", "E", "unknown"], n,
                                 p=[0.04, 0.06, 0.08, 0.07, 0.05, 0.70]),
        "survived": survived,
    })
    return _dirty(df, ["age", "embarked", "fare"], dup_frac=0.01)


DATASETS = {
    "customer_churn.csv": (customer_churn, "churn"),
    "fraud_detection.csv": (fraud_detection, "is_fraud"),
    "house_prices.csv": (house_prices, "sale_price"),
    "heart_disease.csv": (heart_disease, "heart_disease"),
    "titanic.csv": (titanic, "survived"),
}


def main() -> None:
    for filename, (builder, target) in DATASETS.items():
        df = builder()
        path = OUT / filename
        df.to_csv(path, index=False)
        print(f"{filename:24s} {len(df):>6,} rows x {df.shape[1]:>2} cols  target={target}")
    print(f"\nWritten to {OUT}")


if __name__ == "__main__":
    main()
