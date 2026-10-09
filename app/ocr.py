

import difflib
import platform
import re
from pathlib import Path

import pymupdf
import pytesseract
from PIL import Image

# --- настройки ---
ROOT = Path(__file__).resolve().parent.parent      # корень проекта DocSearch
SCANS_DIR = ROOT / "examples" / "scans"
TRUTH_DIR = ROOT / "examples" / "ground_truth"
OUT_DIR = ROOT / "data" / "ocr_output"
DPI = 300              # с каким разрешением «фотографировать» страницу перед OCR
LANG = "rus+eng"       # языки для Tesseract

# На Windows подсказываем, где лежит tesseract.exe (стандартный путь установщика)
if platform.system() == "Windows":
    default_path = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if default_path.exists():
        pytesseract.pytesseract.tesseract_cmd = str(default_path)


def pdf_to_images(pdf_path: Path):
    """Превращает каждую страницу PDF в картинку (PIL Image)."""
    doc = pymupdf.open(pdf_path)
    for page in doc:
        pix = page.get_pixmap(dpi=DPI)
        yield Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    doc.close()


def ocr_pdf(pdf_path: Path) -> str:
    """Распознаёт все страницы PDF и склеивает текст."""
    pages = []
    for i, img in enumerate(pdf_to_images(pdf_path), start=1):
        text = pytesseract.image_to_string(img, lang=LANG)
        pages.append(f"--- страница {i} ---\n{text}")
    return "\n".join(pages)


def normalize(text: str) -> str:
    """Убирает лишние пробелы и переносы, чтобы сравнивать только содержание."""
    text = re.sub(r"--- страница \d+ ---", " ", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def similarity(recognized: str, original: str) -> float:
    """Насколько распознанный текст похож на исходный (0..100%)."""
    a, b = normalize(recognized), normalize(original)
    return difflib.SequenceMatcher(None, a, b).ratio() * 100


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(SCANS_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"В папке {SCANS_DIR} нет PDF-файлов")
        return

    for pdf in pdfs:
        print(f"Распознаю {pdf.name}...")
        text = ocr_pdf(pdf)
        out_file = OUT_DIR / (pdf.stem + ".txt")
        out_file.write_text(text, encoding="utf-8")

        # ищем исходный текст: xxx_scan.pdf -> xxx_original.txt
        truth_file = TRUTH_DIR / (pdf.stem.replace("_scan", "_original") + ".txt")
        if truth_file.exists():
            score = similarity(text, truth_file.read_text(encoding="utf-8"))
            print(f"   сохранено в {out_file.name}, совпадение с оригиналом: {score:.1f}%")
        else:
            print(f"   сохранено в {out_file.name} (исходного текста для сравнения нет)")


if __name__ == "__main__":
    main()