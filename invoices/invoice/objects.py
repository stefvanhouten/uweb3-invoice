import decimal
from typing import Optional

from pydantic import BaseModel


class Product(BaseModel):
    name: str
    product_sku: str
    price: decimal.Decimal
    vat_percentage: decimal.Decimal
    quantity: int


class Invoice(BaseModel):
    client: int
    status: str
    title: str
    description: str
    send_mail: Optional[bool]
    mollie_payment_request: Optional[decimal.Decimal]
    products: list[Product]
