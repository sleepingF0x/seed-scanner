"""Tests for OCR engine module."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from src.ocr_engine import OCREngine


def test_ocr_engine_initialization():
    engine = OCREngine(use_gpu=False)
    assert engine.use_gpu is False


def test_ocr_mock():
    """Test OCR with mocked paddleocr to avoid model download in tests"""
    engine = OCREngine(use_gpu=False)

    # Create mock OCR object
    # PaddleOCR returns [[line1, line2, ...]] where each line is [box, (text, confidence)]
    mock_ocr = Mock()
    mock_ocr.ocr = Mock(return_value=[
        [
            [[(10, 10), (100, 10), (100, 30), (10, 30)], ('abandon ability', 0.95)],
            [[(10, 40), (100, 40), (100, 60), (10, 60)], ('able about', 0.92)]
        ]
    ])
    engine._ocr = mock_ocr

    result = engine.extract_text(Path("fake.png"))
    assert "abandon ability" in result
    assert "able about" in result


def test_extract_text_empty_result():
    engine = OCREngine(use_gpu=False)
    mock_ocr = Mock()
    mock_ocr.ocr = Mock(return_value=[None])
    engine._ocr = mock_ocr

    result = engine.extract_text(Path("fake.png"))
    assert result == ""


def test_extract_text_no_detection():
    engine = OCREngine(use_gpu=False)
    mock_ocr = Mock()
    mock_ocr.ocr = Mock(return_value=None)
    engine._ocr = mock_ocr

    result = engine.extract_text(Path("fake.png"))
    assert result == ""
