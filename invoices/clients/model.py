from uweb3plugins.core.models import richversionrecord
from uweb3plugins.core.paginators.model import searchable_table

from invoices.clients import helpers


class Client(
    richversionrecord.RichVersionedRecord, searchable_table.SearchableTableMixin
):
    """Abstraction class for Clients stored in the database."""

    _RECORD_KEY = "clientNumber"
    MIN_NAME_LENGTH = 5
    MAX_NAME_LENGTH = 100

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._client_ids = None

    def _PreSave(self, cursor):
        bag = helpers.BAGService(bag_api_key="placeholder")
        self["residential"] = bag.is_residential_area("8401RS", "16")
        super()._PreSave(cursor)

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
    def FromClientNumber(cls, connection, clientnumber) -> "Client":
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
    def client_ids(self):
        if not self._client_ids:
            with self.connection as cursor:
                results = cursor.Execute(
                    f"""SELECT ID FROM client WHERE clientNumber = {self['clientNumber']}"""
                )
            self._client_ids = tuple(result["ID"] for result in results)
        return ",".join(str(client_id) for client_id in self._client_ids)

    @property
    def get_vat(self):
        """This property is used to determine the % of VAT to be applied to the client.

        This amount is determined by the following things:
            - If the client is a company, the VAT is 19%.
            - If the client is a person, the VAT is 21%.
            - If the client is a person, but the building is not a residential area
                the vat is 21%.
        """
        v = helpers.VatCalculator()
        return v.check(self).vat_amount

    @property
    def explain_vat(self):
        v = helpers.VatCalculator()
        return v.explain_rules(self)
