import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

from tappy.platform.config import Settings

SMTP_TIMEOUT_SECONDS = 10


@dataclass(frozen=True)
class Envelope:
    recipient: str
    subject: str
    body: str


class MailTransport(Protocol):
    def send(self, envelope: Envelope) -> None: ...


class SmtpTransport:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def send(self, envelope: Envelope) -> None:
        message = EmailMessage()
        message["From"] = self.settings.mail_from
        message["To"] = envelope.recipient
        message["Subject"] = envelope.subject
        message.set_content(envelope.body)
        with smtplib.SMTP(
            self.settings.smtp_host, self.settings.smtp_port, timeout=SMTP_TIMEOUT_SECONDS
        ) as client:
            if self.settings.smtp_starttls:
                client.starttls()
            if self.settings.smtp_username and self.settings.smtp_password:
                client.login(
                    self.settings.smtp_username, self.settings.smtp_password.get_secret_value()
                )
            client.send_message(message)
