#!/usr/bin/env python3
"""
Seed Scanner - Detect cryptocurrency seed phrases in images
"""

import argparse
import sys
from pathlib import Path
from typing import Iterator
from datetime import datetime

from src.config import Config
from src.scanner import ImageScanner
from src.db import Database
from src.hasher import FileHasher
from src.ocr_engine import OCREngine
from src.seed_detector import SeedDetector
from src.reporter import Reporter
from src.mailer import Mailer


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

        for img_path in images:
            result = self.process_image(img_path)
            if result:
                yield result

    def process_image(self, img_path: Path) -> dict:
        """Process single image"""
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
            print(f"[SKIP] {img_path} (exact duplicate)")
            return None

        # Check similar image
        if not self.config.force:
            similar = self.db.find_by_phash_similarity(phash, threshold=5)
            if similar:
                print(f"[SKIP] {img_path} (similar to {similar[0]['file_path']})")
                return None

        print(f"[OCR] {img_path}")

        # OCR
        try:
            ocr_text = self.ocr.extract_text(img_path)
            result['ocr_text'] = ocr_text
        except Exception as e:
            print(f"[ERROR] OCR failed for {img_path}: {e}")
            result['ocr_text'] = f"ERROR: {e}"

        # Detect seed phrases
        if result['ocr_text']:
            seeds = self.detector.detect(result['ocr_text'], fuzzy=True)
            if seeds:
                result['has_seed'] = True
                result['seed_phrase'] = ' '.join(seeds[0])  # Take first match
                print(f"[ALERT] Seed phrase detected in {img_path}")

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

    # Initialize pipeline
    pipeline = ScannerPipeline(config)

    # Scan target
    print(f"Starting scan of: {args.target}")
    print("=" * 60)

    results = list(pipeline.process_directory(args.target))

    # Generate reports
    output_dir = Path(config.output['directory'])
    reporter = Reporter(output_dir)

    json_path, txt_path = None, None
    if config.output['generate_json']:
        json_path = reporter.generate_json_report(results)
        print(f"\nJSON report: {json_path}")

    if config.output['generate_txt']:
        txt_path = reporter.generate_text_report(results)
        print(f"Text report: {txt_path}")

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
                print(f"Email sent to {config.mail['to_address']}")

    # Print summary
    seeds_found = [r for r in results if r['has_seed']]
    print("\n" + "=" * 60)
    print("Scan Complete")
    print(f"Total files processed: {len(results)}")
    print(f"Seed phrases found: {len(seeds_found)}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
