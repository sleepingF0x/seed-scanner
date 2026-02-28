"""Configuration management for seed scanner."""

from pathlib import Path
from typing import Any, Dict, Optional
import yaml


class Config:
    """Configuration management"""

    DEFAULTS = {
        'scanner': {
            'supported_formats': ['.png', '.jpg', '.jpeg', '.bmp', '.webp'],
            'recursive': True
        },
        'ocr': {
            'use_gpu': False,
            'lang': 'en'
        },
        'detection': {
            'seed_lengths': [12, 24],
            'fuzzy_threshold': 1
        },
        'mail': {
            'enabled': False,
            'smtp_server': 'smtp.qq.com',
            'smtp_port': 587,
            'username': '',
            'password': '',
            'to_address': '',
            'subject': '助记词扫描结果 / Seed Scanner Report'
        },
        'output': {
            'directory': './output',
            'generate_json': True,
            'generate_txt': True
        },
        'database': {
            'path': './data/seed_scanner.db'
        },
        'force': False  # Command line only
    }

    def __init__(self, data: Optional[Dict] = None):
        self._config = self._deep_merge(self.DEFAULTS.copy(), data or {})

    @classmethod
    def from_file(cls, path: Path) -> 'Config':
        """Load config from YAML file"""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        data = yaml.safe_load(path.read_text())
        return cls(data)

    def merge_args(self, args: Dict[str, Any]):
        """Merge command line arguments"""
        for key, value in args.items():
            if value is not None:
                self._config[key] = value

    def _deep_merge(self, base: Dict, update: Dict) -> Dict:
        """Deep merge two dictionaries"""
        result = base.copy()
        for key, value in update.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    @property
    def scanner(self) -> Dict:
        return self._config['scanner']

    @property
    def ocr(self) -> Dict:
        return self._config['ocr']

    @property
    def detection(self) -> Dict:
        return self._config['detection']

    @property
    def mail(self) -> Dict:
        return self._config['mail']

    @property
    def output(self) -> Dict:
        return self._config['output']

    @property
    def database(self) -> Dict:
        return self._config['database']

    @property
    def force(self) -> bool:
        return self._config.get('force', False)

    def __getitem__(self, key: str) -> Any:
        return self._config[key]
