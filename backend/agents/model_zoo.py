"""Candidate model registry. Optional gradient-boosting libraries degrade gracefully."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ..core import config


@dataclass
class Candidate:
    key: str
    label: str
    family: str
    builder: Callable[..., Any]
    supports_class_weight: bool = False
    param_grid: Dict[str, List[Any]] = field(default_factory=dict)
    notes: str = ""


def _available(module: str) -> bool:
    import importlib.util

    return importlib.util.find_spec(module) is not None


HAS_XGBOOST = _available("xgboost")
HAS_LIGHTGBM = _available("lightgbm")
HAS_CATBOOST = _available("catboost")


def classification_candidates() -> List[Candidate]:
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
    from sklearn.ensemble import (
        AdaBoostClassifier,
        ExtraTreesClassifier,
        GradientBoostingClassifier,
        HistGradientBoostingClassifier,
        RandomForestClassifier,
    )
    from sklearn.linear_model import LogisticRegression, RidgeClassifier, SGDClassifier
    from sklearn.naive_bayes import GaussianNB
    from sklearn.neighbors import KNeighborsClassifier
    from sklearn.neural_network import MLPClassifier
    from sklearn.svm import SVC
    from sklearn.tree import DecisionTreeClassifier

    rs = config.RANDOM_STATE
    out: List[Candidate] = [
        Candidate("logistic_regression", "Logistic Regression", "linear",
                  lambda **kw: LogisticRegression(max_iter=2000, random_state=rs, **kw), True,
                  {"C": [0.1, 1.0, 10.0]}, "Fast, calibrated baseline."),
        Candidate("ridge_classifier", "Ridge Classifier", "linear",
                  lambda **kw: RidgeClassifier(random_state=rs, **kw), True,
                  {"alpha": [0.1, 1.0, 10.0]}),
        Candidate("sgd_classifier", "SGD Classifier", "linear",
                  lambda **kw: SGDClassifier(loss="log_loss", max_iter=2000, random_state=rs, **kw), True),
        Candidate("linear_discriminant", "Linear Discriminant", "linear",
                  lambda **kw: LinearDiscriminantAnalysis()),
        Candidate("gaussian_nb", "Gaussian Naive Bayes", "probabilistic",
                  lambda **kw: GaussianNB()),
        Candidate("knn", "K-Nearest Neighbours", "instance",
                  lambda **kw: KNeighborsClassifier(n_neighbors=15),
                  param_grid={"n_neighbors": [5, 15, 31]}),
        Candidate("decision_tree", "Decision Tree", "tree",
                  lambda **kw: DecisionTreeClassifier(random_state=rs, max_depth=12, **kw), True,
                  {"max_depth": [6, 12, None]}),
        Candidate("random_forest", "Random Forest", "ensemble",
                  lambda **kw: RandomForestClassifier(n_estimators=300, random_state=rs, n_jobs=-1, **kw), True,
                  {"max_depth": [8, 16, None], "min_samples_leaf": [1, 5]},
                  "Strong tabular default, resistant to noise."),
        Candidate("extra_trees", "Extra Trees", "ensemble",
                  lambda **kw: ExtraTreesClassifier(n_estimators=300, random_state=rs, n_jobs=-1, **kw), True),
        Candidate("gradient_boosting", "Gradient Boosting", "boosting",
                  lambda **kw: GradientBoostingClassifier(random_state=rs)),
        Candidate("hist_gradient_boosting", "HistGradientBoosting", "boosting",
                  lambda **kw: HistGradientBoostingClassifier(random_state=rs, **kw), True,
                  {"learning_rate": [0.05, 0.1], "max_leaf_nodes": [31, 63]},
                  "Native handling of large tabular data."),
        Candidate("adaboost", "AdaBoost", "boosting",
                  lambda **kw: AdaBoostClassifier(random_state=rs)),
        Candidate("svm_rbf", "SVM (RBF)", "kernel",
                  lambda **kw: SVC(probability=True, random_state=rs, **kw), True),
        Candidate("mlp", "Neural Net (MLP)", "neural",
                  lambda **kw: MLPClassifier(hidden_layer_sizes=(128, 64), max_iter=400, random_state=rs),
                  param_grid={"alpha": [1e-4, 1e-3]}, notes="Dense net for non-linear interactions."),
    ]
    if HAS_XGBOOST:
        from xgboost import XGBClassifier
        out.append(Candidate("xgboost", "XGBoost", "boosting",
                             lambda **kw: XGBClassifier(n_estimators=400, learning_rate=0.08, max_depth=6,
                                                        subsample=0.9, colsample_bytree=0.9, random_state=rs,
                                                        tree_method="hist", eval_metric="logloss", n_jobs=-1),
                             param_grid={"max_depth": [4, 6, 8], "learning_rate": [0.05, 0.1]},
                             notes="Usually the Kaggle-grade tabular winner."))
    if HAS_LIGHTGBM:
        from lightgbm import LGBMClassifier
        out.append(Candidate("lightgbm", "LightGBM", "boosting",
                             lambda **kw: LGBMClassifier(n_estimators=500, learning_rate=0.05, num_leaves=63,
                                                         random_state=rs, n_jobs=-1, verbose=-1, **kw), True,
                             {"num_leaves": [31, 63], "learning_rate": [0.03, 0.08]},
                             "Fastest boosting on wide data."))
    if HAS_CATBOOST:
        from catboost import CatBoostClassifier
        out.append(Candidate("catboost", "CatBoost", "boosting",
                             lambda **kw: CatBoostClassifier(iterations=500, learning_rate=0.06, depth=6,
                                                             random_seed=rs, verbose=0),
                             notes="Best-in-class on categorical-heavy data."))
    return out


def regression_candidates() -> List[Candidate]:
    from sklearn.ensemble import (
        AdaBoostRegressor,
        ExtraTreesRegressor,
        GradientBoostingRegressor,
        HistGradientBoostingRegressor,
        RandomForestRegressor,
    )
    from sklearn.linear_model import (
        BayesianRidge,
        ElasticNet,
        HuberRegressor,
        Lasso,
        LinearRegression,
        Ridge,
    )
    from sklearn.neighbors import KNeighborsRegressor
    from sklearn.neural_network import MLPRegressor
    from sklearn.svm import SVR
    from sklearn.tree import DecisionTreeRegressor

    rs = config.RANDOM_STATE
    out: List[Candidate] = [
        Candidate("linear_regression", "Linear Regression", "linear", lambda **kw: LinearRegression()),
        Candidate("ridge", "Ridge", "linear", lambda **kw: Ridge(random_state=rs),
                  param_grid={"alpha": [0.1, 1.0, 10.0]}),
        Candidate("lasso", "Lasso", "linear", lambda **kw: Lasso(random_state=rs, max_iter=5000),
                  param_grid={"alpha": [0.001, 0.01, 0.1]}),
        Candidate("elastic_net", "Elastic Net", "linear",
                  lambda **kw: ElasticNet(random_state=rs, max_iter=5000)),
        Candidate("bayesian_ridge", "Bayesian Ridge", "linear", lambda **kw: BayesianRidge()),
        Candidate("huber", "Huber Regressor", "robust", lambda **kw: HuberRegressor(max_iter=500),
                  notes="Robust to residual outliers."),
        Candidate("knn_regressor", "K-Nearest Neighbours", "instance",
                  lambda **kw: KNeighborsRegressor(n_neighbors=15)),
        Candidate("decision_tree_regressor", "Decision Tree", "tree",
                  lambda **kw: DecisionTreeRegressor(random_state=rs, max_depth=12)),
        Candidate("random_forest_regressor", "Random Forest", "ensemble",
                  lambda **kw: RandomForestRegressor(n_estimators=300, random_state=rs, n_jobs=-1),
                  param_grid={"max_depth": [8, 16, None]}),
        Candidate("extra_trees_regressor", "Extra Trees", "ensemble",
                  lambda **kw: ExtraTreesRegressor(n_estimators=300, random_state=rs, n_jobs=-1)),
        Candidate("gradient_boosting_regressor", "Gradient Boosting", "boosting",
                  lambda **kw: GradientBoostingRegressor(random_state=rs)),
        Candidate("hist_gradient_boosting_regressor", "HistGradientBoosting", "boosting",
                  lambda **kw: HistGradientBoostingRegressor(random_state=rs),
                  param_grid={"learning_rate": [0.05, 0.1], "max_leaf_nodes": [31, 63]}),
        Candidate("adaboost_regressor", "AdaBoost", "boosting",
                  lambda **kw: AdaBoostRegressor(random_state=rs)),
        Candidate("svr", "SVR (RBF)", "kernel", lambda **kw: SVR()),
        Candidate("mlp_regressor", "Neural Net (MLP)", "neural",
                  lambda **kw: MLPRegressor(hidden_layer_sizes=(128, 64), max_iter=500, random_state=rs)),
    ]
    if HAS_XGBOOST:
        from xgboost import XGBRegressor
        out.append(Candidate("xgboost_regressor", "XGBoost", "boosting",
                             lambda **kw: XGBRegressor(n_estimators=400, learning_rate=0.08, max_depth=6,
                                                       subsample=0.9, colsample_bytree=0.9, random_state=rs,
                                                       tree_method="hist", n_jobs=-1),
                             param_grid={"max_depth": [4, 6, 8], "learning_rate": [0.05, 0.1]}))
    if HAS_LIGHTGBM:
        from lightgbm import LGBMRegressor
        out.append(Candidate("lightgbm_regressor", "LightGBM", "boosting",
                             lambda **kw: LGBMRegressor(n_estimators=500, learning_rate=0.05, num_leaves=63,
                                                        random_state=rs, n_jobs=-1, verbose=-1),
                             param_grid={"num_leaves": [31, 63]}))
    if HAS_CATBOOST:
        from catboost import CatBoostRegressor
        out.append(Candidate("catboost_regressor", "CatBoost", "boosting",
                             lambda **kw: CatBoostRegressor(iterations=500, learning_rate=0.06, depth=6,
                                                            random_seed=rs, verbose=0)))
    return out


def clustering_candidates(n_rows: int = 1000) -> List[Candidate]:
    """Partitioning, density and hierarchical approaches — they fail on different shapes.

    `n_clusters` is swept rather than assumed: nobody knows k in advance, so the leaderboard
    ranking by silhouette *is* the search for it.
    """
    from sklearn.cluster import (
        DBSCAN,
        AgglomerativeClustering,
        Birch,
        KMeans,
        MeanShift,
        MiniBatchKMeans,
        SpectralClustering,
    )
    from sklearn.mixture import GaussianMixture

    rs = config.RANDOM_STATE
    ks = [k for k in (2, 3, 4, 5, 6, 8) if k < max(3, n_rows // 10)]
    out: List[Candidate] = []

    for k in ks:
        out.append(Candidate(
            f"kmeans_{k}", f"K-Means (k={k})", "partitioning",
            (lambda k=k: (lambda **kw: KMeans(n_clusters=k, random_state=rs, n_init=10)))(),
            param_grid={"n_clusters": ks},
            notes="Spherical clusters of similar size."))

    for k in ks[:4]:
        out.append(Candidate(
            f"gmm_{k}", f"Gaussian Mixture (k={k})", "probabilistic",
            (lambda k=k: (lambda **kw: GaussianMixture(n_components=k, random_state=rs)))(),
            notes="Elliptical clusters, soft assignment."))
        out.append(Candidate(
            f"agglomerative_{k}", f"Agglomerative (k={k})", "hierarchical",
            (lambda k=k: (lambda **kw: AgglomerativeClustering(n_clusters=k)))(),
            notes="Nested structure, no centroid assumption."))

    out.append(Candidate("dbscan", "DBSCAN", "density",
                         lambda **kw: DBSCAN(eps=0.8, min_samples=5),
                         notes="Finds arbitrary shapes and labels noise as -1."))
    out.append(Candidate("birch", "BIRCH", "hierarchical",
                         lambda **kw: Birch(n_clusters=3),
                         notes="Streaming-friendly on large data."))
    if n_rows <= 3000:
        out.append(Candidate("meanshift", "Mean Shift", "density",
                             lambda **kw: MeanShift(),
                             notes="Infers the cluster count itself; slow above a few thousand rows."))
        out.append(Candidate("spectral", "Spectral Clustering", "graph",
                             lambda **kw: SpectralClustering(n_clusters=3, random_state=rs,
                                                             assign_labels="kmeans"),
                             notes="Graph cut — handles non-convex clusters."))
    if n_rows > 20_000:
        out.append(Candidate("minibatch_kmeans", "MiniBatch K-Means", "partitioning",
                             lambda **kw: MiniBatchKMeans(n_clusters=4, random_state=rs, n_init=5),
                             notes="Scales to very large data."))
    return out


def anomaly_candidates(n_rows: int = 1000) -> List[Candidate]:
    """Outlier detectors across contamination assumptions.

    Contamination is swept because the true outlier rate is exactly what is unknown; the
    leaderboard picks the setting whose flagged population separates most cleanly.
    """
    from sklearn.covariance import EllipticEnvelope
    from sklearn.ensemble import IsolationForest
    from sklearn.neighbors import LocalOutlierFactor
    from sklearn.svm import OneClassSVM

    rs = config.RANDOM_STATE
    out: List[Candidate] = []

    for rate in (0.01, 0.02, 0.05, 0.1):
        out.append(Candidate(
            f"isolation_forest_{int(rate * 100)}", f"Isolation Forest ({rate:.0%})", "ensemble",
            (lambda rate=rate: (lambda **kw: IsolationForest(
                contamination=rate, random_state=rs, n_estimators=200, n_jobs=-1)))(),
            notes="Isolates points by random splits — the tabular default."))

    for rate in (0.02, 0.05):
        out.append(Candidate(
            f"lof_{int(rate * 100)}", f"Local Outlier Factor ({rate:.0%})", "density",
            (lambda rate=rate: (lambda **kw: LocalOutlierFactor(
                contamination=rate, novelty=True, n_neighbors=20)))(),
            notes="Compares local density to neighbours — catches local outliers."))
        out.append(Candidate(
            f"elliptic_{int(rate * 100)}", f"Elliptic Envelope ({rate:.0%})", "covariance",
            (lambda rate=rate: (lambda **kw: EllipticEnvelope(
                contamination=rate, random_state=rs, support_fraction=0.9)))(),
            notes="Assumes a Gaussian core; strong when that holds."))

    if n_rows <= 10_000:
        out.append(Candidate("one_class_svm", "One-Class SVM", "kernel",
                             lambda **kw: OneClassSVM(nu=0.05, kernel="rbf", gamma="scale"),
                             notes="Kernel boundary around the normal region."))
    return out


def candidates_for(task_type: str, n_rows: int = 1000) -> List[Candidate]:
    if task_type == "classification":
        return classification_candidates()
    if task_type == "clustering":
        return clustering_candidates(n_rows)
    if task_type == "anomaly":
        return anomaly_candidates(n_rows)
    # forecasting and ranking both learn a real-valued score, so they reuse the regressors
    return regression_candidates()


def availability() -> Dict[str, bool]:
    return {"xgboost": HAS_XGBOOST, "lightgbm": HAS_LIGHTGBM, "catboost": HAS_CATBOOST}
