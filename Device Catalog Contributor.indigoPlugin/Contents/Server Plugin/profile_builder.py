"""
Build privacy-scrubbed device profiles from native Indigo device objects.

Ported from tools/discover.py to work with indigo.Device instances
(accessed via the Python API) instead of HTTP API JSON dicts.
"""

from datetime import date

try:
    import indigo
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Class mappings (copied from tools/discover.py)
# ---------------------------------------------------------------------------

CLASS_TO_FILE = {
    "indigo.DimmerDevice": "dimmer.json",
    "indigo.RelayDevice": "relay.json",
    "indigo.SensorDevice": "sensor.json",
    "indigo.SpeedControlDevice": "speed-control.json",
    "indigo.SprinklerDevice": "sprinkler.json",
    "indigo.ThermostatDevice": "thermostat.json",
    "indigo.Device": "custom.json",
    "indigo.MultiIODevice": "custom.json",
}

CLASS_COMMANDS = {
    "indigo.RelayDevice": {
        "indigo.device.turnOn": {},
        "indigo.device.turnOff": {},
        "indigo.device.toggle": {},
        "indigo.device.statusRequest": {},
    },
    "indigo.DimmerDevice": {
        "indigo.device.turnOn": {},
        "indigo.device.turnOff": {},
        "indigo.device.toggle": {},
        "indigo.dimmer.setBrightness": {"parameters": {"value": "integer (0-100)"}},
        "indigo.device.statusRequest": {},
    },
    "indigo.SensorDevice": {
        "indigo.device.statusRequest": {},
    },
    "indigo.ThermostatDevice": {
        "indigo.thermostat.setHeatSetpoint": {"parameters": {"value": "number"}},
        "indigo.thermostat.setCoolSetpoint": {"parameters": {"value": "number"}},
        "indigo.thermostat.setHvacMode": {"parameters": {"value": "enum:off,heat,cool,auto,program"}},
        "indigo.thermostat.setFanMode": {"parameters": {"value": "enum:auto,on"}},
        "indigo.device.turnOn": {},
        "indigo.device.turnOff": {},
        "indigo.device.statusRequest": {},
    },
    "indigo.SpeedControlDevice": {
        "indigo.speedcontrol.setSpeedLevel": {"parameters": {"value": "integer (0-100)"}},
        "indigo.speedcontrol.setSpeedIndex": {"parameters": {"value": "integer"}},
        "indigo.device.turnOn": {},
        "indigo.device.turnOff": {},
        "indigo.device.statusRequest": {},
    },
    "indigo.SprinklerDevice": {
        "indigo.sprinkler.run": {"parameters": {"schedule": "list of durations"}},
        "indigo.sprinkler.stop": {},
        "indigo.sprinkler.pause": {},
        "indigo.sprinkler.resume": {},
        "indigo.sprinkler.previousZone": {},
        "indigo.sprinkler.nextZone": {},
        "indigo.device.statusRequest": {},
    },
    "indigo.Device": {},
    "indigo.MultiIODevice": {},
}

CLASS_CAPABILITIES = {
    "indigo.RelayDevice": [
        "supportsOnState", "supportsStatusRequest", "supportsAllLightsOnOff", "supportsAllOff",
    ],
    "indigo.DimmerDevice": [
        "supportsOnState", "supportsStatusRequest", "supportsAllLightsOnOff", "supportsAllOff",
        "supportsColor", "supportsRGB", "supportsRGBandWhiteSimultaneously",
        "supportsWhite", "supportsWhiteTemperature",
        "supportsTwoWhiteLevels", "supportsTwoWhiteLevelsSimultaneously",
    ],
    "indigo.SensorDevice": [
        "supportsOnState", "supportsSensorValue", "supportsStatusRequest",
    ],
    "indigo.ThermostatDevice": [
        "supportsHeatSetpoint", "supportsCoolSetpoint",
        "supportsHvacOperationMode", "supportsHvacFanMode",
        "supportsStatusRequest",
    ],
    "indigo.SpeedControlDevice": [
        "supportsOnState", "supportsStatusRequest",
    ],
    "indigo.SprinklerDevice": [
        "supportsStatusRequest",
    ],
    "indigo.Device": [
        "supportsOnState", "supportsStatusRequest", "supportsAllLightsOnOff",
    ],
    "indigo.MultiIODevice": [
        "supportsOnState", "supportsStatusRequest",
    ],
}

# Map native Indigo class names to the "indigo.ClassName" strings used in the catalog
_CLASS_NAME_MAP = {
    "DimmerDevice": "indigo.DimmerDevice",
    "RelayDevice": "indigo.RelayDevice",
    "SensorDevice": "indigo.SensorDevice",
    "SpeedControlDevice": "indigo.SpeedControlDevice",
    "SprinklerDevice": "indigo.SprinklerDevice",
    "ThermostatDevice": "indigo.ThermostatDevice",
    "MultiIODevice": "indigo.MultiIODevice",
    "Device": "indigo.Device",
}


def infer_type(value):
    """Infer the JSON schema type from a Python value."""
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return "string"


def get_device_class_name(dev):
    """Get the catalog class name string (e.g. 'indigo.ThermostatDevice') from a native device."""
    raw_name = dev.__class__.__name__
    return _CLASS_NAME_MAP.get(raw_name, "indigo.Device")


def extract_protocol(dev):
    """Extract protocol string from native Indigo device."""
    plugin_id = getattr(dev, "pluginId", "")
    protocol = getattr(dev, "protocol", None)

    # Check if protocol is a known constant with a useful value
    if protocol is not None:
        proto_str = str(protocol)
        if proto_str and proto_str not in ("unknown", "Plugin"):
            return proto_str.lower()

    # Infer from plugin ID
    pid_lower = plugin_id.lower()
    if "zwave" in pid_lower:
        return "zwave"
    if "zigbee" in pid_lower:
        return "zigbee"
    if "mqtt" in pid_lower:
        return "mqtt"
    if "insteon" in pid_lower:
        return "insteon"
    return ""


def build_profile(dev, contributor):
    """
    Build a privacy-scrubbed profile dict from a native Indigo device object.

    Only structural metadata is captured (state keys, types, capability flags).
    No device names, addresses, or state values are included.
    """
    dev_class = get_device_class_name(dev)
    capabilities_list = CLASS_CAPABILITIES.get(dev_class, [])

    # Gather capability flags
    capabilities = {}
    for cap in capabilities_list:
        val = getattr(dev, cap, None)
        if val is not None:
            capabilities[cap] = bool(val)
    # Also pick up any extra supports* flags not in the standard list
    for attr in dir(dev):
        if attr.startswith("supports") and attr not in capabilities:
            val = getattr(dev, attr, None)
            if isinstance(val, bool):
                capabilities[attr] = val

    # Extract state keys and infer types from current values (values themselves are not stored)
    states = {}
    dev_states = getattr(dev, "states", {})
    if dev_states:
        for key in dev_states:
            states[key] = {"type": infer_type(dev_states[key])}

    # Extract plugin property keys only (no values - privacy)
    plugin_props_keys = []
    props = getattr(dev, "pluginProps", {})
    if props:
        plugin_props_keys = sorted(props.keys())

    # Get plugin name from Indigo's plugin registry
    plugin_id = getattr(dev, "pluginId", "unknown")
    try:
        plugin_info = indigo.server.getPlugin(plugin_id)
        plugin_name = plugin_info.pluginDisplayName if plugin_info else plugin_id
    except Exception:
        plugin_name = plugin_id

    profile = {
        "pluginId": plugin_id,
        "pluginName": plugin_name,
        "deviceTypeId": getattr(dev, "deviceTypeId", "unknown"),
        "capabilities": capabilities,
        "states": states,
        "metadata": {
            "contributedBy": contributor,
            "discoveredAt": date.today().isoformat(),
        },
    }

    # Optional fields
    model = getattr(dev, "model", "")
    if model:
        profile["model"] = model

    sub_model = getattr(dev, "subModel", "")
    if sub_model:
        profile["subModel"] = sub_model

    protocol = extract_protocol(dev)
    if protocol:
        profile["protocol"] = protocol

    if plugin_props_keys:
        profile["pluginConfigKeys"] = plugin_props_keys

    display_state_id = getattr(dev, "displayStateId", "")
    if display_state_id:
        profile["displayStateId"] = display_state_id

    display_state_image = getattr(dev, "displayStateImageSel", "")
    if display_state_image:
        profile["displayStateImageSel"] = str(display_state_image)

    return profile
