"""Thin, testable wrapper around `aiosmtplib` (docs/10-spec-email-delivery.md).

`SmtpClient` takes already-known connection settings rather than reading
`Settings` internally, so tests can inject a fake without hitting the
network — same DI pattern as `GoogleDriveClient`
(subgraphs/ingestion/drive_client.py).
"""

from email.message import EmailMessage

import aiosmtplib

from finance_agent.config import Settings


class SmtpClient:
    def __init__(self, host: str, port: int, user: str, password: str) -> None:
        self._host = host
        self._port = port
        self._user = user
        self._password = password

    async def send(self, message: EmailMessage) -> None:
        await aiosmtplib.send(
            message,
            hostname=self._host,
            port=self._port,
            username=self._user,
            password=self._password,
            start_tls=True,
        )


def build_smtp_client(settings: Settings) -> SmtpClient:
    missing = [
        var_name
        for var_name, value in (
            ("SMTP_HOST", settings.smtp_host),
            ("SMTP_PORT", settings.smtp_port),
            ("SMTP_USER", settings.smtp_user),
            ("SMTP_PASSWORD", settings.smtp_password),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            f"Missing SMTP config: {', '.join(missing)}. "
            "Set them in backend/.env — see docs/10-spec-email-delivery.md."
        )

    return SmtpClient(
        host=settings.smtp_host,
        port=settings.smtp_port,
        user=settings.smtp_user,
        password=settings.smtp_password,
    )
