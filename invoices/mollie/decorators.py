import uweb3


def MollieNotExistsErrorCatcher(f):
    """Return a 404 page with a default message to prevent leaking data to the customer"""

    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except uweb3.model.NotExistError:
            return args[0].Error("No data found for this request.")

    return wrapper


def MollieHookErrorCatcher(f):
    """Catch all errors and always return 'ok' to prevent lingering mollie notifications."""

    def wrapper(pagemaker, transaction, *args, **kwargs):
        try:
            return f(pagemaker, transaction, *args, **kwargs)
        except (uweb3.model.NotExistError, Exception) as error:
            pagemaker.logger.error(
                f"Error triggered while processing mollie notification for transaction: {transaction} {error}"
            )
        finally:
            return "ok"

    return wrapper
