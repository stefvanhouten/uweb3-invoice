from marshmallow import Schema, fields, EXCLUDE, post_load, validate
from pkg_resources import require
from invoices.base.model.invoice import InvoiceStatus

from invoices.base.pages.helpers.general import round_price


class InvoiceSchema(Schema):

  class Meta:
    unknown = EXCLUDE

  client = fields.Int(required=True, allow_none=False)
  title = fields.Str(required=True, allow_none=False)
  description = fields.Str(required=True, allow_none=False)
  status = fields.Str(
      missing='new')  # Default status to new when field is missing.

  @post_load
  def no_status(self, item, *args, **kwargs):
    """When an empty string is provided set status to new."""
    if not item['status'] or item['status'] == '':
      item['status'] = InvoiceStatus.NEW.value
    if item['status'] == 'on':  # This is for when the checkbox value is passed.
      item['status'] = InvoiceStatus.RESERVATION.value
    return item


class ProductSchema(Schema):
  name = fields.Str(required=True, allow_none=False)
  price = fields.Decimal(required=True, allow_nan=False)
  vat_percentage = fields.Int(required=True, allow_none=False)
  quantity = fields.Int(required=True, allow_none=False)


class WarehouseStockChangeSchema(Schema):

  class Meta:
    unknown = EXCLUDE

  name = fields.Str(required=True, allow_none=False)
  quantity = fields.Method('negative_absolute', deserialize='negative_absolute')

  def negative_absolute(self, quantity):
    """Flip the quantity to a negative value, as this is used to decrement the stock on the warehouse server."""
    return -abs(int(quantity))


class CompanyDetailsSchema(Schema):

  class Meta:
    unknown = EXCLUDE

  name = fields.Str(required=True, allow_none=False)
  telephone = fields.Str(required=True, allow_none=False)
  address = fields.Str(required=True, allow_none=False)
  postalCode = fields.Str(
      required=True,
      allow_none=False,
      validate=validate.Regexp(
          r"^[1-9][0-9]{3} ?(?!sa|sd|ss|SA|SD|SS)[A-Za-z]{2}$",
          error="Should be 4 numbers and 2 letters"))
  city = fields.Str(required=True, allow_none=False)
  country = fields.Str(required=True, allow_none=False)
  vat = fields.Str(required=True, allow_none=False)
  kvk = fields.Str(required=True, allow_none=False)
  bankAccount = fields.Str(required=True, allow_none=False)
  bank = fields.Str(required=True, allow_none=False)
  bankCity = fields.Str(required=True, allow_none=False)
  invoiceprefix = fields.Str(required=True, allow_none=False)


class RequestClientSchema(Schema):

  class Meta:
    unknown = EXCLUDE

  client = fields.Int(required=True, allow_none=False)


class ClientSchema(Schema):

  class Meta:
    unknown = EXCLUDE

  name = fields.Str(required=True, allow_none=False)
  city = fields.Str(required=True, allow_none=False)
  postalCode = fields.Str(required=True, allow_none=False)
  email = fields.Str(required=True, allow_none=False)
  telephone = fields.Str(required=True, allow_none=False)
  address = fields.Str(required=True, allow_none=False)


class PaymentSchema(Schema):

  class Meta:
    unknown = EXCLUDE

  platform = fields.Str(required=True, allow_none=False)
  amount = fields.Decimal(required=True, allow_nan=False)

  @post_load
  def round_amount(self, item, *args, **kwargs):
    """When an empty string is provided set status to new."""
    item['amount'] = round_price(item['amount'])
    return item
