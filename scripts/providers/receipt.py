"""Faker provider for generating realistic receipt data."""

import random

from faker.providers import BaseProvider

from providers.style import generate_style

ITEMS_BY_STORE = {
    "grocery": [
        "Organic Bananas (bunch)", "Whole Milk 1 Gallon", "Sourdough Bread Loaf",
        "Free Range Eggs Dozen", "Baby Spinach 5oz", "Chicken Breast 2lb",
        "Cheddar Cheese Block", "Greek Yogurt 32oz", "Avocados (3 pack)",
        "Olive Oil Extra Virgin", "Brown Rice 2lb Bag", "Atlantic Salmon Fillet",
        "Blueberries Pint", "Almond Butter 16oz", "Sparkling Water 12pk",
        "Whole Wheat Pasta 16oz", "Organic Tomatoes Vine", "Hummus Original 10oz",
    ],
    "restaurant": [
        "Grilled Salmon Entree", "Caesar Salad", "French Onion Soup",
        "Glass House Red Wine", "Sparkling Water", "Mushroom Risotto",
        "Tiramisu", "Espresso Double", "Bread Basket", "Side Mixed Greens",
        "Pan Seared Scallops", "Craft IPA Draft", "Cheesecake Slice",
        "Wagyu Burger", "Lobster Mac and Cheese", "Key Lime Pie",
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
        "Unleaded Regular", "Unleaded Plus", "Unleaded Premium", "Diesel",
    ],
    "pharmacy": [
        "Ibuprofen 200mg 100ct", "Multivitamin Daily 90ct", "Bandages Assorted 30ct",
        "Hand Sanitizer 8oz", "Cough Syrup 8oz", "Allergy Relief 24hr 30ct",
        "First Aid Kit Travel", "Thermometer Digital", "Cold Compress Pack",
        "Prescription Co-Pay", "Sunscreen SPF 50", "Eye Drops Lubricant",
    ],
}

FOOTER_MESSAGES = [
    "THANK YOU FOR SHOPPING WITH US!",
    "Thank you! Please come again.",
    "We appreciate your business!",
    "Have a great day!",
    "See you next time!",
]

RETURN_POLICIES = [
    "Returns accepted within 30 days with receipt.",
    "Exchange or refund within 14 days.",
    "All sales final on clearance items.",
    "Return or exchange within 90 days.",
    None,
    None,
]

RECEIPT_FONTS = ["Courier New, monospace", "Arial, sans-serif", "Lucida Console, monospace"]


class ReceiptProvider(BaseProvider):
    """Generate complete receipt data dicts ready for Jinja2 templates."""

    def receipt_store_type(self) -> str:
        return self.random_element(list(ITEMS_BY_STORE.keys()))

    def receipt_line_items(self, store_type: str | None = None) -> list[dict]:
        """Generate line items appropriate for the store type."""
        if store_type is None:
            store_type = self.receipt_store_type()

        pool = ITEMS_BY_STORE[store_type]

        # gas stations are special: one fuel purchase
        if store_type == "gas_station":
            fuel = self.random_element(pool)
            gallons = round(random.uniform(3, 22), 3)
            ppg = round(random.uniform(2.60, 4.80), 3)
            return [{"description": f"{fuel} {gallons} gal @ ${ppg}/gal", "quantity": 1, "amount": round(gallons * ppg, 2)}]

        count = self.random_int(min=2, max=min(8, len(pool)))
        chosen = random.sample(pool, count)
        items = []
        for desc in chosen:
            qty = self.random_int(min=1, max=4)
            # restaurants are pricier per item than grocery
            if store_type == "restaurant":
                price = round(random.uniform(6.00, 45.00), 2)
            elif store_type == "electronics":
                price = round(random.uniform(8.00, 80.00), 2)
            else:
                price = round(random.uniform(1.50, 65.00), 2)
            items.append({"description": desc, "quantity": qty, "amount": round(qty * price, 2)})
        return items

    def receipt_data(self, store_type: str | None = None) -> dict:
        """Complete receipt dict matching the Jinja2 template variables."""
        if store_type is None:
            store_type = self.receipt_store_type()

        line_items = self.receipt_line_items(store_type)

        subtotal = round(sum(i["amount"] for i in line_items), 2)
        tax_rate = self.random_element([0, 6.0, 6.25, 7.0, 7.5, 8.0, 8.25, 8.875])
        tax = round(subtotal * tax_rate / 100, 2)
        discount = round(random.uniform(1, 5), 2) if random.random() > 0.85 else None
        total = round(subtotal + tax - (discount or 0), 2)

        card_provider = self.generator.credit_card_provider()
        payment_methods = ["Cash", card_provider, "Debit", "Apple Pay", "Google Pay"]
        method = self.random_element(payment_methods)
        is_card = method not in ("Cash", "Apple Pay", "Google Pay")

        store_name = self.generator.company()
        if store_type == "gas_station":
            store_name += " Gas & Mart"

        show_loyalty = random.random() > 0.6

        return {
            "font": self.random_element(RECEIPT_FONTS),
            "store_name": store_name,
            "store_address": self.generator.street_address(),
            "store_city": self.generator.city(),
            "store_state": self.generator.state_abbr(),
            "store_zip": self.generator.postcode(),
            "store_phone": self.generator.phone_number(),
            "date_label": self.random_element(["Date", "Transaction Date", "Sale Date"]),
            "transaction_date": self.generator.date_between(start_date="-90d", end_date="today").strftime(
                self.random_element(["%m/%d/%Y", "%m/%d/%y", "%b %d, %Y"])
            ),
            "transaction_time": self.generator.time() if random.random() > 0.3 else None,
            "transaction_label": self.random_element(["Trans #", "Receipt #", "Order #", "Ref"]),
            "transaction_id": self.generator.numerify("#######"),
            "cashier": self.generator.first_name() if random.random() > 0.4 else None,
            "register": self.generator.numerify("##") if random.random() > 0.5 else None,
            "line_items": line_items,
            "subtotal": subtotal,
            "tax_rate": tax_rate,
            "tax": tax,
            "discount": discount,
            "discount_desc": self.random_element(["Member", "Coupon", "Senior", "Staff"]) if discount else None,
            "total": total,
            "currency_symbol": "$",
            "payment_method": method,
            "card_last_four": self.generator.credit_card_number()[-4:] if is_card else None,
            "auth_code": self.generator.numerify("######") if is_card else None,
            "card_expire": self.generator.credit_card_expire() if is_card else None,
            "change_due": round(random.uniform(0.01, 20.00), 2) if method == "Cash" else None,
            "loyalty_points": self.random_int(min=10, max=500) if show_loyalty else None,
            "loyalty_balance": self.random_int(min=1000, max=9999) if show_loyalty else None,
            "barcode": self.generator.numerify("#### #### #### ####") if random.random() > 0.5 else None,
            "footer_message": self.random_element(FOOTER_MESSAGES),
            "return_policy": self.random_element(RETURN_POLICIES),
            "website": self.generator.url() if random.random() > 0.5 else None,
            **generate_style(),
        }
