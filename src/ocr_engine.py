"""OCR engine module for seed scanner."""

from pathlib import Path
from typing import Optional


class OCREngine:
    """OCR engine using PaddleOCR"""

    def __init__(self, use_gpu: bool = False, lang: str = 'en'):
        self.use_gpu = use_gpu
        self.lang = lang
        self._ocr = None

    @property
    def ocr(self):
        """Lazy initialization of PaddleOCR"""
        if self._ocr is None:
            from paddleocr import PaddleOCR
            self._ocr = PaddleOCR(
                use_angle_cls=True,
                lang=self.lang,
                use_gpu=self.use_gpu,
                show_log=False
            )
        return self._ocr

    def extract_text(self, image_path: Path) -> str:
        """
        Extract text from image using OCR.

        Args:
            image_path: Path to image file

        Returns:
            Extracted text (joined lines)
        """
        result = self.ocr.ocr(str(image_path), cls=True)

        if not result or result[0] is None:
            return ""

        # Extract text from result structure
        lines = []
        for line in result[0]:
            if line:
                text = line[1][0]  # Text content
                confidence = line[1][1]  # Confidence score
                if confidence > 0.5:  # Filter low confidence
                    lines.append(text)

        return ' '.join(lines)

    def extract_text_with_boxes(self, image_path: Path) -> list:
        """
        Extract text with bounding box information.

        Returns:
            List of dicts: [{'text': '...', 'box': [...], 'confidence': 0.95}, ...]
        """
        result = self.ocr.ocr(str(image_path), cls=True)

        if not result or result[0] is None:
            return []

        boxes = []
        for line in result[0]:
            if line:
                boxes.append({
                    'box': line[0],
                    'text': line[1][0],
                    'confidence': line[1][1]
                })

        return boxes
