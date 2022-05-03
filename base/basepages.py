from http import HTTPStatus
import uweb3
from base.pages import clients, invoices
from base.model import model


def CentRound(monies):
  """Rounds the given float to two decimals."""
  if monies:
    return '%.2f' % monies


class PageMaker(uweb3.DebuggingPageMaker, clients.PageMaker,
                invoices.PageMaker):
  """Holds all the request handlers for the application"""

  def __init__(self, *args, **kwds):
    super(PageMaker, self).__init__(*args, **kwds)
    self.connection.modelcache = model.modelcache.ClearCache()

  def _PostInit(self):
    """Sets up all the default vars"""
    self.parser.RegisterFunction('CentRound', CentRound)
    self.parser.RegisterFunction('DateOnly', lambda x: str(x)[0:10])
    self.connection.modelcache = model.modelcache.ClearCache()

  def _PostRequest(self, response):
    cleanups = model.modelcache.CleanCache(self.connection.modelcache)
    return response

  @uweb3.decorators.ContentType('application/json')
  def FourOhFour(self, path):
    """The request could not be fulfilled, this returns a 404."""
    return uweb3.Response(
        {
            "error": True,
            "errors": ["Requested page not found"],
            "http_status": HTTPStatus.NOT_FOUND,
        },
        httpcode=HTTPStatus.NOT_FOUND,
    )
