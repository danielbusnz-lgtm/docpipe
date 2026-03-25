"""Random CSS style generation for visual diversity in synthetic PDFs.

Every document gets a different combination of colors, fonts, spacing,
and table styles so the classifier can't overfit on one visual layout.
"""

import random

# curated palettes that look like real business documents, not random RGB noise
ACCENT_COLORS = [
    "#1a1a2e", "#2c3e50", "#34495e", "#1b4f72", "#0b5345",
    "#4a235a", "#7b241c", "#1e8449", "#2471a3", "#6c3483",
    "#17202a", "#1c2833", "#0e6251", "#784212", "#1a5276",
    "#922b21", "#0d6efd", "#198754", "#dc3545", "#6610f2",
]

BACKGROUND_COLORS = [
    "#ffffff", "#ffffff", "#ffffff",  # most docs are white
    "#fafafa", "#f8f9fa", "#f5f5f0", "#fffef5", "#f0f4f8",
]

FONT_STACKS = [
    "Arial, Helvetica, sans-serif",
    "Georgia, 'Times New Roman', serif",
    "'Courier New', Courier, monospace",
    "Helvetica, Arial, sans-serif",
    "'Trebuchet MS', sans-serif",
    "Verdana, Geneva, sans-serif",
    "'Palatino Linotype', 'Book Antiqua', serif",
]

TABLE_STYLES = ["bordered", "zebra", "minimal", "clean"]

# CSS Grid layouts for invoices. Same HTML sections, rearranged visually.
# Each string is injected as an inline style on the root grid container.
INVOICE_LAYOUTS = {
    "classic": """
        display: grid;
        grid-template-columns: 1fr 1fr;
        grid-template-areas:
            "header   meta"
            "billing  shipping"
            "items    items"
            "totals   totals"
            "terms    terms"
            "footer   footer";
        gap: 20px;
    """,
    "sidebar": """
        display: grid;
        grid-template-columns: 220px 1fr;
        grid-template-areas:
            "header   items"
            "meta     items"
            "billing  items"
            "shipping totals"
            "terms    terms"
            "footer   footer";
        gap: 16px;
    """,
    "single_col": """
        display: grid;
        grid-template-columns: 1fr;
        grid-template-areas:
            "header"
            "meta"
            "billing"
            "shipping"
            "items"
            "totals"
            "terms"
            "footer";
        gap: 14px;
    """,
    "modern": """
        display: grid;
        grid-template-columns: 1fr 280px;
        grid-template-areas:
            "header   header"
            "items    meta"
            "items    billing"
            "items    shipping"
            "totals   totals"
            "terms    terms"
            "footer   footer";
        gap: 20px;
    """,
}


def generate_style() -> dict:
    """Return a dict of randomized CSS values for one document.

    Meant to be merged into the template context alongside field data.
    Templates reference these as {{ accent_color }}, {{ body_font }}, etc.
    """
    accent = random.choice(ACCENT_COLORS)
    table_style = random.choice(TABLE_STYLES)

    return {
        # colors
        "accent_color": accent,
        "bg_color": random.choice(BACKGROUND_COLORS),
        "text_color": random.choice(["#222", "#333", "#111", "#2c2c2c"]),
        "muted_color": random.choice(["#666", "#777", "#888", "#555"]),

        # fonts
        "body_font": random.choice(FONT_STACKS),
        "body_font_size": f"{random.choice([9, 9.5, 10, 10.5, 11])}pt",
        "heading_font_size": f"{random.randint(14, 22)}pt",
        "small_font_size": f"{random.choice([7, 7.5, 8, 8.5])}pt",

        # spacing
        "page_margin": f"{random.choice([1.5, 2, 2.5, 3])}cm",
        "cell_padding": f"{random.randint(5, 10)}px {random.randint(8, 14)}px",
        "section_gap": f"{random.randint(15, 30)}px",

        # table look
        "table_style": table_style,
        "table_header_bg": accent,
        "table_header_text": "#ffffff",
        "table_border_color": random.choice(["#ddd", "#ccc", "#eee", "#bbb", accent]),
        "table_stripe_color": random.choice(["#f8f8f8", "#f2f2f2", "#f5f5f5", "#fafafa"]),

        # borders
        "border_radius": f"{random.choice([0, 0, 2, 4, 6])}px",
        "header_border": random.choice([
            f"2px solid {accent}",
            f"1px solid #ddd",
            f"3px solid {accent}",
            "none",
        ]),

        # layout toggles
        "header_align": random.choice(["left", "left", "center"]),  # left is more common
        "totals_width": f"{random.randint(35, 50)}%",

        # grid layout (invoice only, receipts/contracts ignore this)
        "layout_name": (ln := random.choice(list(INVOICE_LAYOUTS.keys()))),
        "layout_css": INVOICE_LAYOUTS[ln],
    }
