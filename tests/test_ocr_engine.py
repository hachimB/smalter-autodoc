# tests/test_ocr_engine.py

from pathlib import Path
from src.smalter_autodoc.core.ocr_engine import OCREngine


def test_extract_from_pdf_native():
    engine = OCREngine()

    result = engine.extract_from_pdf_native(
        "tests/test_files/welcome_pdf.pdf"
    )

    print(f"\nMéthode: {result.extraction_method}")
    print(f"Caractères: {result.char_count}")
    print(f"Mots: {result.word_count}")
    print(f"Aperçu: {result.text[:200]}...")

    # Assertions minimales pour que ce soit un vrai test
    assert result.extraction_method == "DIRECT"
    assert result.char_count > 0
    assert result.word_count > 0


def test_extract_from_image():
    engine = OCREngine()

    result = engine.extract_from_image(
        "tests/test_files/img.jpg"
    )

    print(f"\nMéthode: {result.extraction_method}")
    print(f"Qualité OCR: {result.ocr_quality.overall}%")
    print(f"Confiance: {result.ocr_quality.confidence}%")
    print(f"Passé: {result.ocr_quality.passed}")

    # Assertions minimales
    assert result.extraction_method == "OCR"
    assert result.char_count > 0
    assert result.ocr_quality is not None
