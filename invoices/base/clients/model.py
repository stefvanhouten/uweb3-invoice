import uweb3

from invoices.base.common import model as common_model


class Client(common_model.RichVersionedRecord):
    """Abstraction class for Clients stored in the database."""

    _RECORD_KEY = "clientNumber"
    MIN_NAME_LENGTH = 5
    MAX_NAME_LENGTH = 100

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
