"""Tests for reporter module."""

import pytest
import json
from pathlib import Path
from datetime import datetime
from src.reporter import Reporter


@pytest.fixture
def sample_results():
    return [
        {
            "file_path": "/path/to/seed1.png",
            "file_hash": "abc123",
            "phash": "def456",
            "ocr_text": "abandon ability able about",
            "has_seed": True,
            "seed_phrase": "abandon ability able about above absent absorb abstract absurd abuse access accident"
        },
        {
            "file_path": "/path/to/none.png",
            "file_hash": "xyz789",
            "phash": "uvw012",
            "ocr_text": "some random text",
            "has_seed": False,
            "seed_phrase": None
        }
    ]


def test_generate_json_report(tmp_path, sample_results):
    output_dir = tmp_path / "output"
    reporter = Reporter(output_dir=output_dir)

    report_path = reporter.generate_json_report(sample_results)

    assert report_path.exists()
    assert report_path.suffix == ".json"

    data = json.loads(report_path.read_text())
    assert "scan_time" in data
    assert "total_files" in data
    assert "seeds_found" in data
    assert len(data["results"]) == 2


def test_generate_text_report(tmp_path, sample_results):
    output_dir = tmp_path / "output"
    reporter = Reporter(output_dir=output_dir)

    report_path = reporter.generate_text_report(sample_results)

    assert report_path.exists()
    assert report_path.suffix == ".txt"

    content = report_path.read_text()
    assert "助记词扫描报告" in content or "Seed Phrase Scan Report" in content
    assert "seed1.png" in content
    assert "abandon ability able" in content


def test_empty_results(tmp_path):
    reporter = Reporter(output_dir=tmp_path)

    report_path = reporter.generate_json_report([])
    data = json.loads(report_path.read_text())
    assert data["total_files"] == 0
    assert data["seeds_found"] == 0


def test_generate_both_reports(tmp_path, sample_results):
    reporter = Reporter(output_dir=tmp_path)
    json_path, text_path = reporter.generate_both(sample_results)

    assert json_path.exists()
    assert text_path.exists()
    assert json_path.suffix == ".json"
    assert text_path.suffix == ".txt"
