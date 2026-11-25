import uuid
from http import HTTPStatus

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette_admin.flash import flash, get_flashed_messages
from starlette_admin.routing import route
from starlette_admin.views import CustomView

from tappy.backoffice.auth import admin_identity
from tappy.backoffice.sales import pesos
from tappy.identity.provisioning import IdentitySummary
from tappy.platform.clock import Clock
from tappy.platform.database import Database
from tappy.sales.errors import ExceptionNotFoundError, SaleError
from tappy.sales.exception_review import (
    ExceptionDetail,
    NoteView,
    RequestedReconciliation,
    add_note,
    read_exception,
    request_reconciliation,
)
from tappy.sales.models import NOTE_MAX_LENGTH
from tappy.sales.payment_exceptions import OpenException, open_exceptions

EXCEPTIONS_PATH = "/exceptions"


class ExceptionsView(CustomView):
    menu_label = "Incidents"
    icon = "fa fa-triangle-exclamation"
    path = EXCEPTIONS_PATH

    def __init__(self, database: Database, clock: Clock, admin_base_url: str) -> None:
        super().__init__()
        self.database = database
        self.clock = clock
        self.exceptions_url = f"{admin_base_url}{EXCEPTIONS_PATH}"
        self.sales_url = f"{admin_base_url}/sales"

    def list_open(self) -> list[OpenException]:
        with self.database.transaction() as db:
            return open_exceptions(db)

    def detail_of(self, exception_id: uuid.UUID) -> ExceptionDetail:
        with self.database.transaction() as db:
            return read_exception(db, exception_id)

    def note(self, actor: IdentitySummary, exception_id: uuid.UUID, text: str) -> NoteView:
        with self.database.transaction() as db:
            return add_note(db, actor, exception_id, text, self.clock.now())

    def reconcile(self, actor: IdentitySummary, exception_id: uuid.UUID) -> RequestedReconciliation:
        with self.database.transaction() as db:
            return request_reconciliation(db, actor, exception_id, self.clock.now())

    def render(
        self, request: Request, name: str, context: dict[str, object], status: int = HTTPStatus.OK
    ) -> Response:
        if self.templates is None:
            raise RuntimeError("ExceptionsView must be mounted before rendering")
        return self.templates.TemplateResponse(
            request=request,
            name=name,
            context={
                "title": self.menu_label,
                "exceptions_url": self.exceptions_url,
                "sales_url": self.sales_url,
                "pesos": pesos,
                "note_max_length": NOTE_MAX_LENGTH,
                "flashed_messages": get_flashed_messages(request),
            }
            | context,
            status_code=status,
        )

    def back_to(self, exception_id: uuid.UUID) -> Response:
        return RedirectResponse(
            f"{self.exceptions_url}/{exception_id}", status_code=HTTPStatus.SEE_OTHER
        )

    @route("")
    async def index(self, request: Request) -> Response:
        admin_identity(request)
        items = await run_in_threadpool(self.list_open)
        return self.render(request, "exceptions.html", {"exceptions": items})

    @route("/{exception_id:uuid}")
    async def detail(self, request: Request) -> Response:
        admin_identity(request)
        exception_id: uuid.UUID = request.path_params["exception_id"]
        try:
            detail = await run_in_threadpool(self.detail_of, exception_id)
        except ExceptionNotFoundError as error:
            return self.render(request, "exception.html", {"problem": str(error)}, 404)
        return self.render(request, "exception.html", {"incident": detail})

    @route("/{exception_id:uuid}/notes", methods=["POST"])
    async def submit_note(self, request: Request) -> Response:
        actor = admin_identity(request)
        exception_id: uuid.UUID = request.path_params["exception_id"]
        form = await request.form()
        try:
            await run_in_threadpool(self.note, actor, exception_id, str(form.get("text") or ""))
        except SaleError as error:
            flash(request, str(error), "error")
        else:
            flash(request, "Note added", "success")
        return self.back_to(exception_id)

    @route("/{exception_id:uuid}/reconciliation", methods=["POST"])
    async def submit_reconciliation(self, request: Request) -> Response:
        actor = admin_identity(request)
        exception_id: uuid.UUID = request.path_params["exception_id"]
        try:
            requested = await run_in_threadpool(self.reconcile, actor, exception_id)
        except SaleError as error:
            flash(request, str(error), "error")
        else:
            flash(request, f"Reconciliation {requested.outcome.replace('_', ' ')}", "success")
        return self.back_to(exception_id)
