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
        print(data["electricity"]["min_price"])

asyncio.run(main())
```

## Development / tests

1. Install dev deps (adds pytest and pytest-asyncio):  
   `pip install -e .[test]`
2. Run tests:  
   `pytest`
