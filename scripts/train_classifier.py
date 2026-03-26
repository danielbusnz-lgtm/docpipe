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


# --- Plot styling ---

CB_COLORS = ["#377eb8", "#ff7f00", "#4daf4a", "#984ea3"]

def _apply_style():
    """Set up professional plot defaults."""
    try:
        plt.style.use(["science", "no-latex"])
    except OSError:
        pass  # scienceplots not installed, use defaults
    plt.rcParams.update({
        "figure.dpi": 150,
        "figure.facecolor": "white",
        "font.size": 12,
        "axes.titlesize": 14,
        "axes.titleweight": "bold",
        "axes.labelsize": 13,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": "#E0E0E0",
        "grid.alpha": 0.7,
        "legend.fontsize": 10,
        "legend.framealpha": 0.9,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
    })


# --- Individual plot functions ---

def _plot_confusion_matrix(y_true, y_pred, classes, path: Path):
    """Row-normalized confusion matrix with raw counts annotated."""
    from sklearn.metrics import confusion_matrix as cm_func

    cm_raw = cm_func(y_true, y_pred, labels=classes)
    cm_norm = cm_raw.astype(float) / cm_raw.sum(axis=1)[:, np.newaxis]

    # build dual annotations: percentage on top, count below
    annot = np.empty_like(cm_raw, dtype=object)
    for i in range(len(classes)):
        for j in range(len(classes)):
            annot[i, j] = f"{cm_norm[i, j]:.1%}\nn={cm_raw[i, j]}"

    fig, ax = plt.subplots(figsize=(8, 6))
    sns.heatmap(
        cm_norm, annot=annot, fmt="", cmap="Blues",
        vmin=0, vmax=1, linewidths=0.5, linecolor="white",
        xticklabels=classes, yticklabels=classes,
        cbar_kws={"label": "Recall", "shrink": 0.8},
        annot_kws={"size": 11}, ax=ax,
    )
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title("Confusion Matrix (Out-of-Fold)")
    ax.set_yticklabels(ax.get_yticklabels(), rotation=0)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_confidence_histogram(y_true, y_pred, y_proba, classes, path: Path):
    """Confidence split by correct vs incorrect predictions."""
    max_conf = y_proba.max(axis=1)
    correct = (y_pred == y_true)
    bins = np.linspace(0, 1, 21)  # fixed 0.05 bins

    fig, axes = plt.subplots(2, 3, figsize=(15, 9))
    axes = axes.flatten()

    def _one(ax, confs, mask, title):
        ax.hist(confs[mask], bins=bins, alpha=0.6, color="#377eb8",
                label="Correct", edgecolor="white", linewidth=0.4)
        ax.hist(confs[~mask], bins=bins, alpha=0.6, color="#e41a1c",
                label="Incorrect", edgecolor="white", linewidth=0.4)
        ax.axvline(CONFIDENCE_THRESHOLD, color="gray", linestyle="--", linewidth=1.5)
        acc = mask.mean()
        ax.set_title(f"{title}  (acc={acc:.2%}, n={len(confs)})")
        ax.set_xlabel("Confidence")
        ax.set_ylabel("Count")
        ax.legend(fontsize=8)
        ax.set_xlim(0, 1)

    # overall
    _one(axes[0], max_conf, correct, "Overall")

    # per class (by true label)
    for i, cls in enumerate(classes):
        mask = (y_true == cls)
        _one(axes[i + 1], max_conf[mask], correct[mask], f"True: {cls}")

    axes[5].set_visible(False)  # hide unused subplot

    fig.suptitle("Confidence Distribution: Correct vs Incorrect", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _expected_calibration_error(y_true_bin, y_prob, n_bins=10):
    """ECE: weighted average of |accuracy - confidence| per bin."""
    bin_edges = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for lo, hi in zip(bin_edges[:-1], bin_edges[1:]):
        mask = (y_prob >= lo) & (y_prob < hi)
        if mask.sum() == 0:
            continue
        bin_acc = y_true_bin[mask].mean()
        bin_conf = y_prob[mask].mean()
        ece += (mask.sum() / len(y_prob)) * abs(bin_acc - bin_conf)
    return ece


def _plot_calibration_curves(y_true, y_proba, classes, path: Path):
    """Per-class calibration with ECE and confidence histogram inset."""
    from sklearn.calibration import calibration_curve

    fig, axes = plt.subplots(2, 2, figsize=(10, 9))

    for i, (cls, ax) in enumerate(zip(classes, axes.flatten())):
        y_bin = (y_true == cls).astype(int)
        prob_true, prob_pred = calibration_curve(
            y_bin, y_proba[:, i], n_bins=10, strategy="uniform"
        )
        ece = _expected_calibration_error(y_bin, y_proba[:, i])

        ax.plot([0, 1], [0, 1], "--", color="#999999", linewidth=1.2, label="Perfect")
        ax.plot(prob_pred, prob_true, "o-", color=CB_COLORS[i], linewidth=2,
                markersize=5, label=f"Model (ECE={ece:.3f})")
        ax.fill_between(prob_pred, prob_pred, prob_true, alpha=0.15, color=CB_COLORS[i])
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_xlabel("Mean Predicted Confidence")
        ax.set_ylabel("Fraction Positive")
        ax.set_title(f"Calibration: {cls}")
        ax.legend(fontsize=9)

        # inset: where the confidence scores actually fall
        ax2 = ax.inset_axes([0.05, 0.05, 0.9, 0.12])
        ax2.hist(y_proba[:, i], bins=20, color=CB_COLORS[i], alpha=0.4, edgecolor="none")
        ax2.set_xlim(0, 1)
        ax2.axis("off")

    fig.suptitle("Calibration Curves (One-vs-Rest)", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_roc_curves(y_true, y_proba, classes, path: Path):
    """Per-class ROC curves with AUC, following sklearn's OvR pattern."""
    from sklearn.metrics import RocCurveDisplay

    y_bin = label_binarize(y_true, classes=classes)
    fig, ax = plt.subplots(figsize=(8, 7))

    for i, cls in enumerate(classes):
        RocCurveDisplay.from_predictions(
            y_bin[:, i], y_proba[:, i],
            name=f"{cls}",
            curve_kwargs=dict(color=CB_COLORS[i]),
            ax=ax,
            plot_chance_level=(i == 0),
        )

    ax.set_title("ROC Curves (One-vs-Rest)")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_pr_curves(y_true, y_proba, classes, path: Path):
    """Per-class Precision-Recall curves with average precision."""
    from sklearn.metrics import precision_recall_curve, average_precision_score, PrecisionRecallDisplay

    y_bin = label_binarize(y_true, classes=classes)
    fig, ax = plt.subplots(figsize=(8, 7))

    for i, cls in enumerate(classes):
        precision, recall, _ = precision_recall_curve(y_bin[:, i], y_proba[:, i])
        ap = average_precision_score(y_bin[:, i], y_proba[:, i])

        PrecisionRecallDisplay(
            precision=precision, recall=recall, average_precision=ap,
        ).plot(ax=ax, name=f"{cls} (AP={ap:.2f})", color=CB_COLORS[i])

    ax.set_title("Precision-Recall Curves (One-vs-Rest)")
    ax.legend(loc="lower left")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_report_heatmap(y_true, y_pred, classes, path: Path):
    """Classification report as a colored heatmap."""
    import pandas as pd

    report = classification_report(y_true, y_pred, target_names=classes, output_dict=True)
    rows = {cls: report[cls] for cls in classes}
    df = pd.DataFrame(rows).T[["precision", "recall", "f1-score"]]

    fig, ax = plt.subplots(figsize=(7, 4))
    sns.heatmap(
        df, annot=True, fmt=".3f", cmap="YlGnBu",
        vmin=0.5, vmax=1.0, linewidths=0.5, linecolor="white",
        cbar_kws={"label": "Score", "shrink": 0.8},
        annot_kws={"size": 13, "fontweight": "bold"}, ax=ax,
    )
    ax.set_title("Classification Report")
    ax.set_yticklabels(ax.get_yticklabels(), rotation=0)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def save_plots(y_true, y_pred, y_proba, classes, tmpdir: Path):
    """Generate all 6 evaluation plots."""
    _apply_style()
    _plot_confusion_matrix(y_true, y_pred, classes, tmpdir / "confusion_matrix.png")
    _plot_confidence_histogram(y_true, y_pred, y_proba, classes, tmpdir / "confidence_histogram.png")
    _plot_calibration_curves(y_true, y_proba, classes, tmpdir / "calibration_curves.png")
    _plot_roc_curves(y_true, y_proba, classes, tmpdir / "roc_curves.png")
    _plot_pr_curves(y_true, y_proba, classes, tmpdir / "pr_curves.png")
    _plot_report_heatmap(y_true, y_pred, classes, tmpdir / "classification_report.png")


def save_manifest(metrics, best_params, classes, label_counts, data_path, tmpdir: Path) -> Path:
    """Record everything needed to reproduce this training run."""
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "python_version": platform.python_version(),
        "sklearn_version": __import__("sklearn").__version__,
        "mlflow_version": mlflow.__version__,
        "data_path": str(data_path),
        "data_md5": file_md5(data_path),
        "n_samples": sum(label_counts.values()),
        "class_counts": label_counts,
        "cv_folds": CV_FOLDS,
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "random_state": RANDOM_STATE,
        "best_params": {str(k): str(v) for k, v in best_params.items()},
        "metrics": metrics,
    }
    path = tmpdir / "manifest.json"
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-path", type=Path, default=TRAINING_DATA_PATH)
    args = parser.parse_args()

    texts, labels = load_data(args.data_path)
    classes = sorted(set(labels))
    label_counts = {l: labels.count(l) for l in classes}

    # MLflow setup
    os.environ.setdefault("MLFLOW_TRACKING_URI", f"sqlite:///{Path.cwd() / 'mlruns.db'}")
    mlflow.set_experiment("inkvault-classifier")

    with mlflow.start_run(run_name="train") as run:

        # dataset params
        mlflow.log_params({
            "n_samples": len(texts),
            "n_classes": len(classes),
            "cv_folds": CV_FOLDS,
            "confidence_threshold": CONFIDENCE_THRESHOLD,
            "random_state": RANDOM_STATE,
            "data_md5": file_md5(args.data_path),
        })
        for cls, count in label_counts.items():
            mlflow.log_param(f"n_{cls}", count)

        # grid search
        logger.info("Running grid search (12 combos x %d folds)...", CV_FOLDS)
        search = run_grid_search(texts, labels)
        log_grid_search_runs(search)

        best_pipeline = search.best_estimator_
        mlflow.log_params({f"best_{k}": str(v) for k, v in search.best_params_.items()})
        mlflow.log_metric("best_cv_f1", round(search.best_score_, 4))

        # out-of-fold evaluation using a fresh pipeline with the best params
        logger.info("Running out-of-fold evaluation...")
        eval_pipeline = build_pipeline()
        eval_pipeline.set_params(**search.best_params_)
        y_true, y_pred, y_proba = evaluate_oof(eval_pipeline, texts, labels)

        # refit on all data for the final model
        best_pipeline.fit(texts, labels)
        classes = list(best_pipeline.classes_)

        # metrics
        metrics = compute_metrics(y_true, y_pred, y_proba, classes)
        mlflow.log_metrics(metrics)
        logger.info("macro_f1=%.4f  accuracy=%.4f  coverage=%.1f%%",
                     metrics["macro_f1"], metrics["accuracy"],
                     metrics["coverage_at_threshold"] * 100)

        # artifacts
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # plots
            logger.info("Generating plots...")
            save_plots(y_true, y_pred, y_proba, classes, tmpdir)
            for png in tmpdir.glob("*.png"):
                mlflow.log_artifact(str(png), artifact_path="plots")

            # classification report JSON
            report = classification_report(y_true, y_pred, target_names=classes, output_dict=True)
            report_path = tmpdir / "classification_report.json"
            with open(report_path, "w") as f:
                json.dump(report, f, indent=2)
            mlflow.log_artifact(str(report_path), artifact_path="reports")

            # manifest
            manifest_path = save_manifest(
                metrics, search.best_params_, classes, label_counts, args.data_path, tmpdir
            )
            mlflow.log_artifact(str(manifest_path), artifact_path="reports")

            # joblib fallback for Lambda
            joblib_path = tmpdir / "classifier.joblib"
            joblib.dump(best_pipeline, joblib_path)
            mlflow.log_artifact(str(joblib_path), artifact_path="model_joblib")

        # MLflow model registry
        import pandas as pd
        mlflow.sklearn.log_model(
            sk_model=best_pipeline,
            artifact_path="model",
            registered_model_name="inkvault-document-classifier",
            input_example=pd.DataFrame({"text": texts[:3]}),
            pip_requirements=["scikit-learn", "joblib"],
        )

        logger.info("Run ID: %s", run.info.run_id)
        logger.info("Done. Run 'mlflow ui' to view results.")


if __name__ == "__main__":
    main()
