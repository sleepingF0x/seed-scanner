"""Tests for database module."""

import pytest
import sqlite3
from pathlib import Path
from src.db import Database


@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "test.db"
    return Database(db_path)


def test_database_initialization(temp_db):
    assert temp_db.db_path.exists()


def test_table_creation(temp_db):
    conn = sqlite3.connect(temp_db.db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='processed_files'")
    assert cursor.fetchone() is not None
    conn.close()


def test_insert_and_query_file(temp_db):
    temp_db.insert_file(
        file_hash="abc123",
        phash="def456",
        file_path="/test/image.png",
        file_size=1024,
        ocr_text="test text",
        has_seed=False,
        seed_phrase=None
    )

    result = temp_db.get_by_file_hash("abc123")
    assert result is not None
    assert result["file_hash"] == "abc123"
    assert result["phash"] == "def456"


def test_exists_by_file_hash(temp_db):
    temp_db.insert_file(
        file_hash="exists_hash",
        phash="phash1",
        file_path="/test/1.png",
        file_size=100,
        ocr_text="",
        has_seed=False,
        seed_phrase=None
    )

    assert temp_db.exists(file_hash="exists_hash") is True
    assert temp_db.exists(file_hash="not_exists") is False


def test_find_similar_phash(temp_db):
    # Insert a file with known phash (16 hex chars for hash_size=8)
    temp_db.insert_file(
        file_hash="hash1",
        phash="aabbccddaabbccdd",
        file_path="/test/1.png",
        file_size=100,
        ocr_text="",
        has_seed=False,
        seed_phrase=None
    )

    # Same phash should be found
    result = temp_db.find_by_phash_similarity("aabbccddaabbccdd", threshold=5)
    assert len(result) == 1


def test_get_files_with_seeds(temp_db):
    # Insert files with and without seeds
    temp_db.insert_file(
        file_hash="with_seed",
        phash="phash1",
        file_path="/test/1.png",
        file_size=100,
        ocr_text="seed phrase here",
        has_seed=True,
        seed_phrase="abandon ability"
    )
    temp_db.insert_file(
        file_hash="no_seed",
        phash="phash2",
        file_path="/test/2.png",
        file_size=100,
        ocr_text="no seed here",
        has_seed=False,
        seed_phrase=None
    )

    results = temp_db.get_files_with_seeds()
    assert len(results) == 1
    assert results[0]["file_hash"] == "with_seed"


def test_get_stats(temp_db):
    temp_db.insert_file(
        file_hash="with_seed",
        phash="phash1",
        file_path="/test/1.png",
        file_size=100,
        ocr_text="",
        has_seed=True,
        seed_phrase=None
    )
    temp_db.insert_file(
        file_hash="no_seed",
        phash="phash2",
        file_path="/test/2.png",
        file_size=100,
        ocr_text="",
        has_seed=False,
        seed_phrase=None
    )

    stats = temp_db.get_stats()
    assert stats["total_processed"] == 2
    assert stats["seeds_found"] == 1
