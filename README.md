# Essent dynamic pricing client

Async client for Essent's public dynamic price API, returning normalized electricity
and gas tariffs ready for Home Assistant or other consumers. Tariff start/end values
are returned as timezone-aware datetimes in the Europe/Amsterdam timezone.

## Usage

```python
import asyncio
from aiohttp import ClientSession
from essent_dynamic_pricing import EssentClient

async def main():
    async with ClientSession() as session:
        client = EssentClient(session=session)
        data = await client.async_get_prices()

        # Electricity data is always available
        print(f"Electricity: {data.electricity.min_price} - {data.electricity.max_price} €/{data.electricity.unit}")

        # Gas data may be None if unavailable from API
        if data.gas:
            print(f"Gas: {data.gas.min_price} - {data.gas.max_price} €/{data.gas.unit}")
        else:
            print("Gas data not available")

asyncio.run(main())
```

## Breaking Changes in v0.3.0

The `gas` field in `EssentPrices` is now `Optional[EnergyData]` instead of required. This handles cases where the Essent API temporarily doesn't provide gas data. Electricity data is still required.

**Before (v0.2.x):**
```python
data = await client.async_get_prices()
print(data.gas.min_price)  # Always worked
```

**After (v0.3.0):**
```python
data = await client.async_get_prices()
if data.gas:
    print(data.gas.min_price)  # Check for None first
```

## Development / tests

1. Install dev deps (adds pytest and pytest-asyncio):  
   `pip install -e .[test]`
2. Run tests:  
   `pytest`
