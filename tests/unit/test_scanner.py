"""Tests for scanner module."""

import pytest
from pathlib import Path
from src.scanner import ImageScanner


def test_scan_directory(tmp_path):
    # Create test directory structure
    (tmp_path / "sub1").mkdir()
    (tmp_path / "sub2").mkdir()

    # Create some image files
    (tmp_path / "img1.png").write_bytes(b"fake png")
    (tmp_path / "img2.jpg").write_bytes(b"fake jpg")
    (tmp_path / "sub1/img3.png").write_bytes(b"fake png")
    (tmp_path / "sub2/img4.bmp").write_bytes(b"fake bmp")

    # Create non-image file
    (tmp_path / "readme.txt").write_text("hello")

    scanner = ImageScanner()
    images = scanner.scan_directory(tmp_path)

    assert len(images) == 4
    assert all(img.suffix in ['.png', '.jpg', '.jpeg', '.bmp', '.webp'] for img in images)


def test_scan_non_recursive(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "root.png").write_bytes(b"fake")
    (tmp_path / "sub/nested.png").write_bytes(b"fake")

    scanner = ImageScanner(recursive=False)
    images = scanner.scan_directory(tmp_path)

    assert len(images) == 1
    assert images[0].name == "root.png"


def test_scan_empty_directory(tmp_path):
    scanner = ImageScanner()
    images = scanner.scan_directory(tmp_path)
    assert len(images) == 0


def test_scan_invalid_path():
    scanner = ImageScanner()
    with pytest.raises(FileNotFoundError):
        list(scanner.scan_directory(Path("/nonexistent")))


def test_supported_formats():
    scanner = ImageScanner()
    expected = {'.png', '.jpg', '.jpeg', '.bmp', '.webp'}
    assert set(scanner.supported_formats) == expected


def test_scan_single_file_valid(tmp_path):
    scanner = ImageScanner()
    file_path = tmp_path / "one.png"
    file_path.write_bytes(b"fake")

    result = scanner.scan_single_file(file_path)
    assert result == file_path


def test_scan_single_file_invalid_suffix(tmp_path):
    scanner = ImageScanner()
    file_path = tmp_path / "one.txt"
    file_path.write_text("hello")

    with pytest.raises(ValueError):
        scanner.scan_single_file(file_path)
