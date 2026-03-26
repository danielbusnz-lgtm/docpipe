"""Test that all evaluation plots generate without errors.

Run with: uv run pytest tests/test_plots.py -v
Plots saved to: classifier/sample_pdfs/plots/ for visual inspection.
"""

import sys
from pathlib import Path

import numpy as np
import pytest
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_predict, StratifiedKFold
from sklearn.pipeline import Pipeline

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

TRAINING_DATA = Path(__file__).parent.parent / "classifier" / "training_data.json"
PLOT_OUTPUT = Path(__file__).parent.parent / "classifier" / "sample_pdfs" / "plots"


@pytest.fixture(scope="module")
def oof_results():
    """Train a quick model and get OOF predictions for plotting."""
    import json

    if not TRAINING_DATA.exists():
        pytest.skip("training_data.json not found")

    with open(TRAINING_DATA) as f:
        data = json.load(f)

    # use a small subset for speed (1000 samples)
    subset = data[:250] + data[2500:2750] + data[5000:5250] + data[7500:7750]
    texts = [s["text"] for s in subset]
    labels = [s["label"] for s in subset]

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(max_features=3000, ngram_range=(1, 2), sublinear_tf=True)),
        ("clf", LogisticRegression(max_iter=500, random_state=42)),
    ])

    cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)
    y_pred = cross_val_predict(pipeline, texts, labels, cv=cv)
    y_proba = cross_val_predict(pipeline, texts, labels, cv=cv, method="predict_proba")

    # fit on all data so we can get classes_ order
    pipeline.fit(texts, labels)
    classes = list(pipeline.classes_)

    PLOT_OUTPUT.mkdir(parents=True, exist_ok=True)

    return np.array(labels), y_pred, y_proba, classes


class TestPlots:
    def test_confusion_matrix(self, oof_results):
        from train_classifier import _apply_style, _plot_confusion_matrix
        y_true, y_pred, _, classes = oof_results
        _apply_style()
        path = PLOT_OUTPUT / "test_confusion_matrix.png"
        _plot_confusion_matrix(y_true, y_pred, classes, path)
        assert path.exists()
        assert path.stat().st_size > 1000  # not an empty file

    def test_confidence_histogram(self, oof_results):
        from train_classifier import _apply_style, _plot_confidence_histogram
        y_true, y_pred, y_proba, classes = oof_results
        _apply_style()
        path = PLOT_OUTPUT / "test_confidence_histogram.png"
        _plot_confidence_histogram(y_true, y_pred, y_proba, classes, path)
        assert path.exists()
        assert path.stat().st_size > 1000

    def test_calibration_curves(self, oof_results):
        from train_classifier import _apply_style, _plot_calibration_curves
        y_true, _, y_proba, classes = oof_results
        _apply_style()
        path = PLOT_OUTPUT / "test_calibration_curves.png"
        _plot_calibration_curves(y_true, y_proba, classes, path)
        assert path.exists()
        assert path.stat().st_size > 1000

    def test_roc_curves(self, oof_results):
        from train_classifier import _apply_style, _plot_roc_curves
        y_true, _, y_proba, classes = oof_results
        _apply_style()
        path = PLOT_OUTPUT / "test_roc_curves.png"
        _plot_roc_curves(y_true, y_proba, classes, path)
        assert path.exists()
        assert path.stat().st_size > 1000

    def test_pr_curves(self, oof_results):
        from train_classifier import _apply_style, _plot_pr_curves
        y_true, _, y_proba, classes = oof_results
        _apply_style()
        path = PLOT_OUTPUT / "test_pr_curves.png"
        _plot_pr_curves(y_true, y_proba, classes, path)
        assert path.exists()
        assert path.stat().st_size > 1000

    def test_report_heatmap(self, oof_results):
        from train_classifier import _apply_style, _plot_report_heatmap
        y_true, y_pred, _, classes = oof_results
        _apply_style()
        path = PLOT_OUTPUT / "test_classification_report.png"
        _plot_report_heatmap(y_true, y_pred, classes, path)
        assert path.exists()
        assert path.stat().st_size > 1000
