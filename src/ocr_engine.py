"""OCR engine module for seed scanner."""

import logging
from pathlib import Path
from time import perf_counter

logger = logging.getLogger("seed_scanner.ocr")


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
            logger.info("Initializing PaddleOCR engine (lang=%s, gpu=%s)", self.lang, self.use_gpu)
            start = perf_counter()
            from paddleocr import PaddleOCR
            self._ocr = PaddleOCR(
                lang=self.lang if self.lang != 'en' else None,
            )
            elapsed = perf_counter() - start
            logger.info("PaddleOCR initialized in %.2fs", elapsed)
        return self._ocr

    def extract_text(self, image_path: Path) -> str:
        """
        Extract text from image using OCR.

        Args:
            image_path: Path to image file

        Returns:
            Extracted text (joined lines)
        """
        logger.debug("Starting OCR extraction: %s", image_path)
        start = perf_counter()

        try:
            result = self.ocr.ocr(str(image_path))
            elapsed = perf_counter() - start

            if not result or len(result) == 0:
                logger.warning("OCR returned empty result for: %s (%.2fs)", image_path, elapsed)
                return ""

            # Keep compatibility with both PaddleOCR response shapes:
            # 1) New shape: [{"rec_texts": [...], "rec_scores": [...]}]
            # 2) Legacy shape: [[[box, (text, score)], ...]]
            texts = []
            for page in result:
                if not page:
                    continue

                if isinstance(page, dict) and 'rec_texts' in page:
                    texts.extend(page['rec_texts'])
                    continue

                if isinstance(page, list):
                    for line in page:
                        if (
                            isinstance(line, list)
                            and len(line) >= 2
                            and isinstance(line[1], tuple)
                            and len(line[1]) >= 1
                        ):
                            texts.append(str(line[1][0]))

            extracted = ' '.join(texts)
            char_count = len(extracted)
            line_count = len(texts)

            if char_count > 0:
                logger.info("OCR success: %s (%.2fs, %d chars, %d lines)",
                           image_path.name, elapsed, char_count, line_count)
            else:
                logger.warning("OCR returned no text: %s (%.2fs)", image_path.name, elapsed)

            return extracted

        except Exception as e:
            elapsed = perf_counter() - start
            logger.error("OCR failed for %s: %s (%.2fs)", image_path, e, elapsed)
            raise

    def extract_text_with_boxes(self, image_path: Path) -> list:
        # Retained for integrations that need OCR coordinates/confidence metadata
        # instead of plain text output.
        """
        Extract text with bounding box information.

        Returns:
            List of dicts: [{'text': '...', 'box': [...], 'confidence': 0.95}, ...]
        """
        result = self.ocr.ocr(str(image_path))

        if not result or result[0] is None:
            return []

        boxes = []
        for line in result[0]:
            if isinstance(line, list) and len(line) >= 2 and line:
                boxes.append({
                    'box': line[0],
                    'text': line[1][0],
                    'confidence': line[1][1]
                })

        return boxes
