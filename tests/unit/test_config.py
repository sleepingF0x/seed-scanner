"""Tests for config module."""

import pytest
from pathlib import Path
from src.config import Config


def test_default_config():
    config = Config()
    assert config.scanner['recursive'] is True
    assert '.png' in config.scanner['supported_formats']


def test_load_from_dict():
    data = {
        'scanner': {'recursive': False},
        'ocr': {'use_gpu': True}
    }
    config = Config(data)
    assert config.scanner['recursive'] is False
    assert config.ocr['use_gpu'] is True


def test_load_from_yaml(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
scanner:
  recursive: false
  supported_formats: [".png", ".jpg"]

mail:
  enabled: true
  username: "test@qq.com"
""")

    config = Config.from_file(config_file)
    assert config.scanner['recursive'] is False
    assert config.mail['username'] == "test@qq.com"


def test_merge_command_line_args():
    config = Config()
    config.merge_args({'scanner': {'recursive': False}, 'force': True})

    assert config.scanner['recursive'] is False
    assert config.force is True
