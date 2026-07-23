# CONVENTIONS.md — Schema Conventions and Formatting Standards

## JSON Formatting

- **2-space indent** everywhere — all catalog files, schema, and generated output use `json.dumps(data, indent=2)`
- **No trailing commas** — standard JSON
- **UTF-8** encoding throughout
- Profiles within each by-class file are **sorted alphabetically by `(pluginId, deviceTypeId)`** — this is enforced by `merge_profiles_into_catalog()` and `discover.py`'s merge step

## Catalog File Naming

By-class files map to Indigo's base device classes:

| File | Indigo Class |
|------|--------------|
| `dimmer.json` | `indigo.DimmerDevice` |
| `relay.json` | `indigo.RelayDevice` |
| `sensor.json` | `indigo.SensorDevice` |
| `speed-control.json` | `indigo.SpeedControlDevice` |
| `sprinkler.json` | `indigo.SprinklerDevice` |
| `thermostat.json` | `indigo.ThermostatDevice` |
| `custom.json` | `indigo.Device` AND `indigo.MultiIODevice` |

`custom.json` is the catch-all for plugin devices that don't fit a typed base class. Both `indigo.Device` and `indigo.MultiIODevice` map to `custom.json` because both use `baseClass: "indigo.Device"` in profile data (MultiIO has no separate file).

## Profile Field Conventions

### Required fields (schema-enforced)

- `pluginId` — reverse-domain string, e.g. `com.lionsheeptechnology.ShellyMQTT`
- `pluginName` — human-readable, as returned by `indigo.server.getPlugin()` or the HTTP API
- `deviceTypeId` — plugin-defined string, from `dev.deviceTypeId`
- `capabilities` — all keys are `supports*` booleans; include every flag from `classCapabilities` even if false
- `states` — keys are state names, values are `{"type": "<jsontype>"}` only; no actual values
- `metadata.contributedBy` — GitHub username or freeform handle
- `metadata.discoveredAt` — ISO 8601 date string `YYYY-MM-DD`

### Optional fields

- `model` — omit if empty string; from `dev.model`
- `subModel` — omit if empty string; from `dev.subModel`
- `protocol` — lowercase string; inferred from `dev.protocol` or `pluginId` pattern
- `pluginConfigKeys` — sorted list of `pluginProps` key names; omit if empty
- `displayStateId` — the state key shown in Indigo UI; omit if empty
- `displayStateImageSel` — stringified image selector; omit if empty
- `metadata.indigoVersion` — optional, not always populated
- `metadata.pluginVersion` — optional, not always populated

### State type inference

Python types map to JSON Schema types as follows:

| Python | Catalog type |
|--------|-------------|
| `bool` | `"boolean"` |
| `int` | `"integer"` |
| `float` | `"number"` |
| anything else | `"string"` |

Note: Python `bool` is checked before `int` because `bool` is a subclass of `int`.

### Capability convention

Each by-class file has a `classCapabilities` array listing the capability flags relevant for that class. Profiles should include all of those flags in their `capabilities` object, even if the value is `false`. Extra `supports*` flags beyond the standard list may be included if discovered.

Standard capability sets by class:
- **relay**: `supportsOnState`, `supportsStatusRequest`, `supportsAllLightsOnOff`, `supportsAllOff`
- **dimmer**: relay flags + `supportsColor`, `supportsRGB`, `supportsRGBandWhiteSimultaneously`, `supportsWhite`, `supportsWhiteTemperature`, `supportsTwoWhiteLevels`, `supportsTwoWhiteLevelsSimultaneously`
- **sensor**: `supportsOnState`, `supportsSensorValue`, `supportsStatusRequest`
- **thermostat**: `supportsHeatSetpoint`, `supportsCoolSetpoint`, `supportsHvacOperationMode`, `supportsHvacFanMode`, `supportsStatusRequest`
- **speed control**: `supportsOnState`, `supportsStatusRequest`
- **sprinkler**: `supportsStatusRequest`
- **custom**: `supportsOnState`, `supportsStatusRequest`, `supportsAllLightsOnOff`

## Protocol Values

Protocol strings are lowercase. Known values in the catalog:
- `zwave` — inferred from `pluginId` containing "zwave"
- `zigbee` — inferred from `pluginId` containing "zigbee"
- `mqtt` — inferred from `pluginId` containing "mqtt" or "MQTT"
- `insteon` — inferred from `pluginId` containing "insteon"

If protocol cannot be determined, the field is omitted entirely.

## Contribution Branch Naming

Automated contribution branches follow the pattern:

```
contribute/<contributorName>/<YYYY-MM-DD>
```

Examples:
- `contribute/simons-plugins/2026-02-17`
- `contribute/CliveS/2026-02-24`

The `auto-merge.yml` workflow matches on `startsWith(github.head_ref, 'contribute/')`.

## Version Numbering (Plugin)

Format: `YYYY.R.patch`
- `YYYY` — year
- `R` — release number within the year
- `patch` — patch increment

Current version: `2024.2.1`. Stored in `Info.plist` as `<key>PluginVersion</key>`. Must be bumped on every PR that touches plugin files.

## Privacy Conventions

These are not schema-enforced but are expected by the contribution process:

- State keys: include all keys, include inferred types from current values, but discard the values themselves
- Config keys: include key names only, never values (no IP addresses, tokens, passwords)
- No device names, IDs, descriptions, folder names, or installation-specific data
- The profile builder implements these conventions — values are passed through `infer_type()` which returns only the type string, never the value

## $schema Reference

Every by-class file includes:
```json
"$schema": "../../schema/device-profile.schema.json"
```

This relative path works when the file is at `catalog/by-class/<name>.json`. Tools create this reference automatically.
