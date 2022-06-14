__author__ = "Arjen Pander <arjen@underdark.nl>"
__version__ = "0.1"

import time

from uweb3 import model

from invoices.mollie import helpers


# ##############################################################################
# Record classes for Mollie integration
#
# Model classes have many methods, this is acceptable
# pylint: disable=R0904
class MollieError(Exception):
    """Raises a mollie specific error"""


class MollieTransactionFailed(MollieError):
    """Raised when a transaction status gets set to failed"""


class MollieTransactionCanceled(MollieError):
    """Raised when a transaction status gets set to canceled"""


class MollieConfigError(MollieError):
    """Raises a config error"""


def allow_update(current_status, new_status):
    if current_status not in (helpers.MollieStatus.OPEN,):
        if current_status == helpers.MollieStatus.PAID == new_status:
            raise model.PermissionError("Mollie transaction is already paid for.")
        raise model.PermissionError(
            "Cannot update transaction, current state is %r new state %r"
            % (current_status, new_status)
        )
    return True


class MollieTransaction(model.Record):
    """Abstraction for the `MollieTransaction` table."""

    def _PreCreate(self, cursor):
        super(MollieTransaction, self)._PreCreate(cursor)
        self["creationTime"] = time.gmtime()

    def _PreSave(self, cursor):
        super(MollieTransaction, self)._PreSave(cursor)
        self["updateTime"] = time.gmtime()

    def SetState(self, status):
        allow_update(self["status"], status)
        change = self["status"] != status  # we return true if a change has happened
        self["status"] = status
        self.Save()
        return change

    @classmethod
    def FromDescription(cls, connection, remoteID):
        """Fetches an order object by remoteID"""
        with connection as cursor:
            order = cursor.Execute(
                """
                SELECT *
                FROM mollieTransaction
                WHERE `description` = "%s"
                """
                % remoteID
            )
        if not order:
            raise model.NotExistError("No order for id %s" % remoteID)
        return cls(connection, order[0])
