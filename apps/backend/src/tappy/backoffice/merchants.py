import uuid
from http import HTTPStatus

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette_admin.flash import flash, get_flashed_messages
from starlette_admin.routing import route
from starlette_admin.views import CustomView

from tappy.identity.provisioning import IdentitySummary
from tappy.merchants.errors import MerchantError
from tappy.merchants.models import (
    BENEFICIARY_NAME_MAX_LENGTH,
    MERCHANT_NAME_MAX_LENGTH,
    PROVIDER_ACCOUNT_ID_MAX_LENGTH,
)
from tappy.merchants.receivers import (
    ReceiverSettings,
    ReceiverView,
    configure_receiver,
    list_receivers,
)
from tappy.merchants.service import (
    MerchantView,
    assign_operator,
    assignable_operators,
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

    def load_page(
        self,
    ) -> tuple[list[MerchantView], list[IdentitySummary], dict[uuid.UUID, ReceiverView]]:
        with self.database.transaction() as db:
            return list_all_merchants(db), assignable_operators(db), list_receivers(db)

    def create(self, name: str) -> MerchantView:
        with self.database.transaction() as db:
            return create_merchant(db, name, self.clock.now())

    def assign(self, merchant_id: uuid.UUID, operator_reference: uuid.UUID) -> bool:
        with self.database.transaction() as db:
            return assign_operator(db, merchant_id, operator_reference, self.clock.now()).created

    def configure(self, merchant_id: uuid.UUID, settings: ReceiverSettings) -> ReceiverView:
        with self.database.transaction() as db:
            return configure_receiver(db, merchant_id, settings, self.clock.now())

    def back_to_list(self) -> Response:
        return RedirectResponse(self.merchants_url, status_code=HTTPStatus.SEE_OTHER)

    @route("")
    async def index(self, request: Request) -> Response:
        if self.templates is None:
            raise RuntimeError("MerchantsView must be mounted before rendering")
        merchants, operators, receivers = await run_in_threadpool(self.load_page)
        return self.templates.TemplateResponse(
            request=request,
            name="merchants.html",
            context={
                "title": self.menu_label,
                "merchants": merchants,
                "operators": operators,
                "receivers": {str(merchant_id): view for merchant_id, view in receivers.items()},
                "beneficiary_max_length": BENEFICIARY_NAME_MAX_LENGTH,
                "provider_account_max_length": PROVIDER_ACCOUNT_ID_MAX_LENGTH,
                "name_max_length": MERCHANT_NAME_MAX_LENGTH,
                "merchants_url": self.merchants_url,
                "flashed_messages": get_flashed_messages(request),
            },
        )

    @route("/create", methods=["POST"])
    async def submit_creation(self, request: Request) -> Response:
        form = await request.form()
        try:
            created = await run_in_threadpool(self.create, str(form.get("name") or ""))
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
            operator_reference = uuid.UUID(str(form.get("operator_reference") or ""))
        except ValueError:
            flash(request, "Choose a valid operator", "error")
            return self.back_to_list()
        try:
            created = await run_in_threadpool(self.assign, merchant_id, operator_reference)
        except MerchantError as error:
            flash(request, str(error), "error")
        else:
            message = "Operator assigned" if created else "That operator is already a member"
            flash(request, message, "success")
        return self.back_to_list()

    @route("/{merchant_id:uuid}/receiver", methods=["POST"])
    async def submit_receiver(self, request: Request) -> Response:
        merchant_id: uuid.UUID = request.path_params["merchant_id"]
        form = await request.form()
        settings = ReceiverSettings(
            provider_account_id=str(form.get("provider_account_id") or ""),
            beneficiary_name=str(form.get("beneficiary_name") or ""),
            clabe=str(form.get("clabe") or ""),
            enabled=form.get("enabled") == "on",
        )
        try:
            await run_in_threadpool(self.configure, merchant_id, settings)
        except MerchantError as error:
            flash(request, str(error), "error")
        else:
            flash(request, "Receiving account saved", "success")
        return self.back_to_list()
