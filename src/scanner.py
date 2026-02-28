"""Scanner module for seed scanner."""

from pathlib import Path
from typing import Iterator


class ImageScanner:
    """Scan directories for image files"""

    DEFAULT_FORMATS = ['.png', '.jpg', '.jpeg', '.bmp', '.webp']

    def __init__(self, recursive: bool = True, formats: list = None):
        self.recursive = recursive
        self.supported_formats = formats or self.DEFAULT_FORMATS

    def scan_directory(self, directory: Path) -> list[Path]:
        """
        Scan directory for image files.

        Args:
            directory: Path to scan

        Returns:
            List of image file paths
        """
        directory = Path(directory)

        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")

        if not directory.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {directory}")

        images = []

        if self.recursive:
            pattern = "**/*"
        else:
            pattern = "*"

        for path in directory.glob(pattern):
            if path.is_file() and path.suffix.lower() in self.supported_formats:
                images.append(path)

        return sorted(images)

    def scan_single_file(self, file_path: Path) -> Path:
        """Validate and return a single image file path"""
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if file_path.suffix.lower() not in self.supported_formats:
            raise ValueError(f"Unsupported file format: {file_path.suffix}")

        return file_path
