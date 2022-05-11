# uweb3-invoice
The mollieTransaction.status column should have a trigger that updates the corresponding invoice to paid whenever a mollie transaction is set to paid.

## config.ini example
[mysql]
user =
password =
database =

[signedCookie]
secret =

[general]
host =
locale =
warehouse_api =
apikey =

[mollie]
methods =
apikey = Mollie apikey
webhook_url = Mollie calls this to update us on payment status changes.
redirect_url = The URL the client is redirected to after a payment.
