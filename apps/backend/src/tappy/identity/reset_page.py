import secrets
from http import HTTPStatus
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from tappy.identity.dependencies import RecoveryDependency
from tappy.identity.errors import InvalidResetLinkError, PasswordPolicyError
from tappy.identity.recovery import RESET_PATH
from tappy.platform.dependencies import ClockDependency, SessionDependency, SettingsDependency

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
MISMATCH = "Passwords do not match"
MALFORMED = "The form could not be processed"


class ResetForm(BaseModel):
    model_config = ConfigDict(extra="ignore")

    token: str = Field(max_length=256)
    new_password: str = Field(min_length=1, max_length=1024)
    confirm_password: str = Field(min_length=1, max_length=1024)


class PageState(BaseModel):
    changed: bool = False
    error: str = ""
    link_invalid: bool = False
    status_code: int = HTTPStatus.OK


def page(request: Request, recovery: RecoveryDependency, state: PageState) -> HTMLResponse:
    nonce = secrets.token_urlsafe(16)
    response = templates.TemplateResponse(
        request=request,
        name="password_reset_page.html",
        context={
            "nonce": nonce,
            "changed": state.changed,
            "error": state.error,
            "link_invalid": state.link_invalid,
            "reset_path": RESET_PATH,
            "minimum_length": recovery.password_policy.minimum_length,
            "maximum_length": recovery.password_policy.maximum_length,
        },
        status_code=state.status_code,
    )
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = (
        f"default-src 'none'; script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; "
        "form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
    )
    return response


def foreign_origin(request: Request, allowed: str) -> bool:
    origin = request.headers.get("origin")
    return origin is not None and origin != allowed


@router.get(RESET_PATH)
def show(request: Request, recovery: RecoveryDependency) -> HTMLResponse:
    return page(request, recovery, PageState())


@router.post(RESET_PATH)
async def submit(
    request: Request,
    db: SessionDependency,
    clock: ClockDependency,
    recovery: RecoveryDependency,
    settings: SettingsDependency,
) -> HTMLResponse:
    if foreign_origin(request, settings.public_base_url):
        return page(request, recovery, PageState(error=MALFORMED, status_code=HTTPStatus.FORBIDDEN))
    try:
        form = ResetForm.model_validate(dict(await request.form()))
    except ValidationError:
        state = PageState(error=MALFORMED, status_code=HTTPStatus.UNPROCESSABLE_CONTENT)
        return page(request, recovery, state)
    if form.new_password != form.confirm_password:
        state = PageState(error=MISMATCH, status_code=HTTPStatus.UNPROCESSABLE_CONTENT)
        return page(request, recovery, state)
    try:
        recovery.confirm(db, form.token, form.new_password, clock.now())
    except InvalidResetLinkError as error:
        state = PageState(error=str(error), link_invalid=True, status_code=HTTPStatus.BAD_REQUEST)
        return page(request, recovery, state)
    except PasswordPolicyError as error:
        state = PageState(error=str(error), status_code=HTTPStatus.UNPROCESSABLE_CONTENT)
        return page(request, recovery, state)
    return page(request, recovery, PageState(changed=True))
