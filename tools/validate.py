#!/usr/bin/env python3
"""Validate all catalog JSON files against the device profile schema."""

import json
import sys
from pathlib import Path

try:
    from jsonschema import validate, ValidationError
except ImportError:
    print("ERROR: jsonschema not installed. Run: pip install jsonschema")
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "schema" / "device-profile.schema.json"
CATALOG_DIR = REPO_ROOT / "catalog" / "by-class"


def load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def main() -> int:
    errors = 0

    # Load schema
    if not SCHEMA_PATH.exists():
        print(f"ERROR: Schema not found at {SCHEMA_PATH}")
        return 1
    schema = load_json(SCHEMA_PATH)

    # Find all by-class JSON files
    class_files = sorted(CATALOG_DIR.glob("*.json"))
    if not class_files:
        print("WARNING: No catalog files found in catalog/by-class/")
        return 0

    # Track all (pluginId, deviceTypeId) pairs for duplicate detection
    seen_profiles: dict[tuple[str, str], str] = {}

    for path in class_files:
        rel = path.relative_to(REPO_ROOT)
        print(f"Validating {rel}...")

        try:
            data = load_json(path)
        except json.JSONDecodeError as e:
            print(f"  ERROR: Invalid JSON: {e}")
            errors += 1
            continue

        # Validate against schema
        try:
            validate(instance=data, schema=schema)
        except ValidationError as e:
            print(f"  ERROR: Schema validation failed: {e.message}")
            print(f"    Path: {' -> '.join(str(p) for p in e.absolute_path)}")
            errors += 1
            continue

        # Check for duplicate profiles
        for profile in data.get("profiles", []):
            key = (profile["pluginId"], profile["deviceTypeId"])
            if key in seen_profiles:
                print(f"  ERROR: Duplicate profile {key} (also in {seen_profiles[key]})")
                errors += 1
            else:
                seen_profiles[key] = str(rel)

        profile_count = len(data.get("profiles", []))
        print(f"  OK ({profile_count} profiles)")

    # Validate _index.json exists and is valid JSON
    index_path = REPO_ROOT / "catalog" / "_index.json"
    if index_path.exists():
        print(f"Validating catalog/_index.json...")
        try:
            load_json(index_path)
            print("  OK")
        except json.JSONDecodeError as e:
            print(f"  ERROR: Invalid JSON: {e}")
            errors += 1
    else:
        print("WARNING: catalog/_index.json not found")

    # Summary
    print()
    total_profiles = len(seen_profiles)
    print(f"Validated {len(class_files)} class files, {total_profiles} profiles total")
    if errors:
        print(f"FAILED: {errors} error(s)")
    else:
        print("PASSED")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
