
"""
Индексация PDF-сканов: OCR, очистка текста и сохранение в SQLite.

Запуск из корня проекта:
    python app/index.py
    python app/index.py --scans D:/scans --db data/docsearch.db

Повторный запуск обрабатывает только новые и изменённые документы.
Отсутствующие PDF не удаляются из поискового индекса автоматически.
"""

import argparse
import time
from pathlib import Path

import pytesseract

from clean import clean_text
from db import DEFAULT_DB, ROOT, connect, delete_document
from ocr import LANG, pdf_to_images


def ocr_pages(pdf_path: Path) -> list[str]:
    """Распознаёт PDF и возвращает текст каждой страницы."""
    return [
        pytesseract.image_to_string(img, lang=LANG)
        for img in pdf_to_images(pdf_path)
    ]


def find_pdfs(scans_dir: Path) -> list[Path]:
    """Находит PDF во всех вложенных папках."""
    return sorted(
        p for p in scans_dir.rglob("*")
        if p.is_file() and p.suffix.lower() == ".pdf"
    )


def index_folder(conn, scans_dir: Path) -> dict:
    files = find_pdfs(scans_dir)

    known = {
        row["path"]: row
        for row in conn.execute(
            "SELECT id, path, size, mtime FROM documents"
        )
    }

    stats = dict(
        new=0,
        updated=0,
        unchanged=0,
        failed=0,
        deleted=0,
        pages=0,
        seconds=0.0,
    )

    seen = set()

    for n, pdf in enumerate(files, start=1):
        rel_path = pdf.relative_to(scans_dir).as_posix()
        seen.add(rel_path)

        try:
            info = pdf.stat()
        except OSError as error:
            print(f"Ошибка чтения файла: {error}")
            stats["failed"] += 1
            continue

        old = known.get(rel_path)

        if (
            old
            and old["size"] == info.st_size
            and old["mtime"] == info.st_mtime
        ):
            stats["unchanged"] += 1
            continue

        print(
            f"[{n}/{len(files)}] {rel_path} ...",
            end=" ",
            flush=True,
        )

        start = time.perf_counter()

        try:
            raw_pages = ocr_pages(pdf)
        except Exception as error:
            print(f"Ошибка OCR: {error}")
            stats["failed"] += 1
            continue

        elapsed = time.perf_counter() - start

        # Документ сохраняется одной транзакцией.
        with conn:
            if old:
                delete_document(conn, old["id"])

            cursor = conn.execute(
                """
                INSERT INTO documents
                    (path, size, mtime, page_count)
                VALUES (?, ?, ?, ?)
                """,
                (
                    rel_path,
                    info.st_size,
                    info.st_mtime,
                    len(raw_pages),
                ),
            )

            conn.executemany(
                """
                INSERT INTO pages
                    (doc_id, page_no, raw_text, text)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        cursor.lastrowid,
                        i,
                        raw,
                        clean_text(raw),
                    )
                    for i, raw in enumerate(raw_pages, start=1)
                ],
            )

        stats["updated" if old else "new"] += 1
        stats["pages"] += len(raw_pages)
        stats["seconds"] += elapsed

        print(f"{len(raw_pages)} стр., {elapsed:.1f} с")

    # Отсутствующие документы сохраняем в базе.
    # Удаление возможно только отдельной подтверждённой операцией.
    missing = set(known) - seen

    if missing:
        print(
            f"\nПредупреждение: {len(missing)} документов "
            "не найдено в папке сканов. "
            "Записи в базе сохранены."
        )

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Распознать PDF-сканы и добавить их в базу"
    )

    parser.add_argument(
        "--scans",
        type=Path,
        default=ROOT / "examples" / "scans",
        help="Папка с PDF-сканами",
    )

    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help="Файл базы данных",
    )

    args = parser.parse_args()

    if not args.scans.is_dir():
        raise SystemExit(
            f"Папка не найдена: {args.scans}"
        )

    conn = connect(args.db)

    try:
        try:
            stats = index_folder(
                conn,
                args.scans.resolve(),
            )
        except KeyboardInterrupt:
            raise SystemExit(
                "\nОстановлено. Обработанные документы сохранены."
            )

        print(
            f"\nГотово. Новых: {stats['new']}, "
            f"обновлено: {stats['updated']}, "
            f"без изменений: {stats['unchanged']}, "
            f"ошибок: {stats['failed']}, "
            f"удалено: {stats['deleted']}"
        )

        if stats["pages"]:
            per_page = stats["seconds"] / stats["pages"]

            print(
                f"Распознано страниц: {stats['pages']} "
                f"за {stats['seconds']:.0f} с "
                f"({per_page:.1f} с на страницу)"
            )

        total = conn.execute(
            "SELECT COUNT(*) FROM documents"
        ).fetchone()[0]

        print(
            f"Всего в базе документов: {total} ({args.db})"
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
