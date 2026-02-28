"""Mailer module for seed scanner."""

import smtplib
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional


class Mailer:
    """Send scan reports via email"""

    def __init__(
        self,
        smtp_server: str = "smtp.qq.com",
        smtp_port: int = 587,
        username: str = "",
        password: str = "",
        to_address: str = "",
        enabled: bool = True
    ):
        self.enabled = enabled
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.to_address = to_address

    def send_report(
        self,
        subject: str,
        body: str,
        attachment: Optional[Path] = None,
        attachment_name: Optional[str] = None
    ) -> bool:
        """
        Send report email with optional attachment.

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            return False

        if not all([self.username, self.password, self.to_address]):
            print("Mail configuration incomplete, skipping email notification")
            return False

        msg = MIMEMultipart()
        msg['From'] = self.username
        msg['To'] = self.to_address
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        if attachment and attachment.exists():
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read_bytes())
            encoders.encode_base64(part)

            filename = attachment_name or attachment.name
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {filename}'
            )
            msg.attach(part)

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            return True
        except Exception as e:
            print(f"Failed to send email: {e}")
            return False
