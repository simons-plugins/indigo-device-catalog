#!/usr/bin/env python3
"""
Discover new Indigo device profiles and add them to the catalog.

Connects to your local Indigo server's HTTP API, finds device types not yet
in the catalog, and generates privacy-scrubbed profiles for the new ones.

Usage:
    python tools/discover.py                          # auto-detect, dry run
    python tools/discover.py --apply                  # write new profiles to catalog
    python tools/discover.py --host 192.168.1.10      # specific host
    python tools/discover.py --port 8176 --no-tls     # custom port, no TLS
    python tools/discover.py --contributor alice       # set contributor name

Requirements:
    - Indigo 2023+ with web server enabled (Preferences > Web Server)
    - Python 3.10+ (no external packages needed)
    - Network access to your Indigo server
"""

import argparse
import json
import ssl
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CATALOG_DIR = REPO_ROOT / "catalog"
BY_CLASS_DIR = CATALOG_DIR / "by-class"
BY_PLUGIN_DIR = CATALOG_DIR / "by-plugin"

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


# ---------------------------------------------------------------------------
# Indigo HTTP API client
# ---------------------------------------------------------------------------

class IndigoAPI:
    """Minimal client for Indigo's HTTP API."""

    def __init__(self, host: str, port: int, use_tls: bool, api_key: str | None = None):
        scheme = "https" if use_tls else "http"
        self.base_url = f"{scheme}://{host}:{port}"
        self.api_key = api_key
        # Allow self-signed certs (common for local Indigo)
        self.ssl_ctx = ssl.create_default_context()
        self.ssl_ctx.check_hostname = False
        self.ssl_ctx.verify_mode = ssl.CERT_NONE

    def _get(self, path: str) -> dict:
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/json")
        if self.api_key:
            req.add_header("Authorization", f"Bearer {self.api_key}")
        resp = urllib.request.urlopen(req, context=self.ssl_ctx, timeout=30)
        return json.loads(resp.read())

    def get_devices(self) -> list[dict]:
        """Get all devices via the v2 API."""
        data = self._get("/v2/api/indigo.devices.json")
        if isinstance(data, list):
            return data
        return data.get("devices", data.get("data", []))

    def get_device(self, device_id: int) -> dict:
        """Get a single device's full details."""
        return self._get(f"/v2/api/indigo.devices/{device_id}.json")

    def get_plugins(self) -> list[dict]:
        """Get plugins list (may not be available on all setups)."""
        try:
            return self._get("/v2/api/indigo.plugins.json")
        except Exception:
            return []


# ---------------------------------------------------------------------------
# Profile builder (same logic as generate_catalog.py)
# ---------------------------------------------------------------------------

def infer_type(value) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return "string"


def extract_protocol(dev: dict) -> str:
    plugin_id = dev.get("pluginId", "")
    protocol = dev.get("protocol", "")
    if protocol and protocol not in ("unknown", "indigo.kProtocol.Plugin"):
        return protocol.lower()
    if "zwave" in plugin_id.lower():
        return "zwave"
    if "zigbee" in plugin_id.lower():
        return "zigbee"
    if "mqtt" in plugin_id.lower() or "MQTT" in plugin_id:
        return "mqtt"
    if "insteon" in plugin_id.lower():
        return "insteon"
    return ""


def build_profile(dev: dict, plugin_name: str, contributor: str) -> dict:
    dev_class = dev.get("class", dev.get("deviceClass", "indigo.Device"))
    capabilities_list = CLASS_CAPABILITIES.get(dev_class, [])

    capabilities = {}
    for cap in capabilities_list:
        val = dev.get(cap)
        if val is not None:
            capabilities[cap] = bool(val)
    for key, val in dev.items():
        if key.startswith("supports") and key not in capabilities and isinstance(val, bool):
            capabilities[key] = val

    states = {}
    raw_states = dev.get("states", {})
    if isinstance(raw_states, dict):
        for key, val in raw_states.items():
            states[key] = {"type": infer_type(val)}

    # Config keys: try pluginProps, fall back to globalProps[pluginId]
    plugin_props_keys = []
    props = dev.get("pluginProps", {})
    if isinstance(props, dict) and props:
        plugin_props_keys = sorted(props.keys())
    else:
        global_props = dev.get("globalProps", {})
        plugin_id = dev.get("pluginId", "")
        if isinstance(global_props, dict) and plugin_id in global_props:
            sub = global_props[plugin_id]
            if isinstance(sub, dict):
                plugin_props_keys = sorted(sub.keys())

    profile = {
        "pluginId": dev.get("pluginId", "unknown"),
        "pluginName": plugin_name,
        "deviceTypeId": dev.get("deviceTypeId", "unknown"),
        "capabilities": capabilities,
        "states": states,
        "metadata": {
            "contributedBy": contributor,
            "discoveredAt": date.today().isoformat(),
        },
    }

    for field, key in [("model", "model"), ("subModel", "subModel")]:
        val = dev.get(key, "")
        if val:
            profile[field] = val

    protocol = extract_protocol(dev)
    if protocol:
        profile["protocol"] = protocol
    if plugin_props_keys:
        profile["pluginConfigKeys"] = plugin_props_keys
    if dev.get("displayStateId"):
        profile["displayStateId"] = dev["displayStateId"]
    if dev.get("displayStateImageSel"):
        profile["displayStateImageSel"] = dev["displayStateImageSel"]

    return profile


# ---------------------------------------------------------------------------
# Catalog operations
# ---------------------------------------------------------------------------

def load_existing_profiles() -> set[tuple[str, str]]:
    """Load all (pluginId, deviceTypeId) pairs already in the catalog."""
    existing = set()
    for path in BY_CLASS_DIR.glob("*.json"):
        with open(path) as f:
            data = json.load(f)
        for p in data.get("profiles", []):
            existing.add((p["pluginId"], p["deviceTypeId"]))
    return existing


def merge_profiles_into_catalog(new_profiles: dict[str, list[dict]]):
    """Merge new profiles into existing catalog files and regenerate indexes."""
    today = date.today().isoformat()

    for dev_class, profiles in new_profiles.items():
        filename = CLASS_TO_FILE.get(dev_class, "custom.json")
        filepath = BY_CLASS_DIR / filename

        if filepath.exists():
            with open(filepath) as f:
                data = json.load(f)
            data["profiles"].extend(profiles)
        else:
            data = {
                "$schema": "../../schema/device-profile.schema.json",
                "baseClass": dev_class,
                "classCapabilities": CLASS_CAPABILITIES.get(dev_class, []),
                "profiles": profiles,
            }
            commands = CLASS_COMMANDS.get(dev_class)
            if commands:
                data["classCommands"] = commands

        data["profiles"] = sorted(data["profiles"], key=lambda p: (p["pluginId"], p["deviceTypeId"]))

        BY_CLASS_DIR.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        print(f"  Updated {filename}: now {len(data['profiles'])} profiles")

    # Regenerate indexes
    regenerate_indexes(today)


def regenerate_indexes(generated_date: str):
    """Regenerate _index.json and by-plugin/_index.json from catalog files."""
    index = {"generated": generated_date, "classes": {}}
    plugin_index = {"generated": generated_date, "plugins": {}}

    for path in sorted(BY_CLASS_DIR.glob("*.json")):
        with open(path) as f:
            data = json.load(f)

        dev_class = data["baseClass"]
        profiles = data.get("profiles", [])

        class_entry = {
            "file": f"by-class/{path.name}",
            "profileCount": len(profiles),
            "plugins": {},
        }
        for p in profiles:
            pid = p["pluginId"]
            if pid not in class_entry["plugins"]:
                class_entry["plugins"][pid] = {"pluginName": p["pluginName"], "deviceTypeIds": []}
            class_entry["plugins"][pid]["deviceTypeIds"].append(p["deviceTypeId"])

            if pid not in plugin_index["plugins"]:
                plugin_index["plugins"][pid] = {"pluginName": p["pluginName"], "deviceTypes": []}
            plugin_index["plugins"][pid]["deviceTypes"].append({
                "baseClass": dev_class,
                "deviceTypeId": p["deviceTypeId"],
            })

        index["classes"][dev_class] = class_entry

    with open(CATALOG_DIR / "_index.json", "w") as f:
        json.dump(index, f, indent=2)

    plugin_index["plugins"] = dict(sorted(plugin_index["plugins"].items()))
    for pid in plugin_index["plugins"]:
        plugin_index["plugins"][pid]["deviceTypes"] = sorted(
            plugin_index["plugins"][pid]["deviceTypes"],
            key=lambda x: (x["baseClass"], x["deviceTypeId"]),
        )

    BY_PLUGIN_DIR.mkdir(parents=True, exist_ok=True)
    with open(BY_PLUGIN_DIR / "_index.json", "w") as f:
        json.dump(plugin_index, f, indent=2)

    print("  Regenerated _index.json and by-plugin/_index.json")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Discover new Indigo device profiles and add to the catalog",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/discover.py                    # dry run against localhost
  python tools/discover.py --apply            # discover and write to catalog
  python tools/discover.py --host 10.0.1.5    # remote Indigo server
  python tools/discover.py --contributor bob   # set contributor name
        """,
    )
    parser.add_argument("--host", default="localhost", help="Indigo server hostname (default: localhost)")
    parser.add_argument("--port", type=int, default=8176, help="Indigo web server port (default: 8176)")
    parser.add_argument("--no-tls", action="store_true", help="Use HTTP instead of HTTPS")
    parser.add_argument("--api-key", help="API key for authentication")
    parser.add_argument("--contributor", default="community", help="Contributor name for metadata (default: community)")
    parser.add_argument("--apply", action="store_true", help="Write new profiles to catalog (default: dry run)")
    args = parser.parse_args()

    api = IndigoAPI(args.host, args.port, not args.no_tls, args.api_key)

    # Step 1: Load existing catalog
    existing = load_existing_profiles()
    print(f"Catalog has {len(existing)} existing profiles")

    # Step 2: Get all devices from Indigo
    print(f"Connecting to {api.base_url}...")
    try:
        all_devices = api.get_devices()
    except Exception as e:
        print(f"ERROR: Could not connect to Indigo: {e}")
        print("\nMake sure:")
        print("  - Indigo web server is enabled (Preferences > Web Server)")
        print("  - The host/port are correct")
        print("  - Try --no-tls if using HTTP")
        return 1

    print(f"Found {len(all_devices)} devices")

    # Step 3: Get plugin names
    plugin_names = {}
    plugins = api.get_plugins()
    if plugins:
        for p in plugins:
            pid = p.get("id", p.get("pluginId", ""))
            pname = p.get("name", p.get("pluginName", pid))
            if pid:
                plugin_names[pid] = pname

    # Step 4: Find unique (class, deviceTypeId) combos not in catalog
    combos: dict[tuple[str, str], int] = {}  # (class, deviceTypeId) -> representative device id
    for dev in all_devices:
        dev_class = dev.get("class", dev.get("deviceClass", "indigo.Device"))
        dev_type = dev.get("deviceTypeId", dev.get("device_type_id", ""))
        plugin_id = dev.get("pluginId", "")
        dev_id = dev.get("id", 0)

        key = (plugin_id, dev_type)
        if key not in existing and key not in combos:
            combos[(plugin_id, dev_type)] = dev_id

    if not combos:
        print("\nNo new device types found - catalog is up to date!")
        return 0

    print(f"\nFound {len(combos)} new device type(s):")
    for (pid, dtype), dev_id in sorted(combos.items()):
        pname = plugin_names.get(pid, pid)
        print(f"  {pname}: {dtype}")

    # Step 5: Fetch full details for each new representative
    print(f"\nFetching details for {len(combos)} device(s)...")
    new_profiles: dict[str, list[dict]] = defaultdict(list)
    errors = 0

    for (plugin_id, dev_type), dev_id in sorted(combos.items()):
        try:
            dev = api.get_device(dev_id)
            dev_class = dev.get("class", dev.get("deviceClass", "indigo.Device"))
            pname = plugin_names.get(plugin_id, plugin_id)
            profile = build_profile(dev, pname, args.contributor)
            new_profiles[dev_class].append(profile)
            print(f"  OK: {pname} / {dev_type}")
        except Exception as e:
            print(f"  FAIL: {plugin_id} / {dev_type} (device {dev_id}): {e}")
            errors += 1

    total_new = sum(len(v) for v in new_profiles.values())
    print(f"\nDiscovered {total_new} new profile(s) ({errors} error(s))")

    if not total_new:
        return 1 if errors else 0

    # Step 6: Apply or dry-run
    if args.apply:
        print("\nApplying to catalog...")
        merge_profiles_into_catalog(new_profiles)
        print(f"\nDone! {total_new} new profile(s) added to catalog.")
        print("Run 'python tools/validate.py' to verify, then commit and PR.")
    else:
        print("\nDry run - showing what would be added:")
        print(json.dumps(
            {cls: [p["pluginId"] + ":" + p["deviceTypeId"] for p in profiles]
             for cls, profiles in new_profiles.items()},
            indent=2,
        ))
        print(f"\nRe-run with --apply to write these to the catalog.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
