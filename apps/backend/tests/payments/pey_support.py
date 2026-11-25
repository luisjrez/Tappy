import json
from pathlib import Path
from typing import Any

import httpx2
from pydantic import SecretStr

from tappy.payments.pey import PeyQrProvider, PeySettings

FIXTURES = Path(__file__).parents[1] / "fixtures" / "pey"
FIXTURE: dict[str, Any] = json.loads((FIXTURES / "codi-qr.json").read_text())
QUERY_FIXTURE: dict[str, Any] = json.loads((FIXTURES / "codi-qr-transactions.json").read_text())
API_KEY = "test-pey-secret-0123456789abcdef"
BASE_URL = "https://pey.test"
CREATED: dict[str, Any] = FIXTURE["responses"]["201"]["default"]


def response(status: int, body: object) -> httpx2.Response:
    if isinstance(body, str):
        return httpx2.Response(status, text=body)
    return httpx2.Response(status, json=body)


class FakePey:
    def __init__(
        self,
        status: int = 201,
        body: object = None,
        error: Exception | None = None,
        pages: list[tuple[int, object]] | None = None,
    ):
        self.status = status
        self.body = CREATED if body is None else body
        self.error = error
        self.pages = pages or []
        self.requests: list[httpx2.Request] = []

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        if request.method == "GET":
            return response(*self.pages.pop(0))
        return response(self.status, self.body)

    def queries(self) -> list[httpx2.Request]:
        return [request for request in self.requests if request.method == "GET"]

    def provider(self) -> PeyQrProvider:
        settings = PeySettings(base_url=BASE_URL, api_key=SecretStr(API_KEY), timeout_seconds=5)
        return PeyQrProvider(settings, transport=httpx2.MockTransport(self.handle))
