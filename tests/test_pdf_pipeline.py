"""Test the full PDF generation and text extraction pipeline."""

import re
import sys
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader
from pypdf import PdfReader
from weasyprint import HTML

TEMPLATES_DIR = Path(__file__).parent.parent / "scripts" / "templates"
env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))


def _render_and_extract(template_name: str, data: dict) -> str:
    """Render a template to PDF in memory, extract text."""
    template = env.get_template(template_name)
    html = template.render(**data)
    pdf_bytes = HTML(string=html).write_pdf()

    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(pdf_bytes)
        tmp = f.name
    reader = PdfReader(tmp)
    text = "\n".join(p.extract_text() or "" for p in reader.pages)
    os.unlink(tmp)
    return text


class TestInvoicePDF:
    def test_renders_without_error(self, fake):
        data = fake.invoice_data()
        text = _render_and_extract("invoice.html", data)
        assert len(text) > 50

    def test_contains_vendor_name(self, fake):
        data = fake.invoice_data()
        text = _render_and_extract("invoice.html", data)
        # vendor name might get split across lines by pypdf
        first_word = data["vendor_name"].split()[0]
        assert first_word in text

    def test_contains_dollar_amounts(self, fake):
        data = fake.invoice_data()
        text = _render_and_extract("invoice.html", data)
        amounts = re.findall(r'\$[\d,.]+', text)
        assert len(amounts) >= 2, "should have at least subtotal and total"

    def test_large_amounts_have_commas(self, fake):
        # generate until we get a large total
        for _ in range(10):
            data = fake.invoice_data()
            if data["total"] >= 1000:
                text = _render_and_extract("invoice.html", data)
                # find the total in extracted text
                amounts = re.findall(r'\$[\d,.]+', text)
                big_amounts = [a for a in amounts if float(a.replace("$","").replace(",","")) >= 1000]
                assert any("," in a for a in big_amounts), f"no commas in big amounts: {big_amounts}"
                return
        pytest.skip("no large totals generated")

    def test_all_layouts_render(self, fake):
        from providers.style import INVOICE_LAYOUTS
        for layout_name, layout_css in INVOICE_LAYOUTS.items():
            data = fake.invoice_data()
            data["layout_css"] = layout_css
            text = _render_and_extract("invoice.html", data)
            assert len(text) > 50, f"layout {layout_name} produced empty text"


class TestReceiptPDF:
    def test_renders_without_error(self, fake):
        data = fake.receipt_data()
        text = _render_and_extract("receipt.html", data)
        assert len(text) > 30

    def test_contains_store_name(self, fake):
        data = fake.receipt_data()
        text = _render_and_extract("receipt.html", data)
        first_word = data["store_name"].split()[0]
        assert first_word in text

    def test_gas_station_shows_gallons(self, fake):
        data = fake.receipt_data(store_type="gas_station")
        text = _render_and_extract("receipt.html", data)
        assert "gal" in text.lower()


class TestContractPDF:
    def test_renders_without_error(self, fake):
        data = fake.contract_data()
        text = _render_and_extract("contract.html", data)
        assert len(text) > 100

    def test_contains_party_names(self, fake):
        data = fake.contract_data()
        text = _render_and_extract("contract.html", data)
        first_word_a = data["party_a_name"].split()[0]
        assert first_word_a in text

    def test_contains_legal_language(self, fake):
        data = fake.contract_data()
        text = _render_and_extract("contract.html", data)
        legal_terms = ["agreement", "party", "shall", "effective date"]
        found = sum(1 for t in legal_terms if t.lower() in text.lower())
        assert found >= 2, "contract should contain legal terminology"


class TestOtherPDFs:
    @pytest.mark.parametrize("subcat", [
        "utility_bill", "bank_statement", "letter",
        "meeting_minutes", "hr_document", "delivery_note",
    ])
    def test_renders_without_error(self, fake, subcat):
        data = fake.other_data(subcategory=subcat)
        text = _render_and_extract(data["template"], data)
        assert len(text) > 30, f"{subcat} produced too little text"
