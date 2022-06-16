from invoices.common import model as common_model
from invoices.invoice import model as invoice_model


class Client(common_model.RichVersionedRecord):
    """Abstraction class for Clients stored in the database."""

    _RECORD_KEY = "clientNumber"
    MIN_NAME_LENGTH = 5
    MAX_NAME_LENGTH = 100

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._invoices = None
        self._client_ids = None

    @classmethod
    def IsFirstClient(cls, connection):
        with connection as cursor:
            return (
                cursor.Execute(
                    """SELECT EXISTS(SELECT * FROM client) as client_exists;"""
                )[0]["client_exists"]
                == 0
            )

    @classmethod
    def FromClientNumber(cls, connection, clientnumber):
        """Returns the client belonging to the given clientnumber."""
        client = list(
            Client.List(
                connection,
                conditions="clientNumber = %d" % int(clientnumber),
                order=[("ID", True)],
                limit=1,
            )
        )
        if not client:
            raise cls.NotExistError(
                "There is no client with clientnumber %r." % clientnumber
            )
        return cls(connection, client[0])

    @property
    def invoices(self):
        if not self._invoices:
            self._invoices = invoice_model.Invoice.List(
                self.connection,
                conditions="client in ({})".format(str(list(self.client_ids))[1:-1]),
            )
        return self._invoices

    @property
    def client_ids(self):
        if not self._client_ids:
            with self.connection as cursor:
                results = cursor.Execute(
                    f"""SELECT ID FROM client WHERE clientNumber = {self['clientNumber']}"""
                )
            self._client_ids = tuple(result["ID"] for result in results)
        return self._client_ids
