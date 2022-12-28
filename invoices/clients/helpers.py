import abc
from dataclasses import dataclass

import requests
from loguru import logger

from invoices.clients import model
from invoices.common.helpers import load_config
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


class TimeStampBag:
    def __init__(self):
        self.config = load_config()
        self.url = self.config["general"]["timestamping_api"]
        self.apikey = self.config["general"]["timestamping_apikey"]

    def create_bag_timestamp(
        self,
        postal_code: str,
        house_number: str,
        house_number_addition: str | None = None,
    ):
        result = requests.post(
            f"{self.url}/timestamp/create",
            json={
                "postal_code": postal_code,
                "house_number": house_number,
                "house_number_addition": house_number_addition,
                "apikey": self.apikey,
            },
        )
        result.raise_for_status()
        return result.json()

    def record_from_id(self, id):
        result = requests.get(
            f"{self.url}/timestamp/details/{id}",
            headers={"apikey": self.apikey},
        )
        result.raise_for_status()
        return result.json()
