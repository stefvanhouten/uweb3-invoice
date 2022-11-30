#!/usr/bin/python
"""Request handlers for the uWeb3 warehouse inventory software"""


import os

from uweb3.templateparser import Parser
from uweb3plugins.core.paginators.columns import Col, ConstantAttr, LinkCol
from uweb3plugins.core.paginators.html_elements import (
    SearchField,
    Table,
    TableHeader,
    TablePagination,
)
from uweb3plugins.core.paginators.table import (
    BasicTable,
    RenderCustomTable,
    TableComponents,
)


def format_as_euro(value):
    return f"€ {value:.2f}"


class InvoiceTable(BasicTable):
    ID = LinkCol(
        "ID",
        attr="sequenceNumber",
        href="/invoice/payments/{sequenceNumber}",
        sortable=True,
    )
    client = LinkCol(
        "Client",
        attr="client.name",
        href="/client/{client.clientNumber}",
    )
    title = Col(
        "Title",
        attr="title",
        sortable=True,
    )
    pdf = LinkCol(
        "PDF",
        attr=ConstantAttr("PDF"),
        href="/pdfinvoice/{sequenceNumber}",
    )
    date_created = Col(
        "Date created",
        attr="dateCreated",
        sortable=True,
    )
    ex_vat = Col(
        "Ex. VAT",
        attr="totals.total_price_without_vat",
        value_formatter=format_as_euro,
    )
    inc_vat = Col(
        "Inc. VAT",
        attr="totals.total_price",
        value_formatter=format_as_euro,
    )
    status = Col(
        "Status",
        attr="status",
        sortable=True,
    )
    actions = Col("Actions", attr=ConstantAttr("Actions"))


class InvoiceTableBody:
    def __init__(self, xsrf_token, *args, **kwargs):
        self.table = None
        self.xsrf_token = xsrf_token

    def __call__(self, table, *args, **kwargs):
        self.table = table
        return self

    @property
    def render(self):
        return Parser().Parse(
            os.path.join(
                os.path.join(os.path.dirname(__file__), "templates"),
                "tables/invoices.html",
            ),
            table=self.table,
            xsrf=self.xsrf_token,
        )


class RenderInvoiceTable(RenderCustomTable):
    def __init__(self, xsrf_token):
        self._renderer = TableComponents()
        self._renderer.add_component(SearchField)
        self._renderer.add_component(Table([TableHeader, InvoiceTableBody(xsrf_token)]))
        self._renderer.add_component(TablePagination)
