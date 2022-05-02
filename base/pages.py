import uweb3

class PageMaker(uweb3.DebuggingPageMaker):
  """Holds all the request handlers for the application"""

  @uweb3.decorators.ContentType('application/json')
  def Index(self):
    """Returns the index template"""
    return {
      'key': 'value'
    }

  def FourOhFour(self, path):
    """The request could not be fulfilled, this returns a 404."""
    self.req.response.httpcode = 404
    return self.parser.Parse('404.html', path=path)