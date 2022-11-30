#!/usr/bin/python
"""Request handlers for the uWeb3 warehouse inventory software"""

import uweb3

from invoices import basepages
from invoices.clients import model
from invoices.common.decorators import json_error_wrapper
from invoices.common.schemas import ClientSchema, RequestClientSchema


class ClientApiPageMaker(basepages.PageMaker):
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
        return dict(client=client)

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
