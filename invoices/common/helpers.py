import configparser
import decimal
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import wtforms


def round_price(d):
    if not isinstance(d, decimal.Decimal):
        d = decimal.Decimal(d)
    cents = decimal.Decimal("0.01")
    return d.quantize(cents, decimal.ROUND_HALF_UP)


@contextmanager
def transaction(connection, cls):
    """Start a transaction in which autocommit is turned off.
    If no error occurs during the transaction the session will be committed to the database (setting autocommit to true also commits),
    and autocommit is restored to True.
    If any (unhandled) Exception occurs the transaction is rolled back and the exception is propagated.

    Arguments:
      @ connection: The databaseconnection available in the PageMaker class.
      @ cls: uweb3.modelRecord
        Any class that derives from the BaseRecord class.
    """
    try:
        cls.autocommit(connection, False)
        yield
    except Exception as e:
        cls.rollback(connection)
        raise e
    finally:
        cls.autocommit(
            connection, True
        )  # This is important, if we do not turn this back on connection will not commit any queries in other requests.


class BaseFactory:
    """Base class for factory classes."""

    def __init__(self):
        self._registered_items = {}

    def register(self, key, builder):
        """Registers a service within the factory.

        Args:
            key (str): The name of the service.
            builder: The builder class for the given service.
                    The builder class is used to supply the Service class with the
                    correct attributes on call. The builder class must have a
                    __call__ method that supplies the service with the
                    provided arguments.
        """
        self._registered_items[key] = builder

    def get_registered_item(self, key, *args, **kwargs):
        """Retrieve a service by name.

        Args:
            key (str): The name of the service by which it was registered.

        Raises:
            ValueError: Raised when the service could not be found in the
            registered services.

        Returns:
            _type_: An authentication service.
        """
        builder = self._registered_items.get(key)
        if not builder:
            raise ValueError(f"No item with key {key} is registered.")
        return builder(*args, **kwargs)


class FormFactory:
    def __init__(self):
        self.base_factory = BaseFactory()

    def register_form(self, key, builder):
        return self.base_factory.register(key, builder)

    def get_form(self, key, *args, **kwargs) -> wtforms.Form:
        return self.base_factory.get_registered_item(key, *args, **kwargs)


class BaseFormServiceBuilder:
    def __init__(self, form):
        self._instance = None
        self.form = form

    def __call__(self, *args, **kwargs):
        if not self._instance:
            self._instance = self.form(*args, **kwargs)
        return self._instance


@dataclass(kw_only=True)
class BaseView:
    template: str
    title: str

    def asdict(self):
        return {
            key: value
            for key, value in self.__dict__.items()
            if key not in ("template",)
        }


def get_config_path() -> Path:
    cwd = Path(os.path.dirname(__file__))
    return Path(cwd.parent / "config.ini")


def load_config():
    path = get_config_path()
    config = configparser.ConfigParser()
    config.read(path)
    return config
