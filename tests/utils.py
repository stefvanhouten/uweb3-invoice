import dataclasses
import json
from dataclasses import asdict


class MockResponse:
    def __init__(self, data, status_code):
        self.data = data
        self.text = data
        self.status_code = status_code

        self.json_data = None
        self.post_data = None
        self.post_headers = None

    def json(self):
        return self.data

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, value):
        self._text = value

    def __call__(self, json=None, post_data=None, post_headers=None, **kwargs):
        self.post_data = post_data
        self.post_headers = post_headers
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
        return self.mock_endpoints[url](json=json)


class MockRequestMollieApi:
    def __init__(self, status_code=200, api_url="https://api.mollie.nl/v2"):
        self.status_code = status_code
        self.mock_endpoints = {
            f"{api_url}/payments": MockResponse(
                json.dumps({"id": 1, "_links": {"checkout": "checkout_gateway_url"}}),
                status_code=200,
            )
        }

    def get(self, url):
        return url

    def post(self, url, data, headers):
        return self.mock_endpoints[url](post_data=data, post_headers=headers)


class MockMollieTransactionModel(dict):
    def __init__(self, record):
        self.record = record

    def __getitem__(self, key):
        return self.record[key]

    def __setitem__(self, key, value):
        self.record[key] = value

    def __eq__(self, value):
        return value == self.record

    def __repr__(self):
        return f"MockMollieTransactionModel({self.record})"

    @classmethod
    def Create(cls, connection, record):
        if not hasattr(record, "ID"):
            record["ID"] = 1
        if dataclasses.is_dataclass(record):
            return MockMollieTransactionModel(asdict(record))
        return MockMollieTransactionModel(record)

    def Save(self):
        return self
