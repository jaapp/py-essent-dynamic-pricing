"""Tests for the Essent client."""

from __future__ import annotations

import asyncio
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from datetime import datetime, timedelta, timezone
from essent_dynamic_pricing.client import _normalize_unit
from essent_dynamic_pricing.models import PriceResponse

from aiohttp import ClientError

from essent_dynamic_pricing import (
    EssentClient,
    EssentConnectionError,
    EssentDataError,
    EssentResponseError,
)


class _MockResponse:
    """Simple mock response."""

    def __init__(self, status: int, body: Any) -> None:
        """Initialize the response."""
        self.status = status
        self._body = body

    async def text(self) -> str:
        """Return the raw body."""
        if isinstance(self._body, str):
            return self._body
        return repr(self._body)

    async def json(self) -> Any:
        """Return the JSON body."""
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class _MockSession:
    """Mock session returning fixed responses."""

    def __init__(self, response: _MockResponse | Exception) -> None:
        self._response = response

    async def get(self, *args: Any, **kwargs: Any) -> _MockResponse:
        """Return the pre-seeded response or raise."""
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def _build_prices() -> dict[str, Any]:
    """Build a sample prices payload."""
    return {
        "prices": [
            {
                "date": "2025-11-16",
                "electricity": {
                    "unitOfMeasurement": "kWh",
                    "tariffs": [
                        {
                            "startDateTime": "2025-11-16T00:00:00",
                            "endDateTime": "2025-11-16T01:00:00",
                            "totalAmount": 0.2,
                        },
                        {
                            "startDateTime": "2025-11-16T01:00:00",
                            "endDateTime": "2025-11-16T02:00:00",
                            "totalAmount": 0.25,
                        },
                    ],
                },
                "gas": {
                    "unit": "m3",
                    "tariffs": [
                        {
                            "startDateTime": "2025-11-16T00:00:00",
                            "endDateTime": "2025-11-16T01:00:00",
                            "totalAmount": 0.8,
                        },
                        {
                            "startDateTime": "2025-11-16T01:00:00",
                            "endDateTime": "2025-11-16T02:00:00",
                            "totalAmount": 0.82,
                        },
                    ],
                },
            },
            {
                "date": "2025-11-17",
                "electricity": {
                    "unitOfMeasurement": "kWh",
                    "tariffs": [
                        {
                            "startDateTime": "2025-11-17T00:00:00",
                            "endDateTime": "2025-11-17T01:00:00",
                            "totalAmount": 0.22,
                        },
                    ],
                },
                "gas": {
                    "unit": "m3",
                    "tariffs": [
                        {
                            "startDateTime": "2025-11-17T00:00:00",
                            "endDateTime": "2025-11-17T01:00:00",
                            "totalAmount": 0.85,
                        },
                    ],
                },
            },
        ]
    }


@pytest.mark.asyncio
async def test_fetch_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test a successful fetch."""
    response = _MockResponse(status=200, body=_build_prices())
    client = EssentClient(_MockSession(response))

    data = await client.async_get_prices()

    assert data.electricity.min_price == 0.2
    assert data.electricity.max_price == 0.25
    assert data.gas.unit == "m³"
    assert data.electricity.tariffs[0].start == datetime(
        2025, 11, 16, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam")
    )
    assert data.gas.tariffs[0].start.tzinfo == ZoneInfo("Europe/Amsterdam")


@pytest.mark.asyncio
async def test_non_ok_status() -> None:
    """Test non-200 handling."""
    response = _MockResponse(status=500, body="error")
    client = EssentClient(_MockSession(response))

    with pytest.raises(EssentResponseError):
        await client.async_get_prices()


@pytest.mark.asyncio
async def test_invalid_json() -> None:
    """Test invalid JSON handling."""
    response = _MockResponse(status=200, body=ValueError("boom"))
    client = EssentClient(_MockSession(response))

    with pytest.raises(EssentResponseError):
        await client.async_get_prices()


@pytest.mark.asyncio
async def test_missing_prices() -> None:
    """Test empty prices payload."""
    response = _MockResponse(status=200, body={"prices": []})
    client = EssentClient(_MockSession(response))

    with pytest.raises(EssentDataError):
        await client.async_get_prices()


@pytest.mark.asyncio
async def test_connection_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test connection errors are raised properly."""
    client = EssentClient(_MockSession(ClientError("boom")))

    with pytest.raises(EssentConnectionError):
        await client.async_get_prices()


@pytest.mark.asyncio
async def test_missing_energy_block() -> None:
    """Response missing electricity or gas data should error."""
    today = datetime.now(timezone.utc).date().isoformat()
    response = _MockResponse(
        status=200,
        body={"prices": [{"date": today, "electricity": None, "gas": {}}]},
    )
    client = EssentClient(_MockSession(response))

    with pytest.raises(EssentDataError, match="Response missing electricity data"):
        await client.async_get_prices()


@pytest.mark.asyncio
async def test_selects_today_entry() -> None:
    """When today's date is present it should be preferred."""
    today = datetime.now(timezone.utc).date().isoformat()
    body = {
        "prices": [
            {
                "date": today,
                "electricity": {
                    "tariffs": [
                        {
                            "startDateTime": "2025-11-16T00:00:00",
                            "endDateTime": "2025-11-16T01:00:00",
                            "totalAmount": 0.3,
                        }
                    ],
                    "unitOfMeasurement": "kWh",
                },
                "gas": {
                    "tariffs": [
                        {
                            "startDateTime": "2025-11-16T00:00:00",
                            "endDateTime": "2025-11-16T01:00:00",
                            "totalAmount": 0.9,
                        }
                    ],
                    "unit": "m3",
                },
            },
            {
                "date": "2025-11-17",
                "electricity": {
                    "tariffs": [
                        {
                            "startDateTime": "2025-11-17T00:00:00",
                            "endDateTime": "2025-11-17T01:00:00",
                            "totalAmount": 0.4,
                        }
                    ],
                    "unitOfMeasurement": "kWh",
                },
                "gas": {
                    "tariffs": [
                        {
                            "startDateTime": "2025-11-17T00:00:00",
                            "endDateTime": "2025-11-17T01:00:00",
                            "totalAmount": 1.0,
                        }
                    ],
                    "unit": "m3",
                },
            },
        ]
    }
    client = EssentClient(_MockSession(_MockResponse(status=200, body=body)))

    data = await client.async_get_prices()

    assert data.electricity.min_price == 0.3
    assert data.electricity.tariffs_tomorrow[0].total_amount == 0.4
    assert data.gas.tariffs_tomorrow[0].total_amount == 1.0


@pytest.mark.asyncio
async def test_missing_gas_for_future_day() -> None:
    """Missing gas for a future day should not block electricity data."""
    today = datetime.now(timezone.utc).date()
    tomorrow = today + timedelta(days=1)
    response = _MockResponse(
        status=200,
        body={
            "prices": [
                {
                    "date": today.isoformat(),
                    "electricity": {
                        "tariffs": [
                            {
                                "startDateTime": "2025-11-16T00:00:00",
                                "endDateTime": "2025-11-16T01:00:00",
                                "totalAmount": 0.3,
                            }
                        ],
                        "unitOfMeasurement": "kWh",
                    },
                    "gas": {
                        "tariffs": [
                            {
                                "startDateTime": "2025-11-16T00:00:00",
                                "endDateTime": "2025-11-16T01:00:00",
                                "totalAmount": 0.9,
                            }
                        ],
                        "unit": "m3",
                    },
                },
                {
                    "date": tomorrow.isoformat(),
                    "electricity": {
                        "tariffs": [
                            {
                                "startDateTime": "2025-11-17T00:00:00",
                                "endDateTime": "2025-11-17T01:00:00",
                                "totalAmount": 0.4,
                            }
                        ],
                        "unitOfMeasurement": "kWh",
                    },
                },
            ]
        },
    )
    client = EssentClient(_MockSession(response))

    data = await client.async_get_prices()

    assert data.electricity.tariffs_tomorrow[0].total_amount == 0.4
    assert data.gas.tariffs_tomorrow == []


@pytest.mark.asyncio
async def test_invalid_today_structure() -> None:
    """Invalid today structure should raise."""
    today = datetime.now(timezone.utc).date().isoformat()
    response = _MockResponse(
        status=200,
        body={
            "prices": [
                {"date": "not-today"},
                {"date": today, "electricity": "bad", "gas": "bad"},
            ]
        },
    )
    client = EssentClient(_MockSession(response))

    with pytest.raises(EssentDataError, match="Invalid data structure"):
        await client.async_get_prices()


@pytest.mark.asyncio
async def test_no_tariffs() -> None:
    """No tariffs should raise a data error."""
    today = datetime.now(timezone.utc).date().isoformat()
    response = _MockResponse(
        status=200,
        body={
            "prices": [
                {
                    "date": today,
                    "electricity": {"tariffs": []},
                    "gas": {"tariffs": [{"totalAmount": 0.8}], "unit": "m3"},
                }
            ]
        },
    )
    client = EssentClient(_MockSession(response))

    with pytest.raises(EssentDataError, match="No tariffs found for electricity"):
        await client.async_get_prices()


@pytest.mark.asyncio
async def test_no_amounts() -> None:
    """Tariffs without totals should raise a data error."""
    today = datetime.now(timezone.utc).date().isoformat()
    response = _MockResponse(
        status=200,
        body={
            "prices": [
                {
                    "date": today,
                    "electricity": {
                        "tariffs": [
                            {
                                "startDateTime": "2025-11-16T00:00:00",
                                "endDateTime": "2025-11-16T01:00:00",
                            }
                        ]
                    },
                    "gas": {"tariffs": [{"totalAmount": 0.8}], "unit": "m3"},
                }
            ]
        },
    )
    client = EssentClient(_MockSession(response))

    with pytest.raises(EssentDataError, match="No usable tariff values for electricity"):
        await client.async_get_prices()


@pytest.mark.asyncio
async def test_no_unit() -> None:
    """Missing unit should raise a data error."""
    today = datetime.now(timezone.utc).date().isoformat()
    response = _MockResponse(
        status=200,
        body={
            "prices": [
                {
                    "date": today,
                    "electricity": {
                        "tariffs": [
                            {
                                "startDateTime": "2025-11-16T00:00:00",
                                "endDateTime": "2025-11-16T01:00:00",
                                "totalAmount": 0.25,
                            }
                        ]
                    },
                    "gas": {
                        "tariffs": [
                            {
                                "startDateTime": "2025-11-16T00:00:00",
                                "endDateTime": "2025-11-16T01:00:00",
                                "totalAmount": 0.82,
                            }
                        ],
                        "unit": "m³",
                    },
                }
            ]
        },
    )
    client = EssentClient(_MockSession(response))

    with pytest.raises(EssentDataError, match="No unit provided for electricity"):
        await client.async_get_prices()


@pytest.mark.asyncio
async def test_missing_tariff_bounds() -> None:
    """Missing start or end should raise a data error."""
    today = datetime.now(timezone.utc).date().isoformat()
    response = _MockResponse(
        status=200,
        body={
            "prices": [
                {
                    "date": today,
                    "electricity": {
                        "tariffs": [{"endDateTime": "2025-11-16T01:00:00"}],
                        "unit": "kWh",
                    },
                    "gas": {
                        "tariffs": [
                            {
                                "startDateTime": "2025-11-16T00:00:00",
                                "totalAmount": 0.8,
                            }
                        ],
                        "unit": "m3",
                    },
                }
            ]
        },
    )
    client = EssentClient(_MockSession(response))

    with pytest.raises(EssentDataError, match="Tariff missing start or end for electricity"):
        await client.async_get_prices()


def test_normalize_unit_passthrough() -> None:
    """Unknown unit should be returned unchanged."""
    assert _normalize_unit("unknown") == "unknown"


def test_select_days_prefers_today_and_tomorrow() -> None:
    """_select_days should return today entry and next as tomorrow when available."""
    today = datetime.now(timezone.utc).date().isoformat()
    resp = PriceResponse.from_dict(
        {
            "prices": [
                {
                    "date": today,
                    "electricity": {"unit": "kWh", "tariffs": [{"totalAmount": 1}]},
                    "gas": {"unit": "m3", "tariffs": [{"totalAmount": 1}]},
                },
                {
                    "date": "next",
                    "electricity": {"unit": "kWh", "tariffs": [{"totalAmount": 2}]},
                    "gas": {"unit": "m3", "tariffs": [{"totalAmount": 2}]},
                },
            ]
        }
    )

    selected_today, selected_tomorrow = EssentClient._select_days(resp.prices)

    assert selected_today.electricity.tariffs[0].total_amount == 1
    assert selected_tomorrow is not None
    assert selected_tomorrow.electricity.tariffs[0].total_amount == 2


def test_select_days_invalid_structure_raises() -> None:
    """Empty prices should raise a data error."""
    with pytest.raises(EssentDataError, match="No price data available"):
        EssentClient._select_days([])
