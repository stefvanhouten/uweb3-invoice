import pytest
import requests

from tests.fixtures import session, url


class TestLoginSystem:
    def test_login(self):
        session = requests.Session()
        result = session.post(
            url + "/login",
            data={"email": "admin@underdark.nl", "password": "password"},
            headers={"Accept": "application/json"},
        )
        assert result.status_code == 200
        assert session.cookies.get_dict().get("session") is not None

    @pytest.mark.parametrize(
        "page_url, expected_page",
        [
            (
                "/",
                "/login",
            ),
            (
                "/login",
                "/login",
            ),
            (
                "/logout",
                "/logout",
            ),
        ],
    )
    def test_page_access(self, page_url, expected_page):
        """Validate that a loggedin user has access to the page and that all these pages load without issues."""
        result = requests.get(url + page_url, headers={"Accept": "application/json"})

        assert result.status_code == 200
        assert result.url == url + expected_page

    @pytest.mark.parametrize(
        "page_url, expected_page",
        [
            (
                "/",
                "/invoices",
            ),
            (
                "/login",
                "/invoices",
            ),
            (
                "/logout",
                "/logout",
            ),
        ],
    )
    def test_page_access_loggedin(self, session, page_url, expected_page):
        result = session.get(url + page_url, headers={"Accept": "application/json"})

        assert result.status_code == 200
        assert result.url == url + expected_page
