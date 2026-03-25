"""Faker provider for "other" category documents.

Generates utility bills, bank statements, letters, meeting minutes,
HR documents, and delivery notes. These exist so the classifier
has a rejection class for documents that aren't invoices, receipts,
or contracts.
"""

import random

from faker.providers import BaseProvider

from providers.style import generate_style

SUBCATEGORIES = [
    "utility_bill",
    "bank_statement",
    "letter",
    "meeting_minutes",
    "hr_document",
    "delivery_note",
]

UTILITY_TYPES = [
    ("Electric", "kWh", (0.08, 0.25), (300, 2000)),
    ("Gas", "therms", (0.80, 2.50), (20, 150)),
    ("Water", "gallons", (0.003, 0.012), (2000, 12000)),
    ("Sewer", "gallons", (0.005, 0.015), (2000, 12000)),
]

LETTER_SUBJECTS = [
    "Regarding the upcoming changes to your account",
    "Follow-up on our recent conversation",
    "Important update about your membership",
    "Response to your inquiry dated {date}",
    "Notification of policy changes effective {date}",
    "Invitation to the annual general meeting",
    "Acknowledgment of your recent correspondence",
    "Confirmation of your appointment on {date}",
]

MEETING_TOPICS = [
    "Q{q} Budget Review",
    "Product Roadmap Update",
    "Hiring Plan Discussion",
    "Quarterly Business Review",
    "Security Incident Debrief",
    "Office Relocation Planning",
    "Annual Performance Review Process",
    "Vendor Selection for {project}",
]

HR_DOC_TYPES = [
    "offer_letter",
    "policy_update",
    "benefits_summary",
]


class OtherProvider(BaseProvider):
    """Generate documents that don't fit invoice/receipt/contract categories."""

    def other_subcategory(self) -> str:
        return self.random_element(SUBCATEGORIES)

    def utility_bill_data(self) -> dict:
        utility_type, unit, (rate_min, rate_max), (usage_min, usage_max) = self.random_element(UTILITY_TYPES)
        usage = self.random_int(min=usage_min, max=usage_max)
        rate = round(random.uniform(rate_min, rate_max), 4)
        current_charges = round(usage * rate, 2)
        prev_balance = round(random.uniform(0, 200), 2) if random.random() > 0.6 else 0
        payments = prev_balance if prev_balance > 0 and random.random() > 0.3 else 0
        fees = round(random.uniform(2, 15), 2)
        total = round(current_charges + prev_balance - payments + fees, 2)

        billing_start = self.generator.date_between(start_date="-60d", end_date="-30d")
        billing_end = self.generator.date_between(start_date="-30d", end_date="today")

        return {
            "subcategory": "utility_bill",
            "template": "other_utility.html",
            "utility_company": self.generator.company() + f" {utility_type}",
            "utility_type": utility_type,
            "account_number": self.generator.numerify("####-####-####"),
            "service_address": self.generator.address().replace("\n", ", "),
            "customer_name": self.generator.name(),
            "statement_date": self.generator.date_between(start_date="-7d", end_date="today").strftime("%B %d, %Y"),
            "billing_period": f"{billing_start.strftime('%m/%d/%Y')} - {billing_end.strftime('%m/%d/%Y')}",
            "due_date": self.generator.date_between(start_date="+10d", end_date="+30d").strftime("%B %d, %Y"),
            "meter_number": self.generator.numerify("M-########"),
            "usage": usage,
            "unit": unit,
            "rate": rate,
            "current_charges": current_charges,
            "prev_balance": prev_balance,
            "payments": payments,
            "fees": fees,
            "total": total,
            **generate_style(),
        }

    def bank_statement_data(self) -> dict:
        num_transactions = self.random_int(min=8, max=25)
        opening_balance = round(random.uniform(500, 25000), 2)
        balance = opening_balance

        transactions = []
        for _ in range(num_transactions):
            is_debit = random.random() > 0.35
            amount = round(random.uniform(5, 2000), 2)
            if is_debit:
                balance = round(balance - amount, 2)
                desc = self.random_element([
                    "POS Purchase", "ATM Withdrawal", "Online Transfer",
                    "Direct Debit", "Wire Transfer", "Check #" + self.generator.numerify("####"),
                    "ACH Payment", "Bill Pay",
                ]) + " " + self.generator.company()
            else:
                balance = round(balance + amount, 2)
                desc = self.random_element([
                    "Direct Deposit", "ACH Credit", "Wire Transfer In",
                    "Mobile Deposit", "Interest Payment", "Refund",
                ]) + " " + self.generator.company()

            transactions.append({
                "date": self.generator.date_between(start_date="-30d", end_date="today").strftime("%m/%d"),
                "description": desc,
                "debit": f"{amount:.2f}" if is_debit else "",
                "credit": f"{amount:.2f}" if not is_debit else "",
                "balance": f"{balance:.2f}",
            })

        return {
            "subcategory": "bank_statement",
            "template": "other_bank.html",
            "bank_name": self.generator.company() + " Bank",
            "branch_address": self.generator.address().replace("\n", ", "),
            "customer_name": self.generator.name(),
            "customer_address": self.generator.address().replace("\n", ", "),
            "account_number": "****" + self.generator.numerify("####"),
            "account_type": self.random_element(["Checking", "Savings", "Money Market"]),
            "statement_period": f"{self.generator.date_between(start_date='-30d').strftime('%m/%d/%Y')} - {self.generator.date_between(start_date='-3d').strftime('%m/%d/%Y')}",
            "opening_balance": f"{opening_balance:.2f}",
            "closing_balance": f"{balance:.2f}",
            "transactions": transactions,
            **generate_style(),
        }

    def letter_data(self) -> dict:
        date = self.generator.date_between(start_date="-30d", end_date="today")
        subject = self.random_element(LETTER_SUBJECTS).replace(
            "{date}", date.strftime("%B %d, %Y")
        )

        paragraphs = []
        for _ in range(self.random_int(min=2, max=4)):
            paragraphs.append(self.generator.paragraph(nb_sentences=self.random_int(min=3, max=6)))

        return {
            "subcategory": "letter",
            "template": "other_letter.html",
            "sender_name": self.generator.name(),
            "sender_title": self.generator.job(),
            "sender_company": self.generator.company(),
            "sender_address": self.generator.address().replace("\n", ", "),
            "sender_phone": self.generator.phone_number(),
            "sender_email": self.generator.company_email(),
            "date": date.strftime("%B %d, %Y"),
            "recipient_name": self.generator.name(),
            "recipient_title": self.generator.job(),
            "recipient_company": self.generator.company(),
            "recipient_address": self.generator.address().replace("\n", ", "),
            "subject": subject,
            "salutation": self.random_element(["Dear", "Dear Mr.", "Dear Ms.", "Dear Dr."]),
            "paragraphs": paragraphs,
            "closing": self.random_element(["Sincerely,", "Best regards,", "Kind regards,", "Respectfully,"]),
            "cc": [self.generator.name() for _ in range(self.random_int(min=0, max=2))],
            **generate_style(),
        }

    def meeting_minutes_data(self) -> dict:
        topic = self.random_element(MEETING_TOPICS).replace(
            "{q}", str(self.random_int(min=1, max=4))
        ).replace("{project}", self.generator.bs().title())
        attendees = [self.generator.name() for _ in range(self.random_int(min=3, max=8))]
        absent = [self.generator.name() for _ in range(self.random_int(min=0, max=3))]

        agenda_items = []
        for i in range(self.random_int(min=3, max=6)):
            actions = []
            for _ in range(self.random_int(min=0, max=3)):
                actions.append({
                    "task": self.generator.sentence(),
                    "assigned": self.random_element(attendees),
                    "due": self.generator.date_between(start_date="+3d", end_date="+30d").strftime("%m/%d/%Y"),
                })
            agenda_items.append({
                "number": i + 1,
                "title": self.generator.sentence(nb_words=4).rstrip("."),
                "discussion": self.generator.paragraph(nb_sentences=2),
                "actions": actions,
            })

        return {
            "subcategory": "meeting_minutes",
            "template": "other_meeting.html",
            "meeting_title": topic,
            "organization": self.generator.company(),
            "date": self.generator.date_between(start_date="-14d", end_date="today").strftime("%B %d, %Y"),
            "time_start": self.generator.time(pattern="%I:%M %p"),
            "time_end": self.generator.time(pattern="%I:%M %p"),
            "location": self.random_element([
                "Conference Room A", "Board Room", "Zoom Meeting",
                "Teams Call", "Room 201", self.generator.company() + " Office",
            ]),
            "facilitator": self.random_element(attendees),
            "attendees": attendees,
            "absent": absent,
            "agenda_items": agenda_items,
            "next_meeting": self.generator.date_between(start_date="+7d", end_date="+30d").strftime("%B %d, %Y"),
            "prepared_by": self.random_element(attendees),
            **generate_style(),
        }

    def delivery_note_data(self) -> dict:
        num_items = self.random_int(min=2, max=10)
        items = []
        for _ in range(num_items):
            ordered = self.random_int(min=1, max=50)
            shipped = ordered if random.random() > 0.15 else self.random_int(min=1, max=ordered)
            items.append({
                "sku": self.generator.bothify("???-#####").upper(),
                "description": self.generator.catch_phrase(),
                "qty_ordered": ordered,
                "qty_shipped": shipped,
                "backordered": ordered - shipped,
            })

        return {
            "subcategory": "delivery_note",
            "template": "other_delivery.html",
            "company_name": self.generator.company(),
            "company_address": self.generator.address().replace("\n", ", "),
            "company_phone": self.generator.phone_number(),
            "doc_title": self.random_element(["DELIVERY NOTE", "PACKING SLIP", "SHIPPING NOTICE"]),
            "doc_number": self.generator.bothify("DN-####-???").upper(),
            "date": self.generator.date_between(start_date="-14d", end_date="today").strftime("%m/%d/%Y"),
            "order_ref": self.generator.bothify("SO-#####").upper(),
            "ship_to_name": self.generator.name(),
            "ship_to_company": self.generator.company(),
            "ship_to_address": self.generator.address().replace("\n", ", "),
            "carrier": self.random_element(["FedEx", "UPS", "USPS", "DHL", "Freight Carrier"]),
            "tracking": self.generator.numerify("1Z############") if random.random() > 0.3 else None,
            "items": items,
            "notes": self.random_element([
                "Please inspect all items upon delivery.",
                "Contact warehouse for discrepancies.",
                "Signature required upon receipt.",
                None,
            ]),
            **generate_style(),
        }

    def hr_document_data(self) -> dict:
        """Generate an offer letter or policy update."""
        doc_type = self.random_element(HR_DOC_TYPES)

        if doc_type == "offer_letter":
            return {
                "subcategory": "hr_document",
                "template": "other_hr.html",
                "hr_doc_type": "offer_letter",
                "company_name": self.generator.company(),
                "company_address": self.generator.address().replace("\n", ", "),
                "date": self.generator.date_between(start_date="-30d", end_date="today").strftime("%B %d, %Y"),
                "candidate_name": self.generator.name(),
                "candidate_address": self.generator.address().replace("\n", ", "),
                "position": self.generator.job(),
                "department": self.random_element(["Engineering", "Marketing", "Operations", "Finance", "HR", "Sales"]),
                "salary": f"${self.random_int(min=50, max=200) * 1000:,}",
                "start_date": self.generator.date_between(start_date="+14d", end_date="+60d").strftime("%B %d, %Y"),
                "manager": self.generator.name(),
                "benefits": self.random_element([
                    "Medical, dental, and vision insurance; 401(k) with 4% match; 15 days PTO",
                    "Full health coverage; stock options; unlimited PTO; annual bonus",
                    "Health and dental; 10 days PTO; professional development budget",
                ]),
                "signatory_name": self.generator.name(),
                "signatory_title": self.random_element(["VP of People", "HR Director", "Head of Talent"]),
                **generate_style(),
            }
        else:
            return {
                "subcategory": "hr_document",
                "template": "other_hr.html",
                "hr_doc_type": "policy_update",
                "company_name": self.generator.company(),
                "company_address": self.generator.address().replace("\n", ", "),
                "date": self.generator.date_between(start_date="-30d", end_date="today").strftime("%B %d, %Y"),
                "policy_title": self.random_element([
                    "Remote Work Policy Update",
                    "Updated Time Off and Leave Policy",
                    "Revised Code of Conduct",
                    "Information Security Policy",
                    "Travel and Expense Policy Update",
                ]),
                "effective_date": self.generator.date_between(start_date="+7d", end_date="+60d").strftime("%B %d, %Y"),
                "paragraphs": [self.generator.paragraph(nb_sentences=3) for _ in range(3)],
                "signatory_name": self.generator.name(),
                "signatory_title": self.random_element(["VP of People", "HR Director", "Head of Talent", "Chief People Officer"]),
                **generate_style(),
            }

    def other_data(self, subcategory: str | None = None) -> dict:
        """Generate one random 'other' document."""
        if subcategory is None:
            subcategory = self.other_subcategory()

        generators = {
            "utility_bill": self.utility_bill_data,
            "bank_statement": self.bank_statement_data,
            "letter": self.letter_data,
            "meeting_minutes": self.meeting_minutes_data,
            "hr_document": self.hr_document_data,
            "delivery_note": self.delivery_note_data,
        }
        return generators[subcategory]()
