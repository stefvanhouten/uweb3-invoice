#!/usr/bin/python
"""Request handlers for the uWeb3 warehouse inventory software"""

# standard modules

# uweb modules
import os

import uweb3

from invoices import basepages
from invoices.clients import model
from invoices.common.decorators import (
    NotExistsErrorCatcher,
    json_error_wrapper,
    loggedin,
)
from invoices.common.schemas import ClientSchema, RequestClientSchema


class PageMaker(basepages.PageMaker):
    """Holds all the request handlers for the application"""

    TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")

    @uweb3.decorators.ContentType("application/json")
    @json_error_wrapper
    def RequestClients(self):
        return {
            "clients": list(model.Client.List(self.connection)),
        }

    @uweb3.decorators.ContentType("application/json")
    @json_error_wrapper
    def RequestNewClient(self):
        """Creates a new client, or displays an error."""
        client = ClientSchema().load(dict(self.post))
        new_client = model.Client.Create(self.connection, client)
        return new_client

    @uweb3.decorators.ContentType("application/json")
    @json_error_wrapper
    def RequestClient(self, client=None):
        """Returns the client details.

        Takes:
          client: int
        """
        client_number = RequestClientSchema().load({"client": client})

        client = model.Client.FromClientNumber(self.connection, client_number["client"])
        return {"client": client}

    @uweb3.decorators.ContentType("application/json")
    @json_error_wrapper
    def RequestSaveClient(self):
        """Returns the client details.

        Takes:
          client: int
        """
        client_number = RequestClientSchema().load(dict(self.post))
        client = model.Client.FromClientNumber(self.connection, client_number["client"])
        data = ClientSchema().load(dict(self.post), partial=True)
        client.update(data)
        client.Save()
        return client

    @loggedin
    @uweb3.decorators.checkxsrf
    @uweb3.decorators.TemplateParser("clients.html")
    def RequestClientsPage(self):
        return {
            "title": "Clients",
            "page_id": "clients",
            "clients": list(model.Client.List(self.connection)),
        }

    @loggedin
    @uweb3.decorators.checkxsrf
    def RequestNewClientPage(self):
        """Creates a new client, or displays an error."""
        model.Client.Create(
            self.connection,
            {
                "name": self.post.getfirst("name"),
                "telephone": self.post.getfirst("telephone", ""),
                "email": self.post.getfirst("email", ""),
                "address": self.post.getfirst("address", ""),
                "postalCode": self.post.getfirst("postalCode", ""),
                "city": self.post.getfirst("city", ""),
            },
        )
        return self.req.Redirect("/clients", httpcode=303)

    @loggedin
    @uweb3.decorators.checkxsrf
    @uweb3.decorators.TemplateParser("client.html")
    def RequestClientPage(self, client=None):
        """Returns the client details.

        Takes:
          client: int
        """
        client = model.Client.FromClientNumber(self.connection, int(client))
        return {"title": "Client", "page_id": "client", "client": client}

    @loggedin
    @uweb3.decorators.checkxsrf
    @NotExistsErrorCatcher
    def RequestSaveClientPage(self):
        """Returns the client details.

        Takes:
          client: int
        """
        client = model.Client.FromClientNumber(
            self.connection, int(self.post.getfirst("client"))
        )
        client["name"] = self.post.getfirst("name")
        client["telephone"] = self.post.getfirst("telephone", "")
        client["email"] = self.post.getfirst("email", "")
        client["address"] = self.post.getfirst("address", "")
        client["postalCode"] = self.post.getfirst("postalCode", "")
        client["city"] = self.post.getfirst("city", "")
        client.Save()
        return self.req.Redirect(f'/client/{client["clientNumber"]}')
