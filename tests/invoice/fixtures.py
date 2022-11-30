import pytest


@pytest.fixture(scope="module")
def products():
    return {
        "products": [
            {
                "product_sku": "test",
                "name": "test product",
                "quantity": 1,
            },
            {
                "product_sku": "another sku",
                "name": "another product",
                "quantity": 1,
            },
        ]
    }
