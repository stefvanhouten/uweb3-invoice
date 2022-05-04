from functools import wraps
from http import HTTPStatus
import uweb3
from base.model import model
from marshmallow import ValidationError


def NotExistsErrorCatcher(f):
  """Decorator to return a 404 if a NotExistError exception was returned."""

  def wrapper(*args, **kwargs):
    try:
      return f(*args, **kwargs)
    except model.NotExistError as error:
      return args[0].RequestInvalidcommand(error=error)

  return wrapper


def json_error_wrapper(func):
  wraps(func)

  def wrapper_schema_validation(*args, **kwargs):
    try:
      return func(*args, **kwargs)
    except model.NotExistError as msg:
      return uweb3.Response(
          {
              "error": True,
              "errors": msg.args,
              "http_status": HTTPStatus.NOT_FOUND,
          },
          httpcode=HTTPStatus.NOT_FOUND,
      )
    except ValueError as e:
      return uweb3.Response(
          {
              "error": True,
              "errors": e.args,
              "http_status": HTTPStatus.NOT_FOUND,
          },
          httpcode=HTTPStatus.NOT_FOUND,
      )
    except ValidationError as error:
      return uweb3.Response(
          {
              "error": True,
              "errors": error.messages,
              "http_status": HTTPStatus.BAD_REQUEST,
          },
          httpcode=HTTPStatus.BAD_REQUEST,
      )
    except Exception as err:
      print(err)
      return uweb3.Response(
          {
              "error": True,
              "errors": ["Something went wrong!"],
              "http_status": HTTPStatus.INTERNAL_SERVER_ERROR,
          },
          httpcode=HTTPStatus.INTERNAL_SERVER_ERROR,
      )

  return wrapper_schema_validation
