import os
import sys

# Third-party modules
import uweb3
from loguru import logger

from invoices.clients.urls import urls as client_urls
from invoices.invoice.urls import urls as invoice_urls
from invoices.login.urls import urls as login_urls
from invoices.mollie.urls import urls as mollie_urls
from invoices.pickup.urls import urls as pickup_urls
from invoices.settings.urls import urls as setting_urls

# Application
from . import basepages

logger.remove()


def setup_logging(is_dev: bool):
    """Setup loguru logging for the application.

    If running in development mode diagnose will be enabled, this means
    that when exceptions are logged the full stacktrace will be printed.
    This also means that sensitive information might be logged.
    """
    if not is_dev:
        logger.add(
            "logs/loguru_prod.log",
            level="WARNING",
            rotation="1 week",
            compression="zip",
            diagnose=False,
        )
        return

    logger.add(sys.stderr, level="DEBUG")
    logger.add(
        "logs/loguru_debug.log",
        level="WARNING",
        rotation="1 day",
        compression="zip",
        diagnose=True,
    )
    logger.debug("Running invoices in development mode.")


def main():
    """Creates a uWeb3 application.

    The application is created from the following components:

    - The presenter class (PageMaker) which implements the request handlers.
    - The routes iterable, where each 2-tuple defines a url-pattern and the
      name of a presenter method which should handle it.
    - The execution path, internally used to find templates etc.
    """
    urls = (
        setting_urls
        + login_urls
        + client_urls
        + invoice_urls
        + mollie_urls
        + pickup_urls
        + [
            # Helper files
            ("(/styles/.*)", "Static"),
            ("(/js/.*)", "Static"),
            ("(/media/.*)", "Static"),
            ("(/favicon.ico)", "Static"),
            ("(/favicon/.*)", "Static"),
            ("(/.*)", "RequestInvalidcommand"),
        ]
    )
    app = uweb3.uWeb(
        basepages.PageMaker,
        urls,
        os.path.dirname(__file__),
    )
    setup_logging(app.config.config.getboolean("general", "development"))

    return app
