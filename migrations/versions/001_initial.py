"""Create initial tables.

Revision ID: 001
Revises:
Create Date: 2026-03-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables."""
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("s3_key", sa.String(500), nullable=False),
        sa.Column("doc_type", sa.String(50)),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
    )

    op.create_table(
        "invoice_extractions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vendor_name", sa.String(255), nullable=False),
        sa.Column("invoice_number", sa.String(100)),
        sa.Column("invoice_date", sa.String(50)),
        sa.Column("due_date", sa.String(50)),
        sa.Column("subtotal", sa.Numeric(12, 2)),
        sa.Column("tax", sa.Numeric(12, 2)),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(10), server_default="USD"),
        sa.Column("payment_terms", sa.String(100)),
        sa.Column("raw_json", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime),
    )

    op.create_table(
        "receipt_extractions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vendor_name", sa.String(255), nullable=False),
        sa.Column("receipt_date", sa.String(50)),
        sa.Column("subtotal", sa.Numeric(12, 2)),
        sa.Column("tax", sa.Numeric(12, 2)),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("payment_method", sa.String(50)),
        sa.Column("raw_json", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime),
    )

    op.create_table(
        "contract_extractions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parties", postgresql.ARRAY(sa.Text)),
        sa.Column("effective_date", sa.String(50)),
        sa.Column("expiration_date", sa.String(50)),
        sa.Column("contract_value", sa.Numeric(12, 2)),
        sa.Column("key_terms", postgresql.ARRAY(sa.Text)),
        sa.Column("summary", sa.Text),
        sa.Column("raw_json", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime),
    )

    op.create_table(
        "line_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("extraction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("extraction_type", sa.String(50), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("quantity", sa.Numeric(10, 3), server_default="1.0"),
        sa.Column("unit_price", sa.Numeric(12, 2)),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("category", sa.String(100)),
        sa.Column("created_at", sa.DateTime),
    )

    op.create_index("idx_documents_doc_type", "documents", ["doc_type"])
    op.create_index("idx_invoice_extractions_doc_id", "invoice_extractions", ["document_id"])
    op.create_index("idx_receipt_extractions_doc_id", "receipt_extractions", ["document_id"])
    op.create_index("idx_contract_extractions_doc_id", "contract_extractions", ["document_id"])
    op.create_index("idx_line_items_extraction", "line_items", ["extraction_id", "extraction_type"])


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table("line_items")
    op.drop_table("contract_extractions")
    op.drop_table("receipt_extractions")
    op.drop_table("invoice_extractions")
    op.drop_table("documents")
