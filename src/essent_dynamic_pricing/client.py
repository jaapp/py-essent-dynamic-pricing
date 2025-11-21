"""Async client for Essent dynamic pricing."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from typing import Any

from aiohttp import ClientError, ClientResponse, ClientSession, ClientTimeout

from .exceptions import EssentConnectionError, EssentDataError, EssentResponseError
from .models import EssentData, EssentEnergyData

API_ENDPOINT = "https://www.essent.nl/api/public/tariffmanagement/dynamic-prices/v1/"
CLIENT_TIMEOUT = ClientTimeout(total=10)


def _tariff_sort_key(tariff: dict[str, Any]) -> str:
    """Sort key for tariffs based on start time."""
    return tariff.get("startDateTime", "")


def _normalize_unit(unit: str) -> str:
    """Normalize unit strings to human-friendly values."""
    unit_normalized = unit.replace("³", "3").lower()
    if unit_normalized == "kwh":
        return "kWh"
    if unit_normalized in {"m3", "m^3"}:
        return "m³"
    return unit


class EssentClient:
    """Client for fetching Essent dynamic pricing data."""

    def __init__(
        self,
        session: ClientSession,
        *,
        endpoint: str = API_ENDPOINT,
        timeout: ClientTimeout = CLIENT_TIMEOUT,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self._endpoint = endpoint
        self._timeout = timeout

    async def async_get_prices(self) -> EssentData:
        """Fetch and normalize Essent dynamic pricing data."""
        response = await self._request()
        body = await response.text()

        if response.status != HTTPStatus.OK:
            raise EssentResponseError(
                f"Unexpected status {response.status} from Essent API: {body}"
            )

        try:
            data = await response.json()
        except ValueError as err:
            raise EssentResponseError("Invalid JSON received from Essent API") from err

        prices = data.get("prices") or []
        if not prices:
            raise EssentDataError("No price data available")

        today, tomorrow = self._select_days(prices)

        electricity_block = today.get("electricity")
        gas_block = today.get("gas")

        if not isinstance(electricity_block, dict) or not isinstance(gas_block, dict):
            raise EssentDataError("Response missing electricity or gas data")

        return {
            "electricity": self._normalize_energy_block(
                electricity_block,
                "electricity",
                tomorrow.get("electricity") if isinstance(tomorrow, dict) else None,
            ),
            "gas": self._normalize_energy_block(
                gas_block,
                "gas",
                tomorrow.get("gas") if isinstance(tomorrow, dict) else None,
            ),
        }

    async def _request(self) -> ClientResponse:
        """Perform the HTTP request."""
        try:
            return await self._session.get(
                self._endpoint,
                timeout=self._timeout,
                headers={"Accept": "application/json"},
            )
        except ClientError as err:
            raise EssentConnectionError(f"Error communicating with API: {err}") from err

    @staticmethod
    def _select_days(
        prices: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        """Find entries for today and tomorrow from the price list."""
        current_date = datetime.now(timezone.utc).astimezone().date().isoformat()
        dict_prices = [price for price in prices if isinstance(price, dict)]
        if not dict_prices:
            raise EssentDataError("Invalid data structure for current prices")

        today = next(
            (price for price in dict_prices if price.get("date") == current_date),
            dict_prices[0],
        )

        tomorrow: dict[str, Any] | None = None
        today_index = dict_prices.index(today)
        if today_index + 1 < len(dict_prices):
            tomorrow = dict_prices[today_index + 1]

        return today, tomorrow

    def _normalize_energy_block(
        self,
        data: dict[str, Any],
        energy_type: str,
        tomorrow: dict[str, Any] | None,
    ) -> EssentEnergyData:
        """Normalize the energy block into the client format."""
        tariffs_today = sorted(
            data.get("tariffs", []),
            key=_tariff_sort_key,
        )
        if not tariffs_today:
            raise EssentDataError(f"No tariffs found for {energy_type}")

        tariffs_tomorrow: list[dict[str, Any]] = []
        if tomorrow:
            tariffs_tomorrow = sorted(
                tomorrow.get("tariffs", []),
                key=_tariff_sort_key,
            )
        unit = (data.get("unitOfMeasurement") or data.get("unit") or "").strip()

        amounts = [
            float(total)
            for tariff in tariffs_today
            if (total := tariff.get("totalAmount")) is not None
        ]
        if not amounts:
            raise EssentDataError(f"No usable tariff values for {energy_type}")

        if not unit:
            raise EssentDataError(f"No unit provided for {energy_type}")

        return {
            "tariffs": tariffs_today,
            "tariffs_tomorrow": tariffs_tomorrow,
            "unit": _normalize_unit(unit),
            "min_price": min(amounts),
            "avg_price": sum(amounts) / len(amounts),
            "max_price": max(amounts),
        }
