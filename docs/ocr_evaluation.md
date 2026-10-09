# OCR quality evaluation

A log of OCR quality measurements. New runs are appended at the end, so you can see how the results change over time.

## Method

**Test set:** 4 fictional documents of different types with simulated scan defects (skew, blur, noise, low resolution). The original text of each document is stored in `examples/ground_truth/`.

**Metric:** the share of matching characters between the recognized text and the original, after normalizing whitespace and case (`difflib.SequenceMatcher`). The metric is rough, especially for tables; switching to the standard CER (character error rate) is planned.

**How to run:** `python app/ocr.py`

## 2026-10-09: baseline

Settings: Tesseract 5, languages `rus+eng`, PDF pages rendered at 300 dpi, no image preprocessing.

| Document | Scan quality | Similarity |
|---|---|---|
| Demand letter for payment of a debt | good (~180 dpi) | 99.5% |
| Motion for a court-ordered expert examination | medium (~150 dpi, skew, noise) | 99.6% |
| Response to the demand letter | medium (~150 dpi, skew, noise) | 98.7% |
| Delivery note with a table | poor (~125 dpi, heavy blur and noise, skew) | 64.5% |

Observations:
- Regular text is recognized almost without errors, even on medium-quality scans.
- On the poor scan, text outside the table is recognized well (company names, tax IDs, document numbers, dates, surnames), but the table content is lost entirely: grid lines and small blurry text get in the way.
- OCR sometimes substitutes Latin letters for similar-looking Cyrillic ones ("Ha" instead of "На"), which can break exact-match search.
- Lines in the signature block get reordered, but this does not affect search.

Next steps:
- normalize Latin look-alike letters inside Russian words;
- preprocessing: remove table lines, deskew, binarize;
- try a Tesseract page segmentation mode suited for tables;
- send pages where Tesseract has low confidence to a local vision model;
- switch to the CER metric.
