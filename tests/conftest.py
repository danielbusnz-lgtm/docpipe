"""Shared fixtures for the test suite."""

import sys
from pathlib import Path

import pytest
from faker import Faker

# let tests import from scripts/providers/
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from providers.contract import ContractProvider
from providers.invoice import InvoiceProvider
from providers.other import OtherProvider
from providers.receipt import ReceiptProvider


@pytest.fixture
def fake():
    """Faker instance with all document providers registered."""
    f = Faker("en_US")
    f.add_provider(InvoiceProvider)
    f.add_provider(ReceiptProvider)
    f.add_provider(ContractProvider)
    f.add_provider(OtherProvider)
    return f
