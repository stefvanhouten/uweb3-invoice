from pymysql import Date
import pytest
from invoices.base.pages import invoices


@pytest.fixture
def mt940_result():
  return [{
      'invoice': 'PF-2022-001',
      'amount': '100.76',
      'customer_reference': 'NONREF',
      'entry_date': Date(2001, 1, 1),
      'transaction_id': 'N123'
  }, {
      'invoice': '2022-001',
      'amount': '65.20',
      'customer_reference': 'NONREF',
      'entry_date': Date(2001, 1, 1),
      'transaction_id': 'N124'
  }, {
      'invoice': '2022-002',
      'amount': '952.10',
      'customer_reference': 'NONREF',
      'entry_date': Date(2001, 1, 1),
      'transaction_id': 'N125'
  }]


class TestClass:

  def test_create_product_list_positive(self):
    """This test method tests the function that is used to send stock-change requests to uweb3 warehouse."""
    test_products = [
        {
            'name': 'some_name',
            'quantity': 5
        },
        {
            'name': 'some_name',
            'quantity': 10
        },
    ]
    results = invoices.CreateCleanProductList(test_products)
    assert [{'name': 'some_name', 'quantity': 15}] == results

  def test_create_product_list_negative(self):
    test_products = [
        {
            'name': 'some_name',
            'quantity': 5
        },
        {
            'name': 'some_name',
            'quantity': 10
        },
    ]
    results = invoices.CreateCleanProductList(test_products, negative_abs=True)
    assert [{'name': 'some_name', 'quantity': -15}] == results

  def test_create_product_list_multiple_items(self):
    test_products = [{
        'name': 'some_name',
        'quantity': 5
    }, {
        'name': 'some_name',
        'quantity': 10
    }, {
        'name': 'another_product',
        'quantity': 1
    }, {
        'name': 'another_product',
        'quantity': 100
    }, {
        'name': 'yet another product',
        'quantity': 1000000
    }]
    results = invoices.CreateCleanProductList(test_products)
    assert [
        {
            'name': 'some_name',
            'quantity': 15
        },
        {
            'name': 'another_product',
            'quantity': 101
        },
        {
            'name': 'yet another product',
            'quantity': 1000000
        },
    ] == results

  def test_mt940_processing(self, mt940_result):
    data = None
    with open('tests/test_mt940.sta', 'r') as f:
      data = f.read()
    io_files = [{'filename': 'test', 'content': data}]
    results = invoices.MT940_processor(io_files).process_files()
    assert mt940_result == results

  def test_mt940_processing_multi_file(self, mt940_result):
    data = None
    with open('tests/test_mt940.sta', 'r') as f:
      data = f.read()
    io_files = [{
        'filename': 'test',
        'content': data
    }, {
        'filename': 'test',
        'content': data
    }, {
        'filename': 'test',
        'content': data
    }]
    results = invoices.MT940_processor(io_files).process_files()
    assert results == [
        *mt940_result, *mt940_result, *mt940_result
    ]  # Parsing the same file 3 times should return into the same results 3 times.
