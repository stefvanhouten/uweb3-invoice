from invoices.clients import helpers


class MockBAGRequestService(helpers.IBAGRequest):
    def postcode_huisnummer(self, postcode: str, huisnummer: str) -> dict:
        match (postcode, huisnummer):
            case ("WOONFUNCTIE", "WOONFUNCTIE"):
                return {
                    "_embedded": {
                        "adressen": [
                            {
                                "adresseerbaarObjectIdentificatie": "WOONFUNCTIE",
                            }
                        ]
                    }
                }
            case _:
                return {}

    def verblijfsobjecten(self, identificatie: str) -> dict:
        match identificatie:
            case "WOONFUNCTIE":
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

        mock_response = mock.postcode_huisnummer(
            postcode="WOONFUNCTIE", huisnummer="WOONFUNCTIE"
        )

        assert bag.adresseerbaar_object(json_response=mock_response) == "WOONFUNCTIE"

    def test_gebruiksdoelen(self):
        bag = helpers.BAGProcessingService()
        mock = MockBAGRequestService(apikey="test", endpoint="test")

        mock_response = mock.postcode_huisnummer(
            postcode="WOONFUNCTIE", huisnummer="WOONFUNCTIE"
        )
        identifier = bag.adresseerbaar_object(json_response=mock_response)

        assert identifier is not None

        mock_identifier_response = mock.verblijfsobjecten(identificatie=identifier)

        assert ["woonfunctie"] == bag.gebruiksdoelen(
            json_response=mock_identifier_response
        )
