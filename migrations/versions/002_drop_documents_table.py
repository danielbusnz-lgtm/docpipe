"""Drop documents table and FK constraints.

Document metadata lives in DynamoDB. Extraction tables reference
document_id as a plain UUID without a foreign key.

Revision ID: 002
Revises: 001
"""

from alembic import op

revision = "002"
down_revision = "001"


def upgrade():
    op.drop_constraint("invoice_extractions_document_id_fkey", "invoice_extractions", type_="foreignkey")
    op.drop_constraint("receipt_extractions_document_id_fkey", "receipt_extractions", type_="foreignkey")
    op.drop_constraint("contract_extractions_document_id_fkey", "contract_extractions", type_="foreignkey")
    op.create_index("ix_invoice_extractions_document_id", "invoice_extractions", ["document_id"])
    op.create_index("ix_receipt_extractions_document_id", "receipt_extractions", ["document_id"])
    op.create_index("ix_contract_extractions_document_id", "contract_extractions", ["document_id"])
    op.drop_table("documents")


def downgrade():
    op.execute("""
        CREATE TABLE documents (
            id UUID PRIMARY KEY,
            filename VARCHAR(255) NOT NULL,
            s3_key VARCHAR(500) NOT NULL,
            doc_type VARCHAR(50),
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    op.drop_index("ix_invoice_extractions_document_id", "invoice_extractions")
    op.drop_index("ix_receipt_extractions_document_id", "receipt_extractions")
    op.drop_index("ix_contract_extractions_document_id", "contract_extractions")
    op.create_foreign_key("invoice_extractions_document_id_fkey", "invoice_extractions", "documents", ["document_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key("receipt_extractions_document_id_fkey", "receipt_extractions", "documents", ["document_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key("contract_extractions_document_id_fkey", "contract_extractions", "documents", ["document_id"], ["id"], ondelete="CASCADE")
