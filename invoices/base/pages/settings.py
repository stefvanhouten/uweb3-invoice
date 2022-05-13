# standard modules
import marshmallow

# uweb modules
import uweb3
from invoices.base.model import model
from invoices.base.pages.invoices import CompanyDetailsSchema


class PageMaker:

  @uweb3.decorators.loggedin
  @uweb3.decorators.TemplateParser('settings.html')
  def RequestSettings(self, errors={}):
    """Returns the settings page."""
    settings = None
    highestcompanyid = model.Companydetails.HighestNumber(self.connection)
    if highestcompanyid:
      settings = model.Companydetails.FromPrimary(self.connection,
                                                  highestcompanyid)
    return {
        'title': 'Settings',
        'page_id': 'settings',
        'warehouse': self.options.get('general', {}),
        'settings': settings,
        'errors': errors
    }

  @uweb3.decorators.loggedin
  @uweb3.decorators.checkxsrf
  def RequestSettingsSave(self):
    """Saves the changes and returns the settings page."""
    fieldstorage_to_dict = {
        key: self.post.getfirst(key, '') for key in list(self.post.keys())
    }
    try:
      newsettings = CompanyDetailsSchema().load(fieldstorage_to_dict)
    except marshmallow.exceptions.ValidationError as error:
      return self.RequestSettings(errors=error.messages)

    settings = None
    increment = model.Companydetails.HighestNumber(self.connection)

    try:
      settings = model.Companydetails.FromPrimary(self.connection, increment)
    except uweb3.model.NotExistError:
      pass

    if settings:
      settings.Create(self.connection, newsettings)
    else:
      model.Companydetails.Create(self.connection, newsettings)

    return self.RequestSettings()

  @uweb3.decorators.loggedin
  @uweb3.decorators.checkxsrf
  def RequestWarehouseSettingsSave(self):
    self.config.Update('general', 'warehouse_api',
                       self.post.getfirst('warehouse_api'))
    self.config.Update('general', 'apikey', self.post.getfirst('apikey'))
    return self.req.Redirect('/settings', httpcode=303)
