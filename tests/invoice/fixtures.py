import pytest


@pytest.fixture(scope="module")
def products():
    return {
        "products": [
            {
                "sku": "test",
                "name": "test product",
                "quantity": 1,
            },
        ]
    }
