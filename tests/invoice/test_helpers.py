from http import HTTPStatus

import pytest

from invoices.invoice import helpers
from tests.invoice.fixtures import products


class MockRequestAPI:
    def __init__(self, products, status_code=200):
        self.mock_endpoints = {
            "url/products?apikey=apikey": MockResponse(products, status_code),
            "url/products/bulk_remove_stock?apikey=apikey": MockResponse(
                products, status_code
            ),
            "url/products/bulk_add?apikey=apikey": MockResponse(products, status_code),
        }

    def get(self, url):
        return self.mock_endpoints[url]

    def post(self, url, json):
        return self.mock_endpoints[url](json)


class MockResponse:
    def __init__(self, data, status_code):
        self.data = data
        self.status_code = status_code
        self.json_data = None

    def json(self):
        return self.data

    def __call__(self, json, **kwargs):
        self.json_data = json
        return self


@pytest.fixture(scope="module")
def mock_api(products) -> helpers.WarehouseApi:
    yield helpers.WarehouseApi("url", "apikey", MockRequestAPI(products))


class TestApiHelper:
    def test_product_dtos(self, products):
        assert helpers._create_product_dtos(
            products["products"], "This is a test reference"
        ) == [{"sku": "test", "quantity": 1, "reference": "This is a test reference"}]

    def test_get_products(self, mock_api: helpers.WarehouseApi, products):
        assert mock_api.get_products() == products["products"]

    def test_add_order(self, mock_api: helpers.WarehouseApi, products):
        result = mock_api.add_order(products["products"], "This is a test reference")
        # Test that the outgoing json_data is set correctly
        assert result.json_data == {
            "products": [
                {"sku": "test", "quantity": 1, "reference": "This is a test reference"}
            ],
            "reference": "This is a test reference",
        }

    def test_cancel_order(self, mock_api: helpers.WarehouseApi, products):
        result = mock_api.cancel_order(products["products"], "This is a test reference")
        assert result.json_data == {
            "products": [
                {"sku": "test", "quantity": 1, "reference": "This is a test reference"}
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
                    "url", "apikey", MockRequestAPI(products, status_code)
                )
                mock_api.get_products()

    def test_unhandled_api_errors(self, products):
        with pytest.raises(helpers.WarehouseException):
            mock_api = helpers.WarehouseApi(
                "url", "apikey", MockRequestAPI(products, 10000)
            )
            mock_api.get_products()
