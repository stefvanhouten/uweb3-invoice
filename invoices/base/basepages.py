import time
from http import HTTPStatus

import marshmallow
import uweb3

from invoices.base.model import model
from invoices.base.pages import clients, invoices, mollie, settings
from invoices.base.pages.helpers.schemas import CompanyDetailsSchema

API_VERSION = '/api/v1'


class PageMaker(uweb3.DebuggingPageMaker, uweb3.LoginMixin, clients.PageMaker,
                invoices.PageMaker, settings.PageMaker, mollie.PageMaker):
  """Holds all the request handlers for the application"""

  def __init__(self, *args, **kwds):
    super(PageMaker, self).__init__(*args, **kwds)

  def _PostInit(self):
    """Sets up all the default vars"""
    self.validatexsrf()
    self.parser.RegisterFunction('CentRound', lambda x: '%.2f' % x
                                 if x else None)
    self.parser.RegisterFunction('items', lambda x: x.items())
    self.parser.RegisterFunction('DateOnly', lambda x: str(x)[0:10])
    self.parser.RegisterFunction(
        'isProForma', lambda x: bool(str(x).startswith(model.PRO_FORMA_PREFIX)))
    self.parser.RegisterTag('year', time.strftime('%Y'))
    self.parser.RegisterTag(
        'header',
        self.parser.JITTag(lambda: self.parser.Parse('parts/header.html')))
    self.parser.RegisterTag(
        'footer',
        self.parser.JITTag(lambda *args, **kwargs: self.parser.Parse(
            'parts/footer.html', *args, **kwargs)))
    self.parser.RegisterTag('xsrf', self._Get_XSRF())
    self.parser.RegisterTag('user', self.user)

  def _PostRequest(self, response):
    response.headers.update({
        'Access-Control-Allow-Origin': '*',
    })
    return response

  def _ReadSession(self):
    """Attempts to read the session for this user from his session cookie"""
    try:
      user = model.Session(self.connection)
    except Exception:
      raise ValueError('Session cookie invalid')
    try:
      user = model.User.FromPrimary(self.connection, int(str(user)))
    except model.NotExistError:
      return None
    if user['active'] != 'true':
      raise ValueError('User not active, session invalid')
    return user

  @uweb3.decorators.loggedin
  def RequestIndex(self):
    """Returns the homepage"""
    return self.req.Redirect('/invoices', httpcode=303)

  @uweb3.decorators.TemplateParser('login.html')
  def RequestLogin(self, url=None):
    """Please login"""
    if self.user:
      return self.RequestIndex()
    if not url and 'url' in self.get:
      url = self.get.getfirst('url')
    return {'url': url}

  @uweb3.decorators.checkxsrf
  @uweb3.decorators.TemplateParser('logout.html')
  def RequestLogout(self):
    """Handles logouts"""
    message = 'You were already logged out.'
    if self.user:
      message = ''
      if 'action' in self.post:
        session = model.Session(self.connection)
        session.Delete()
        return self.req.Redirect('/login')
    return {'message': message}

  @uweb3.decorators.checkxsrf
  def HandleLogin(self):
    """Handles a username/password combo post."""
    if (self.user or 'email' not in self.post or 'password' not in self.post):
      return self.RequestIndex()
    url = self.post.getfirst('url', None) if self.post.getfirst(
        'url', '').startswith('/') else '/'
    try:
      self._user = model.User.FromLogin(self.connection,
                                        self.post.getfirst('email'),
                                        self.post.getfirst('password'))
      model.Session.Create(self.connection, int(self.user), path="/")
      print('login successful.', self.post.getfirst('email'))
      # redirect 303 to make sure we GET the next page, not post again to avoid leaking login details.
      return self.req.Redirect(url, httpcode=303)
    except model.User.NotExistError as error:
      self.parser.RegisterTag('loginerror', '%s' % error)
      print('login failed.', self.post.getfirst('email'))
    return self.RequestLogin(url)

  @uweb3.decorators.checkxsrf
  def RequestResetPassword(self, email=None, resethash=None):
    """Handles the post for the reset password."""
    message = None
    error = False
    if not email and not resethash:
      try:
        user = model.User.FromEmail(self.connection,
                                    self.post.getfirst('email', ''))
      except model.User.NotExistError:
        error = True
        if self.debug:
          print('Password reset request for unknown user %s:' %
                self.post.getfirst('email', ''))
      if not error:
        resethash = user.PasswordResetHash()
        content = self.parser.Parse('email/resetpass.txt',
                                    email=user['email'],
                                    host=self.options['general']['host'],
                                    resethash=resethash)
        try:
          with mail.MailSender(
              local_hostname=self.options['general']['host']) as send_mail:
            send_mail.Text(user['email'], 'CMS password reset', content)
        except mail.SMTPConnectError:
          if not self.debug:
            return self.Error(
                'Mail could not be send due to server error, please contact support.'
            )
        if self.debug:
          print('Password reset for %s:' % user['email'], content)

      message = 'If that was an email address that we know, a mail with reset instructions will be in your mailbox soon.'
      return self.parser.Parse('reset.html', message=message)
    try:
      user = model.User.FromEmail(self.connection, email)
    except model.User.NotExistError:
      return self.parser.Parse(
          'reset.html', message='Sorry, that\'s not the right reset code.')
    if resethash != user.PasswordResetHash():
      return self.parser.Parse(
          'reset.html', message='Sorry, that\'s not the right reset code.')

    if 'password' in self.post:
      if self.post.getfirst('password') == self.post.getfirst(
          'password_confirm', ''):
        try:
          user.UpdatePassword(self.post.getfirst('password', ''))
        except ValueError:
          return self.parser.Parse(
              'reset.html', message='Password too short, 8 characters minimal.')
        model.Session.Create(self.connection, int(user), path="/")
        self._user = user
        return self.parser.Parse(
            'reset.html',
            message='Your password has been updated, and you are logged in.')
      else:
        return self.parser.Parse('reset.html',
                                 message='The passwords don\'t match.')
    return self.parser.Parse('resetform.html',
                             resethash=resethash,
                             resetuser=user,
                             message='')

  @uweb3.decorators.checkxsrf
  @uweb3.decorators.TemplateParser('setup.html')
  def RequestSetup(self):
    """Allows the user to setup various fields, and create an admin user.

    If these fields are already filled out, this page will not function any
    longer.
    """
    if not model.User.IsFirstUser(self.connection):
      return self.RequestLogin()

    if ('email' in self.post and 'password' in self.post and
        'password_confirm' in self.post and self.post.getfirst('password')
        == self.post.getfirst('password_confirm')):

      # We do this because marshmallow only validates dicts. Calling dict(self.post) does not work propperly because the values of the dict will be indexfield.
      fieldstorage_to_dict = {
          key: self.post.getfirst(key, '') for key in list(self.post.keys())
      }
      try:
        settings = CompanyDetailsSchema().load(fieldstorage_to_dict)
        model.Companydetails.Create(self.connection, settings)
        user = model.User.Create(self.connection, {
            'ID': 1,
            'email': self.post.getfirst('email'),
            'active': 'true',
            'password': self.post.getfirst('password'),
        },
                                 generate_password_hash=True)
      except ValueError:
        return {
            'errors': {
                'password': ['Password too short, 8 characters minimal.']
            },
            'postdata': fieldstorage_to_dict
        }
      except marshmallow.exceptions.ValidationError as error:
        return {'errors': error.messages, 'postdata': fieldstorage_to_dict}

      self.config.Update('general', 'host', self.post.getfirst('hostname'))
      self.config.Update('general', 'locale',
                         self.post.getfirst('locale', 'en_GB'))
      self.config.Update('general', 'warehouse_api',
                         self.post.getfirst('warehouse_api'))
      self.config.Update('general', 'apikey', self.post.getfirst('apikey'))
      model.Session.Create(self.connection, int(user), path="/")
      return self.req.Redirect('/', httpcode=301)

  def RequestInvalidcommand(self, command=None, error=None, httpcode=404):
    """Returns an error message"""
    uweb3.logging.warning('Bad page %r requested with method %s', command,
                          self.req.method)
    if command is None and error is None:
      command = '%s for method %s' % (self.req.path, self.req.method)
    page_data = self.parser.Parse('404.html', command=command, error=error)
    return uweb3.Response(content=page_data, httpcode=httpcode)

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

  def Error(self, error='', httpcode=500, link=None):
    """Returns a generic error page based on the given parameters."""
    uweb3.logging.error('Error page triggered: %r', error)
    page_data = self.parser.Parse('error.html', error=error, link=link)
    return uweb3.Response(content=page_data, httpcode=httpcode)
