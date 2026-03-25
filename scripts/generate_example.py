"""Preview PDFs and their extracted text for each document type.

Usage:
    uv run python scripts/generate_example.py
"""

import sys
from pathlib import Path

# allow imports from scripts/ when run directly
sys.path.insert(0, str(Path(__file__).parent))

from faker import Faker
from jinja2 import Environment, FileSystemLoader
from pypdf import PdfReader
from weasyprint import HTML

from providers.invoice import InvoiceProvider
from providers.receipt import ReceiptProvider
from providers.contract import ContractProvider

fake = Faker("en_US")
fake.add_provider(InvoiceProvider)
fake.add_provider(ReceiptProvider)
fake.add_provider(ContractProvider)

TEMPLATES_DIR = Path(__file__).parent / "templates"
OUTPUT_DIR = Path(__file__).parent.parent / "classifier" / "sample_pdfs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))


def render_pdf(template_name: str, data: dict, output_path: Path) -> None:
    template = env.get_template(template_name)
    html_content = template.render(**data)
    HTML(string=html_content).write_pdf(str(output_path))


def extract_text(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


if __name__ == "__main__":
    for doc_type, gen_method, template in [
        ("invoice", fake.invoice_data, "invoice.html"),
        ("receipt", fake.receipt_data, "receipt.html"),
        ("contract", fake.contract_data, "contract.html"),
    ]:
        data = gen_method()
        pdf_path = OUTPUT_DIR / f"example_{doc_type}.pdf"

        print(f"\n{'='*60}")
        print(f"Generating {doc_type} PDF...")
        render_pdf(template, data, pdf_path)
        print(f"Saved to: {pdf_path}")

        text = extract_text(pdf_path)
        print(f"\n--- Extracted text ({len(text.split())} words) ---\n")
        print(text[:600])
        print("..." if len(text) > 600 else "")
