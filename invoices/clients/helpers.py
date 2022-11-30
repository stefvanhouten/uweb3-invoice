import abc
from dataclasses import dataclass
from http import HTTPStatus

import requests
from loguru import logger

from invoices.clients import model
from invoices.common.libs import pyvies


@dataclass
class ViesResult:
    is_valid: bool  # True if the VAT number is valid
    errors: list[str] | None  # List of errors that occured during validation


class ViesService:
    def __init__(self, service: pyvies.IVies = pyvies.Vies()):
        self.service = service

    def process(self, vat_number: int, vat_country_code: str) -> ViesResult:
        """Validate the VAT number for a given country with VIES.

        Args:
            vat_number: VAT number to validate.
            vat_country_code: Country code of the VAT number.

        Returns:
            ViesResult: Result of the validation.
        """
        try:
            result = self.service.request(vat_number, vat_country_code)
        except (
            pyvies.ViesValidationError,
            pyvies.ViesError,
        ) as exc:
            logger.error("PyVies error occured %s" % exc)
            return ViesResult(is_valid=False, errors=[str(exc)])
        except pyvies.ViesHTTPError as exc:
            logger.error("PyVies HTTP error occured %s" % exc)
            return ViesResult(
                is_valid=False,
                errors=["An error occured while communicating with the VIES service."],
            )

        except Exception as exc:
            logger.exception(exc)
            return ViesResult(
                is_valid=False,
                errors=["Unhandled error occured while validating with VIES."],
            )

        if not result or "valid" not in result or not result["valid"]:
            return ViesResult(
                is_valid=False,
                errors=["VAT number is not valid"],
            )

        return ViesResult(is_valid=True, errors=None)


class IVatRule(abc.ABC):
    """Interface for VAT rule determination."""

    def __init__(self, weight: int, vat_amount: int, details: str) -> None:
        """
        Args:
            weight (int): The weight of the rule. The rule with the highest weight will
                be used.
            vat_amount (int): The VAT amount to be applied.
            details (str): Explanation of the rule, and why it was applied.
        """
        self.weight = weight
        self.vat_amount = vat_amount
        self.details = details

    @abc.abstractmethod
    def process(self, client: model.Client) -> int | None:
        """Processes the current VAT rule and returns the VAT amount if the rule
        applies."""
        pass


class VatCalculator:
    def __init__(self):
        self._registerd_rules = []
        self._initiate_rules()

    def _initiate_rules(self):
        """Register the default VAT rules that we currently use."""
        self.register_rule(
            VatRuleIndividual(
                weight=1,
                vat_amount=19,
                details="19% VAT for individuals when the building is a residential area.",
            )
        )
        self.register_rule(
            VatRuleCompany(
                weight=1,
                vat_amount=21,
                details="21% VAT for companies.",
            )
        )
        self.register_rule(
            VatRuleIndividualNonResidential(
                weight=10,
                vat_amount=21,
                details="21% VAT for individuals when the building is not a residential area.",
            )
        )

    def check(self, client: model.Client) -> IVatRule:
        """Return the VAT rule that applies to the given client.
        If no rule applied a default rule will be returned.

        Args:
            client (model.Client): The client to check the VAT rule for.

        Returns:
            IVatRule: The VAT rule that applies to the given client.
        """

        results = self._process(client)
        return results[0]

    def _process(self, client: model.Client) -> list[IVatRule]:
        """Actually process the VAT rules and return the results in order based on weight.

        When no rule applies a default rule will be returned.
        """
        results = sorted(
            # Filter out the rules that don't apply
            [res for res in self._registerd_rules if res.process(client)],
            # Order by weight
            key=lambda x: x.weight,
            # Reverse the result so that the highest weight is first
            reverse=True,
        )

        if results:
            return results

        return [
            DefaultVatRule(
                weight=0,
                vat_amount=21,
                details="No specific VAT rules apply, using default rule of 21% VAT.",
            )
        ]

    def explain_rules(self, client: model.Client) -> list[str]:
        """Return a list of explanations for the VAT rules that apply to the given client.

        Args:
            client (model.Client): The client to check the VAT rule for.

        Returns:
            list[str]: The explanations for the VAT rules that apply to the given client.
                Also indicates which rule is actually applied.
        """
        results = [res.details for res in self._process(client)]
        results[0] += " (applied rule)"
        return results

    def register_rule(self, rule: IVatRule) -> None:
        self._registerd_rules.append(rule)


class DefaultVatRule(IVatRule):
    """A default VAT rule that applies when no other rule applies."""

    def process(self, client: model.Client) -> int | None:
        return self.vat_amount


class VatRuleCompany(IVatRule):
    """VAT rule for when the client type is a company."""

    def process(self, client: model.Client) -> int | None:
        if client["client_type"] == "Company":
            return self.vat_amount


class VatRuleIndividual(IVatRule):
    """VAT rule for when the client type is an individual and the building they live in
    is that of a residential area.

    https://www.belastingdienst.nl/wps/wcm/connect/bldcontentnl/berichten/nieuws/
        wetsvoorstel-nultarief-btw-zonnepanelen
    """

    def process(self, client: model.Client) -> int | None:
        if client["client_type"] == "Individual" and client["residential"]:
            return self.vat_amount


class VatRuleIndividualNonResidential(IVatRule):
    """VAT rule for when the client type is an individual and the building they live in
    or they provided is not a residential area.

    https://www.belastingdienst.nl/wps/wcm/connect/bldcontentnl/berichten/nieuws/
        wetsvoorstel-nultarief-btw-zonnepanelen
    """

    def process(self, client: model.Client) -> int | None:
        if client["client_type"] == "Individual" and not client["residential"]:
            return self.vat_amount


class BAGProcessingService:
    """Service for extracting the address information out of the BAG
    API response."""

    def adresseerbaar_object(self, json_response: dict):
        """Extract the adresseerbaar object from the BAG response."""
        return json_response["_embedded"]["adressen"][0][
            "adresseerbaarObjectIdentificatie"
        ]

    def gebruiksdoelen(self, json_response: dict):
        """Extract the gebruiksdoelen from the BAG response."""
        return json_response["verblijfsobject"]["gebruiksdoelen"]


class BAGRequestService:
    """Service for making requests to the BAG API."""

    def __init__(self, apikey: str, endpoint: str):
        self.apikey = apikey
        self.endpoint = endpoint

        self.s = requests.Session()
        self.s.headers.update({"X-Api-Key": self.apikey})

    def postcode_huisnummer(self, postcode: str, huisnummer: str) -> dict | None:
        """Send a request to the BAG API for the given postcode and huisnummer.

        Args:
            postcode (str): The zipcode for the address.
            huisnummer (str): The house number for the address.

        Returns:
            dict: The JSON response from the BAG API.
        """
        response = self.s.get(
            f"{self.endpoint}/adressen?postcode={postcode}&huisnummer={huisnummer}",
        )

        if response.status_code != HTTPStatus.OK:
            return

        return response.json()

    def verblijfsobjecten(self, identificatie: str) -> dict | None:
        """Send a request to the verblijfsobjecten endpoint of the BAG API.

        Args:
            identificatie (str): The 'adresseerbaarObjectIdentificatie' value from the
                address endpoint.

        Returns:
            dict: The JSON response from the BAG API.
        """
        response = self.s.get(
            f"{self.endpoint}/verblijfsobjecten/{identificatie}",
            headers={"Accept-Crs": "epsg:28992"},
        )

        if response.status_code != HTTPStatus.OK:
            return

        return response.json()


class BAGService:
    """Service that is responsible for validation that a given address is a residential
    area."""

    def __init__(
        self,
        bag_api_key: str,
        endpoint: str = "https://api.bag.acceptatie.kadaster.nl/lvbag/individuelebevragingen/v2",
        request: BAGRequestService | None = None,
        processing: BAGProcessingService | None = None,
    ):
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
        response = self.request.postcode_huisnummer(postcode, huisnummer)

        if not response:
            return False

        object = self.processing.adresseerbaar_object(response)
        response = self.request.verblijfsobjecten(object)

        if not response:
            return False

        doeleind = self.processing.gebruiksdoelen(response)
        return "woonfunctie" in doeleind
