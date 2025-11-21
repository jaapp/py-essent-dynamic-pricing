"""Models used by the Essent dynamic client."""

from __future__ import annotations

from typing import Any, TypedDict


class EssentEnergyData(TypedDict):
    """Data for a single Essent energy type."""

    tariffs: list[dict[str, Any]]
    tariffs_tomorrow: list[dict[str, Any]]
    unit: str
    min_price: float
    avg_price: float
    max_price: float


EssentData = dict[str, EssentEnergyData]
