#!/usr/bin/python
"""Request handlers for the uWeb3 warehouse inventory software"""

# standard modules
from marshmallow import Schema, fields, EXCLUDE

# uweb modules
import uweb3
from invoices.base.model import model
from invoices.base.decorators import NotExistsErrorCatcher, json_error_wrapper


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
    client_number = RequestClientSchema().load({'client': client})

    client = model.Client.FromClientNumber(self.connection,
                                           client_number['client'])
    return {'client': client}

  @uweb3.decorators.ContentType('application/json')
  @json_error_wrapper
  def RequestSaveClient(self):
    """Returns the client details.

    Takes:
      client: int
    """
    client_number = RequestClientSchema().load(dict(self.post))
    client = model.Client.FromClientNumber(self.connection,
                                           client_number['client'])
    data = ClientSchema().load(dict(self.post), partial=True)
    client.update(data)
    client.Save()
    return client

  @uweb3.decorators.loggedin
  @uweb3.decorators.checkxsrf
  @uweb3.decorators.TemplateParser('clients/clients.html')
  def RequestClientsPage(self):
    return {
        'title': 'Clients',
        'page_id': 'clients',
        'clients': list(model.Client.List(self.connection)),
    }

  @uweb3.decorators.loggedin
  @uweb3.decorators.checkxsrf
  def RequestNewClientPage(self):
    """Creates a new client, or displays an error."""
    model.Client.Create(
        self.connection, {
            'name': self.post.getfirst('name'),
            'telephone': self.post.getfirst('telephone', ''),
            'email': self.post.getfirst('email', ''),
            'address': self.post.getfirst('address', ''),
            'postalCode': self.post.getfirst('postalCode', ''),
            'city': self.post.getfirst('city', ''),
        })
    return self.req.Redirect('/clients', httpcode=303)

  @uweb3.decorators.loggedin
  @uweb3.decorators.checkxsrf
  @uweb3.decorators.TemplateParser('clients/client.html')
  def RequestClientPage(self, client=None):
    """Returns the client details.

    Takes:
      client: int
    """
    client = model.Client.FromClientNumber(self.connection, int(client))
    return {'title': 'Client', 'page_id': 'client', 'client': client}

  @uweb3.decorators.loggedin
  @uweb3.decorators.checkxsrf
  @NotExistsErrorCatcher
  def RequestSaveClientPage(self):
    """Returns the client details.

    Takes:
      client: int
    """
    client = model.Client.FromClientNumber(self.connection,
                                           int(self.post.getfirst('client')))
    client['name'] = self.post.getfirst('name')
    client['telephone'] = self.post.getfirst('telephone', '')
    client['email'] = self.post.getfirst('email', '')
    client['address'] = self.post.getfirst('address', '')
    client['postalCode'] = self.post.getfirst('postalCode', '')
    client['city'] = self.post.getfirst('city', '')
    client.Save()
    return self.req.Redirect(f'/client/{client["clientNumber"]}')
