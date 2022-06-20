import pytest
import requests

from tests.fixtures import session, url


class TestSystem:
    @pytest.mark.parametrize(
        "page_url",
        [
            "/invoices",
            "/invoices/new",  # For this test to pass the warehouse server must be running.
            "/invoices/mt940",
        ],
    )
    def test_page_access(self, session, page_url):
        """Validate that a loggedin user has access to the page and that all these pages load without issues."""
        result = session.get(url + page_url, headers={"Accept": "application/json"})
        no_login = requests.get(url + page_url, headers={"Accept": "application/json"})

        assert result.status_code == 200
        assert result.url == url + page_url
        assert no_login.url != url + page_url
