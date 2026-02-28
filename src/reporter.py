"""Reporter module for seed scanner."""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any


class Reporter:
    """Generate scan reports in JSON and text formats"""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_json_report(self, results: List[Dict[str, Any]]) -> Path:
        """Generate JSON format report"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self.output_dir / f"scan_result_{timestamp}.json"

        seeds_found = [r for r in results if r.get("has_seed")]

        report = {
            "scan_time": datetime.now().isoformat(),
            "total_files": len(results),
            "seeds_found": len(seeds_found),
            "results": results
        }

        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        return report_path

    def generate_text_report(self, results: List[Dict[str, Any]]) -> Path:
        """Generate human-readable text report"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self.output_dir / f"scan_result_{timestamp}.txt"

        seeds_found = [r for r in results if r.get("has_seed")]

        lines = [
            "=" * 60,
            "助记词扫描报告 / Seed Phrase Scan Report",
            "=" * 60,
            f"扫描时间 / Scan Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"扫描文件总数 / Total Files: {len(results)}",
            f"发现助记词 / Seeds Found: {len(seeds_found)}",
            "=" * 60,
            "",
        ]

        if seeds_found:
            lines.append("⚠️  检测到的助记词 / Detected Seed Phrases:")
            lines.append("-" * 60)

            for i, result in enumerate(seeds_found, 1):
                lines.append(f"\n[{i}]")
                lines.append(f"  文件路径 / File: {result['file_path']}")
                lines.append(f"  助记词 / Seed: {result['seed_phrase']}")
                lines.append("")
        else:
            lines.append("✅ 未发现助记词 / No seed phrases detected.")

        lines.extend([
            "",
            "=" * 60,
            "详细结果 / Detailed Results:",
            "=" * 60,
            ""
        ])

        for result in results:
            status = "🚨 SEED" if result.get("has_seed") else "  -"
            lines.append(f"{status} {result['file_path']}")

        report_path.write_text('\n'.join(lines), encoding='utf-8')
        return report_path

    def generate_both(self, results: List[Dict[str, Any]]) -> tuple[Path, Path]:
        """Generate both JSON and text reports"""
        json_path = self.generate_json_report(results)
        text_path = self.generate_text_report(results)
        return json_path, text_path
