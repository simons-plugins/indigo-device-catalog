#!/usr/bin/env python3
"""Merge a device-catalog contribution file into the by-class catalog.

A contribution file is what the Device Catalog Contributor plugin emits and
what contributors attach to GitHub issues. It is either:

  * a "bundle": an object keyed by by-class filename (e.g. ``custom.json``),
    each value being a class block (``{baseClass, classCapabilities,
    profiles, classCommands?}``); or
  * a single class block with a top-level ``baseClass`` and ``profiles``.

Profiles are merged additively: any ``(pluginId, deviceTypeId)`` already
present in the catalog is skipped, so re-running is idempotent. Class-level
capabilities and commands are unioned (never removed). Both catalog indexes
are regenerated afterwards.

Usage:
    python tools/merge_contribution.py <contribution.json>

Exit status:
    0  merge succeeded (whether or not anything new was added)
    1  the contribution could not be parsed / had an unrecognised shape

The summary line reports how many profiles were added vs skipped so callers
(e.g. CI) can decide whether there is anything to open a PR for.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

# Reuse the catalog constants and index regeneration from discover.py so the
# two tools stay in lock-step on file naming, defaults and index format.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from discover import (  # noqa: E402
    BY_CLASS_DIR,
    CLASS_CAPABILITIES,
    CLASS_COMMANDS,
    CLASS_TO_FILE,
    load_existing_profiles,
    regenerate_indexes,
)

DEFAULT_SCHEMA = "../../schema/device-profile.schema.json"


def iter_class_blocks(contribution):
    """Yield ``(baseClass, block)`` tuples from a contribution.

    Accepts either a single class block or a bundle keyed by filename.
    """
    if not isinstance(contribution, dict):
        raise ValueError("contribution must be a JSON object")

    if "baseClass" in contribution and "profiles" in contribution:
        yield contribution["baseClass"], contribution
        return

    blocks = [
        value
        for value in contribution.values()
        if isinstance(value, dict) and "baseClass" in value
    ]
    if not blocks:
        raise ValueError(
            "unrecognised contribution shape: expected a class block or a "
            "bundle of class blocks keyed by filename"
        )
    for block in blocks:
        yield block["baseClass"], block


def union_list(existing, extra):
    """Append items from ``extra`` not already in ``existing`` (order kept)."""
    out = list(existing)
    for item in extra:
        if item not in out:
            out.append(item)
    return out


def union_dict(existing, extra):
    """Add keys from ``extra`` missing in ``existing`` (existing wins)."""
    out = dict(existing)
    for key, value in extra.items():
        if key not in out:
            out[key] = value
    return out


def canonical(data):
    """Return a class-file dict with keys in the catalog's canonical order."""
    out = {"$schema": data.get("$schema", DEFAULT_SCHEMA), "baseClass": data["baseClass"]}
    out["classCapabilities"] = data.get("classCapabilities", [])
    out["profiles"] = data["profiles"]
    if data.get("classCommands"):
        out["classCommands"] = data["classCommands"]
    return out


def load_class_file(dev_class, filepath):
    """Load an existing by-class file or build a fresh one from defaults."""
    if filepath.exists():
        with open(filepath) as f:
            return json.load(f)
    data = {
        "$schema": DEFAULT_SCHEMA,
        "baseClass": dev_class,
        "classCapabilities": list(CLASS_CAPABILITIES.get(dev_class, [])),
        "profiles": [],
    }
    commands = CLASS_COMMANDS.get(dev_class)
    if commands:
        data["classCommands"] = dict(commands)
    return data


def merge(contribution):
    """Merge a parsed contribution into the catalog. Returns (added, skipped)."""
    existing_pairs = load_existing_profiles()
    added = 0
    skipped = 0
    touched_files = []

    for dev_class, block in iter_class_blocks(contribution):
        filename = CLASS_TO_FILE.get(dev_class, "custom.json")
        filepath = BY_CLASS_DIR / filename
        data = load_class_file(dev_class, filepath)
        before = json.dumps(data, sort_keys=True)

        new_here = 0
        for profile in block.get("profiles", []):
            key = (profile["pluginId"], profile["deviceTypeId"])
            if key in existing_pairs:
                skipped += 1
                continue
            data["profiles"].append(profile)
            existing_pairs.add(key)
            new_here += 1
            added += 1

        data["profiles"].sort(key=lambda p: (p["pluginId"], p["deviceTypeId"]))
        data["classCapabilities"] = union_list(
            data.get("classCapabilities", []), block.get("classCapabilities", [])
        )
        if block.get("classCommands"):
            data["classCommands"] = union_dict(
                data.get("classCommands", {}), block["classCommands"]
            )

        data = canonical(data)
        if json.dumps(data, sort_keys=True) == before:
            print(f"  {filename}: no change")
            continue

        BY_CLASS_DIR.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        touched_files.append(filename)
        print(f"  {filename}: +{new_here} profile(s), now {len(data['profiles'])}")

    if touched_files:
        regenerate_indexes(date.today().isoformat())

    return added, skipped


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contribution", help="Path to the contribution JSON file")
    args = parser.parse_args()

    try:
        with open(args.contribution) as f:
            contribution = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR: could not read contribution: {e}")
        return 1

    try:
        added, skipped = merge(contribution)
    except (ValueError, KeyError) as e:
        print(f"ERROR: {e}")
        return 1

    print()
    print(f"Merge complete: {added} profile(s) added, {skipped} already present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
