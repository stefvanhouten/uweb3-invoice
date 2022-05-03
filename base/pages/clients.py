#!/usr/bin/python
"""Request handlers for the uWeb3 warehouse inventory software"""

# standard modules
from marshmallow import Schema, fields, EXCLUDE

# uweb modules
import uweb3
from base.model import model
from base.decorators import NotExistsErrorCatcher, json_error_wrapper

class RequestClient(Schema):
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


class PageMaker:
  """Holds all the request handlers for the application"""
  @uweb3.decorators.ContentType('application/json')
  @json_error_wrapper
  def RequestClients(self):
    return {
        'clients': list(model.Client.List(self.connection)),
    }
  @uweb3.decorators.ContentType('application/json')
  @json_error_wrapper
  def RequestNewClient(self):
    """Creates a new client, or displays an error."""
    client = ClientSchema().load(dict(self.post))
    new_client = model.Client.Create(self.connection, client)
    return new_client

  @uweb3.decorators.ContentType('application/json')
  @json_error_wrapper
  def RequestClient(self, client=None):
    """Returns the client details.

    Takes:
      client: int
    """
    client = model.Client.FromClientNumber(self.connection, int(client))
    return {'client': client}

  @uweb3.decorators.ContentType('application/json')
  @json_error_wrapper
  def RequestSaveClient(self):
    """Returns the client details.

    Takes:
      client: int
    """
    client_number = RequestClient().load(self.post)
    client = model.Client.FromClientNumber(self.connection, client_number['client'])
    data = ClientSchema().load(self.post, partial=True)
    client.update(data)
    client.Save()
    return client
