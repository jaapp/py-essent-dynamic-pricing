# Home Assistant Integration Changes Required

This document describes the changes needed in the Home Assistant `essent` integration to support `essent-dynamic-pricing` v0.3.0.

## Breaking Change Summary

**Library v0.3.0** makes the `gas` field optional in `EssentPrices`:

```python
# BEFORE (v0.2.x)
@dataclass
class EssentPrices:
    electricity: EnergyData  # Required
    gas: EnergyData          # Required

# AFTER (v0.3.0)
@dataclass
class EssentPrices:
    electricity: EnergyData           # Required
    gas: Optional[EnergyData]         # Can be None
```

## Why This Change?

The Essent API currently has a technical issue where gas data is missing. This causes the integration to completely fail, leaving all sensors (both electricity and gas) unavailable. By making gas optional:

- ✅ Electricity sensors continue working when gas data is missing
- ✅ Gas sensors gracefully show "unavailable" instead of crashing
- ✅ When API is fixed, all sensors work normally again

## Required Changes to HA Integration

### File: `homeassistant/components/essent/sensor.py`

**Update the `native_value` property** in the `EssentSensor` class to handle None:

```python
@property
def native_value(self) -> float | None:
    """Return the sensor value."""
    # Get the appropriate energy data based on sensor type
    energy_data = (
        self.coordinator.data.electricity
        if self._energy_type == "electricity"
        else self.coordinator.data.gas
    )

    # Return None if this energy type is unavailable
    if energy_data is None:
        return None

    # Use the value function to extract the specific metric
    return self._value_fn(energy_data)
```

**Alternative approach** - Check during sensor setup (if you want to skip creating sensors):

```python
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Essent sensor platform."""
    coordinator: EssentDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[EssentSensor] = []

    # Always create electricity sensors
    for sensor_description in ELECTRICITY_SENSORS:
        entities.append(
            EssentSensor(coordinator, sensor_description, "electricity")
        )

    # Only create gas sensors if gas data is available
    if coordinator.data.gas is not None:
        for sensor_description in GAS_SENSORS:
            entities.append(
                EssentSensor(coordinator, sensor_description, "gas")
            )

    async_add_entities(entities)
```

## Testing the Changes

### Test Case 1: Gas Missing (Current API State)
- **Expected**: Electricity sensors show values, gas sensors show "unavailable"
- **Library returns**: `EssentPrices(electricity=EnergyData(...), gas=None)`

### Test Case 2: Both Available (Normal Operation)
- **Expected**: All sensors show values
- **Library returns**: `EssentPrices(electricity=EnergyData(...), gas=EnergyData(...))`

### Test Case 3: Both Missing
- **Expected**: Integration fails with error (rare edge case)
- **Library raises**: `EssentDataError("Response missing both electricity and gas data")`

## Migration Steps

1. Update `manifest.json` dependency:
   ```json
   "requirements": ["essent-dynamic-pricing==0.3.0"]
   ```

2. Update `sensor.py` with null-check logic (shown above)

3. Test with current API (gas=None scenario)

4. Submit PR to home-assistant/core with:
   - Updated manifest.json
   - Updated sensor.py
   - Note in PR description about handling API outages

## Rollback Plan

If issues arise, revert to v0.2.7 and accept that the integration will be broken when gas data is missing from the API.