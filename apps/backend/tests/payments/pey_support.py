import json
from pathlib import Path
from typing import Any

import httpx2
from pydantic import SecretStr

from tappy.payments.pey import PeyQrProvider, PeySettings

FIXTURE: dict[str, Any] = json.loads(
    (Path(__file__).parents[1] / "fixtures" / "pey" / "codi-qr.json").read_text()
)
API_KEY = "test-pey-secret-0123456789abcdef"
BASE_URL = "https://pey.test"
CREATED: dict[str, Any] = FIXTURE["responses"]["201"]["default"]


class FakePey:
    def __init__(self, status: int = 201, body: object = None, error: Exception | None = None):
        self.status = status
        self.body = CREATED if body is None else body
        self.error = error
        self.requests: list[httpx2.Request] = []

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        if isinstance(self.body, str):
            return httpx2.Response(self.status, text=self.body)
        return httpx2.Response(self.status, json=self.body)

    def provider(self) -> PeyQrProvider:
        settings = PeySettings(base_url=BASE_URL, api_key=SecretStr(API_KEY), timeout_seconds=5)
        return PeyQrProvider(settings, transport=httpx2.MockTransport(self.handle))
