# DocSearch
Local document search for scanned PDFs: OCR, LLM-based metadata extraction and hybrid (keyword + semantic) search. Fully offline, documents never leave the server.



Local search over an archive of scanned documents: optical character recognition (OCR), automatic cataloging with a local LLM, and keyword plus semantic search. Runs fully offline: documents never leave the server.

## Problem

A practicing lawyer keeps case documents on paper and as scanned PDFs without a text layer, all in Russian. The documents vary widely: letters, requests, court motions, demand letters, delivery notes. Finding the right document means searching by hand, and the query can be anything: a surname, a number, a fragment of a phrase, or just the gist of the document.

User requirements:
- no manual data entry for document cards;
- a single search box that handles any query;
- fully local processing: the documents contain personal data and confidential client information.

## How it works

```
Scanned PDF → OCR → text cleanup → LLM extracts metadata → SQLite (full-text index + embeddings) → search page
```

Status:
- [x] OCR for scanned PDFs (Tesseract) and quality evaluation
- [ ] Text cleanup
- [ ] SQLite database and full-text search (FTS5)
- [ ] Metadata extraction with a local LLM (document type, date, organizations, summary)
- [ ] Semantic search (embeddings) and hybrid ranking
- [ ] Web search interface
- [ ] Docker packaging for server deployment

## Results

Regular documents are recognized with ~99% similarity to the original, even on medium-quality scans. The weak spot is tables on poor scans (64.5% on the test delivery note). Details: [docs/ocr_evaluation.md](docs/ocr_evaluation.md) (in Russian).

## Privacy

- All processing runs locally, with no cloud services or external APIs.
- The repository contains only fictional demo documents (`examples/`). Real documents, OCR output, and the database are excluded via `.gitignore`.

## Getting started

Requires Python 3.13 and Tesseract 5 with Russian language data.

```bash
# Windows (PowerShell)
py -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
python app/ocr.py
```

Recognized text is saved to `data/ocr_output/`, and the console shows the similarity to the original for each document.

## Project structure

```
app/ocr.py              OCR for scanned PDFs and quality evaluation
docs/                   reports and measurements
examples/scans/         demo scans (fictional documents)
examples/ground_truth/  original text of the demo documents, used to evaluate OCR
data/                   output (not committed)
```

## Tech stack

Python, Tesseract OCR, PyMuPDF. Planned: SQLite (FTS5), Ollama, Streamlit, Docker.