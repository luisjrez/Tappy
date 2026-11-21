import secrets
from http import HTTPStatus
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from tappy.identity.dependencies import RecoveryDependency
from tappy.identity.errors import InvalidResetLinkError, PasswordPolicyError
from tappy.identity.recovery import RESET_PATH
from tappy.platform.dependencies import ClockDependency, SessionDependency

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
MISMATCH = "Passwords do not match"


def page(
    request: Request,
    *,
    changed: bool = False,
    error: str = "",
    status_code: int = HTTPStatus.OK,
) -> HTMLResponse:
    nonce = secrets.token_urlsafe(16)
    response = templates.TemplateResponse(
        request=request,
        name="password_reset_page.html",
        context={"nonce": nonce, "changed": changed, "error": error},
        status_code=status_code,
    )
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = (
        f"default-src 'none'; script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; "
        "form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
    )
    return response


@router.get(RESET_PATH)
def show(request: Request) -> HTMLResponse:
    return page(request)


@router.post(RESET_PATH)
async def submit(
    request: Request,
    db: SessionDependency,
    clock: ClockDependency,
    recovery: RecoveryDependency,
) -> HTMLResponse:
    form = await request.form()
    token, new_password, confirmation = (
        value if isinstance(value, str) else ""
        for value in (form.get("token"), form.get("new_password"), form.get("confirm_password"))
    )
    if new_password != confirmation:
        return page(request, error=MISMATCH, status_code=HTTPStatus.UNPROCESSABLE_CONTENT)
    try:
        recovery.confirm(db, token, new_password, clock.now())
    except InvalidResetLinkError as error:
        return page(request, error=str(error), status_code=HTTPStatus.BAD_REQUEST)
    except PasswordPolicyError as error:
        return page(request, error=str(error), status_code=HTTPStatus.UNPROCESSABLE_CONTENT)
    return page(request, changed=True)
