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


def test_extract_text_new_paddleocr_response():
    """Supports PaddleOCR response with rec_texts entries."""
    engine = OCREngine(use_gpu=False)
    mock_ocr = Mock()
    mock_ocr.ocr = Mock(return_value=[
        {"rec_texts": ["abandon ability", "able about"], "rec_scores": [0.95, 0.92]}
    ])
    engine._ocr = mock_ocr

    result = engine.extract_text(Path("fake.png"))
    assert result == "abandon ability able about"


def test_extract_text_with_boxes_legacy_response():
    """extract_text_with_boxes keeps compatibility for legacy line response."""
    engine = OCREngine(use_gpu=False)
    mock_ocr = Mock()
    mock_ocr.ocr = Mock(return_value=[
        [
            [[(10, 10), (100, 10), (100, 30), (10, 30)], ("abandon ability", 0.95)],
            [[(10, 40), (100, 40), (100, 60), (10, 60)], ("able about", 0.92)],
        ]
    ])
    engine._ocr = mock_ocr

    result = engine.extract_text_with_boxes(Path("fake.png"))
    assert len(result) == 2
    assert result[0]["text"] == "abandon ability"
    assert result[0]["confidence"] == 0.95


def test_extract_text_retries_with_safe_runtime_on_paddle_onednn_error():
    """Retries once with safe runtime flags when Paddle oneDNN/PIR throws."""
    engine = OCREngine(use_gpu=False)

    failing_ocr = Mock()
    failing_ocr.ocr = Mock(side_effect=Exception(
        "(Unimplemented) ConvertPirAttribute2RuntimeAttribute not support "
        "[pir::ArrayAttribute<pir::DoubleAttribute>]"
    ))

    working_ocr = Mock()
    working_ocr.ocr = Mock(return_value=[
        {"rec_texts": ["abandon ability"], "rec_scores": [0.95]}
    ])

    engine._ocr = failing_ocr

    with patch.object(engine, "_build_ocr_engine", return_value=working_ocr) as mock_build:
        result = engine.extract_text(Path("fake.png"))

    assert result == "abandon ability"
    mock_build.assert_called_once_with(safe_mode=True)
    assert failing_ocr.ocr.call_count == 1
    assert working_ocr.ocr.call_count == 1
