from invoices.clients import helpers


class MockBAGRequestService(helpers.IBAGRequest):
    def postcode_huisnummer(self, postcode: str, huisnummer: str) -> dict:
        match (postcode, huisnummer):
            case ("1234AB", "1"):
                return {
                    "_embedded": {
                        "adressen": [
                            {
                                "adresseerbaarObjectIdentificatie": "12341",
                            }
                        ]
                    }
                }
            case _:
                return {}

    def verblijfsobjecten(self, identificatie: str) -> dict:
        match identificatie:
            case "12341":
                return {
                    "verblijfsobject": {
                        "gebruiksdoelen": [
                            "woonfunctie",
                        ]
                    }
                }
            case _:
                return {
                    "verblijfsobject": {
                        "gebruiksdoelen": [
                            "kantoor",
                        ]
                    }
                }


class TestBAGProcessor:
    def test_adresseerbaar_object(self):
        bag = helpers.BAGProcessingService()
        mock = MockBAGRequestService(apikey="test", endpoint="test")

        assert (
            bag.adresseerbaar_object(
                mock.postcode_huisnummer(postcode="1234AB", huisnummer="1")
            )
            == "12341"
        )

    def test_gebruiksdoelen(self):
        bag = helpers.BAGProcessingService()
        mock = MockBAGRequestService(apikey="test", endpoint="test")

        assert ["woonfunctie"] == bag.gebruiksdoelen(
            mock.verblijfsobjecten(identificatie="12341")
        )
