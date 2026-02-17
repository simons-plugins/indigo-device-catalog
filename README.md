# Indigo Device Capability Catalog

A machine-readable catalog of device capabilities across the [Indigo](https://www.indigodomo.com) home automation ecosystem.

## Why This Exists

Indigo has 6 base device classes (relay, dimmer, thermostat, sensor, sprinkler, speed control), but a thermostat from Shelly MQTT is fundamentally different from one created by Z-Wave -- different capability flags, states, and control methods. This catalog maps `(baseClass, pluginId, deviceTypeId)` to actual capabilities so that:

- **iOS/web clients** can render device controls at runtime without hardcoding per-plugin logic
- **Developers** building Indigo integrations can understand what devices support
- **The community** can contribute profiles for plugins not yet cataloged

## Structure

```
catalog/
  _index.json              # Master index of all profiles
  by-class/
    thermostat.json        # All thermostat profiles across plugins
    dimmer.json
    relay.json
    sensor.json
    speed-control.json
    sprinkler.json
    custom.json            # indigo.Device / indigo.MultiIODevice
  by-plugin/
    _index.json            # Cross-reference: plugin -> device types
schema/
  device-profile.schema.json
```

### By-Class Files

Each file contains all profiles for a single Indigo base class. Every profile documents:

- **Plugin identity**: `pluginId`, `pluginName`, `deviceTypeId`
- **Capabilities**: which `supports*` flags are true/false
- **States**: all state keys with inferred types
- **Config keys**: `pluginProps` key names (no values)
- **Display**: `displayStateId`, `displayStateImageSel`

### Master Index

`catalog/_index.json` provides a lightweight summary suitable for loading at app startup to determine which profiles are available.

## Usage

### Looking up a device's capabilities

```python
import json

# Load the class file
with open("catalog/by-class/thermostat.json") as f:
    data = json.load(f)

# Find a specific plugin's profile
profile = next(
    p for p in data["profiles"]
    if p["pluginId"] == "com.lionsheeptechnology.ShellyMQTT"
    and p["deviceTypeId"] == "shelly-trv"
)

print(profile["capabilities"])
# {"supportsHeatSetpoint": true, "supportsCoolSetpoint": false, ...}
```

### iOS app integration

The catalog JSON can be bundled into an iOS app's resources. At runtime, look up the device's `pluginId` and `deviceTypeId` to determine which controls to render -- no code changes needed when new device types are added.

## Privacy

This catalog contains **no personal data**:
- No device names, addresses, or descriptions
- No IP addresses, API keys, or configuration values
- No device counts or folder structures
- Only structural metadata: plugin IDs, device type IDs, capability flags, and state key names

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to add profiles for plugins not yet in the catalog.

## License

[MIT](LICENSE)
