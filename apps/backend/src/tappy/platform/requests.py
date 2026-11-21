from starlette.requests import Request

UNKNOWN_ORIGIN = "unknown"


def client_origin(request: Request) -> str:
    return request.client.host if request.client else UNKNOWN_ORIGIN
