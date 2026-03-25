"""Generate example invoice PDFs and show extracted text."""

import random
from pathlib import Path

from faker import Faker
from jinja2 import Environment, FileSystemLoader
from pypdf import PdfReader
from weasyprint import HTML

fake = Faker()
Faker.seed(42)
random.seed(42)

TEMPLATES_DIR = Path(__file__).parent / "templates"
OUTPUT_DIR = Path(__file__).parent.parent / "classifier" / "sample_pdfs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

INVOICE_ITEMS_BY_INDUSTRY = {
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


def pick_line_items(industry: str | None = None) -> list[dict]:
    """Generate realistic line items for a given industry."""
    if industry is None:
        industry = random.choice(list(INVOICE_ITEMS_BY_INDUSTRY.keys()))

    items_pool = INVOICE_ITEMS_BY_INDUSTRY[industry]
    num_items = random.randint(2, min(7, len(items_pool)))
    chosen = random.sample(items_pool, num_items)

    line_items = []
    for desc, max_qty, (min_price, max_price) in chosen:
        qty = random.randint(1, max_qty)
        price = round(random.uniform(min_price, max_price), 2)
        line_items.append({
            "description": desc,
            "quantity": qty,
            "unit_price": price,
            "amount": round(qty * price, 2),
        })
    return line_items


def generate_invoice_data(industry: str | None = None) -> dict:
    """Generate realistic invoice field values with Faker."""
    if industry is None:
        industry = random.choice(list(INVOICE_ITEMS_BY_INDUSTRY.keys()))

    line_items = pick_line_items(industry)

    subtotal = round(sum(item["amount"] for item in line_items), 2)
    tax_rate = random.choice([6.0, 7.0, 7.5, 8.0, 8.25, 8.875, 9.0, 10.0])
    tax = round(subtotal * tax_rate / 100, 2)
    shipping = round(random.uniform(0, 50), 2) if random.random() > 0.5 else None
    discount_pct = random.choice([0, 5, 10]) if random.random() > 0.7 else 0
    discount = round(subtotal * discount_pct / 100, 2) if discount_pct else None
    total = subtotal + tax
    if shipping:
        total += shipping
    if discount:
        total -= discount
    total = round(total, 2)

    doc_labels = ["INVOICE", "TAX INVOICE", "STATEMENT", "BILLING STATEMENT", "BILL"]
    number_labels = ["Invoice #", "Ref", "Statement No", "Document #", "Bill #"]

    return {
        "font": random.choice(["Arial, sans-serif", "Georgia, serif", "Courier New, monospace", "Helvetica, sans-serif"]),
        "vendor_name": fake.company(),
        "vendor_address": fake.street_address(),
        "vendor_city": fake.city(),
        "vendor_state": fake.state_abbr(),
        "vendor_zip": fake.zipcode(),
        "vendor_phone": fake.phone_number(),
        "vendor_email": fake.company_email(),
        "vendor_tax_id": fake.ein() if random.random() > 0.3 else None,
        "doc_label": random.choice(doc_labels),
        "doc_number_label": random.choice(number_labels),
        "doc_number": f"{fake.bothify('???').upper()}-{fake.year()}-{fake.numerify('#####')}",
        "doc_date": fake.date_between(start_date="-1y", end_date="today").strftime(
            random.choice(["%m/%d/%Y", "%B %d, %Y", "%d-%b-%Y", "%Y-%m-%d"])
        ),
        "due_date": fake.date_between(start_date="today", end_date="+60d").strftime(
            random.choice(["%m/%d/%Y", "%B %d, %Y", "%d-%b-%Y"])
        ),
        "po_number": fake.bothify("PO-####") if random.random() > 0.5 else None,
        "bill_to_name": fake.name(),
        "bill_to_company": fake.company() if random.random() > 0.4 else None,
        "bill_to_address": fake.street_address(),
        "bill_to_city": fake.city(),
        "bill_to_state": fake.state_abbr(),
        "bill_to_zip": fake.zipcode(),
        "ship_to_name": fake.name() if random.random() > 0.5 else None,
        "ship_to_address": fake.street_address(),
        "ship_to_city": fake.city(),
        "ship_to_state": fake.state_abbr(),
        "ship_to_zip": fake.zipcode(),
        "line_items": line_items,
        "subtotal": subtotal,
        "tax_rate": tax_rate,
        "tax": tax,
        "shipping": shipping,
        "discount_pct": discount_pct,
        "discount": discount,
        "total": total,
        "currency_symbol": "$",
        "payment_terms": random.choice(["Net 30", "Net 15", "Net 45", "Due on Receipt", "Net 60", "2/10 Net 30"]),
        "notes": random.choice([
            "Thank you for your business!",
            "Please remit payment by the due date.",
            "Late payments subject to 1.5% monthly interest.",
            None,
        ]),
        "bank_name": fake.company() + " Bank" if (show_bank := random.random() > 0.5) else None,
        "bank_account": fake.numerify("####-####-####") if show_bank else None,
        "bank_routing": fake.numerify("#########") if show_bank else None,
    }


RECEIPT_ITEMS_BY_TYPE = {
    "grocery": [
        "Organic Bananas (bunch)", "Whole Milk 1 Gallon", "Sourdough Bread Loaf",
        "Free Range Eggs Dozen", "Baby Spinach 5oz", "Chicken Breast 2lb",
        "Cheddar Cheese Block", "Greek Yogurt 32oz", "Avocados (3 pack)",
        "Olive Oil Extra Virgin", "Brown Rice 2lb Bag", "Atlantic Salmon Fillet",
        "Blueberries Pint", "Almond Butter 16oz", "Sparkling Water 12pk",
    ],
    "restaurant": [
        "Grilled Salmon Entree", "Caesar Salad", "French Onion Soup",
        "Glass House Red Wine", "Sparkling Water", "Mushroom Risotto",
        "Tiramisu", "Espresso Double", "Bread Basket", "Side Mixed Greens",
        "Pan Seared Scallops", "Craft IPA Draft", "Cheesecake Slice",
    ],
    "hardware": [
        "2x4 Lumber 8ft", "Drywall Screws 1lb Box", "Interior Latex Paint Gal",
        "Paint Roller Kit 9in", "Masking Tape 2in", "Wood Glue 16oz",
        "Sandpaper 220 Grit 5pk", "LED Bulb 60W 4pk", "Electrical Tape",
        "PVC Pipe 3/4in 10ft", "Copper Fitting 1/2in", "Wire Nuts Assorted",
        "Safety Glasses", "Work Gloves Leather", "Caulk Silicone Clear",
    ],
    "electronics": [
        "USB-C Charging Cable 6ft", "Wireless Mouse", "Screen Protector",
        "Phone Case Clear", "HDMI Cable 4K 3ft", "Bluetooth Speaker",
        "Laptop Stand Aluminum", "Webcam 1080p", "SD Card 128GB",
        "Power Bank 20000mAh", "Keyboard Mechanical", "Mouse Pad XL",
    ],
    "gas_station": [
        "Unleaded Regular", "Unleaded Premium", "Diesel",
    ],
    "pharmacy": [
        "Ibuprofen 200mg 100ct", "Multivitamin Daily 90ct", "Bandages Assorted 30ct",
        "Hand Sanitizer 8oz", "Cough Syrup 8oz", "Allergy Relief 24hr 30ct",
        "First Aid Kit Travel", "Thermometer Digital", "Cold Compress Pack",
        "Prescription Co-Pay", "Sunscreen SPF 50", "Eye Drops Lubricant",
    ],
}

CONTRACT_TYPES = {
    "consulting": {
        "title": "Consulting Services Agreement",
        "type": "Consulting Agreement",
        "party_a_role": "Client",
        "party_b_role": "Consultant",
        "sections": [
            {"title": "Scope of Services", "clauses": [
                "Consultant shall provide the professional consulting services described in Exhibit A attached hereto.",
                "Consultant shall devote sufficient time, attention, and resources to perform the Services in a professional and workmanlike manner.",
                "Any changes to the scope of Services shall require written approval from both parties.",
            ]},
            {"title": "Compensation", "clauses": [
                "Client shall pay Consultant a fee of {rate} per hour for Services rendered.",
                "Consultant shall submit monthly itemized statements detailing hours worked and Services performed.",
                "Payment shall be due within thirty (30) days of receipt of each statement.",
            ]},
            {"title": "Term and Termination", "clauses": [
                "This Agreement shall commence on the Effective Date and continue for a period of {duration}.",
                "Either party may terminate this Agreement upon thirty (30) days prior written notice.",
                "Upon termination, Client shall pay Consultant for all Services performed through the effective date of termination.",
            ]},
            {"title": "Confidentiality", "clauses": [
                "Consultant agrees to maintain in strict confidence all proprietary information disclosed by Client.",
                "This obligation shall survive termination of this Agreement for a period of two (2) years.",
            ]},
            {"title": "Intellectual Property", "clauses": [
                "All work product created by Consultant in the course of performing Services shall be the sole property of Client.",
                "Consultant hereby assigns all rights, title, and interest in such work product to Client.",
            ]},
        ],
    },
    "nda": {
        "title": "Non-Disclosure Agreement",
        "type": "Confidentiality Agreement",
        "party_a_role": "Disclosing Party",
        "party_b_role": "Receiving Party",
        "sections": [
            {"title": "Definition of Confidential Information", "clauses": [
                "Confidential Information means any and all non-public information, whether written, oral, electronic, or visual, disclosed by the Disclosing Party.",
                "Confidential Information includes but is not limited to trade secrets, business plans, financial data, customer lists, technical specifications, and proprietary software.",
                "Confidential Information does not include information that is or becomes publicly available through no fault of the Receiving Party.",
            ]},
            {"title": "Obligations of Receiving Party", "clauses": [
                "The Receiving Party shall use the Confidential Information solely for the purpose of evaluating a potential business relationship.",
                "The Receiving Party shall not disclose the Confidential Information to any third party without prior written consent.",
                "The Receiving Party shall protect the Confidential Information with at least the same degree of care used to protect its own confidential information.",
            ]},
            {"title": "Term", "clauses": [
                "This Agreement shall remain in effect for a period of {duration} from the Effective Date.",
                "The obligations of confidentiality shall survive the expiration or termination of this Agreement for a period of three (3) years.",
            ]},
            {"title": "Return of Materials", "clauses": [
                "Upon written request or termination, the Receiving Party shall promptly return or destroy all Confidential Information and any copies thereof.",
                "The Receiving Party shall certify in writing that all Confidential Information has been returned or destroyed.",
            ]},
        ],
    },
    "employment": {
        "title": "Employment Agreement",
        "type": "Employment Contract",
        "party_a_role": "Employer",
        "party_b_role": "Employee",
        "sections": [
            {"title": "Position and Duties", "clauses": [
                "Employer hereby employs Employee in the position of {job_title}.",
                "Employee shall perform such duties as are customarily associated with the position and as may be assigned from time to time by Employer.",
                "Employee shall devote full-time professional efforts to the performance of duties hereunder.",
            ]},
            {"title": "Compensation and Benefits", "clauses": [
                "Employer shall pay Employee an annual base salary of {salary}, payable in accordance with Employer's standard payroll practices.",
                "Employee shall be eligible to participate in all employee benefit plans and programs generally available to employees of similar status.",
                "Employee shall be entitled to {pto_days} days of paid time off per calendar year.",
            ]},
            {"title": "Term and Termination", "clauses": [
                "Employment under this Agreement shall commence on the Effective Date and shall continue on an at-will basis.",
                "Either party may terminate this Agreement at any time with or without cause upon {notice_period} days written notice.",
                "Upon termination, Employee shall return all company property, documents, and materials.",
            ]},
            {"title": "Non-Compete", "clauses": [
                "During employment and for a period of {noncompete_months} months thereafter, Employee shall not directly or indirectly engage in any business that competes with Employer.",
                "This restriction shall apply within a {noncompete_radius} mile radius of Employer's principal place of business.",
            ]},
        ],
    },
    "service": {
        "title": "Master Service Agreement",
        "type": "Service Agreement",
        "party_a_role": "Client",
        "party_b_role": "Service Provider",
        "sections": [
            {"title": "Services", "clauses": [
                "Service Provider shall provide the services described in one or more Statements of Work executed by the parties.",
                "Each Statement of Work shall describe the specific services, deliverables, timeline, and fees applicable thereto.",
                "Service Provider shall perform all Services in a professional manner consistent with industry standards.",
            ]},
            {"title": "Fees and Payment", "clauses": [
                "Client shall pay Service Provider the fees set forth in the applicable Statement of Work.",
                "Service Provider shall submit monthly statements for Services rendered. Payment shall be due within {payment_days} days of receipt.",
                "Late payments shall accrue interest at the rate of 1.5% per month or the maximum rate permitted by law.",
            ]},
            {"title": "Term", "clauses": [
                "This Agreement shall commence on the Effective Date and continue for an initial term of {duration}.",
                "This Agreement shall automatically renew for successive one-year periods unless either party provides written notice of non-renewal at least sixty (60) days prior to expiration.",
            ]},
            {"title": "Limitation of Liability", "clauses": [
                "In no event shall either party be liable for any indirect, incidental, special, or consequential damages.",
                "The total aggregate liability of Service Provider under this Agreement shall not exceed the total fees paid by Client during the twelve (12) months preceding the claim.",
            ]},
            {"title": "Indemnification", "clauses": [
                "Each party shall indemnify, defend, and hold harmless the other party from any third-party claims arising from its breach of this Agreement.",
                "The indemnifying party shall have sole control of the defense and settlement of any such claim.",
            ]},
        ],
    },
}


def generate_receipt_data(store_type: str | None = None) -> dict:
    """Generate realistic receipt field values with Faker."""
    if store_type is None:
        store_type = random.choice(list(RECEIPT_ITEMS_BY_TYPE.keys()))

    items_pool = RECEIPT_ITEMS_BY_TYPE[store_type]

    if store_type == "gas_station":
        fuel = random.choice(items_pool)
        gallons = round(random.uniform(5, 20), 3)
        ppg = round(random.uniform(2.80, 4.50), 3)
        line_items = [{"description": f"{fuel} {gallons} gal @ ${ppg}/gal", "quantity": 1, "amount": round(gallons * ppg, 2)}]
    else:
        num_items = random.randint(2, min(8, len(items_pool)))
        chosen = random.sample(items_pool, num_items)
        line_items = []
        for desc in chosen:
            qty = random.randint(1, 4)
            price = round(random.uniform(1.50, 65.00), 2)
            line_items.append({"description": desc, "quantity": qty, "amount": round(qty * price, 2)})

    subtotal = round(sum(i["amount"] for i in line_items), 2)
    tax_rate = random.choice([0, 6.0, 6.25, 7.0, 7.5, 8.0, 8.25, 8.875])
    tax = round(subtotal * tax_rate / 100, 2)
    discount = round(random.uniform(1, 5), 2) if random.random() > 0.8 else None
    total = round(subtotal + tax - (discount or 0), 2)

    payment_methods = ["Cash", "Visa", "Mastercard", "Amex", "Debit", "Apple Pay", "Google Pay"]
    method = random.choice(payment_methods)
    is_card = method in ("Visa", "Mastercard", "Amex", "Debit")

    return {
        "font": random.choice(["Courier New, monospace", "Arial, sans-serif", "Lucida Console, monospace"]),
        "store_name": fake.company() if store_type != "gas_station" else fake.company() + " Gas & Mart",
        "store_address": fake.street_address(),
        "store_city": fake.city(),
        "store_state": fake.state_abbr(),
        "store_zip": fake.zipcode(),
        "store_phone": fake.phone_number(),
        "date_label": random.choice(["Date", "Transaction Date", "Sale Date"]),
        "transaction_date": fake.date_between(start_date="-90d", end_date="today").strftime(
            random.choice(["%m/%d/%Y", "%m/%d/%y", "%b %d, %Y"])
        ),
        "transaction_time": fake.time() if random.random() > 0.3 else None,
        "transaction_label": random.choice(["Trans #", "Receipt #", "Order #", "Ref"]),
        "transaction_id": fake.numerify("#######"),
        "cashier": fake.first_name() if random.random() > 0.4 else None,
        "register": fake.numerify("##") if random.random() > 0.5 else None,
        "line_items": line_items,
        "subtotal": subtotal,
        "tax_rate": tax_rate,
        "tax": tax,
        "discount": discount,
        "discount_desc": random.choice(["Member", "Coupon", "Senior", "Staff"]) if discount else None,
        "total": total,
        "currency_symbol": "$",
        "payment_method": method,
        "card_last_four": fake.numerify("####") if is_card else None,
        "auth_code": fake.numerify("######") if is_card else None,
        "change_due": round(random.uniform(0.01, 20.00), 2) if method == "Cash" else None,
        "loyalty_points": random.randint(10, 500) if random.random() > 0.6 else None,
        "loyalty_balance": random.randint(1000, 9999) if random.random() > 0.6 else None,
        "barcode": fake.numerify("#### #### #### ####") if random.random() > 0.5 else None,
        "footer_message": random.choice([
            "THANK YOU FOR SHOPPING WITH US!",
            "Thank you! Please come again.",
            "We appreciate your business!",
            "Have a great day!",
        ]),
        "return_policy": random.choice([
            "Returns accepted within 30 days with receipt.",
            "Exchange or refund within 14 days.",
            "All sales final on clearance items.",
            None,
        ]),
        "website": fake.url() if random.random() > 0.5 else None,
    }


def generate_contract_data(contract_type: str | None = None) -> dict:
    """Generate realistic contract field values with Faker."""
    if contract_type is None:
        contract_type = random.choice(list(CONTRACT_TYPES.keys()))

    template = CONTRACT_TYPES[contract_type]

    rate = f"${random.randint(100, 500)}"
    duration = random.choice(["six (6) months", "one (1) year", "twelve (12) months", "two (2) years", "twenty-four (24) months"])
    salary = f"${random.randint(60, 250) * 1000:,}"
    job_title = fake.job()

    sections = []
    for i, section in enumerate(template["sections"], 1):
        clauses = []
        for clause in section["clauses"]:
            clause = clause.replace("{rate}", rate)
            clause = clause.replace("{duration}", duration)
            clause = clause.replace("{salary}", salary)
            clause = clause.replace("{job_title}", job_title)
            clause = clause.replace("{pto_days}", str(random.randint(10, 25)))
            clause = clause.replace("{notice_period}", str(random.choice([14, 30, 60, 90])))
            clause = clause.replace("{noncompete_months}", str(random.choice([6, 12, 18, 24])))
            clause = clause.replace("{noncompete_radius}", str(random.choice([25, 50, 100])))
            clause = clause.replace("{payment_days}", str(random.choice([15, 30, 45])))
            clauses.append(clause)
        sections.append({"number": i, "title": section["title"], "clauses": clauses})

    recitals = random.choice([
        [
            f"{fake.company()} desires to engage the services of {fake.company()} for professional consulting",
            "The parties wish to set forth the terms and conditions governing such engagement",
        ],
        [
            "The parties have been engaged in discussions regarding a potential business relationship",
            "In connection therewith, the parties may disclose certain confidential and proprietary information",
        ],
        None,
    ])

    exhibits = random.choice([
        ["Exhibit A - Statement of Work", "Exhibit B - Fee Schedule"],
        ["Exhibit A - Scope of Services", "Exhibit B - Payment Schedule", "Exhibit C - Insurance Requirements"],
        ["Schedule A - Compensation Details"],
        None,
    ])

    return {
        "font": random.choice(["Georgia, serif", "Times New Roman, serif", "Garamond, serif", "Arial, sans-serif"]),
        "contract_title": template["title"],
        "contract_type": template["type"],
        "effective_date": fake.date_between(start_date="-60d", end_date="+60d").strftime(
            random.choice(["%B %d, %Y", "%m/%d/%Y", "%d %B %Y"])
        ),
        "party_a_name": fake.company(),
        "party_a_entity_type": random.choice(["Delaware corporation", "New York LLC", "California corporation", "Texas limited partnership", "Florida LLC"]),
        "party_a_address": fake.street_address(),
        "party_a_city": fake.city(),
        "party_a_state": fake.state_abbr(),
        "party_a_zip": fake.zipcode(),
        "party_a_role": template["party_a_role"],
        "party_a_signatory": fake.name(),
        "party_a_title": random.choice(["CEO", "President", "Managing Director", "VP of Operations", "General Counsel"]),
        "party_b_name": fake.company() if contract_type != "employment" else fake.name(),
        "party_b_entity_type": random.choice(["LLC", "sole proprietorship", "corporation", None]) if contract_type != "employment" else None,
        "party_b_address": fake.street_address(),
        "party_b_city": fake.city(),
        "party_b_state": fake.state_abbr(),
        "party_b_zip": fake.zipcode(),
        "party_b_role": template["party_b_role"],
        "party_b_signatory": fake.name(),
        "party_b_title": random.choice(["Owner", "Principal", "Director", "Partner", "Manager"]) if contract_type != "employment" else None,
        "recitals": recitals,
        "sections": sections,
        "exhibits": exhibits,
        "page_count": random.randint(2, 8),
    }


def render_pdf(template_name: str, data: dict, output_path: Path) -> None:
    """Render an HTML template to a PDF file."""
    template = env.get_template(template_name)
    html_content = template.render(**data)
    HTML(string=html_content).write_pdf(str(output_path))


def extract_text(pdf_path: Path) -> str:
    """Extract text from a PDF using pypdf."""
    reader = PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


if __name__ == "__main__":
    for doc_type, gen_func, template in [
        ("invoice", generate_invoice_data, "invoice.html"),
        ("receipt", generate_receipt_data, "receipt.html"),
        ("contract", generate_contract_data, "contract.html"),
    ]:
        data = gen_func()
        pdf_path = OUTPUT_DIR / f"example_{doc_type}.pdf"

        print(f"\n{'='*60}")
        print(f"Generating {doc_type} PDF...")
        render_pdf(template, data, pdf_path)
        print(f"Saved to: {pdf_path}")

        text = extract_text(pdf_path)
        print(f"\n--- Extracted text ({len(text.split())} words) ---\n")
        print(text[:600])
        print("..." if len(text) > 600 else "")
