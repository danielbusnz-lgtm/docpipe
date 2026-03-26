"""Statistical and quality tests for the generated training data.

These go beyond "does it render" and check whether the data
is actually good enough to train a classifier on.
"""

import json
import re
from pathlib import Path

import pytest

TRAINING_DATA_PATH = Path(__file__).parent.parent / "classifier" / "training_data.json"


@pytest.fixture(scope="module")
def training_data():
    """Load the full training dataset. Skip if it hasn't been generated yet."""
    if not TRAINING_DATA_PATH.exists():
        pytest.skip("training_data.json not found, run generate_training_data.py first")
    with open(TRAINING_DATA_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def texts_by_label(training_data):
    """Group extracted text by label."""
    grouped = {}
    for sample in training_data:
        label = sample["label"]
        if label not in grouped:
            grouped[label] = []
        grouped[label].append(sample["text"])
    return grouped


def _tokenize(text: str) -> set[str]:
    """Lowercase split, drop short tokens and pure numbers."""
    return {
        w for w in text.lower().split()
        if len(w) > 2 and not w.replace(".", "").replace(",", "").isdigit()
    }


# --- 1. Near-duplicate detection ---

class TestNearDuplicates:
    def test_no_exact_duplicates(self, training_data):
        texts = [s["text"] for s in training_data]
        assert len(set(texts)) == len(texts), "found exact duplicate texts"

    def test_no_near_duplicates_in_sample(self, training_data):
        """Check 200 random pairs per class for suspiciously high similarity."""
        import random
        random.seed(42)

        for label in ["invoice", "receipt", "contract", "other"]:
            samples = [s["text"] for s in training_data if s["label"] == label]
            pairs_checked = 0
            near_dupes = 0

            for _ in range(200):
                a, b = random.sample(samples, 2)
                tokens_a = _tokenize(a)
                tokens_b = _tokenize(b)
                if not tokens_a or not tokens_b:
                    continue
                jaccard = len(tokens_a & tokens_b) / len(tokens_a | tokens_b)
                if jaccard > 0.85:
                    near_dupes += 1
                pairs_checked += 1

            pct = near_dupes / max(pairs_checked, 1) * 100
            assert pct < 5, f"{label}: {pct:.1f}% near-duplicate pairs (threshold 5%)"


# --- 2. Vocabulary diversity ---

class TestVocabularyDiversity:
    def test_minimum_unique_tokens_per_class(self, texts_by_label):
        """Each class should use a broad vocabulary, not the same 50 words."""
        for label, texts in texts_by_label.items():
            all_tokens = set()
            for text in texts[:500]:  # sample 500 to keep it fast
                all_tokens.update(_tokenize(text))
            # contracts have legal boilerplate so lower threshold
            min_expected = 200 if label == "contract" else 300
            assert len(all_tokens) >= min_expected, (
                f"{label}: only {len(all_tokens)} unique tokens, expected >= {min_expected}"
            )

    def test_vocabulary_grows_with_samples(self, texts_by_label):
        """Adding more samples should keep adding new words, not plateau immediately."""
        for label, texts in texts_by_label.items():
            tokens_at_100 = set()
            for text in texts[:100]:
                tokens_at_100.update(_tokenize(text))

            tokens_at_500 = set(tokens_at_100)
            for text in texts[100:500]:
                tokens_at_500.update(_tokenize(text))

            growth = len(tokens_at_500) / max(len(tokens_at_100), 1)
            assert growth >= 1.15, (
                f"{label}: vocab only grew {growth:.2f}x from 100 to 500 samples, "
                "data might be too repetitive"
            )


# --- 3. Token overlap between classes ---

class TestInterClassSeparation:
    def test_classes_have_distinct_vocabulary(self, texts_by_label):
        """Invoice and receipt vocab should overlap but not be identical."""
        vocabs = {}
        for label, texts in texts_by_label.items():
            tokens = set()
            for text in texts[:500]:
                tokens.update(_tokenize(text))
            vocabs[label] = tokens

        pairs = [
            ("invoice", "receipt"),
            ("invoice", "contract"),
            ("receipt", "contract"),
            ("invoice", "other"),
        ]
        for a, b in pairs:
            overlap = len(vocabs[a] & vocabs[b])
            union = len(vocabs[a] | vocabs[b])
            jaccard = overlap / max(union, 1)
            # classes should share some common English but not be too similar
            assert jaccard < 0.70, (
                f"{a} vs {b}: Jaccard similarity {jaccard:.2f}, "
                "vocabulary is too similar for the classifier to distinguish"
            )


# --- 4. Temporal consistency ---

class TestTemporalConsistency:
    def test_invoice_due_date_after_doc_date(self, fake):
        """Due date should not come before the invoice date."""
        from datetime import datetime

        formats = ["%m/%d/%Y", "%B %d, %Y", "%d-%b-%Y", "%Y-%m-%d"]

        def try_parse(date_str):
            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            return None

        violations = 0
        for _ in range(100):
            data = fake.invoice_data()
            doc = try_parse(data["doc_date"])
            due = try_parse(data["due_date"])
            if doc and due and due < doc:
                violations += 1

        assert violations < 5, f"{violations}/100 invoices have due date before doc date"


# --- 5. Document length distribution ---

class TestLengthDistribution:
    def test_lengths_vary_within_class(self, texts_by_label):
        """Text lengths should not all be the same."""
        for label, texts in texts_by_label.items():
            lengths = [len(t.split()) for t in texts[:500]]
            avg = sum(lengths) / len(lengths)
            std = (sum((x - avg) ** 2 for x in lengths) / len(lengths)) ** 0.5
            cv = std / max(avg, 1)  # coefficient of variation
            assert cv > 0.05, (
                f"{label}: coefficient of variation {cv:.3f}, "
                "text lengths are too uniform"
            )

    def test_no_extremely_short_documents(self, texts_by_label):
        for label, texts in texts_by_label.items():
            short = [t for t in texts if len(t.split()) < 10]
            assert len(short) == 0, f"{label}: {len(short)} docs under 10 words"


# --- 6. Amount distribution ---

class TestAmountDistribution:
    def test_invoice_totals_spread_realistically(self, training_data):
        """Totals should span a wide range, not cluster around one value."""
        invoices = [s for s in training_data if s["label"] == "invoice"]
        amounts = []
        for s in invoices[:500]:
            matches = re.findall(r'\$[\d,.]+', s["text"])
            if matches:
                # grab the last dollar amount (usually the total)
                last = matches[-1].replace("$", "").replace(",", "")
                try:
                    amounts.append(float(last))
                except ValueError:
                    pass

        assert len(amounts) >= 400, "couldn't extract enough amounts"
        mn, mx = min(amounts), max(amounts)
        spread = mx / max(mn, 0.01)
        assert spread >= 10, (
            f"invoice totals range ${mn:.0f} to ${mx:.0f}, "
            f"spread ratio {spread:.1f}x is too narrow"
        )


# --- 7. Encoding and character quality ---

class TestEncodingQuality:
    def test_no_garbled_unicode(self, training_data):
        """Check for common encoding artifacts in extracted text."""
        bad_patterns = [
            "\ufffd",           # replacement character
            "\xc3\xa2\xc2\x80",  # mangled UTF-8 sequences
            "(cid:",            # PDF CID encoding leak
        ]
        issues = 0
        for s in training_data[:1000]:
            for pattern in bad_patterns:
                if pattern in s["text"]:
                    issues += 1
                    break

        assert issues < 5, f"{issues}/1000 samples have encoding artifacts"

    def test_text_is_printable(self, training_data):
        """Extracted text should be mostly printable ASCII + common punctuation."""
        import string
        allowed = set(string.printable)

        bad_count = 0
        for s in training_data[:500]:
            non_printable = sum(1 for c in s["text"] if c not in allowed)
            if non_printable > len(s["text"]) * 0.05:  # more than 5% non-printable
                bad_count += 1

        assert bad_count == 0, f"{bad_count}/500 samples have >5% non-printable characters"


# --- 8. Seed reproducibility ---

class TestReproducibility:
    def test_same_seed_same_output(self, fake):
        """Seeded Faker + seeded random should produce identical data."""
        import random as stdlib_random

        from faker import Faker
        from providers.invoice import InvoiceProvider

        # seed both Faker and stdlib random
        stdlib_random.seed(12345)
        f1 = Faker("en_US")
        f1.add_provider(InvoiceProvider)
        f1.seed_instance(12345)
        data1 = f1.invoice_data()

        stdlib_random.seed(12345)
        f2 = Faker("en_US")
        f2.add_provider(InvoiceProvider)
        f2.seed_instance(12345)
        data2 = f2.invoice_data()

        assert data1["vendor_name"] == data2["vendor_name"]
        assert data1["doc_number"] == data2["doc_number"]
        assert data1["total"] == data2["total"]
