import json
import re
from io import BytesIO
from typing import Callable, Optional

import mt940
from loguru import logger
from pydantic import BaseModel
from uweb3.libs.mail import MailSender
from weasyprint import HTML

from invoices.common import helpers as common_helpers
from invoices.common.libs import bag
from invoices.invoice import model, objects
from invoices.mollie.mollie import helpers as mollie_module


def mail_invoice(recipients, subject, body, attachments=None):
    """Used for sending a mail with attachments or as plain text.

    Args:
        recipients (list[str]): The recipients to send it to
        subject (str): The mail subject
        body (str): The mail body
        attachments: The attachments that should be send with this mail
        mailconfig (dict): Config with host/port for the mailserver.
            example: { 'host': 'localhost', 'port': 25 }
    """
    if attachments:
        with MailSender() as send_mail:
            send_mail.Attachments(
                recipients=recipients,
                subject=subject,
                content=body,
                attachments=attachments,
            )
    else:
        with MailSender() as send_mail:
            send_mail.Text(recipients=recipients, subject=subject, content=body)


def create_mollie_request(invoice, amount, connection, mollie_config):
    """Generate a new mollie payment request and return its url

    Args:
        invoice (InvoiceSchema): The invoice
        amount (str/Decimal): The amount for the mollie payment request
        connection (self.connection): Db connection
        mollie_config (self.options['mollie']): The mollie config

    Returns:
        _type_: _description_
    """
    mollie_request_object = mollie_module.MollieTransactionObject(
        invoice["ID"],
        common_helpers.round_price(amount),
        invoice["description"],
        invoice["sequenceNumber"],
    )
    mollie_gateway = mollie_module.mollie_factory(connection, mollie_config)
    return mollie_gateway.create_transaction(mollie_request_object)["href"]


def to_pdf(html, filename=None):
    """Returns a PDF based on the given HTML."""
    result = BytesIO()
    HTML(string=html).write_pdf(result)
    if filename:
        result.filename = filename
        return result
    return result.getvalue()


class MT940_processor:
    INVOICE_REGEX_PATTERN = r"((.*)-[0-9]{4}-[0-9]{3})|((.*)-PF-[0-9]{4}-[0-9]{3})"

    def __init__(self, files, prefix="invoice"):
        self.files = files

    def process_files(self):
        """Processes the contents of all MT-940 files."""
        results = []
        for f in self.files:
            # XXX: The content of an MT-940 file should be str. uweb3 handles this, but should we also check this?
            results.extend(self._regex_search(f.value.decode("utf-8")))
        return results

    def _regex_search(self, data):
        """Parse data and match patterns that could indicate a invoice or a pro forma invoice

        Arguments:
          @ data: str
            Data read from .STA file.

        Returns:
          List of dictionaries that matched the invoice pattern.
          [
            {
              invoice: sequenceNumber,
              amount: value
            }
          ]
        """
        results = []
        transactions = mt940.models.Transactions(
            processors=dict(
                pre_statement=[
                    mt940.processors.add_currency_pre_processor("EUR"),
                ],
            )
        )
        transactions.parse(data)

        for transaction in transactions:
            matches = re.finditer(
                self.INVOICE_REGEX_PATTERN,
                transaction.data["transaction_details"],
                re.MULTILINE,
            )
            potential_invoice_references = self._clean_results(matches, transaction)
            results.extend(potential_invoice_references)
        return results

    def _clean_results(self, matches, transaction):
        """Iterates over all found matches and returns the matches in a dict.

        Arguments:
          @ matches:
            The found regex matches
          @ transaction:
            The current transaction that is being parsed.

        Returns:
          List of dictionaries that matched the invoice pattern
            [
              {
                invoice: sequenceNumber,
                amount: value
              }
            ]
        """
        amount = str(
            transaction.data["amount"].amount
        )  # Get the value of the transaction
        return [
            {
                "invoice": x.group(),
                "amount": amount,
                "customer_reference": transaction.data.get("customer_reference"),
                "entry_date": transaction.data.get("entry_date"),
                "transaction_id": transaction.data.get("id"),
            }
            for x in matches
        ]


class InvoiceServiceBuilder(common_helpers.BaseFormServiceBuilder):
    def __init__(self, form, client_method: Callable):
        self._instance = None
        self.form = form
        self.client_method = client_method

    def _populate_select(self, client_number):
        self._instance.client.choices = [
            (c["ID"], c["name"]) for c in self.client_method(client_number)
        ]

    def __call__(self, *args, client_number, **kwargs):
        if not self._instance:
            self._instance = self.form(*args, **kwargs)
            self._populate_select(client_number)
        return self._instance


def map_products_to_warehouse_products(connection, invoice_form):
    record = dict(invoice_form.data)
    record["products"] = []

    # Find the product name by the chosen product SKU
    for product in invoice_form.products.data:
        if product["product_sku"] == "":
            continue

        wh_product = model.WarehouseProduct.FromSku(connection, product["product_sku"])
        record["products"].append(
            dict(
                name=wh_product["name"],
                product_sku=product["product_sku"],
                price=product["price"],
                vat_percentage=product["vat_percentage"],
                quantity=product["quantity"],
            )
        )
    return record


class InvoiceSetupError(Exception):
    """An error that is raised whenever the InvoiceService setup process fails."""


class InvoiceServiceBagConfig(BaseModel):
    apikey: str
    url: str


class InvoiceServiceGeneralConfig(BaseModel):
    warehouse_api: str
    apikey: str


class InvoiceServiceMollieConfig(BaseModel):
    apikey: str
    redirect_url: str
    webhook_url: str


class InvoiceServiceConfig(BaseModel):
    bag: InvoiceServiceBagConfig
    general: InvoiceServiceGeneralConfig
    mollie: InvoiceServiceMollieConfig


class RequestContext(BaseModel):
    class Config:
        arbitrary_types_allowed = True

    request_service: bag.IBAGRequest
    is_residential: bool = False
    mollie_request_url: Optional[str] = None
    invoice: Optional[model.Invoice] = None


class InvoiceService:
    """Controller that can be used to create a new Invoice.

    Creating an invoice is a multi-step process, containing the following procedures:
        1. Check client address and determine if it is a residential address via BAG
        2. Create the actual invoice
        3. Update the Warehouse through the Warehouse API
        4. Store the BAG data that was used to determine if the address is residential
        5. Create a Mollie payment link if required.

    Note that this service does not use ACID, if any of the steps after invoice creation
    fail the invoice will still be created. This is by design.
    """

    INVOICE_MODEL = model.Invoice
    WAREHOUSE_ORDER_MODEL = model.WarehouseOrder
    BAGDATA_MODEL = model.BAGData

    def __init__(self, connection, config: InvoiceServiceConfig):
        self._client = None

        self._connection = connection
        self._config = config

    @property
    def client(self) -> model.Client:
        if not self._client:
            raise InvoiceSetupError("Not a valid client selected.")

        return self._client

    def set_client(self, client: model.Client):
        """Set the client that will be used for the current creation process.

        Args:
            client (model.Client): The client for which the invoice will be created.

        Raises:
            InvoiceSetupError: Raised when the setup process fails.
        """
        if not client or not isinstance(client, model.Client):
            raise InvoiceSetupError("Not a valid client selected.")

        self._client = client

    def create(self, invoice_data: objects.Invoice) -> RequestContext:
        # Create a context object for the current creation request.
        logger.info("Creating new invoice for client {}", self.client["ID"])

        context = RequestContext(
            request_service=bag.BAGRequestService(
                apikey=self._config.bag.apikey,
                endpoint=self._config.bag.url,
            )
        )

        self._pre_create(invoice_data=invoice_data, context=context)
        self._create(invoice_data=invoice_data, context=context)
        self._post_create(invoice_data=invoice_data, context=context)

        return context

    def _pre_create(self, invoice_data: objects.Invoice, context: RequestContext):
        # Choose the BAGRequestService that we want to use to communicate with the BAG API.
        # Use the default response service provided by the BAGService to handle response
        # processing.
        bag_service = bag.BAGService(
            bag_api_key=self._config.bag.apikey,
            request=context.request_service,
        )

        # Send a request to the BAG API to check if the client's address is that of a
        # residential area.
        logger.debug("Requesting BAG data for client {}", self.client["ID"])
        context.is_residential = bag_service.is_residential_area(
            postcode=self.client["postalCode"],  # type: ignore
            huisnummer=self.client["house_number"],  # type: ignore
        )

    def _create(self, invoice_data: objects.Invoice, context: RequestContext):
        logger.debug("Creating invoice for client {}", self.client["ID"])
        context.invoice = InvoiceService.INVOICE_MODEL.Create(
            self._connection,
            invoice_data.dict(),
        )

    def _post_create(
        self,
        invoice_data: objects.Invoice,
        context: RequestContext,
    ):
        invoice = context.invoice

        if not invoice:
            return

        # Send a request to the warehouse API to create a new order,
        # this will update the stock of the products and create a new order on the system.
        logger.info("Creating warehouse order for invoice {}", invoice["ID"])
        InvoiceService.WAREHOUSE_ORDER_MODEL.Create(
            {
                "url": self._config.general.warehouse_api,
                "apikey": self._config.general.apikey,
            },
            {
                "description": invoice["client"]["name"],
                "status": invoice["status"],
                "reference": invoice["sequenceNumber"],
                "products": [
                    p.dict(include={"product_sku", "quantity"})
                    for p in invoice_data.products
                ],
            },
        )

        reqs = []
        resp = []
        # Gather request/response data for all outgoing requests to BAG.
        # We need to save this data in case we need to prove that the client's address
        # is indeed a residential area.
        for res in context.request_service.get_history():
            reqs.append({"url": res.request.url, "headers": dict(res.request.headers)})
            resp.append(res.json())

        logger.info("Creating BAG data for invoice {}", invoice["ID"])
        InvoiceService.BAGDATA_MODEL.Create(
            self._connection,
            {
                "request": json.dumps(reqs),
                "response": json.dumps(resp),
                "invoice": invoice["ID"],
            },
        )

        # Generate a Mollie payment URL for the invoice.
        if invoice_data.mollie_payment_request:
            context.mollie_request_url = create_mollie_request(
                invoice,
                invoice_data.mollie_payment_request,
                self._connection,
                self._config.mollie.dict(),
            )
