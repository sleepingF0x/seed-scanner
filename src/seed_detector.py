"""Seed detector module for seed scanner."""

from pathlib import Path
from typing import List, Optional


class SeedDetector:
    """Detect cryptocurrency seed phrases in text"""

    SEED_LENGTHS = [12, 24]  # Standard BIP39 seed lengths
    FUZZY_THRESHOLD = 1      # Max edit distance for fuzzy matching

    def __init__(self, wordlist_path: Path = None):
        if wordlist_path is None:
            wordlist_path = Path(__file__).parent.parent / "data" / "bip39_wordlist.txt"

        self.wordlist_path = Path(wordlist_path)
        self.wordlist = self._load_wordlist()
        self.wordlist_set = set(self.wordlist)

    def _load_wordlist(self) -> List[str]:
        """Load BIP39 wordlist from file"""
        content = self.wordlist_path.read_text()
        return [word.strip().lower() for word in content.strip().split('\n') if word.strip()]

    def detect(self, text: str, fuzzy: bool = True) -> List[List[str]]:
        """
        Detect seed phrases in text.

        Args:
            text: OCR extracted text
            fuzzy: Enable fuzzy matching for OCR errors

        Returns:
            List of detected seed phrases (each is a list of words)
        """
        # Normalize text: lowercase, split by whitespace and common separators
        # Include alphanumeric for OCR errors (like '0' instead of 'o')
        import re
        words = re.findall(r"\b[a-zA-Z0-9]+\b", text.lower())

        matches = []  # List of (start_index, length, words_tuple)

        # Slide through words looking for seed-length sequences
        # Process longer lengths first to prioritize them
        for length in sorted(self.SEED_LENGTHS, reverse=True):
            for i in range(len(words) - length + 1):
                candidate = words[i:i + length]

                if self._is_valid_seed(candidate, fuzzy):
                    normalized = tuple(self._normalize_seed(candidate, fuzzy))
                    matches.append((i, length, normalized))

        # Filter out overlapping matches, keeping longer ones
        results = []
        used_indices = set()

        # Sort by length (descending), then by start position
        for start, length, words_tuple in sorted(matches, key=lambda x: (-x[1], x[0])):
            # Check if this range overlaps with any already used
            end = start + length
            overlap = False
            for i in range(start, end):
                if i in used_indices:
                    overlap = True
                    break

            if not overlap:
                results.append(list(words_tuple))
                for i in range(start, end):
                    used_indices.add(i)

        return results

    def _is_valid_seed(self, words: List[str], fuzzy: bool) -> bool:
        """Check if word list is a valid seed phrase"""
        valid_count = 0

        for word in words:
            if word in self.wordlist_set:
                valid_count += 1
            elif fuzzy:
                # Try fuzzy matching
                if self._find_closest_word(word):
                    valid_count += 1

        # All words must be valid BIP39 words
        return valid_count == len(words)

    def _normalize_seed(self, words: List[str], fuzzy: bool) -> List[str]:
        """Normalize seed words (apply fuzzy corrections)"""
        if not fuzzy:
            return words

        return [self._find_closest_word(word) or word for word in words]

    def _find_closest_word(self, word: str) -> Optional[str]:
        """Find closest word in wordlist using Levenshtein distance"""
        if word in self.wordlist_set:
            return word

        # Only try fuzzy match for words with reasonable length
        if len(word) < 4:
            return None

        best_match = None
        best_distance = self.FUZZY_THRESHOLD + 1

        for candidate in self.wordlist:
            distance = self._levenshtein(word, candidate)
            if distance < best_distance:
                best_distance = distance
                best_match = candidate

        return best_match if best_distance <= self.FUZZY_THRESHOLD else None

    @staticmethod
    def _levenshtein(s1: str, s2: str) -> int:
        """Calculate Levenshtein distance between two strings"""
        if len(s1) < len(s2):
            return SeedDetector._levenshtein(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                # Cost is 0 if characters match, 1 otherwise
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]
