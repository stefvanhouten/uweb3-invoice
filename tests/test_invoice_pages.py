import pytest
from pymysql import Date

from invoices.base.common.schemas import WarehouseStockChangeSchema
from invoices.base.invoice import helpers as invoice_helpers


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


class TestClass:
    def test_mt940_processing(self, mt940_result):
        data = None
        with open("tests/test_mt940.sta", "r") as f:
            data = f.read()
        io_files = [{"filename": "test", "content": data}]
        results = invoice_helpers.MT940_processor(io_files).process_files()
        assert mt940_result == results

    def test_mt940_processing_multi_file(self, mt940_result):
        data = None
        with open("tests/test_mt940.sta", "r") as f:
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
