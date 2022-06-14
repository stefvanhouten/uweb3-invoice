import dataclasses
from dataclasses import asdict


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


class MockWarehouseApi:
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


class MockRequestMollieApi:
    def __init__(self, status_code=200):
        self.status_code = 200

    def get(self, url):
        return url

    def post(self, url, data):
        return url


class MockMollieTransactionModel:
    @classmethod
    def Create(cls, connection, record):
        if not hasattr(record, "ID"):
            record["ID"] = 1
        if dataclasses.is_dataclass(record):
            return asdict(record)
        return record
