import base64
import hashlib

from cryptography.fernet import Fernet

from tappy.platform.config import Settings

PURPOSE = b"tappy-outbound-email-v1"


class Sealer:
    def __init__(self, secret: str) -> None:
        key = hashlib.sha256(PURPOSE + secret.encode()).digest()
        self.fernet = Fernet(base64.urlsafe_b64encode(key))

    @classmethod
    def from_settings(cls, settings: Settings) -> Sealer:
        return cls(settings.secret_key.get_secret_value())

    def seal(self, text: str) -> str:
        return self.fernet.encrypt(text.encode()).decode()

    def open(self, sealed: str) -> str:
        return self.fernet.decrypt(sealed.encode()).decode()
