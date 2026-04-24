"""Document type classification service.

Load the trained TF-IDF + LogisticRegression pipeline and classify
incoming document text. Used by the pipeline processor to route
documents to the correct Claude extraction prompt.

The model is loaded once on first call and cached in memory.
"""

import logging
import re
from pathlib import Path

import joblib

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).parent.parent.parent / "classifier" / "model.joblib"
CONFIDENCE_THRESHOLD = 0.75

_model = None


def _load_model(path: Path = MODEL_PATH):
    """Load the joblib model on first call, cache for subsequent calls."""
    global _model
    if _model is None:
        _model = joblib.load(path)
        logger.info("Loaded classifier from %s", path)
    return _model


def _preprocess(text: str) -> str:
    """Normalize whitespace from messy PDF extraction."""
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text


def classify(text: str, model=None) -> tuple[str, float]:
    """Classify a document's extracted text.

    Returns (doc_type, confidence). If confidence is below the
    threshold or the text is too short, returns ("unknown", score).
    The pipeline processor uses this to decide whether to send the
    document to Claude or flag it for human review.

    Args:
        text: Raw text extracted from a PDF by pypdf.
        model: Optional pre-loaded pipeline, for testing.

    Returns:
        Tuple of (predicted label, confidence score).
    """
    pipeline = model or _load_model()

    # garbage in, unknown out
    clean = _preprocess(text)
    if len(clean.split()) < 10:
        logger.warning("Text too short (%d words), returning unknown", len(clean.split()))
        return "unknown", 0.0

    # check if the vectorizer can extract any known tokens
    tfidf = pipeline.named_steps["tfidf"]
    vector = tfidf.transform([clean])
    if vector.nnz == 0:
        logger.warning("No known tokens in text, returning unknown")
        return "unknown", 0.0

    # predict
    proba = pipeline.predict_proba([clean])[0]
    max_idx = proba.argmax()
    confidence = float(proba[max_idx])
    predicted = pipeline.classes_[max_idx]

    if confidence < CONFIDENCE_THRESHOLD:
        logger.info("Low confidence %.2f for '%s', returning unknown", confidence, predicted)
        return "unknown", confidence

    return predicted, confidence
