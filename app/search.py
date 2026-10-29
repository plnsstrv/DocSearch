"""
Поиск по базе из терминала.

Примеры (из корня проекта):
  python app/search.py ТехноСнаб
  python app/search.py накладная 342
  python app/search.py 2-1487/2025

Как устроен поиск:
  - слова приводятся к основе (стемминг), поэтому запрос «мониторы»
    находит и «монитор», и «монитора», и «мониторов»;
  - всё, где есть цифры (номера, даты, ИНН), ищется точно;
  - короткие слова вроде «в», «на», «по» пропускаются;
  - сначала ищутся документы, где есть все слова запроса; если таких нет,
    показываются документы хотя бы с одним из слов.
"""

import argparse
import re
from pathlib import Path

import snowballstemmer

from db import DEFAULT_DB, connect

STEMMER = snowballstemmer.stemmer("russian")
MIN_WORD = 3   # слова короче пропускаем: это предлоги и союзы
MIN_STEM = 4   # по совсем короткой основе находится слишком много лишнего

SEARCH_SQL = """
SELECT d.path, d.page_count, p.page_no,
       snippet(pages_fts, 0, '[', ']', '…', 12) AS fragment
FROM pages_fts
JOIN pages p ON p.id = pages_fts.rowid
JOIN documents d ON d.id = p.doc_id
WHERE pages_fts MATCH ?
ORDER BY bm25(pages_fts)            -- сначала самые подходящие страницы
LIMIT 200
"""


def build_terms(query: str) -> list[str]:
    """Превращает запрос пользователя в условия для поиска FTS5."""
    terms = []
    for chunk in query.replace("ё", "е").replace("Ё", "Е").split():
        if any(ch.isdigit() for ch in chunk):
            # номер вроде «2-1487/2025» ищем как точную фразу
            phrase = chunk.strip("«»\"'.,;:()")
            terms.append('"' + phrase.replace('"', '""') + '"')
            continue
        for word in re.findall(r"[^\W\d_]+", chunk.lower()):
            if len(word) < MIN_WORD:
                continue
            stem = STEMMER.stemWord(word)
            if len(stem) >= MIN_STEM:
                terms.append(f'"{stem}"*')     # * = любое окончание
            else:
                terms.append(f'"{word}"')
    return terms


def search(conn, terms: list[str], operator: str, limit: int):
    """Ищет страницы и группирует их по документам."""
    rows = conn.execute(SEARCH_SQL, (f" {operator} ".join(terms),)).fetchall()
    documents = {}
    for row in rows:
        doc = documents.setdefault(row["path"], {
            "page_count": row["page_count"],
            "fragment": row["fragment"],     # фрагмент с самой подходящей страницы
            "pages": [],
        })
        doc["pages"].append(row["page_no"])
    return list(documents.items())[:limit]


def main():
    parser = argparse.ArgumentParser(description="Поиск по распознанным документам")
    parser.add_argument("query", nargs="+", help="что искать")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="файл базы данных")
    parser.add_argument("--limit", type=int, default=10, help="сколько документов показать")
    args = parser.parse_args()

    if not args.db.exists():
        raise SystemExit(f"Базы {args.db} ещё нет. Сначала запусти: python app/index.py")
    conn = connect(args.db)
    total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    if total == 0:
        raise SystemExit("База пустая. Сначала запусти: python app/index.py")

    terms = build_terms(" ".join(args.query))
    if not terms:
        raise SystemExit("Запрос слишком короткий: введи слово от трёх букв или номер.")

    print(f"Запрос к базе: {' AND '.join(terms)}")
    results = search(conn, terms, "AND", args.limit)
    if not results and len(terms) > 1:
        print("Документов со всеми словами нет, показываю документы хотя бы с одним из них.")
        results = search(conn, terms, "OR", args.limit)

    if not results:
        print(f"Ничего не найдено (всего в базе документов: {total}).")
        return

    print(f"Найдено документов: {len(results)}\n")
    for n, (path, doc) in enumerate(results, start=1):
        pages = ", ".join(str(p) for p in sorted(doc["pages"]))
        print(f"{n}. {path}  (совпадения на стр. {pages} из {doc['page_count']})")
        print(f"   {' '.join(doc['fragment'].split())}\n")


if __name__ == "__main__":
    main()
