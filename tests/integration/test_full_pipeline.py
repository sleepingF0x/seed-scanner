"""Integration tests for full scanner pipeline."""

import pytest
from pathlib import Path
from PIL import Image
from src.main import ScannerPipeline
from src.config import Config


@pytest.fixture
def sample_image_with_seed(tmp_path):
    """Create a test image with seed phrase text"""
    # Note: This requires actual OCR to work, may need mocking
    img_path = tmp_path / "seed_wallet.png"

    # Create a simple test image
    img = Image.new('RGB', (400, 100), color='white')
    img.save(img_path)
    return img_path


def test_full_pipeline(tmp_path, sample_image_with_seed):
    """Test the full pipeline with mocked OCR"""
    from unittest.mock import Mock, patch

    config = Config()
    config._config['database']['path'] = str(tmp_path / "test.db")

    pipeline = ScannerPipeline(config)

    # Mock OCR to return a seed phrase
    pipeline.ocr.extract_text = Mock(return_value=
        "abandon ability able about above absent absorb abstract absurd abuse access accident")

    result = pipeline.process_image(sample_image_with_seed)

    assert result is not None
    assert result['has_seed'] is True
    assert 'abandon' in result['seed_phrase']
