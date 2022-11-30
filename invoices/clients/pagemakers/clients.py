#!/usr/bin/python
import os

import uweb3
from uweb3plugins.core.paginators.table import RenderCompleteTable, calc_total_pages

from invoices import basepages
from invoices.clients import forms, helpers, model, tables, views
from invoices.common.decorators import NotExistsErrorCatcher, ParseView, loggedin
from invoices.common.helpers import BaseFormServiceBuilder, FormFactory
from invoices.invoice import model as invoice_model
from invoices.invoice.tables import InvoiceTable, RenderInvoiceTable


class PageMaker(basepages.PageMaker):
    """Holds all the request handlers for the application"""

    TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.forms = FormFactory()
        self.forms.register_form(
            "new_client",
            BaseFormServiceBuilder(forms.ClientForm),
        )
        self.forms.register_form(
            "edit_client",
            BaseFormServiceBuilder(forms.ClientForm),
        )

    @loggedin
    @uweb3.decorators.checkxsrf
    @ParseView
    @NotExistsErrorCatcher
    def RequestClientsPage(self):
        new_client_form: forms.ClientForm = self.forms.get_form("new_client")  # type: ignore

        result, total_items, page = model.Client.IntergratedTable(
            connection=self.connection,
            request_data=self.get,
            page_size=self.page_size,
            searchable=(
                "ID",
                "name",
            ),
            default_sort=[("ID", True)],
        )
        table = tables.ClientTable(
            result,
            sort_by=self.get.getfirst("sort_by"),
            sort_direction=self.get.getfirst("sort_direction"),
            search_url="/clients",
            page=page,
            total_pages=calc_total_pages(total_items, self.page_size),
            renderer=RenderCompleteTable(),
            query=self.get.getfirst("query"),
        )
        return views.ClientsOverview(
            new_client_form=new_client_form,
            success=self.get.get("message", None),
            clients_table=table,
        )

    @loggedin
    @uweb3.decorators.checkxsrf
    def RequestNewClientPage(self):
        """Creates a new client, or displays an error."""
        new_client_form: forms.ClientForm = self.forms.get_form("new_client", self.post)  # type: ignore

        if not new_client_form.validate():
            return self.RequestClientsPage()

        if new_client_form.client_type.data == "Company":
            vies = helpers.ViesService()
            result = vies.process(
                vat_number=new_client_form.vat_number.data,
                vat_country_code="NL",
            )
            if result.errors or not result.is_valid:
                new_client_form.vat_number.errors = result.errors
                return self.RequestClientsPage()

        model.Client.Create(self.connection, new_client_form.data)
        return self.req.Redirect("/clients?message=success", httpcode=303)

    @loggedin
    @uweb3.decorators.checkxsrf
    @ParseView
    @NotExistsErrorCatcher
    def RequestClientPage(self, client=None):
        """Returns the client details.

        Takes:
            client: int
        """
        client = model.Client.FromClientNumber(self.connection, int(client))
        edit_client_form: forms.ClientForm = self.forms.get_form("edit_client", self.post)  # type: ignore

        if not edit_client_form.errors:
            edit_client_form.process(data=client | {"client": client["clientNumber"]})

        result, total_items, page = invoice_model.Invoice.IntergratedTable(
            connection=self.connection,
            request_data=self.get,
            page_size=self.page_size,
            conditions=[f"client in ({client.client_ids})"],
            searchable=("sequenceNumber", "title", "dateCreated", "status"),
            default_sort=[("ID", True)],
        )

        table = InvoiceTable(
            result,
            sort_by=self.get.getfirst("sort_by"),
            sort_direction=self.get.getfirst("sort_direction"),
            search_url=f"/client/{client['clientNumber']}",
            page=page,
            total_pages=calc_total_pages(total_items, self.page_size),
            renderer=RenderInvoiceTable(xsrf_token=self._Get_XSRF()),
            query=self.get.getfirst("query"),
        )

        return views.Client(
            title=str(client["name"]),
            client=client,
            invoices_table=table,
            edit_client_form=edit_client_form,
            success=self.get.getfirst("message", ""),
        )

    @loggedin
    @uweb3.decorators.checkxsrf
    @NotExistsErrorCatcher
    def RequestSaveClientPage(self, clientNumber: int):
        """Returns the client details.

        Takes:
            clientNumber: int
        """
        form: forms.ClientForm = self.forms.get_form("edit_client", self.post)  # type: ignore

        if not form.validate():
            return self.RequestClientPage(clientNumber)

        client = model.Client.FromClientNumber(self.connection, int(clientNumber))
        client.update(form.data)

        if "vat_number" in client._Changes() and client["vat_number"]:
            vies = helpers.ViesService()
            result = vies.process(
                vat_number=form.vat_number.data,
                vat_country_code="NL",
            )
            if result.errors or not result.is_valid:
                form.vat_number.errors = result.errors
                return self.RequestClientPage(clientNumber)

        client.Save()
        return self.req.Redirect(
            f'/client/{client["clientNumber"]}?message=success', httpcode=303
        )
