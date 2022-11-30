from dataclasses import dataclass, field

from invoices.clients import forms, model, tables
from invoices.common.helpers import BaseView
from invoices.invoice.tables import InvoiceTable


@dataclass(kw_only=True)
class Client(BaseView):
    title: str
    client: model.Client
    invoices_table: InvoiceTable
    success: str
    edit_client_form: forms.ClientForm
    template: str = field(default="client.html")


@dataclass(kw_only=True)
class ClientsOverview(BaseView):
    new_client_form: forms.ClientForm
    success: str
    clients_table: tables.ClientTable
    title: str = field(default="Clients")
    template: str = field(default="clients.html")
