"""Tests for mailer module."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from src.mailer import Mailer


def test_mailer_initialization():
    mailer = Mailer(
        smtp_server="smtp.qq.com",
        smtp_port=587,
        username="test@qq.com",
        password="secret",
        to_address="recv@example.com"
    )
    assert mailer.smtp_server == "smtp.qq.com"


@patch('smtplib.SMTP')
def test_send_report(mock_smtp_class):
    mock_smtp = Mock()
    mock_smtp_class.return_value.__enter__ = Mock(return_value=mock_smtp)
    mock_smtp_class.return_value.__exit__ = Mock(return_value=False)

    mailer = Mailer(
        smtp_server="smtp.qq.com",
        smtp_port=587,
        username="test@qq.com",
        password="secret",
        to_address="recv@example.com"
    )

    # Mock file content
    mock_report = Mock()
    mock_report.read_bytes.return_value = b"Test report content"
    mock_report.exists.return_value = True

    result = mailer.send_report(
        subject="Test Report",
        body="See attached report",
        attachment=mock_report
    )

    assert result is True
    mock_smtp.starttls.assert_called_once()
    mock_smtp.login.assert_called_once_with("test@qq.com", "secret")
    mock_smtp.send_message.assert_called_once()


def test_mailer_disabled():
    mailer = Mailer(enabled=False)
    result = mailer.send_report(subject="Test", body="Body")
    assert result is False
