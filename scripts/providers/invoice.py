"""Faker provider for generating realistic invoice data."""

import random

from faker.providers import BaseProvider

from providers.style import generate_style

ITEMS_BY_INDUSTRY = {
    "construction": [
        ("Site preparation and excavation", 1, (2000, 15000)),
        ("Concrete formwork supply and install", 1, (3000, 12000)),
        ("Framing lumber package", 1, (1500, 8000)),
        ("Drywall installation per sheet", 50, (12, 25)),
        ("Roofing shingles bundle", 20, (30, 80)),
        ("Electrical rough-in per outlet", 15, (45, 120)),
        ("Plumbing fixture installation", 5, (150, 500)),
        ("HVAC ductwork linear ft", 100, (8, 22)),
        ("Exterior paint labor", 1, (1200, 4500)),
        ("Demolition and debris removal", 1, (800, 3500)),
        ("Foundation waterproofing", 1, (2000, 6000)),
        ("Window installation per unit", 8, (200, 600)),
        ("Flooring tile installation per sqft", 200, (4, 12)),
        ("Permit and inspection fees", 1, (200, 1500)),
    ],
    "legal_services": [
        ("Legal consultation - partner review", 3, (350, 650)),
        ("Contract drafting and review", 5, (250, 450)),
        ("Due diligence research hours", 10, (200, 400)),
        ("Court filing fees", 1, (50, 500)),
        ("Document preparation and filing", 1, (150, 800)),
        ("Mediation session hourly", 4, (300, 600)),
        ("Corporate formation services", 1, (500, 2500)),
        ("Trademark search and filing", 1, (300, 1200)),
        ("Deposition transcript preparation", 1, (200, 600)),
        ("Paralegal research hours", 8, (75, 175)),
    ],
    "retail": [
        ("Office chairs ergonomic model", 10, (120, 450)),
        ("Standing desk adjustable 60in", 5, (350, 800)),
        ("Printer toner cartridge black", 20, (25, 65)),
        ("Copy paper case 10 reams", 10, (35, 55)),
        ("Wireless keyboard and mouse combo", 15, (25, 80)),
        ("Monitor 27in 4K display", 5, (250, 600)),
        ("Desk organizer set", 20, (10, 35)),
        ("Whiteboard 4x6 ft magnetic", 3, (80, 200)),
        ("Filing cabinet 4-drawer", 5, (150, 350)),
        ("Surge protector 8-outlet", 10, (15, 40)),
    ],
    "saas": [
        ("Monthly platform subscription", 1, (500, 5000)),
        ("Additional user licenses (per seat)", 25, (10, 50)),
        ("API usage overage charges", 1, (100, 2000)),
        ("Premium support plan", 1, (200, 1500)),
        ("Data storage addon 100GB", 1, (50, 300)),
        ("SSO/SAML integration setup", 1, (500, 2000)),
        ("Custom integration development hours", 10, (150, 300)),
        ("Annual maintenance and updates", 1, (1000, 5000)),
        ("Onboarding and training session", 1, (500, 2500)),
        ("Dedicated server instance monthly", 1, (200, 800)),
    ],
    "healthcare": [
        ("Patient consultation initial visit", 1, (150, 500)),
        ("X-ray imaging chest PA lateral", 1, (100, 350)),
        ("Laboratory panel CBC comprehensive", 1, (50, 200)),
        ("Physical therapy session 60min", 4, (80, 200)),
        ("Prescription medication dispensing fee", 1, (10, 50)),
        ("Medical supplies sterile dressing kit", 10, (5, 25)),
        ("Ultrasound diagnostic", 1, (200, 600)),
        ("Surgical procedure room fee", 1, (1000, 5000)),
        ("Anesthesia per 15min unit", 4, (100, 300)),
        ("Post-operative follow up visit", 1, (75, 250)),
    ],
    "freight": [
        ("Freight transport LTL 500lbs", 1, (200, 800)),
        ("Full truckload 40ft container", 1, (1500, 5000)),
        ("Fuel surcharge", 1, (50, 300)),
        ("Liftgate delivery service", 1, (50, 150)),
        ("Inside delivery to dock", 1, (75, 200)),
        ("Residential delivery surcharge", 1, (50, 125)),
        ("Customs clearance and brokerage", 1, (100, 500)),
        ("Warehouse storage per pallet per day", 30, (2, 8)),
        ("Packaging and crating service", 1, (50, 300)),
        ("Insurance coverage shipment value", 1, (25, 200)),
    ],
}

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

FONTS = ["Arial, sans-serif", "Georgia, serif", "Courier New, monospace", "Helvetica, sans-serif"]

DATE_FORMATS = ["%m/%d/%Y", "%B %d, %Y", "%d-%b-%Y", "%Y-%m-%d"]


class InvoiceProvider(BaseProvider):
    """Generate complete invoice data dicts ready for Jinja2 templates."""

    def invoice_industry(self) -> str:
        return self.random_element(list(ITEMS_BY_INDUSTRY.keys()))

    def invoice_line_items(self, industry: str | None = None) -> list[dict]:
        """Pick 2-7 items from an industry pool with random qty and price."""
        if industry is None:
            industry = self.invoice_industry()

        pool = ITEMS_BY_INDUSTRY[industry]
        count = self.random_int(min=2, max=min(7, len(pool)))
        chosen = random.sample(pool, count)

        items = []
        for desc, max_qty, (min_price, max_price) in chosen:
            qty = self.random_int(min=1, max=max_qty)
            price = round(random.uniform(min_price, max_price), 2)
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
            "font": self.random_element(FONTS),
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
