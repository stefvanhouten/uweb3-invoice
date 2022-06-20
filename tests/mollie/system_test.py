import pytest
import requests

from tests.fixtures import url


class TestMollieSystem:
    @pytest.mark.parametrize(
        "page_url",
        [
            "/api/v1/mollie/redirect/1/1",  # Page that shows message that the order could not be found
            "/api/v1/mollie/notification/1/1",  # Mollie notification page
        ],
    )
    def test_page_access(self, page_url):
        result = requests.get(url + page_url, headers={"Accept": "application/json"})
        assert result.status_code == 200
