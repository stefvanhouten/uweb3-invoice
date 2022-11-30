import os

from uweb3.templateparser import Parser
from wtforms import Field, Form
from wtforms.widgets import TextInput


class Legend(Field):
    """Fake field that will be rendered as <legend>value</legend>"""

    widget = TextInput()

    def _value(self):
        pass

    def process_formdata(self, valuelist):
        pass


class BaseForm(Form):
    @property
    def render(self):
        return Parser(
            path=os.path.join(os.path.dirname(__file__), "templates"),
            templates=("default_form.html",),
        ).Parse("default_form.html", __form=self)

    @property
    def data(self):
        """Return data stored in fields as a dict.
        Fields with prefix legend_ are excluded from the dict.
        """
        return {
            name: f.data
            for name, f in self._fields.items()
            if not str(name).startswith("legend_")
        }
