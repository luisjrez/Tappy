import uuid
from http import HTTPStatus

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette_admin.flash import flash, get_flashed_messages
from starlette_admin.routing import route
from starlette_admin.views import CustomView

from tappy.identity.errors import IdentityError
from tappy.identity.operators import create_operator, deactivate_operator, list_operators
from tappy.identity.provisioning import IdentitySummary
from tappy.platform.clock import Clock
from tappy.platform.database import Database

OPERATORS_PATH = "/operators"


class OperatorsView(CustomView):
    menu_label = "Operators"
    icon = "fa fa-users"
    path = OPERATORS_PATH

    def __init__(self, database: Database, clock: Clock, admin_base_url: str) -> None:
        super().__init__()
        self.database = database
        self.clock = clock
        self.operators_url = f"{admin_base_url}{OPERATORS_PATH}"

    def operators(self) -> list[IdentitySummary]:
        with self.database.transaction() as db:
            return list_operators(db)

    def register(self, email: str, initial_password: str) -> IdentitySummary:
        with self.database.transaction() as db:
            return create_operator(db, email, initial_password)

    def retire(self, reference: uuid.UUID) -> IdentitySummary:
        with self.database.transaction() as db:
            return deactivate_operator(db, reference, self.clock.now())

    def back_to_list(self) -> Response:
        return RedirectResponse(self.operators_url, status_code=HTTPStatus.SEE_OTHER)

    @route("")
    async def index(self, request: Request) -> Response:
        if self.templates is None:
            raise RuntimeError("OperatorsView must be mounted before rendering")
        return self.templates.TemplateResponse(
            request=request,
            name="operators.html",
            context={
                "title": self.menu_label,
                "operators": await run_in_threadpool(self.operators),
                "operators_url": self.operators_url,
                "flashed_messages": get_flashed_messages(request),
            },
        )

    @route("/create", methods=["POST"])
    async def submit_creation(self, request: Request) -> Response:
        form = await request.form()
        email = str(form.get("email") or "")
        initial_password = str(form.get("initial_password") or "")
        try:
            created = await run_in_threadpool(self.register, email, initial_password)
        except IdentityError as error:
            flash(request, str(error), "error")
        else:
            flash(request, f"Operator {created.email} created", "success")
        return self.back_to_list()

    @route("/{reference:uuid}/deactivate", methods=["POST"])
    async def submit_deactivation(self, request: Request) -> Response:
        reference: uuid.UUID = request.path_params["reference"]
        try:
            operator = await run_in_threadpool(self.retire, reference)
        except IdentityError as error:
            flash(request, str(error), "error")
        else:
            flash(request, f"Operator {operator.email} deactivated", "success")
        return self.back_to_list()
