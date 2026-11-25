import uuid
from http import HTTPStatus
from urllib.parse import urlencode

from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import Response
from starlette_admin.routing import route
from starlette_admin.views import CustomView

from tappy.backoffice.auth import admin_identity
from tappy.identity.provisioning import IdentitySummary
from tappy.merchants.errors import MerchantNotFoundError
from tappy.platform.clock import Clock
from tappy.platform.database import Database
from tappy.sales.errors import SaleNotFoundError
from tappy.sales.history import HistoryPage, HistoryQuery, InvalidCursorError, sale_history
from tappy.sales.schemas import HistoryParams
from tappy.sales.service import SaleView, read_sale

SALES_PATH = "/sales"
INVALID_FILTERS = "Invalid filters"


def pesos(amount_cents: int) -> str:
    return f"{amount_cents // 100:,}.{amount_cents % 100:02d}"


class SalesView(CustomView):
    menu_label = "Sales"
    icon = "fa fa-receipt"
    path = SALES_PATH

    def __init__(self, database: Database, clock: Clock, admin_base_url: str) -> None:
        super().__init__()
        self.database = database
        self.clock = clock
        self.sales_url = f"{admin_base_url}{SALES_PATH}"

    def history(self, actor: IdentitySummary, query: HistoryQuery) -> HistoryPage:
        with self.database.transaction() as db:
            return sale_history(db, actor, query)

    def sale(self, actor: IdentitySummary, sale_id: uuid.UUID) -> SaleView:
        with self.database.transaction() as db:
            return read_sale(db, actor, sale_id, self.clock.now())

    def render(
        self, request: Request, name: str, context: dict[str, object], status: int = HTTPStatus.OK
    ) -> Response:
        if self.templates is None:
            raise RuntimeError("SalesView must be mounted before rendering")
        return self.templates.TemplateResponse(
            request=request,
            name=name,
            context={"title": self.menu_label, "sales_url": self.sales_url, "pesos": pesos}
            | context,
            status_code=status,
        )

    def problem(self, request: Request, message: str, status: int) -> Response:
        return self.render(request, "sales_problem.html", {"message": message}, status)

    def next_url(self, request: Request, cursor: str | None) -> str | None:
        if cursor is None:
            return None
        kept = {key: value for key, value in request.query_params.items() if key != "cursor"}
        return f"{self.sales_url}?{urlencode({**kept, 'cursor': cursor})}"

    @route("")
    async def index(self, request: Request) -> Response:
        actor = admin_identity(request)
        try:
            params = HistoryParams.model_validate(dict(request.query_params))
        except ValidationError:
            return self.problem(request, INVALID_FILTERS, HTTPStatus.BAD_REQUEST)
        try:
            page = await run_in_threadpool(self.history, actor, params.to_query())
        except InvalidCursorError as error:
            return self.problem(request, str(error), HTTPStatus.BAD_REQUEST)
        except MerchantNotFoundError as error:
            return self.problem(request, str(error), HTTPStatus.NOT_FOUND)
        return self.render(
            request,
            "sales.html",
            {"sales": page.items, "next_url": self.next_url(request, page.next_cursor)},
        )

    @route("/{sale_id:uuid}")
    async def detail(self, request: Request) -> Response:
        actor = admin_identity(request)
        sale_id: uuid.UUID = request.path_params["sale_id"]
        try:
            sale = await run_in_threadpool(self.sale, actor, sale_id)
        except SaleNotFoundError as error:
            return self.problem(request, str(error), HTTPStatus.NOT_FOUND)
        return self.render(request, "sale.html", {"sale": sale})
