"""Tests for hasher module."""

import pytest
from pathlib import Path
from PIL import Image
from src.hasher import FileHasher


@pytest.fixture
def sample_image(tmp_path):
    """Create a simple test image"""
    img_path = tmp_path / "test.png"
    img = Image.new('RGB', (100, 100), color='red')
    img.save(img_path)
    return img_path


def test_calculate_file_hash(sample_image):
    hasher = FileHasher()
    file_hash = hasher.calculate_file_hash(sample_image)

    assert isinstance(file_hash, str)
    assert len(file_hash) == 64  # SHA256 hex string length

    # Same file should produce same hash
    file_hash2 = hasher.calculate_file_hash(sample_image)
    assert file_hash == file_hash2


def test_calculate_phash(sample_image):
    hasher = FileHasher()
    phash = hasher.calculate_phash(sample_image)

    assert isinstance(phash, str)

    # Same image should produce same phash
    phash2 = hasher.calculate_phash(sample_image)
    assert phash == phash2


def test_phash_similarity(tmp_path):
    hasher = FileHasher()

    # Create two similar images (same color, slightly different size)
    img1_path = tmp_path / "img1.png"
    img2_path = tmp_path / "img2.png"

    img1 = Image.new('RGB', (100, 100), color='blue')
    img2 = Image.new('RGB', (105, 105), color='blue')

    img1.save(img1_path)
    img2.save(img2_path)

    phash1 = hasher.calculate_phash(img1_path)
    phash2 = hasher.calculate_phash(img2_path)

    # Similar images should have small hamming distance
    distance = hasher.hamming_distance(phash1, phash2)
    assert distance < 10  # Should be quite similar


def test_file_hash_different_content(tmp_path):
    hasher = FileHasher()

    # Two different images
    img1_path = tmp_path / "img1.png"
    img2_path = tmp_path / "img2.png"

    Image.new('RGB', (100, 100), color='red').save(img1_path)
    Image.new('RGB', (100, 100), color='blue').save(img2_path)

    hash1 = hasher.calculate_file_hash(img1_path)
    hash2 = hasher.calculate_file_hash(img2_path)

    assert hash1 != hash2
