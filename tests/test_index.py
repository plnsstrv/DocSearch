
import sys
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from index import index_folder


class TestIndexSafety(unittest.TestCase):

    def test_empty_folder_does_not_delete_documents(self):
        with tempfile.TemporaryDirectory() as temp:
            scans_dir = Path(temp) / "scans"
            scans_dir.mkdir()

            conn = sqlite3.connect(":memory:")
            conn.row_factory = sqlite3.Row

            try:
                conn.execute("""
                    CREATE TABLE documents (
                        id INTEGER PRIMARY KEY,
                        path TEXT,
                        size INTEGER,
                        mtime REAL
                    )
                """)

                conn.execute(
                    "INSERT INTO documents (path, size, mtime) VALUES (?, ?, ?)",
                    ("example.pdf", 100, 123.0),
                )
                conn.commit()

                with patch("index.delete_document") as delete_mock:
                    stats = index_folder(conn, scans_dir)

                remaining = conn.execute(
                    "SELECT COUNT(*) FROM documents"
                ).fetchone()[0]

                self.assertEqual(remaining, 1)
                self.assertEqual(stats["deleted"], 0)
                delete_mock.assert_not_called()

            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
