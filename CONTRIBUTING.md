# Contributing to the Indigo Device Catalog

Thank you for helping expand the catalog! Every new device profile helps the community build better Indigo clients.

## Before You Start

- Check if the device type is already cataloged in the relevant `catalog/by-class/*.json` file
- Each unique `(pluginId, deviceTypeId)` combination needs only one profile

## How to Contribute

### Option 1: GitHub Issue (Easiest)

1. Open a [New Device Profile](../../issues/new?template=new-device-profile.md) issue
2. Fill in the template with your device details
3. A maintainer will add it to the catalog

### Option 2: Pull Request

1. Fork this repository
2. Add your profile to the appropriate `catalog/by-class/*.json` file
3. Run validation: `python tools/validate.py`
4. Submit a PR

### What to Include

For each device profile, we need:

| Field | Required | Example |
|-------|----------|---------|
| `pluginId` | Yes | `com.example.myplugin` |
| `pluginName` | Yes | `My Plugin` |
| `deviceTypeId` | Yes | `myDeviceType` |
| `model` | No | `Widget Pro 3000` |
| `protocol` | No | `mqtt` |
| `capabilities` | Yes | `{"supportsOnState": true, ...}` |
| `states` | Yes | `{"onOffState": {"type": "boolean"}, ...}` |
| `pluginConfigKeys` | No | `["address", "pollInterval"]` |
| `displayStateId` | No | `onOffState` |

### What NOT to Include

- Device names, descriptions, or folder assignments
- IP addresses, MAC addresses, or physical locations
- API keys, passwords, or authentication tokens
- Actual state values -- only the key names and types
- Device counts or any information about your specific installation

### Getting Device Information

In the Indigo scripting console, you can inspect a device:

```python
dev = indigo.devices[123456789]  # Replace with your device ID

# These are safe to share:
print(f"pluginId: {dev.pluginId}")
print(f"deviceTypeId: {dev.deviceTypeId}")
print(f"model: {dev.model}")
print(f"subModel: {dev.subModel}")
print(f"protocol: {dev.protocol}")
print(f"displayStateId: {dev.displayStateId}")

# Capability flags:
for attr in dir(dev):
    if attr.startswith("supports"):
        print(f"  {attr}: {getattr(dev, attr)}")

# State keys and types (DO NOT share actual values):
for key, val in dev.states.items():
    print(f"  {key}: {type(val).__name__}")

# Plugin config keys only (DO NOT share values):
print(f"pluginProps keys: {list(dev.pluginProps.keys())}")
```

### Validation

All JSON files must validate against `schema/device-profile.schema.json`. The CI pipeline runs validation automatically on PRs. To validate locally:

```bash
python tools/validate.py
```

## Code of Conduct

Be respectful. This is a community resource for making Indigo better for everyone.
