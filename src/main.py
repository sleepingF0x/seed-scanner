#!/usr/bin/env python3
"""
Seed Scanner - Detect cryptocurrency seed phrases in images
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Iterator
from datetime import datetime
from time import perf_counter

from src.config import Config
from src.scanner import ImageScanner
from src.db import Database
from src.hasher import FileHasher
from src.ocr_engine import OCREngine
from src.seed_detector import SeedDetector
from src.reporter import Reporter
from src.mailer import Mailer
from src.logger import setup_logging

logger = logging.getLogger("seed_scanner")


def parse_args(args=None):
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Scan images for cryptocurrency seed phrases'
    )
    parser.add_argument(
        'target',
        type=Path,
        help='Directory or file to scan'
    )
    parser.add_argument(
        '--config', '-c',
        type=Path,
        help='Path to config file'
    )
    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Force re-scan, ignore database records'
    )
    parser.add_argument(
        '--output', '-o',
        type=Path,
        help='Output directory for reports'
    )
    parser.add_argument(
        '--no-mail',
        action='store_true',
        help='Disable email notification'
    )
    parser.add_argument(
        '--log-level', '-l',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level (default: INFO)'
    )
    return parser.parse_args(args)


class ScannerPipeline:
    """Main scanning pipeline coordinating all components"""

    def __init__(self, config: Config):
        self.config = config
        self.db = Database(Path(config.database['path']))
        self.hasher = FileHasher()
        self.ocr = OCREngine(
            use_gpu=config.ocr['use_gpu'],
            lang=config.ocr['lang']
        )
        self.detector = SeedDetector()
        self.results = []

    def process_directory(self, target: Path) -> Iterator[dict]:
        """Process all images in directory"""
        scanner = ImageScanner(
            recursive=self.config.scanner['recursive'],
            formats=self.config.scanner['supported_formats']
        )

        images = scanner.scan_directory(target)
        image_list = list(images)
        total = len(image_list)
        logger.info("Found %d images to process in %s", total, target)

        for idx, img_path in enumerate(image_list, 1):
            logger.debug("Processing [%d/%d]: %s", idx, total, img_path)
            result = self.process_image(img_path)
            if result:
                yield result

    def process_image(self, img_path: Path) -> dict:
        """Process single image"""
        logger.debug("Processing image: %s", img_path)
        file_hash = self.hasher.calculate_file_hash(img_path)
        phash = self.hasher.calculate_phash(img_path)

        result = {
            'file_path': str(img_path),
            'file_hash': file_hash,
            'phash': phash,
            'file_size': img_path.stat().st_size,
            'ocr_text': '',
            'has_seed': False,
            'seed_phrase': None
        }

        # Check exact duplicate
        if not self.config.force and self.db.exists(file_hash=file_hash):
            logger.debug("Skip %s (exact duplicate)", img_path.name)
            return None

        # Check similar image
        if not self.config.force:
            similar = self.db.find_by_phash_similarity(phash, threshold=5)
            if similar:
                logger.debug("Skip %s (similar to %s)", img_path.name, similar[0]['file_path'])
                return None

        logger.info("OCR processing: %s", img_path)

        # OCR
        try:
            ocr_text = self.ocr.extract_text(img_path)
            result['ocr_text'] = ocr_text
        except Exception as e:
            logger.error("OCR failed for %s: %s", img_path, e)
            result['ocr_text'] = f"ERROR: {e}"

        # Detect seed phrases
        if result['ocr_text']:
            seeds = self.detector.detect(result['ocr_text'], fuzzy=True)
            if seeds:
                result['has_seed'] = True
                result['seed_phrase'] = ' '.join(seeds[0])  # Take first match
                logger.warning("SEED PHRASE DETECTED in %s", img_path)

        # Save to database
        self.db.insert_file(
            file_hash=result['file_hash'],
            phash=result['phash'],
            file_path=result['file_path'],
            file_size=result['file_size'],
            ocr_text=result['ocr_text'],
            has_seed=result['has_seed'],
            seed_phrase=result['seed_phrase']
        )

        return result


def main():
    """Main entry point"""
    args = parse_args()

    # Setup logging
    setup_logging(args.log_level)

    # Load configuration
    if args.config and args.config.exists():
        config = Config.from_file(args.config)
    else:
        config = Config()

    # Merge command line arguments
    cli_args = {
        'force': args.force,
        'output': {'directory': str(args.output)} if args.output else None
    }
    config.merge_args({k: v for k, v in cli_args.items() if v is not None})

    logger.info("=" * 60)
    logger.info("Seed Scanner starting")
    logger.info("Target: %s", args.target)
    logger.info("Log level: %s", args.log_level)
    logger.info("=" * 60)

    start_time = perf_counter()

    # Initialize pipeline
    pipeline = ScannerPipeline(config)

    # Scan target
    results = list(pipeline.process_directory(args.target))

    elapsed = perf_counter() - start_time
    logger.info("Scan completed in %.2f seconds", elapsed)

    # Generate reports
    output_dir = Path(config.output['directory'])
    reporter = Reporter(output_dir)

    json_path, txt_path = None, None
    if config.output['generate_json']:
        json_path = reporter.generate_json_report(results)
        logger.info("JSON report: %s", json_path)

    if config.output['generate_txt']:
        txt_path = reporter.generate_text_report(results)
        logger.info("Text report: %s", txt_path)

    # Send email
    if config.mail['enabled'] and not args.no_mail:
        mailer = Mailer(**config.mail)

        seeds_found = [r for r in results if r['has_seed']]
        subject = config.mail['subject']
        body = f"""
Seed Scanner Report
==================
Scan time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Total files: {len(results)}
Seeds found: {len(seeds_found)}

See attached report for details.
        """.strip()

        attachment = txt_path or json_path
        if attachment:
            success = mailer.send_report(subject, body, attachment)
            if success:
                logger.info("Email sent to %s", config.mail['to_address'])

    # Print summary
    seeds_found = [r for r in results if r['has_seed']]
    logger.info("=" * 60)
    logger.info("Scan Complete")
    logger.info("Total files processed: %d", len(results))
    logger.info("Seed phrases found: %d", len(seeds_found))
    logger.info("Total time: %.2f seconds", elapsed)

    return 0


if __name__ == '__main__':
    sys.exit(main())
