"""Models used by the Essent dynamic client."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

from mashumaro.mixins.dict import DataClassDictMixin


@dataclass
class Tariff(DataClassDictMixin):
    """A single tariff entry."""

    start: Optional[str] = field(default=None, metadata={"alias": "startDateTime"})
    end: Optional[str] = field(default=None, metadata={"alias": "endDateTime"})
    total_amount: Optional[float] = field(default=None, metadata={"alias": "totalAmount"})
    total_amount_ex: Optional[float] = field(default=None, metadata={"alias": "totalAmountEx"})
    total_amount_vat: Optional[float] = field(default=None, metadata={"alias": "totalAmountVat"})
    groups: List[dict[str, Any]] = field(default_factory=list)

    class Config:
        serialize_by_alias = True


@dataclass
class EnergyBlock(DataClassDictMixin):
    """Raw energy block from the API."""

    tariffs: List[Tariff] = field(default_factory=list)
    unit: Optional[str] = None
    unit_of_measurement: Optional[str] = field(default=None, metadata={"alias": "unitOfMeasurement"})

    class Config:
        serialize_by_alias = True


@dataclass
class PriceDay(DataClassDictMixin):
    """Prices for a day."""

    date: str
    electricity: EnergyBlock
    gas: EnergyBlock

    class Config:
        serialize_by_alias = True


@dataclass
class PriceResponse(DataClassDictMixin):
    """Top level API response."""

    prices: List[PriceDay]

    class Config:
        serialize_by_alias = True


@dataclass
class EnergyData(DataClassDictMixin):
    """Normalized energy data."""

    tariffs: List[Tariff]
    tariffs_tomorrow: List[Tariff]
    unit: str
    min_price: float
    avg_price: float
    max_price: float

    class Config:
        serialize_by_alias = True


@dataclass
class EssentPrices(DataClassDictMixin):
    """Normalized Essent prices for both energy types."""

    electricity: EnergyData
    gas: EnergyData

    class Config:
        serialize_by_alias = True
