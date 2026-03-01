"""OCR engine module for seed scanner."""

import logging
import os
import inspect
from pathlib import Path
from time import perf_counter

logger = logging.getLogger("seed_scanner.ocr")


class OCREngine:
    """OCR engine using PaddleOCR"""

    def __init__(self, use_gpu: bool = False, lang: str = 'en'):
        self.use_gpu = use_gpu
        self.lang = lang
        self._ocr = None
        self._safe_mode_enabled = False

    def _build_ocr_engine(self, safe_mode: bool = False):
        """Build a PaddleOCR instance with optional compatibility-safe settings."""
        from paddleocr import PaddleOCR
        kwargs = self._build_ocr_kwargs(PaddleOCR, safe_mode=safe_mode)
        return PaddleOCR(**kwargs)

    def _build_ocr_kwargs(self, constructor, safe_mode: bool) -> dict:
        kwargs = {
            "lang": self.lang if self.lang != 'en' else None,
        }

        optional_kwargs = {
            "use_gpu": self.use_gpu,
        }
        if safe_mode:
            # Workaround for Paddle runtime incompatibilities in some CPU builds.
            optional_kwargs["enable_mkldnn"] = False

        try:
            supported = set(inspect.signature(constructor).parameters)
        except (TypeError, ValueError):
            supported = set()

        for key, value in optional_kwargs.items():
            if key in supported:
                kwargs[key] = value

        return kwargs

    @staticmethod
    def _is_paddle_onednn_runtime_error(exc: Exception) -> bool:
        message = str(exc)
        return (
            "ConvertPirAttribute2RuntimeAttribute not support" in message
            or "onednn_instruction.cc" in message
        )

    @property
    def ocr(self):
        """Lazy initialization of PaddleOCR"""
        if self._ocr is None:
            logger.info("Initializing PaddleOCR engine (lang=%s, gpu=%s)", self.lang, self.use_gpu)
            start = perf_counter()
            self._ocr = self._build_ocr_engine(safe_mode=self._safe_mode_enabled)
            elapsed = perf_counter() - start
            logger.info("PaddleOCR initialized in %.2fs", elapsed)
        return self._ocr

    def _retry_with_safe_runtime(self, image_path: Path) -> str:
        logger.warning(
            "Retrying OCR with safe runtime settings for: %s",
            image_path.name,
        )
        self._safe_mode_enabled = True
        os.environ["FLAGS_use_mkldnn"] = "0"
        self._ocr = self._build_ocr_engine(safe_mode=True)
        result = self._ocr.ocr(str(image_path))
        return self._extract_text_from_result(result)

    @staticmethod
    def _extract_text_from_result(result) -> str:
        if not result or len(result) == 0:
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

        return ' '.join(texts)

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
        except Exception as e:
            if self._is_paddle_onednn_runtime_error(e) and not self._safe_mode_enabled:
                result = self._retry_with_safe_runtime(image_path)
                elapsed = perf_counter() - start
                if result:
                    logger.info("OCR success after safe retry: %s (%.2fs)", image_path.name, elapsed)
                else:
                    logger.warning("OCR safe retry returned no text: %s (%.2fs)", image_path.name, elapsed)
                return result

            elapsed = perf_counter() - start
            logger.error("OCR failed for %s: %s (%.2fs)", image_path, e, elapsed)
            raise

        try:
            elapsed = perf_counter() - start
            extracted = self._extract_text_from_result(result)
            if not extracted:
                logger.warning("OCR returned empty result for: %s (%.2fs)", image_path, elapsed)
                return ""
            char_count = len(extracted)
            line_count = len(extracted.split())

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
