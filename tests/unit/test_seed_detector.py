"""Tests for seed_detector module."""

import pytest
from pathlib import Path
from src.seed_detector import SeedDetector


@pytest.fixture
def detector():
    return SeedDetector(wordlist_path=Path("data/bip39_wordlist.txt"))


def test_load_wordlist(detector):
    assert len(detector.wordlist) == 2048
    assert "abandon" in detector.wordlist
    assert "zoo" in detector.wordlist


def test_detect_exact_12_words(detector):
    # Valid 12-word seed phrase
    text = "abandon ability able about above absent absorb abstract absurd abuse access accident"
    results = detector.detect(text)

    assert len(results) == 1
    assert len(results[0]) == 12
    assert results[0][0] == "abandon"


def test_detect_exact_24_words(detector):
    # Valid 24-word seed phrase
    text = ("abandon ability able about above absent absorb abstract absurd abuse access "
            "accident account accuse achieve acid acoustic acquire across act action actor actress actual")
    results = detector.detect(text)

    assert len(results) == 1
    assert len(results[0]) == 24


def test_detect_multiple_phrases(detector):
    text = ("abandon ability able about above absent absorb abstract absurd abuse access "
            "hello world some other text "
            "zoo zone zero year youth you young zone zoo zone zero")

    results = detector.detect(text)
    # Should detect the 12-word phrase at the start
    assert len(results) >= 1


def test_no_detection(detector):
    text = "hello world this is just some random text without any seed words"
    results = detector.detect(text)
    assert len(results) == 0


def test_fuzzy_match_with_typo(detector):
    # "aband0n" with zero instead of 'o'
    text = "aband0n ability able about above absent absorb abstract absurd abuse access accident"
    results = detector.detect(text, fuzzy=True)

    assert len(results) == 1
    assert results[0][0] == "abandon"  # Should correct the typo


def test_levenshtein_distance(detector):
    assert detector._levenshtein("abandon", "abandon") == 0
    assert detector._levenshtein("abandon", "aband0n") == 1
    assert detector._levenshtein("word", "w0rd") == 1
    assert detector._levenshtein("hello", "hallo") == 1


def test_fuzzy_threshold(detector):
    # Too different, should not match
    text = "abcd1234 xyz9999 ..."  # Gibberish
    results = detector.detect(text, fuzzy=True)
    assert len(results) == 0
