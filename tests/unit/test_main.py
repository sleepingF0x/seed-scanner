"""Tests for main module."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock


def test_parse_args():
    from src.main import parse_args

    args = parse_args(['/path/to/scan'])
    assert args.target == Path('/path/to/scan')
    assert args.config is None
    assert args.force is False

    args = parse_args(['/path/to/scan', '--config', 'cfg.yaml', '--force'])
    assert args.config == Path('cfg.yaml')
    assert args.force is True


@patch('src.main.ImageScanner')
@patch('src.main.Database')
@patch('src.main.FileHasher')
@patch('src.main.OCREngine')
def test_scanner_pipeline(mock_ocr_class, mock_hasher_class, mock_db_class, mock_scanner_class):
    from src.main import ScannerPipeline

    # Setup mocks
    mock_config = Mock()
    mock_config.scanner = {'recursive': True, 'supported_formats': ['.png']}
    mock_config.database = {'path': '/tmp/test.db'}
    mock_config.ocr = {'use_gpu': False, 'lang': 'en'}
    mock_config.force = False

    pipeline = ScannerPipeline(mock_config)

    # Verify components initialized
    mock_db_class.assert_called_once_with(Path('/tmp/test.db'))
    mock_scanner_class.assert_not_called()  # Only called in process_directory
    mock_ocr_class.assert_called_once_with(use_gpu=False, lang='en')
