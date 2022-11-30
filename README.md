# uWeb3-invoice

This software can be used to create invoices, manage payments and schedule appointments.
To use this software you need to have a running instance of the uweb3 warehouse: https://github.com/underdarknl/uweb3warehouse

**Warehouse requirements**
- Generated an API access key
  - This key has to be active
- Created at least one product
  -  Configured prices and discount ranges for the product

**Invoices configuration**
- On the 'www.invoice-app-url/settings' page
  - Added a production API key for Mollie
  - Configured the Mollie redirect URL
    - Customer is redirected to this page by Mollie when a transaction is handled
  - Configured the Mollie webhook URL
    - This is the endpoint that Mollie uses to update the system when the status of a payment changes.
  - Configured company settings
    - This information is displayed on the generated invoice PDF. All changes to this information are stored with a VersionRecord, meaning changes will only affect the data on NEW invoices. Old invoices remain accurate with the details that were used when the invoice was created.

## Vscode debug and dev config
```
{
    // Use IntelliSense to learn about possible attributes.
    // Hover to view descriptions of existing attributes.
    // For more information, visit: https://go.microsoft.com/fwlink/?linkid=830387
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Invoice",
            "type": "python",
            "request": "launch",
            "module": "serve",
            "justMyCode": false,
            "env": {
                // If you want to use the most recent uWeb3 features that are still in
                // development include the path to your local repostiroy.
                "PYTHONPATH": "/path/to/WIP/uweb3:/path/to/WIP/uweb3plugins"
            }
        }
    ]
}
```
## config.ini example
```
[mysql]
user = str
password = str
database = str

[signedCookie]
secret = generated

[general]
host = str                          # localhost
locale = str                        # nl_NL
warehouse_api = str                 # url to the API endpoint of https://github.com/underdarknluweb3warehouse
apikey = str                        # key for API access
development = bool

[mollie]
apikey = Mollie apikey
test_apikey = Mollie test api key
webhook_url = Mollie calls this to update us on payment status changes.
redirect_url = The URL the client is redirected to after a payment.

[templates]
allowed_paths = /path/to/project    # This is the path to the template folder from which
                                     # externalinline may import.

```

## Installation
**DEV**
Clone the uweb3 repository and choose the branch that you want to use.
> git clone https://github.com/underdarknl/uweb3

Setup the Invoice repostiry
> git clone https://github.com/underdarknl/uweb3-invoice.git
> python3.10 -m venv env
> source env/bin/activate
> (env) >>> pip3 install -r ../uweb3/requirements.txt
> (env) >>> pip3 install -r requirements.txt

Setup the database:
-  `./schema/schema.sql`
   -  Seed the created database with `./schema/payment_platforms.sql`
   -  Apply all migrations in `./schema/migrations` in the order they appear.
