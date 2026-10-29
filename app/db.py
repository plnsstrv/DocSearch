"""
База данных SQLite: документы, их страницы и полнотекстовый индекс.

Таблицы:
  documents  — один PDF-файл: путь, размер, дата изменения, число страниц
  pages      — текст каждой страницы: как распознал OCR и после очистки
  pages_fts  — полнотекстовый индекс (SQLite FTS5) по очищенному тексту
"""

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent      # корень проекта DocSearch
DEFAULT_DB = ROOT / "data" / "docsearch.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id          INTEGER PRIMARY KEY,
    path        TEXT NOT NULL UNIQUE,   -- путь относительно папки со сканами
    size        INTEGER NOT NULL,       -- размер файла в байтах
    mtime       REAL NOT NULL,          -- когда файл последний раз менялся
    page_count  INTEGER NOT NULL,
    indexed_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS pages (
    id        INTEGER PRIMARY KEY,
    doc_id    INTEGER NOT NULL REFERENCES documents(id),
    page_no   INTEGER NOT NULL,
    raw_text  TEXT NOT NULL,   -- как распознал OCR: если улучшим очистку,
                               -- не придётся заново распознавать сканы
    text      TEXT NOT NULL    -- после очистки, по нему идёт поиск
);
CREATE INDEX IF NOT EXISTS pages_doc_id ON pages(doc_id);

-- Полнотекстовый индекс. content='pages' значит, что сам текст хранится
-- в таблице pages, а здесь только индекс для быстрого поиска по словам.
CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(
    text,
    content='pages',
    content_rowid='id',
    tokenize='unicode61'
);

-- Триггеры: индекс сам обновляется, когда страницы добавляются,
-- меняются или удаляются.
CREATE TRIGGER IF NOT EXISTS pages_after_insert AFTER INSERT ON pages BEGIN
    INSERT INTO pages_fts(rowid, text) VALUES (new.id, new.text);
END;
CREATE TRIGGER IF NOT EXISTS pages_after_delete AFTER DELETE ON pages BEGIN
    INSERT INTO pages_fts(pages_fts, rowid, text) VALUES ('delete', old.id, old.text);
END;
CREATE TRIGGER IF NOT EXISTS pages_after_update AFTER UPDATE ON pages BEGIN
    INSERT INTO pages_fts(pages_fts, rowid, text) VALUES ('delete', old.id, old.text);
    INSERT INTO pages_fts(rowid, text) VALUES (new.id, new.text);
END;
"""


def connect(db_path: Path = DEFAULT_DB) -> sqlite3.Connection:
    """Открывает базу (создаёт, если её ещё нет)."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row      # строки можно читать по имени: row["path"]
    _check_fts5(conn)
    conn.executescript(SCHEMA)
    return conn


def delete_document(conn: sqlite3.Connection, doc_id: int) -> None:
    """Удаляет документ и его страницы (индекс почистят триггеры)."""
    conn.execute("DELETE FROM pages WHERE doc_id = ?", (doc_id,))
    conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))


def _check_fts5(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("CREATE VIRTUAL TABLE temp.fts5_check USING fts5(x)")
        conn.execute("DROP TABLE temp.fts5_check")
    except sqlite3.OperationalError:
        raise SystemExit(
            "SQLite в этой сборке Python не поддерживает полнотекстовый поиск FTS5. "
            f"Версия SQLite: {sqlite3.sqlite_version}."
        )
