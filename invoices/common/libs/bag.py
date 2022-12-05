import abc
import functools
from dataclasses import dataclass

import requests
from loguru import logger

from invoices.common import helpers as common_helpers


@dataclass
class BAGError:
    message: str


class IBAGProcessing(abc.ABC):
    @abc.abstractmethod
    def adresseerbaar_object(self, json_response: dict) -> str | BAGError:
        pass

    @abc.abstractmethod
    def gebruiksdoelen(self, json_response: dict) -> list[str] | BAGError:
        pass


class IBAGRequest(abc.ABC):
    def __init__(self, apikey: str, endpoint: str):
        self.apikey = apikey
        self.endpoint = endpoint
        self._history: list[requests.Response] = []

    def get_history(self) -> list[requests.Response]:
        return self._history

    @abc.abstractmethod
    def postcode_huisnummer(self, postcode: str, huisnummer: str) -> dict | BAGError:
        pass

    @abc.abstractmethod
    def verblijfsobjecten(self, identificatie: str) -> dict | BAGError:
        pass


class BAGProcessingService(IBAGProcessing):
    """Service for extracting the address information out of the BAG
    API response."""

    def adresseerbaar_object(self, json_response: dict) -> str | BAGError:
        """Extract the adresseerbaar object from the BAG response."""

        if (
            "_embedded" not in json_response
            or "adressen" not in json_response["_embedded"]
        ):
            return BAGError("No data found for requested address")

        if (
            "adresseerbaarObjectIdentificatie"
            not in json_response["_embedded"]["adressen"][0]
        ):
            return BAGError("Address object identificatie could not be found")

        return json_response["_embedded"]["adressen"][0][
            "adresseerbaarObjectIdentificatie"
        ]

    def gebruiksdoelen(self, json_response: dict) -> list[str] | BAGError:
        """Extract the gebruiksdoelen from the BAG response."""
        if (
            "verblijfsobject" not in json_response
            or "gebruiksdoelen" not in json_response["verblijfsobject"]
        ):
            return BAGError(
                "No 'verblijfsobject/gebruiksdoel' found for requested address"
            )

        return json_response["verblijfsobject"]["gebruiksdoelen"]


def bag_api_error_handler(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except requests.exceptions.Timeout:
            logger.info("Connection to the BAG service timed out.")
            return BAGError(message="Connection the the BAG API timed out.")
        except requests.exceptions.ConnectionError as e:
            logger.exception("Error occured while connecting to the BAG API. ", e)
            return BAGError(
                message="Connection the the BAG service could not be established."
            )
        except requests.exceptions.HTTPError as e:
            logger.exception("BAG service returned an error.")
            return BAGError(f"BAG service returned an error: {e}")
        except requests.RequestException:
            logger.exception("Unhandled exception during BAG API request.")
            return BAGError(message="Unhandled exception during BAG API request.")

    return wrapper


class BAGRequestService(IBAGRequest):
    """Service for making requests to the BAG API."""

    def __init__(self, apikey: str, endpoint: str):
        super().__init__(apikey, endpoint)

        self.s = requests.Session()
        self.s.headers.update({"X-Api-Key": self.apikey})

    @bag_api_error_handler
    def postcode_huisnummer(self, postcode: str, huisnummer: str) -> dict | BAGError:
        """Send a request to the BAG API for the given postcode and huisnummer.

        Args:
            postcode (str): The zipcode for the address.
            huisnummer (str): The house number for the address.

        Returns:
            dict: The JSON response from the BAG API.
            BAGError: When an error occured during the request.
        """

        response = self.s.get(
            f"{self.endpoint}/adressen?postcode={postcode}&huisnummer={huisnummer}",
        )
        self._history.append(response)
        response.raise_for_status()
        return response.json()

    @bag_api_error_handler
    def verblijfsobjecten(self, identificatie: str) -> dict | BAGError:
        """Send a request to the verblijfsobjecten endpoint of the BAG API.

        Args:
            identificatie (str): The 'adresseerbaarObjectIdentificatie' value from the
                address endpoint.

        Returns:
            dict: The JSON response from the BAG API.
            BAGError: When an error occured during the request.
        """
        response = self.s.get(
            f"{self.endpoint}/verblijfsobjecten/{identificatie}",
            headers={"Accept-Crs": "epsg:28992"},
        )
        self._history.append(response)
        response.raise_for_status()
        return response.json()


class BAGService:
    """Service that is responsible for validation that a given address is a residential
    area."""

    def __init__(
        self,
        endpoint: str = "https://api.bag.acceptatie.kadaster.nl/lvbag/individuelebevragingen/v2",
        bag_api_key: str | None = None,
        request: IBAGRequest | None = None,
        processing: IBAGProcessing | None = None,
    ):
        """Initialize the BAG service.

        Arguments:
            endpoint (str | None): The endpoint to use for the BAG API.
            bag_api_key (str | None): The API key to use for the BAG API.
                If no key is provided one will be read from the config.
            request (BAGRequestService | None): The request service to use for the BAG,
                if no RequestService is provided a default one will be used.
            processing (BAGProcessingService | None): The processing service to use for
                the BAG, if no ProcessingService is provided a default one will be used.
        """
        if not bag_api_key:
            logger.info("No BAG API key provided, loading from config file.")
            config = common_helpers.load_config()
            bag_api_key = config["bag"]["apikey"]

        if not request:
            request = BAGRequestService(
                apikey=bag_api_key,
                endpoint=endpoint,
            )

        if not processing:
            processing = BAGProcessingService()

        self.request = request
        self.processing = processing

    def is_residential_area(self, postcode: str, huisnummer: str) -> bool:
        # TODO: Handle responses with no results, handle errors
        response = self.request.postcode_huisnummer(postcode, huisnummer)

        if isinstance(response, BAGError):
            return False

        addressable_object = self.processing.adresseerbaar_object(response)

        if isinstance(addressable_object, BAGError):
            return False

        response = self.request.verblijfsobjecten(addressable_object)

        if isinstance(response, BAGError):
            return False

        doeleind = self.processing.gebruiksdoelen(response)

        if isinstance(doeleind, BAGError):
            return False

        return "woonfunctie" in doeleind
