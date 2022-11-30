import decimal
from dataclasses import dataclass, field

from invoices.common.helpers import BaseView
from invoices.invoice import forms, model, tables
from invoices.mollie import model as mollie_model


@dataclass(kw_only=True)
class InvoicesOverview(BaseView):
    invoices_table: tables.InvoiceTable
    title: str = field(default="Overview")
    template: str = field(default="invoices.html")


@dataclass(kw_only=True)
class CreateNewInvoice(BaseView):
    client: model.Client
    vat_amount: decimal.Decimal
    api_url: str
    apikey: str
    scripts: list[str]
    styles: list[str]
    invoice_form: forms.InvoiceForm
    title: str = field(default="New invoice")
    template: str = field(default="create.html")


@dataclass(kw_only=True)
class InvoiceDetails(BaseView):
    title: str
    invoice: model.Invoice
    products: list[model.InvoiceProduct]
    totals: dict[str, decimal.Decimal]
    template: str = field(default="invoice.html")


@dataclass(kw_only=True)
class InvoicePayments(BaseView):
    title: str
    invoice: model.Invoice
    payments: list[model.InvoicePayment]
    totals: dict[str, decimal.Decimal]
    mollie_payments: list[mollie_model.MollieTransaction]
    platforms: list[model.PaymentPlatform]
    template: str = field(default="payments.html")


@dataclass(kw_only=True)
class ImportMt940(BaseView):
    payments: list
    failed_invoices: list
    mt940_preview: bool
    title: str = field(default="Import MT940")
    template: str = field(default="mt940.html")
