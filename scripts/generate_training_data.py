"""Generate training data by rendering synthetic PDFs and extracting text.

Builds invoices, receipts, contracts, and "other" documents as PDFs
using Faker + Jinja2 + WeasyPrint, then extracts text with pypdf.
The extracted text is what the classifier trains on.

Parallelized with ProcessPoolExecutor for speed on multi-core machines.

Usage:
    uv run python scripts/generate_training_data.py
    uv run python scripts/generate_training_data.py --per-class 100  # smaller run
"""

import argparse
import json
import logging
import os
import sys
import tempfile
from pathlib import Path

from tqdm.contrib.concurrent import process_map

# allow imports from scripts/
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"
OUTPUT_PATH = Path(__file__).parent.parent / "classifier" / "training_data.json"


def _setup_faker():
    """Create a Faker instance with all providers registered."""
    from faker import Faker

    from providers.contract import ContractProvider
    from providers.invoice import InvoiceProvider
    from providers.other import OtherProvider
    from providers.receipt import ReceiptProvider

    fake = Faker("en_US")
    fake.add_provider(InvoiceProvider)
    fake.add_provider(ReceiptProvider)
    fake.add_provider(ContractProvider)
    fake.add_provider(OtherProvider)
    return fake


def _generate_tasks(per_class: int) -> list[dict]:
    """Build all data dicts and render HTML strings. Runs in main process."""
    from jinja2 import Environment, FileSystemLoader

    fake = _setup_faker()
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

    tasks = []

    # invoices
    invoice_tpl = env.get_template("invoice.html")
    for i in range(per_class):
        data = fake.invoice_data()
        html = invoice_tpl.render(**data)
        tasks.append({"id": f"inv_{i:04d}", "label": "invoice", "html": html})

    # receipts
    receipt_tpl = env.get_template("receipt.html")
    for i in range(per_class):
        data = fake.receipt_data()
        html = receipt_tpl.render(**data)
        tasks.append({"id": f"rec_{i:04d}", "label": "receipt", "html": html})

    # contracts
    contract_tpl = env.get_template("contract.html")
    for i in range(per_class):
        data = fake.contract_data()
        html = contract_tpl.render(**data)
        tasks.append({"id": f"con_{i:04d}", "label": "contract", "html": html})

    # other (utility bills, bank statements, letters, etc.)
    for i in range(per_class):
        data = fake.other_data()
        tpl = env.get_template(data["template"])
        html = tpl.render(**data)
        tasks.append({"id": f"oth_{i:04d}", "label": "other", "html": html})

    logger.info(
        "Generated %d tasks: %d per class (invoice, receipt, contract, other)",
        len(tasks), per_class,
    )
    return tasks


def _render_and_extract(task: dict) -> dict | None:
    """Render one HTML string to PDF, extract text. Runs in worker process."""
    from pypdf import PdfReader
    from weasyprint import HTML

    try:
        pdf_bytes = HTML(string=task["html"]).write_pdf()

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name

        reader = PdfReader(tmp_path)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        os.unlink(tmp_path)

        if len(text.split()) < 10:
            return None

        return {
            "id": task["id"],
            "label": task["label"],
            "text": text,
        }
    except Exception as e:
        logger.warning("Failed to render %s: %s", task["id"], e)
        return None


def _render_and_ocr(task: dict) -> dict | None:
    """Render HTML to PDF, convert to image, OCR with Tesseract.

    Produces the messy text a real scanned document would have.
    Trained alongside pypdf text so the classifier handles both.
    """
    import cv2
    import numpy as np
    import pytesseract
    from pdf2image import convert_from_path
    from weasyprint import HTML

    try:
        pdf_bytes = HTML(string=task["html"]).write_pdf()

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name

        # PDF -> image at 200 DPI
        images = convert_from_path(tmp_path, dpi=200, first_page=1, last_page=1)
        os.unlink(tmp_path)

        if not images:
            return None

        # preprocess: grayscale + binarize (Otsu)
        img = np.array(images[0])
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # OCR
        text = pytesseract.image_to_string(thresh, config="--oem 3 --psm 6")

        if len(text.split()) < 10:
            return None

        return {
            "id": task["id"] + "_ocr",
            "label": task["label"],
            "text": text,
        }
    except Exception as e:
        logger.warning("Failed OCR for %s: %s", task["id"], e)
        return None


def main():
    parser = argparse.ArgumentParser(description="Generate classifier training data")
    parser.add_argument("--per-class", type=int, default=500, help="Samples per document class")
    parser.add_argument("--workers", type=int, default=max(1, os.cpu_count() - 4), help="Parallel workers")
    parser.add_argument("--ocr-ratio", type=float, default=0.0,
                        help="Fraction of samples to also generate as OCR text (0.0 to 1.0)")
    args = parser.parse_args()

    logger.info("Generating %d samples per class with %d workers", args.per_class, args.workers)

    # step 1: generate data + render HTML (fast, main process)
    tasks = _generate_tasks(args.per_class)

    # step 2: render PDFs + extract text with pypdf (parallel)
    results = process_map(
        _render_and_extract,
        tasks,
        max_workers=args.workers,
        chunksize=10,
        desc="Rendering PDFs",
    )

    samples = [r for r in results if r is not None]
    logger.info("pypdf extraction: %d samples", len(samples))

    # step 3: optionally also OCR a subset (much slower, ~2-3x per doc)
    if args.ocr_ratio > 0:
        import random
        ocr_count = int(len(tasks) * args.ocr_ratio)
        ocr_tasks = random.sample(tasks, ocr_count)
        logger.info("Running OCR on %d samples (%.0f%%)...", ocr_count, args.ocr_ratio * 100)

        ocr_results = process_map(
            _render_and_ocr,
            ocr_tasks,
            max_workers=max(1, args.workers // 2),  # OCR is heavier, fewer workers
            chunksize=5,
            desc="OCR extraction",
        )
        ocr_samples = [r for r in ocr_results if r is not None]
        logger.info("OCR extraction: %d samples", len(ocr_samples))
        samples.extend(ocr_samples)

    # step 4: save
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(samples, f)

    label_counts = {}
    for s in samples:
        label_counts[s["label"]] = label_counts.get(s["label"], 0) + 1

    logger.info("Saved %d samples to %s", len(samples), OUTPUT_PATH)
    logger.info("Per class: %s", label_counts)
    failed = len(tasks) - len([r for r in results if r is not None])
    if failed:
        logger.warning("%d samples failed to render", failed)


if __name__ == "__main__":
    main()
