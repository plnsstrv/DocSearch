
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "app")
)

from db import connect
from index import index_folder


class TestIndex(unittest.TestCase):

    def setUp(self):
        # Each test uses a temporary directory and database.
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

        self.scans = self.root / "scans"
        self.scans.mkdir()

        self.db_path = self.root / "test.db"
        self.conn = connect(self.db_path)

    def tearDown(self):
        self.conn.close()
        self.temp.cleanup()

    def create_pdf(self, name="test.pdf", content=b"fake pdf"):
        # OCR is mocked, so a real PDF is not required.
        pdf = self.scans / name
        pdf.write_bytes(content)
        return pdf

    def document_count(self):
        return self.conn.execute(
            "SELECT COUNT(*) FROM documents"
        ).fetchone()[0]

    def page_count(self):
        return self.conn.execute(
            "SELECT COUNT(*) FROM pages"
        ).fetchone()[0]

    def search_count(self, query):
        return self.conn.execute(
            "SELECT COUNT(*) FROM pages_fts WHERE pages_fts MATCH ?",
            (query,)
        ).fetchone()[0]

    def test_new_document_is_indexed(self):
        self.create_pdf()

        with patch(
            "index.ocr_pages",
            return_value=["alpha document"]
        ) as mock_ocr:
            stats = index_folder(self.conn, self.scans)

        self.assertEqual(stats["new"], 1)
        self.assertEqual(stats["pages"], 1)
        self.assertEqual(self.document_count(), 1)
        self.assertEqual(self.page_count(), 1)
        self.assertEqual(self.search_count("alpha"), 1)

        mock_ocr.assert_called_once()

    def test_unchanged_document_is_skipped(self):
        self.create_pdf()

        with patch(
            "index.ocr_pages",
            return_value=["alpha document"]
        ):
            index_folder(self.conn, self.scans)

        # Unchanged files must not be processed again.
        with patch("index.ocr_pages") as mock_ocr:
            stats = index_folder(self.conn, self.scans)

        self.assertEqual(stats["unchanged"], 1)
        self.assertEqual(stats["new"], 0)
        self.assertEqual(stats["updated"], 0)
        self.assertEqual(self.document_count(), 1)
        self.assertEqual(self.page_count(), 1)

        mock_ocr.assert_not_called()

    def test_changed_document_is_updated(self):
        pdf = self.create_pdf()

        with patch(
            "index.ocr_pages",
            return_value=["alpha document"]
        ):
            index_folder(self.conn, self.scans)

        # Change the file size to trigger reindexing.
        pdf.write_bytes(b"modified fake pdf content")

        with patch(
            "index.ocr_pages",
            return_value=["beta document"]
        ) as mock_ocr:
            stats = index_folder(self.conn, self.scans)

        self.assertEqual(stats["updated"], 1)
        self.assertEqual(self.document_count(), 1)
        self.assertEqual(self.page_count(), 1)

        # Old search terms must disappear from FTS5.
        self.assertEqual(self.search_count("alpha"), 0)

        # New search terms must appear in FTS5.
        self.assertEqual(self.search_count("beta"), 1)

        # Verify the new OCR text was actually saved.
        saved_text = self.conn.execute(
            "SELECT raw_text FROM pages"
        ).fetchone()["raw_text"]

        self.assertEqual(saved_text, "beta document")

        mock_ocr.assert_called_once()

    def test_empty_folder_does_not_delete_documents(self):
        pdf = self.create_pdf()

        with patch(
            "index.ocr_pages",
            return_value=["alpha document"]
        ):
            index_folder(self.conn, self.scans)

        pdf.unlink()

        # Missing files must not trigger OCR or deletion.
        with patch("index.ocr_pages") as mock_ocr:
            with patch("index.delete_document") as mock_delete:
                stats = index_folder(self.conn, self.scans)

        self.assertEqual(stats["deleted"], 0)
        self.assertEqual(self.document_count(), 1)
        self.assertEqual(self.page_count(), 1)
        self.assertEqual(self.search_count("alpha"), 1)

        mock_ocr.assert_not_called()
        mock_delete.assert_not_called()


if __name__ == "__main__":
    unittest.main()
