import datetime
import pytest

from invoices.base.model import invoice
from uweb3.libs.sqltalk import mysql


class TestClass:

  @pytest.fixture()
  def connection(self):
    yield mysql.Connect(host='localhost',
                        user='invoices',
                        passwd='invoices',
                        db='invoices',
                        charset='utf8')

  def test_validate_payment_period(self):
    assert invoice.PAYMENT_PERIOD == datetime.timedelta(14)

  def test_pro_forma_prefix(self):
    assert "PF" == invoice.PRO_FORMA_PREFIX
