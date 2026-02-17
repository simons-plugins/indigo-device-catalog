---
name: New Device Profile
about: Submit a device profile for a plugin not yet in the catalog
title: "[Profile] PLUGIN_NAME - DEVICE_TYPE"
labels: new-profile
---

## Device Information

**Plugin ID**: `com.example.myplugin`
**Plugin Name**: My Plugin
**Device Type ID**: `myDeviceType`
**Base Class**: (e.g., indigo.RelayDevice, indigo.DimmerDevice, indigo.ThermostatDevice, indigo.SensorDevice)
**Model** (optional):
**Protocol** (optional): (e.g., zwave, zigbee, mqtt, http)

## Capability Flags

<!-- Check all that apply for your device. Remove any that don't exist for the base class. -->

- [ ] supportsOnState
- [ ] supportsStatusRequest
- [ ] supportsAllLightsOnOff
- [ ] supportsAllOff
- [ ] supportsHeatSetpoint
- [ ] supportsCoolSetpoint
- [ ] supportsHvacOperationMode
- [ ] supportsHvacFanMode
- [ ] supportsSensorValue
- [ ] supportsColor
- [ ] supportsRGB
- [ ] supportsRGBandWhiteSimultaneously
- [ ] supportsWhite
- [ ] supportsWhiteTemperature
- [ ] supportsTwoWhiteLevels
- [ ] supportsTwoWhiteLevelsSimultaneously

## State Keys

<!-- List state key names and their data types (string, number, integer, boolean).
     DO NOT include actual values. -->

| State Key | Type | Description |
|-----------|------|-------------|
| `onOffState` | boolean | On/off state |
| | | |

## Plugin Config Keys

<!-- List the keys from pluginProps. DO NOT include values. -->

- `key1`
- `key2`

## Display

**displayStateId**: `onOffState`
**displayStateImageSel** (optional):

## Privacy Checklist

- [ ] I have NOT included any device names or descriptions
- [ ] I have NOT included any IP addresses or physical locations
- [ ] I have NOT included any API keys or passwords
- [ ] I have NOT included any actual state values
- [ ] I have NOT included any pluginProps values
