"""Async client for Essent dynamic pricing."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any

from aiohttp import ClientError, ClientResponse, ClientSession, ClientTimeout
from mashumaro.exceptions import ExtraKeysError, InvalidFieldValue, MissingField

from .exceptions import EssentConnectionError, EssentDataError, EssentResponseError
from .models import (
    EnergyData,
    EssentPrices,
    PriceResponse,
    PriceDay,
    Tariff,
)

API_ENDPOINT = "https://www.essent.nl/api/public/tariffmanagement/dynamic-prices/v1/"
CLIENT_TIMEOUT = ClientTimeout(total=10)


def _tariff_sort_key(tariff: Tariff) -> str:
    """Sort key for tariffs based on start time."""
    return tariff.start or ""


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

    async def async_get_prices(self) -> EssentPrices:
        """Fetch and normalize Essent dynamic pricing data."""
        response = await self._request()
        body = await response.text()

        if response.status != HTTPStatus.OK:
            raise EssentResponseError(
                f"Unexpected status {response.status} from Essent API: {body}"
            )

        try:
            price_response = PriceResponse.from_dict(await response.json())
        except (MissingField, InvalidFieldValue, ExtraKeysError) as err:
            raise EssentDataError("Invalid data structure for current prices") from err
        except ValueError as err:
            raise EssentResponseError("Invalid JSON received from Essent API") from err

        if not price_response.prices:
            raise EssentDataError("No price data available")

        today, tomorrow = self._select_days(price_response.prices)

        if today.electricity is None or today.gas is None:
            raise EssentDataError("Response missing electricity or gas data")

        return EssentPrices(
            electricity=self._normalize_energy_block(
                today.electricity,
                "electricity",
                tomorrow.electricity if tomorrow else None,
            ),
            gas=self._normalize_energy_block(
                today.gas,
                "gas",
                tomorrow.gas if tomorrow else None,
            ),
        )

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
        prices: list[PriceDay],
    ) -> tuple[PriceDay, PriceDay | None]:
        """Find entries for today and tomorrow from the price list."""
        if not prices:
            raise EssentDataError("No price data available")

        current_date = datetime.now(timezone.utc).astimezone().date().isoformat()
        today_index = 0
        for idx, price in enumerate(prices):
            if price.date == current_date:
                today_index = idx
                break

        today = prices[today_index]
        tomorrow: PriceDay | None = None
        if today_index + 1 < len(prices):
            tomorrow = prices[today_index + 1]

        return today, tomorrow

    def _normalize_energy_block(
        self,
        data: Any,
        energy_type: str,
        tomorrow: Any | None,
    ) -> EnergyData:
        """Normalize the energy block into the client format."""
        tariffs_today = sorted(data.tariffs, key=_tariff_sort_key)
        if not tariffs_today:
            raise EssentDataError(f"No tariffs found for {energy_type}")

        tariffs_tomorrow = sorted(tomorrow.tariffs, key=_tariff_sort_key) if tomorrow else []
        unit_raw = (data.unit_of_measurement or data.unit or "").strip()

        amounts = [
            float(total)
            for tariff in tariffs_today
            if (total := tariff.total_amount) is not None
        ]
        if not amounts:
            raise EssentDataError(f"No usable tariff values for {energy_type}")

        if not unit_raw:
            raise EssentDataError(f"No unit provided for {energy_type}")

        return EnergyData(
            tariffs=tariffs_today,
            tariffs_tomorrow=tariffs_tomorrow,
            unit=_normalize_unit(unit_raw),
            min_price=min(amounts),
            avg_price=sum(amounts) / len(amounts),
            max_price=max(amounts),
        )
