"""Test the pipeline processor with mocked services."""

from unittest.mock import MagicMock, patch

import pytest

from src.pipeline.processor import process_document


@pytest.fixture
def mock_deps():
    """Create all the mock dependencies the processor needs."""
    s3_client = MagicMock()
    anthropic_client = MagicMock()
    dynamo_table = MagicMock()
    db_session = MagicMock()

    # DynamoDB returns a document record
    dynamo_table.get_item.return_value = {
        "Item": {
            "document_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "s3_key": "documents/test-doc-123/invoice.pdf",
            "status": "uploaded",
        }
    }

    return {
        "document_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "s3_client": s3_client,
        "anthropic_client": anthropic_client,
        "dynamo_table": dynamo_table,
        "db_session": db_session,
        "bucket": "test-bucket",
    }


class TestProcessDocument:
    @patch("src.pipeline.processor.storage")
    @patch("src.pipeline.processor.validator")
    @patch("src.pipeline.processor.extractor")
    @patch("src.pipeline.processor.classifier")
    @patch("src.pipeline.processor.dynamo")
    @patch("src.pipeline.processor._extract_text")
    def test_happy_path_invoice(self, mock_text, mock_dynamo, mock_clf,
                                 mock_ext, mock_val, mock_store, mock_deps):
        # setup mocks
        mock_dynamo.get_document.return_value = {
            "document_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "s3_key": "documents/test/invoice.pdf",
        }
        mock_text.return_value = "INVOICE Acme Corp Total $500 Net 30 some long text here"
        mock_clf.classify.return_value = ("invoice", 0.95)
        mock_ext.extract.return_value = MagicMock()  # fake extraction
        mock_val.validate.return_value = MagicMock(is_valid=True, warnings=[])

        process_document(**mock_deps)

        # verify each step was called
        mock_dynamo.get_document.assert_called_once()
        mock_text.assert_called_once()
        mock_clf.classify.assert_called_once()
        mock_ext.extract.assert_called_once()
        mock_val.validate.assert_called_once()
        mock_store.store.assert_called_once()

        # verify status updates happened
        status_calls = [c.args[2] for c in mock_dynamo.update_status.call_args_list]
        assert "classifying" in status_calls
        assert "extracting" in status_calls
        assert "validating" in status_calls
        assert "completed" in status_calls

    @patch("src.pipeline.processor.dynamo")
    @patch("src.pipeline.processor._extract_text")
    def test_unknown_doc_skips_extraction(self, mock_text, mock_dynamo, mock_deps):
        mock_dynamo.get_document.return_value = {
            "document_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "s3_key": "documents/test/other.pdf",
        }
        mock_text.return_value = "Some random document with enough text to classify"

        with patch("src.pipeline.processor.classifier") as mock_clf:
            mock_clf.classify.return_value = ("unknown", 0.3)
            process_document(**mock_deps)

        # should go straight to completed, no extraction
        status_calls = [c.args[2] for c in mock_dynamo.update_status.call_args_list]
        assert "completed" in status_calls
        assert "validating" not in status_calls

    @patch("src.pipeline.processor.validator")
    @patch("src.pipeline.processor.extractor")
    @patch("src.pipeline.processor.classifier")
    @patch("src.pipeline.processor.dynamo")
    @patch("src.pipeline.processor._extract_text")
    def test_validation_failure_sets_failed(self, mock_text, mock_dynamo,
                                             mock_clf, mock_ext, mock_val, mock_deps):
        mock_dynamo.get_document.return_value = {
            "document_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "s3_key": "documents/test/invoice.pdf",
        }
        mock_text.return_value = "INVOICE with enough text to classify and process here"
        mock_clf.classify.return_value = ("invoice", 0.9)
        mock_ext.extract.return_value = MagicMock()
        mock_val.validate.return_value = MagicMock(
            is_valid=False, errors=["Vendor name is empty"]
        )

        process_document(**mock_deps)

        status_calls = [c.args[2] for c in mock_dynamo.update_status.call_args_list]
        assert "failed" in status_calls

    @patch("src.pipeline.processor.dynamo")
    def test_missing_document_returns_early(self, mock_dynamo, mock_deps):
        mock_dynamo.get_document.return_value = None

        process_document(**mock_deps)

        # should not crash, just log and return
        mock_dynamo.update_status.assert_not_called()

    @patch("src.pipeline.processor.classifier")
    @patch("src.pipeline.processor.dynamo")
    @patch("src.pipeline.processor._extract_text")
    def test_exception_sets_failed_status(self, mock_text, mock_dynamo,
                                           mock_clf, mock_deps):
        mock_dynamo.get_document.return_value = {
            "document_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "s3_key": "documents/test/invoice.pdf",
        }
        mock_text.return_value = "INVOICE enough text to process here and classify"
        mock_clf.classify.side_effect = RuntimeError("something broke")

        with pytest.raises(RuntimeError):
            process_document(**mock_deps)

        # should have tried to set failed status
        status_calls = [c.args[2] for c in mock_dynamo.update_status.call_args_list]
        assert "failed" in status_calls
