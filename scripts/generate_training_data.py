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

        # skip if extraction produced almost nothing
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


def main():
    parser = argparse.ArgumentParser(description="Generate classifier training data")
    parser.add_argument("--per-class", type=int, default=500, help="Samples per document class")
    parser.add_argument("--workers", type=int, default=max(1, os.cpu_count() - 4), help="Parallel workers")
    args = parser.parse_args()

    logger.info("Generating %d samples per class with %d workers", args.per_class, args.workers)

    # step 1: generate data + render HTML (fast, main process)
    tasks = _generate_tasks(args.per_class)

    # step 2: render PDFs + extract text (slow, parallel)
    results = process_map(
        _render_and_extract,
        tasks,
        max_workers=args.workers,
        chunksize=10,
        desc="Rendering PDFs",
    )

    # step 3: filter out failures and save
    samples = [r for r in results if r is not None]
    failed = len(tasks) - len(samples)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(samples, f, indent=2)

    # summary
    label_counts = {}
    for s in samples:
        label_counts[s["label"]] = label_counts.get(s["label"], 0) + 1

    logger.info("Saved %d samples to %s", len(samples), OUTPUT_PATH)
    logger.info("Per class: %s", label_counts)
    if failed:
        logger.warning("%d samples failed to render", failed)


if __name__ == "__main__":
    main()
