"""Train the document classifier and track everything with MLflow.

Runs GridSearchCV to find the best TF-IDF + LogisticRegression params,
evaluates with out-of-fold cross-validation, logs metrics/plots/model
to MLflow, and saves a joblib fallback for Lambda deployment.

Usage:
    uv run python scripts/train_classifier.py
    mlflow ui  # view results at http://localhost:5000
"""

import argparse
import hashlib
import json
import logging
import os
import platform
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless, before other matplotlib imports

import joblib
import matplotlib.pyplot as plt
import mlflow
import numpy as np
import seaborn as sns
from sklearn.calibration import CalibrationDisplay
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    classification_report,
    ConfusionMatrixDisplay,
    f1_score,
    log_loss,
    roc_auc_score,
)
from sklearn.model_selection import (
    cross_val_predict,
    GridSearchCV,
    StratifiedKFold,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import label_binarize

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

TRAINING_DATA_PATH = Path(__file__).parent.parent / "classifier" / "training_data.json"
CONFIDENCE_THRESHOLD = 0.75
CV_FOLDS = 5
RANDOM_STATE = 42


def load_data(path: Path) -> tuple[list[str], list[str]]:
    """Load training samples, return (texts, labels). Fails fast on bad data."""
    with open(path) as f:
        data = json.load(f)

    texts = [s["text"] for s in data]
    labels = [s["label"] for s in data]

    assert len(texts) > 0, "empty training data"
    assert set(labels) == {"invoice", "receipt", "contract", "other"}, (
        f"unexpected labels: {set(labels)}"
    )

    counts = {l: labels.count(l) for l in sorted(set(labels))}
    logger.info("Loaded %d samples: %s", len(texts), counts)
    return texts, labels


def file_md5(path: Path) -> str:
    """Hash the training data so the manifest can prove which data produced which model."""
    return hashlib.md5(path.read_bytes()).hexdigest()


def build_pipeline() -> Pipeline:
    """Create a fresh TF-IDF + LogisticRegression pipeline.

    These are the base params. GridSearchCV overrides some of them
    during the search. The ones not in the search grid stay fixed.
    """
    return Pipeline([
        ("tfidf", TfidfVectorizer(
            sublinear_tf=True,
            max_df=0.5,
            min_df=2,
            max_features=5000,
            ngram_range=(1, 2),
        )),
        ("clf", LogisticRegression(
            C=1.0,
            max_iter=1000,
            solver="lbfgs",
            class_weight="balanced",
            random_state=RANDOM_STATE,
        )),
    ])


def run_grid_search(texts, labels) -> GridSearchCV:
    """Try different param combos and return the best one."""
    param_grid = {
        "tfidf__max_features": [5000, 10000],
        "tfidf__ngram_range": [(1, 1), (1, 2)],
        "clf__C": [0.1, 1.0, 10.0],
    }

    cv = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)

    search = GridSearchCV(
        build_pipeline(),
        param_grid,
        cv=cv,
        scoring="f1_macro",
        n_jobs=-1,
        refit=True,
    )
    search.fit(texts, labels)

    logger.info("Best CV F1: %.4f | Params: %s", search.best_score_, search.best_params_)
    return search


def log_grid_search_runs(search: GridSearchCV):
    """Log each grid search candidate as a nested MLflow child run."""
    results = search.cv_results_

    for i in range(len(results["params"])):
        with mlflow.start_run(run_name=f"grid_{i:02d}", nested=True):
            mlflow.log_params({
                str(k): str(v) for k, v in results["params"][i].items()
            })
            mlflow.log_metric("cv_f1_mean", round(float(results["mean_test_score"][i]), 4))
            mlflow.log_metric("cv_f1_std", round(float(results["std_test_score"][i]), 4))


def evaluate_oof(pipeline: Pipeline, texts, labels):
    """Get predictions for every document without data leakage.

    Each document is predicted by a model that never saw it during
    training. Returns the true labels, predicted labels, and
    probability scores for every sample.
    """
    cv = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)

    y_pred = cross_val_predict(pipeline, texts, labels, cv=cv, n_jobs=-1)

    y_proba = cross_val_predict(
        pipeline, texts, labels, cv=cv, method="predict_proba", n_jobs=-1
    )

    return np.array(labels), y_pred, y_proba


def compute_metrics(y_true, y_pred, y_proba, classes) -> dict:
    """Compute everything we want to track in MLflow."""
    metrics = {}

    # overall scores
    metrics["accuracy"] = round(accuracy_score(y_true, y_pred), 4)
    metrics["macro_f1"] = round(f1_score(y_true, y_pred, average="macro"), 4)
    metrics["weighted_f1"] = round(f1_score(y_true, y_pred, average="weighted"), 4)
    metrics["log_loss"] = round(log_loss(y_true, y_proba, labels=classes), 4)

    # ROC AUC needs binary labels (one column per class)
    y_bin = label_binarize(y_true, classes=classes)
    metrics["roc_auc_ovr"] = round(
        roc_auc_score(y_bin, y_proba, average="macro", multi_class="ovr"), 4
    )

    # what % of predictions are confident enough to auto-classify
    max_conf = y_proba.max(axis=1)
    metrics["coverage_at_threshold"] = round(
        (max_conf >= CONFIDENCE_THRESHOLD).mean(), 4
    )

    # per-class breakdown
    report = classification_report(y_true, y_pred, target_names=classes, output_dict=True)
    for cls in classes:
        metrics[f"{cls}_precision"] = round(report[cls]["precision"], 4)
        metrics[f"{cls}_recall"] = round(report[cls]["recall"], 4)
        metrics[f"{cls}_f1"] = round(report[cls]["f1-score"], 4)

    # per-class calibration (Brier score, lower is better)
    for i, cls in enumerate(classes):
        y_cls = (y_true == cls).astype(int)
        metrics[f"{cls}_brier"] = round(brier_score_loss(y_cls, y_proba[:, i]), 4)

    return metrics
