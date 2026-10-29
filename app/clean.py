"""
Очистка распознанного текста перед записью в базу.

Что исправляет:
  1. Латинские буквы вместо русских. Tesseract иногда путает похожие буквы:
     «Ha сумму» вместо «На сумму», «OOO» вместо «ООО». На глаз разницы нет,
     а для поиска это разные слова.
  2. Букву «ё». Поиск SQLite не считает «ё» и «е» одной буквой, а люди почти
     всегда пишут «е». Поэтому в базе везде будет «е».
  3. Лишние пробелы, пустые строки и служебный символ конца страницы.
"""

import re

# латинские буквы, которые выглядят так же, как русские
LOOKALIKES = "ABCEHKMOPTXaceopxy"
LATIN_TO_CYRILLIC = str.maketrans(LOOKALIKES, "АВСЕНКМОРТХасеорху")

WORD_RE = re.compile(r"[^\W\d_]+")       # слово = подряд идущие буквы
CYRILLIC_RE = re.compile(r"[а-яёА-ЯЁ]")
LATIN_RE = re.compile(r"[a-zA-Z]")


def fix_lookalikes(text: str) -> str:
    """Заменяет латинские буквы-двойники на русские там, где слово явно русское."""
    words = list(WORD_RE.finditer(text))
    is_russian = [bool(CYRILLIC_RE.search(m.group())) for m in words]

    parts, last = [], 0
    for i, match in enumerate(words):
        word = match.group()
        if not LATIN_RE.search(word):
            continue

        if is_russian[i]:
            # в слове есть и русские, и латинские буквы: «Пpетензия»
            fixed = word.translate(LATIN_TO_CYRILLIC)
        elif set(word) <= set(LOOKALIKES) and _next_to_russian(is_russian, i):
            # слово целиком из букв-двойников среди русских слов: «Ha сумму»
            fixed = word.translate(LATIN_TO_CYRILLIC)
        else:
            # обычное латинское слово: SSD, Core, IPS
            continue

        parts.append(text[last:match.start()])
        parts.append(fixed)
        last = match.end()

    parts.append(text[last:])
    return "".join(parts)


def _next_to_russian(is_russian: list[bool], i: int) -> bool:
    before = i > 0 and is_russian[i - 1]
    after = i + 1 < len(is_russian) and is_russian[i + 1]
    return before or after


def clean_text(text: str) -> str:
    text = text.replace("\x0c", "")              # символ конца страницы от Tesseract
    text = fix_lookalikes(text)
    text = text.replace("ё", "е").replace("Ё", "Е")
    text = re.sub(r"[ \t]+", " ", text)          # несколько пробелов подряд -> один
    text = re.sub(r" *\n *", "\n", text)         # пробелы в начале и конце строк
    text = re.sub(r"\n{3,}", "\n\n", text)       # много пустых строк -> одна
    return text.strip()
