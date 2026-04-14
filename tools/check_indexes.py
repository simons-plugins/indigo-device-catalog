#!/usr/bin/env python3
"""Check that catalog/_index.json and catalog/by-plugin/_index.json are
in sync with the by-class files.

Regenerates both indexes in memory from the by-class files and compares
against the committed versions, ignoring the `generated` timestamp field.
Exits non-zero on any mismatch so CI can block stale PRs.

This is the read-only counterpart of `discover.py::regenerate_indexes`.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CATALOG_DIR = REPO_ROOT / "catalog"
BY_CLASS_DIR = CATALOG_DIR / "by-class"
BY_PLUGIN_DIR = CATALOG_DIR / "by-plugin"


def build_indexes() -> tuple[dict, dict]:
    """Build both indexes from the by-class files in memory."""
    index: dict = {"classes": {}}
    plugin_index: dict = {"plugins": {}}

    for path in sorted(BY_CLASS_DIR.glob("*.json")):
        with open(path) as f:
            data = json.load(f)

        dev_class = data["baseClass"]
        profiles = data.get("profiles", [])

        class_entry: dict = {
            "file": f"by-class/{path.name}",
            "profileCount": len(profiles),
            "plugins": {},
        }
        for p in profiles:
            pid = p["pluginId"]
            if pid not in class_entry["plugins"]:
                class_entry["plugins"][pid] = {
                    "pluginName": p["pluginName"],
                    "deviceTypeIds": [],
                }
            class_entry["plugins"][pid]["deviceTypeIds"].append(p["deviceTypeId"])

            if pid not in plugin_index["plugins"]:
                plugin_index["plugins"][pid] = {
                    "pluginName": p["pluginName"],
                    "deviceTypes": [],
                }
            plugin_index["plugins"][pid]["deviceTypes"].append(
                {"baseClass": dev_class, "deviceTypeId": p["deviceTypeId"]}
            )

        index["classes"][dev_class] = class_entry

    plugin_index["plugins"] = dict(sorted(plugin_index["plugins"].items()))
    for pid in plugin_index["plugins"]:
        plugin_index["plugins"][pid]["deviceTypes"] = sorted(
            plugin_index["plugins"][pid]["deviceTypes"],
            key=lambda x: (x["baseClass"], x["deviceTypeId"]),
        )

    return index, plugin_index


def strip_generated(d: dict) -> dict:
    """Return a copy of the dict without its top-level `generated` field."""
    return {k: v for k, v in d.items() if k != "generated"}


def main() -> int:
    errors = 0

    if not BY_CLASS_DIR.exists():
        print(f"ERROR: {BY_CLASS_DIR} not found")
        return 1

    expected_index, expected_plugin_index = build_indexes()

    for rel, expected in [
        (CATALOG_DIR / "_index.json", expected_index),
        (BY_PLUGIN_DIR / "_index.json", expected_plugin_index),
    ]:
        label = rel.relative_to(REPO_ROOT)
        if not rel.exists():
            print(f"ERROR: {label} is missing — run tools/discover.py")
            errors += 1
            continue

        with open(rel) as f:
            committed = json.load(f)

        if strip_generated(committed) != expected:
            print(f"ERROR: {label} is out of sync with catalog/by-class/")
            print("  Run tools/discover.py on a local checkout and commit the result.")
            errors += 1
        else:
            print(f"OK  {label}")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
