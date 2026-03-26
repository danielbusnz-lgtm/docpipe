"""Test the Faker data providers produce valid, complete data."""


import pytest


class TestInvoiceProvider:
    def test_returns_all_required_fields(self, fake):
        data = fake.invoice_data()
        required = [
            "vendor_name", "vendor_address", "vendor_city",
            "doc_label", "doc_number", "doc_date", "due_date",
            "bill_to_name", "bill_to_address",
            "line_items", "subtotal", "tax", "total",
            "payment_terms", "currency_symbol",
        ]
        for field in required:
            assert field in data, f"missing field: {field}"

    def test_line_items_have_correct_structure(self, fake):
        data = fake.invoice_data()
        assert len(data["line_items"]) >= 2
        for item in data["line_items"]:
            assert "description" in item
            assert "quantity" in item
            assert "unit_price" in item
            assert "amount" in item
            assert item["quantity"] > 0
            assert item["unit_price"] > 0

    def test_totals_add_up(self, fake):
        data = fake.invoice_data()
        line_total = sum(i["amount"] for i in data["line_items"])
        assert abs(data["subtotal"] - line_total) < 0.01

    def test_vendor_email_matches_company(self, fake):
        data = fake.invoice_data()
        # email should contain some form of the company name
        slug = data["vendor_name"].lower().replace(" ", "").replace(",", "").replace("-", "")[:10]
        assert slug[:5] in data["vendor_email"].lower()

    def test_field_labels_vary(self, fake):
        labels = set()
        for _ in range(20):
            data = fake.invoice_data()
            labels.add(data["bill_to_label"])
        assert len(labels) >= 3, f"only got {labels}, expected more variety"

    def test_industries_vary(self, fake):
        industries = set()
        for _ in range(50):
            industries.add(fake.invoice_industry())
        assert len(industries) >= 5

    def test_style_fields_present(self, fake):
        data = fake.invoice_data()
        style_fields = ["accent_color", "body_font", "table_style", "layout_css"]
        for field in style_fields:
            assert field in data, f"missing style field: {field}"


class TestReceiptProvider:
    def test_returns_all_required_fields(self, fake):
        data = fake.receipt_data()
        required = [
            "store_name", "store_address", "transaction_date",
            "line_items", "subtotal", "total", "payment_method",
        ]
        for field in required:
            assert field in data, f"missing field: {field}"

    def test_gas_station_has_fuel_item(self, fake):
        data = fake.receipt_data(store_type="gas_station")
        assert len(data["line_items"]) == 1
        desc = data["line_items"][0]["description"]
        assert "gal @" in desc

    def test_card_fields_present_for_card_payment(self, fake):
        # keep generating until we get a card payment
        for _ in range(20):
            data = fake.receipt_data()
            if data["payment_method"] not in ("Cash", "Apple Pay", "Google Pay"):
                assert data["card_last_four"] is not None
                assert len(data["card_last_four"]) == 4
                return
        pytest.skip("didn't get a card payment in 20 tries")

    def test_cash_has_change_due(self, fake):
        for _ in range(30):
            data = fake.receipt_data()
            if data["payment_method"] == "Cash":
                assert data["change_due"] is not None
                assert data["change_due"] > 0
                return
        pytest.skip("didn't get cash payment in 30 tries")

    def test_receipt_fonts_favor_monospace(self, fake):
        mono_count = 0
        for _ in range(20):
            data = fake.receipt_data()
            if "Courier" in data["body_font"] or "Console" in data["body_font"]:
                mono_count += 1
        assert mono_count >= 10, "receipts should mostly use monospace"


class TestContractProvider:
    def test_returns_all_required_fields(self, fake):
        data = fake.contract_data()
        required = [
            "contract_title", "contract_type", "effective_date",
            "party_a_name", "party_b_name",
            "party_a_role", "party_b_role",
            "sections",
        ]
        for field in required:
            assert field in data, f"missing field: {field}"

    def test_sections_have_clauses(self, fake):
        data = fake.contract_data()
        assert len(data["sections"]) >= 2
        for section in data["sections"]:
            assert "title" in section
            assert "clauses" in section
            assert len(section["clauses"]) >= 1

    def test_contract_types_vary(self, fake):
        types = set()
        for _ in range(20):
            data = fake.contract_data()
            types.add(data["contract_type"])
        assert len(types) >= 3

    def test_employment_has_person_not_company(self, fake):
        data = fake.contract_data(contract_type="employment")
        # party_b should be a person name, not a company
        assert data["party_b_title"] is None


class TestOtherProvider:
    def test_all_subcategories_work(self, fake):
        for subcat in ["utility_bill", "bank_statement", "letter",
                       "meeting_minutes", "hr_document", "delivery_note"]:
            data = fake.other_data(subcategory=subcat)
            assert "template" in data
            assert "subcategory" in data
            assert data["subcategory"] == subcat

    def test_bank_statement_has_transactions(self, fake):
        data = fake.other_data(subcategory="bank_statement")
        assert len(data["transactions"]) >= 8
        txn = data["transactions"][0]
        assert "date" in txn
        assert "description" in txn

    def test_bank_amounts_have_commas(self, fake):
        data = fake.other_data(subcategory="bank_statement")
        # check that large balances have commas
        balance = data["closing_balance"]
        if float(balance.replace(",", "")) >= 1000:
            assert "," in balance

    def test_utility_bill_fields(self, fake):
        data = fake.other_data(subcategory="utility_bill")
        assert data["total"] > 0
        assert data["usage"] > 0
        assert data["meter_number"].startswith("M-")

    def test_letter_has_paragraphs(self, fake):
        data = fake.other_data(subcategory="letter")
        assert len(data["paragraphs"]) >= 2

    def test_delivery_note_has_no_prices(self, fake):
        data = fake.other_data(subcategory="delivery_note")
        for item in data["items"]:
            assert "price" not in item
            assert "amount" not in item
            assert "qty_shipped" in item
