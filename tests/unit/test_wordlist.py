"""Tests for BIP39 wordlist."""


def test_wordlist_has_2048_words():
    """Verify wordlist has exactly 2048 words."""
    with open("data/bip39_wordlist.txt") as f:
        words = [line.strip() for line in f if line.strip()]
    assert len(words) == 2048


def test_wordlist_all_lowercase():
    """Verify all words are lowercase."""
    with open("data/bip39_wordlist.txt") as f:
        words = [line.strip() for line in f if line.strip()]
    for word in words:
        assert word.islower(), f"Word '{word}' is not lowercase"


def test_wordlist_no_duplicates():
    """Verify no duplicate words."""
    with open("data/bip39_wordlist.txt") as f:
        words = [line.strip() for line in f if line.strip()]
    assert len(words) == len(set(words))


def test_wordlist_has_known_words():
    """Verify known BIP39 words are present."""
    with open("data/bip39_wordlist.txt") as f:
        words = set(line.strip() for line in f if line.strip())

    # Check some known BIP39 words
    assert "abandon" in words
    assert "ability" in words
    assert "zoo" in words
    assert "zone" in words
    assert "zero" in words
