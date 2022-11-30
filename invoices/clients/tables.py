from uweb3plugins.core.paginators.columns import Col, LinkCol
from uweb3plugins.core.paginators.table import BasicTable


def format_as_euro(value):
    return f"€ {value:.2f}"


class ClientTable(BasicTable):
    ID = Col(
        "ID",
        attr="ID",
        sortable=True,
    )
    name = LinkCol(
        "Name",
        attr="name",
        href="/client/{clientNumber}",
        sortable=True,
    )
