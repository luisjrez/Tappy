from typing import Annotated

from fastapi import Depends, Request

from tappy.payments.provider import QrProvider


def get_qr_provider(request: Request) -> QrProvider:
    provider: QrProvider = request.app.state.qr_provider
    return provider


QrProviderDependency = Annotated[QrProvider, Depends(get_qr_provider)]
