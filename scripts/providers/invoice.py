"""Faker provider for generating realistic invoice data."""

import json
import random
from pathlib import Path

from faker.providers import BaseProvider

from providers.style import generate_style

VOCAB_PATH = Path(__file__).parent.parent.parent / "classifier" / "vocab" / "items.json"

# price ranges (min, max) and qty ranges (min, max) per category
CATEGORY_PRICING = {
    "construction": {"price": (50, 15000), "qty": (1, 20)},
    "legal_services": {"price": (75, 650), "qty": (1, 10)},
    "retail": {"price": (10, 800), "qty": (1, 50)},
    "office": {"price": (5, 500), "qty": (1, 30)},
    "saas": {"price": (10, 5000), "qty": (1, 25)},
    "cloud_services": {"price": (0.50, 3000), "qty": (1, 1)},
    "healthcare": {"price": (5, 5000), "qty": (1, 10)},
    "freight": {"price": (25, 5000), "qty": (1, 5)},
    "technology": {"price": (50, 2000), "qty": (1, 20)},
    "services": {"price": (100, 3000), "qty": (1, 10)},
    "manufacturing": {"price": (200, 10000), "qty": (1, 5)},
    "hardware": {"price": (5, 500), "qty": (1, 25)},
    "hospitality": {"price": (20, 2000), "qty": (1, 10)},
}

# loaded once on first use
_vocab_cache: dict | None = None


def _load_vocab() -> dict[str, list[str]]:
    global _vocab_cache
    if _vocab_cache is None:
        with open(VOCAB_PATH) as f:
            _vocab_cache = json.load(f)
        # exclude grocery_receipt (that's for receipts, not invoices)
        _vocab_cache.pop("grocery_receipt", None)
    return _vocab_cache


DOC_LABELS = ["INVOICE", "TAX INVOICE", "STATEMENT", "BILLING STATEMENT", "BILL"]

NUMBER_FORMATS = [
    "INV-{year}{month}-{seq}",
    "{prefix}-{year}-{seq}",
    "#{seq}",
    "{prefix}{seq}",
]

PAYMENT_TERMS = ["Net 30", "Net 15", "Net 45", "Due on Receipt", "Net 60", "2/10 Net 30"]

NOTES = [
    "Thank you for your business!",
    "Please remit payment by the due date.",
    "Late payments subject to 1.5% monthly interest.",
    "Questions? Contact our billing department.",
    None,
    None,
]

DATE_FORMATS = ["%m/%d/%Y", "%B %d, %Y", "%d-%b-%Y", "%Y-%m-%d"]


class InvoiceProvider(BaseProvider):
    """Generate complete invoice data dicts ready for Jinja2 templates."""

    def invoice_industry(self) -> str:
        vocab = _load_vocab()
        return self.random_element(list(vocab.keys()))

    def invoice_line_items(self, industry: str | None = None) -> list[dict]:
        """Pick 2-7 items from an industry pool with random qty and price."""
        vocab = _load_vocab()
        if industry is None:
            industry = self.invoice_industry()

        pool = vocab.get(industry, vocab["services"])
        pricing = CATEGORY_PRICING.get(industry, {"price": (10, 1000), "qty": (1, 10)})
        count = self.random_int(min=2, max=min(7, len(pool)))
        chosen = random.sample(pool, count)

        items = []
        for desc in chosen:
            qty = self.random_int(min=pricing["qty"][0], max=pricing["qty"][1])
            price = round(random.uniform(*pricing["price"]), 2)
            items.append({
                "description": desc,
                "quantity": qty,
                "unit_price": price,
                "amount": round(qty * price, 2),
            })
        return items

    def invoice_number(self) -> str:
        """Date-prefixed invoice number like INV-202503-0042."""
        date = self.generator.date_between(start_date="-1y", end_date="today")
        fmt = self.random_element(NUMBER_FORMATS)
        return fmt.format(
            year=date.strftime("%Y"),
            month=date.strftime("%m"),
            prefix=self.generator.lexify("???").upper(),
            seq=str(self.random_int(min=1, max=99999)).zfill(5),
        )

    def _vendor_email(self, company_name: str) -> str:
        """billing@companyname.com instead of random garbage."""
        slug = company_name.lower().replace(" ", "").replace(",", "").replace("-", "")[:20]
        domain = self.random_element(["com", "net", "co", "io"])
        prefix = self.random_element(["billing", "accounts", "invoices", "ar", "finance"])
        return f"{prefix}@{slug}.{domain}"

    def invoice_data(self, industry: str | None = None) -> dict:
        """Complete invoice dict matching the Jinja2 template variables."""
        if industry is None:
            industry = self.invoice_industry()

        line_items = self.invoice_line_items(industry)
        vendor_name = self.generator.company()

        subtotal = round(sum(i["amount"] for i in line_items), 2)
        tax_rate = self.random_element([6.0, 7.0, 7.5, 8.0, 8.25, 8.875, 9.0, 10.0])
        tax = round(subtotal * tax_rate / 100, 2)
        shipping = round(random.uniform(5, 50), 2) if random.random() > 0.5 else None
        discount_pct = self.random_element([5, 10]) if random.random() > 0.8 else 0
        discount = round(subtotal * discount_pct / 100, 2) if discount_pct else None
        total = round(subtotal + tax + (shipping or 0) - (discount or 0), 2)

        invoice_date = self.generator.date_between(start_date="-1y", end_date="today")
        show_bank = random.random() > 0.5

        return {
            "vendor_name": vendor_name,
            "vendor_address": self.generator.street_address(),
            "vendor_city": self.generator.city(),
            "vendor_state": self.generator.state_abbr(),
            "vendor_zip": self.generator.postcode(),
            "vendor_phone": self.generator.phone_number(),
            "vendor_email": self._vendor_email(vendor_name),
            "vendor_tax_id": self.generator.ein() if random.random() > 0.3 else None,
            "doc_label": self.random_element(DOC_LABELS),
            "doc_number_label": self.random_element(["Invoice #", "Ref", "Statement No", "Document #", "Bill #"]),
            "doc_number": self.invoice_number(),
            "doc_date": invoice_date.strftime(self.random_element(DATE_FORMATS)),
            "due_date": self.generator.date_between(
                start_date=invoice_date, end_date="+90d"
            ).strftime(self.random_element(DATE_FORMATS)),
            "po_number": self.generator.bothify("PO-####") if random.random() > 0.5 else None,
            "bill_to_name": self.generator.name(),
            "bill_to_company": self.generator.company() if random.random() > 0.4 else None,
            "bill_to_address": self.generator.street_address(),
            "bill_to_city": self.generator.city(),
            "bill_to_state": self.generator.state_abbr(),
            "bill_to_zip": self.generator.postcode(),
            "ship_to_name": self.generator.name() if random.random() > 0.5 else None,
            "ship_to_address": self.generator.street_address(),
            "ship_to_city": self.generator.city(),
            "ship_to_state": self.generator.state_abbr(),
            "ship_to_zip": self.generator.postcode(),
            "line_items": line_items,
            "subtotal": subtotal,
            "tax_rate": tax_rate,
            "tax": tax,
            "shipping": shipping,
            "discount_pct": discount_pct,
            "discount": discount,
            "total": total,
            "currency_symbol": "$",
            "payment_terms": self.random_element(PAYMENT_TERMS),
            "notes": self.random_element(NOTES),
            "bank_name": self.generator.company() + " Bank" if show_bank else None,
            "bank_account": self.generator.iban() if show_bank else None,
            "bank_routing": self.generator.aba() if show_bank else None,
            **generate_style(),
        }
