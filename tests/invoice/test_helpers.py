from http import HTTPStatus

import pytest
from pymysql import Date

from invoices.common.schemas import WarehouseStockChangeSchema
from invoices.invoice import forms
from invoices.invoice import helpers
from invoices.invoice import helpers as invoice_helpers
from tests.invoice.fixtures import products
from tests.utils import MockWarehouseApi


@pytest.fixture(scope="module")
def mock_api(products) -> helpers.WarehouseApi:
    yield helpers.WarehouseApi("url", "apikey", MockWarehouseApi(products))


@pytest.fixture
def mt940_result():
    return [
        {
            "invoice": "PF-2022-001",
            "amount": "100.76",
            "customer_reference": "NONREF",
            "entry_date": Date(2001, 1, 1),
            "transaction_id": "N123",
        },
        {
            "invoice": "2022-001",
            "amount": "65.20",
            "customer_reference": "NONREF",
            "entry_date": Date(2001, 1, 1),
            "transaction_id": "N124",
        },
        {
            "invoice": "2022-002",
            "amount": "952.10",
            "customer_reference": "NONREF",
            "entry_date": Date(2001, 1, 1),
            "transaction_id": "N125",
        },
    ]


class TestApiHelper:
    def test_get_products(self, mock_api: helpers.WarehouseApi, products):
        assert mock_api.get_products() == products["products"]

    def test_add_order(self, mock_api: helpers.WarehouseApi, products):
        result = mock_api.add_order(products["products"], "This is a test reference")
        # Test that the outgoing json_data is set correctly
        assert result.json_data == {
            "products": [
                {"sku": "test", "quantity": 1, "reference": "This is a test reference"},
                {
                    "sku": "another sku",
                    "quantity": 1,
                    "reference": "This is a test reference",
                },
            ],
            "reference": "This is a test reference",
        }

    def test_cancel_order(self, mock_api: helpers.WarehouseApi, products):
        result = mock_api.cancel_order(products["products"], "This is a test reference")
        assert result.json_data == {
            "products": [
                {"sku": "test", "quantity": 1, "reference": "This is a test reference"},
                {
                    "sku": "another sku",
                    "quantity": 1,
                    "reference": "This is a test reference",
                },
            ],
            "reference": "This is a test reference",
        }

    def test_handled_api_errors(self, products):
        test_status_codes = [
            HTTPStatus.NOT_FOUND,
            HTTPStatus.FORBIDDEN,
            HTTPStatus.INTERNAL_SERVER_ERROR,
            HTTPStatus.CONFLICT,
        ]
        for status_code in test_status_codes:
            with pytest.raises(helpers.WarehouseException):
                mock_api = helpers.WarehouseApi(
                    "url", "apikey", MockWarehouseApi(products, status_code)
                )
                mock_api.get_products()

    def test_unhandled_api_errors(self, products):
        with pytest.raises(helpers.WarehouseException):
            mock_api = helpers.WarehouseApi(
                "url", "apikey", MockWarehouseApi(products, 10000)
            )
            mock_api.get_products()


class TestFormSetup:
    def test_get_invoice_form(self, mock_api: helpers.WarehouseApi):
        """This test validates that the invoice creation form is populated propperly"""
        mock_clients = [{"ID": 1, "name": "test client"}]
        form = forms.get_invoice_form(
            mock_clients, mock_api.get_products(), postdata=None
        )
        assert form.client.choices == [(c["ID"], c["name"]) for c in mock_clients]

        select_list = [("", "Select product")] + [
            (p["sku"], p["name"]) for p in mock_api.get_products()
        ]
        assert form.product.entries[0].sku.choices == select_list


class TestMT940Processer:
    def test_mt940_processing(self, mt940_result):
        data = None
        with open("tests/invoice/test_mt940.sta", "r") as f:
            data = f.read()
        io_files = [{"filename": "test", "content": data}]
        results = invoice_helpers.MT940_processor(io_files).process_files()
        assert mt940_result == results

    def test_mt940_processing_multi_file(self, mt940_result):
        data = None
        with open("tests/invoice/test_mt940.sta", "r") as f:
            data = f.read()
        io_files = [
            {"filename": "test", "content": data},
            {"filename": "test", "content": data},
            {"filename": "test", "content": data},
        ]
        results = invoice_helpers.MT940_processor(io_files).process_files()
        assert results == [
            *mt940_result,
            *mt940_result,
            *mt940_result,
        ]  # Parsing the same file 3 times should return into the same results 3 times.

    def test_stock_change_schema(self):
        product = WarehouseStockChangeSchema().load(
            {"name": "product_1", "quantity": 5}
        )
        assert product["quantity"] == -5

    def test_stock_change_schema_many(self):
        products = WarehouseStockChangeSchema(many=True).load(
            [
                {"name": "product_1", "quantity": 5},
                {"name": "product_2", "quantity": 10},
            ]
        )
        assert products[0]["quantity"] == -5
        assert products[1]["quantity"] == -10


class TestHelperFunctions:
    def test_product_name_from_sku(self, products):
        name = helpers._product_name_from_sku(
            products["products"], {"sku": "another sku"}
        )
        assert name == "another product"

    def test_product_dtos(self, products):
        assert helpers._create_product_dtos(
            products["products"], "This is a test reference"
        ) == [
            {"sku": "test", "quantity": 1, "reference": "This is a test reference"},
            {
                "sku": "another sku",
                "quantity": 1,
                "reference": "This is a test reference",
            },
        ]
