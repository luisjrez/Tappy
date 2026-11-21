import uuid
from http import HTTPStatus

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette_admin.flash import flash, get_flashed_messages
from starlette_admin.routing import route
from starlette_admin.views import CustomView

from tappy.identity.models import IdentityStatus
from tappy.identity.operators import list_operators
from tappy.identity.provisioning import IdentitySummary
from tappy.merchants.errors import MerchantError
from tappy.merchants.service import (
    MerchantView,
    assign_operator,
    create_merchant,
    list_all_merchants,
)
from tappy.platform.clock import Clock
from tappy.platform.database import Database

MERCHANTS_PATH = "/merchants"


class MerchantsView(CustomView):
    menu_label = "Merchants"
    icon = "fa fa-store"
    path = MERCHANTS_PATH

    def __init__(self, database: Database, clock: Clock, admin_base_url: str) -> None:
        super().__init__()
        self.database = database
        self.clock = clock
        self.merchants_url = f"{admin_base_url}{MERCHANTS_PATH}"

    def overview(self) -> tuple[list[MerchantView], list[IdentitySummary]]:
        with self.database.transaction() as db:
            operators = [
                operator
                for operator in list_operators(db)
                if operator.status is IdentityStatus.ACTIVE
            ]
            return list_all_merchants(db), operators

    def register(self, name: str) -> MerchantView:
        with self.database.transaction() as db:
            return create_merchant(db, name, self.clock.now())

    def link(self, merchant_id: uuid.UUID, operator_id: uuid.UUID) -> bool:
        with self.database.transaction() as db:
            return assign_operator(db, merchant_id, operator_id, self.clock.now()).created

    def back_to_list(self) -> Response:
        return RedirectResponse(self.merchants_url, status_code=HTTPStatus.SEE_OTHER)

    @route("")
    async def index(self, request: Request) -> Response:
        if self.templates is None:
            raise RuntimeError("MerchantsView must be mounted before rendering")
        merchants, operators = await run_in_threadpool(self.overview)
        return self.templates.TemplateResponse(
            request=request,
            name="merchants.html",
            context={
                "title": self.menu_label,
                "merchants": merchants,
                "operators": operators,
                "merchants_url": self.merchants_url,
                "flashed_messages": get_flashed_messages(request),
            },
        )

    @route("/create", methods=["POST"])
    async def submit_creation(self, request: Request) -> Response:
        form = await request.form()
        name = form.get("name")
        try:
            created = await run_in_threadpool(self.register, name if isinstance(name, str) else "")
        except MerchantError as error:
            flash(request, str(error), "error")
        else:
            flash(request, f"Merchant {created.name} created", "success")
        return self.back_to_list()

    @route("/{merchant_id:uuid}/members", methods=["POST"])
    async def submit_assignment(self, request: Request) -> Response:
        merchant_id: uuid.UUID = request.path_params["merchant_id"]
        form = await request.form()
        try:
            operator_id = uuid.UUID(str(form.get("operator_reference") or ""))
            created = await run_in_threadpool(self.link, merchant_id, operator_id)
        except ValueError:
            flash(request, "Choose a valid operator", "error")
        except MerchantError as error:
            flash(request, str(error), "error")
        else:
            message = "Operator assigned" if created else "That operator is already a member"
            flash(request, message, "success")
        return self.back_to_list()
