import pytest
import requests

from tests.fixtures import session, url


class TestPickupSystem:
    @pytest.mark.parametrize(
        "page_url",
        [
            "/clients",
        ],
    )
    def test_page_access(self, session, page_url):
        """Validate that a loggedin user has access to the page and that all these pages load without issues."""
        result = session.get(url + page_url, headers={"Accept": "application/json"})
        result_no_login = requests.get(
            url + page_url, headers={"Accept": "application/json"}
        )

        assert result.status_code == 200
        assert result.url == url + page_url
        assert result_no_login != url + page_url
