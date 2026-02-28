"""Hasher module for seed scanner."""

import hashlib
from pathlib import Path
import imagehash
from PIL import Image


class FileHasher:
    """Calculate file and perceptual hashes for images"""

    @staticmethod
    def calculate_file_hash(file_path: Path) -> str:
        """Calculate SHA256 hash of file contents"""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    @staticmethod
    def calculate_phash(file_path: Path) -> str:
        """Calculate perceptual hash (pHash) of image"""
        with Image.open(file_path) as img:
            # Convert to RGB if necessary
            if img.mode != 'RGB':
                img = img.convert('RGB')
            phash = imagehash.phash(img)
            return str(phash)

    @staticmethod
    def hamming_distance(hash1: str, hash2: str) -> int:
        """Calculate Hamming distance between two phash strings"""
        h1 = imagehash.hex_to_hash(hash1)
        h2 = imagehash.hex_to_hash(hash2)
        return h1 - h2
