# ARCHITECTURE.md — System Architecture

## Overview

The indigo-device-catalog is a community-maintained, schema-validated JSON catalog of Indigo device capabilities. It has three distinct layers:

1. **The catalog itself** — static JSON files in `catalog/`
2. **The contributor toolchain** — CLI tool (`tools/discover.py`) and Indigo plugin for building and submitting profiles
3. **CI pipeline** — GitHub Actions for validation, auto-merge, versioning, and release

## Core Data Model

The fundamental identity of a device profile is a triple: `(baseClass, pluginId, deviceTypeId)`.

- `baseClass` — one of 8 Indigo base device classes (e.g. `indigo.ThermostatDevice`)
- `pluginId` — reverse-domain plugin identifier (e.g. `com.lionsheeptechnology.ShellyMQTT`)
- `deviceTypeId` — plugin-defined string (e.g. `shelly-trv`)

A profile captures only structural metadata — no personal data, no configuration values, no device names. This is enforced by the profile builder, not the schema (schema allows any string, but the builders never write values).

## Catalog Storage Layout

```
catalog/
  _index.json              # Lightweight summary: class -> {profileCount, plugins{}}
  by-class/
    dimmer.json            # All dimmer profiles (5 profiles, 4 plugins)
    relay.json             # All relay profiles  (25 profiles, 18 plugins)
    sensor.json            # All sensor profiles (34 profiles, 10 plugins)
    thermostat.json        # All thermostat profiles (4 profiles, 4 plugins)
    custom.json            # indigo.Device + indigo.MultiIODevice (50 profiles)
    sprinkler.json         # Sprinkler profiles (1 profile)
    speed-control.json     # Speed control (1 profile)
  by-plugin/
    _index.json            # Cross-reference: pluginId -> [{baseClass, deviceTypeId}]
```

The `_index.json` at the top level is the startup manifest — iOS/web clients load this first to know what's available without loading all class files.

The `by-plugin/_index.json` is a cross-reference that inverts the by-class structure, grouping by plugin instead of by class. It is regenerated automatically alongside `_index.json`.

## Schema Validation Architecture

Schema: `schema/device-profile.schema.json` (JSON Schema Draft-07)

Top-level structure per by-class file:
```json
{
  "baseClass": "indigo.ThermostatDevice",
  "classCapabilities": ["supportsHeatSetpoint", ...],
  "classCommands": { "indigo.thermostat.setHeatSetpoint": {...} },
  "profiles": [...]
}
```

Each profile in `profiles[]` must have:
- `pluginId`, `pluginName`, `deviceTypeId` (required strings)
- `capabilities` (object: string -> boolean)
- `states` (object: string -> `{type: "number"|"integer"|"string"|"boolean"}`)
- `metadata.contributedBy` + `metadata.discoveredAt` (required)

Optional profile fields: `model`, `subModel`, `protocol`, `pluginConfigKeys`, `displayStateId`, `displayStateImageSel`.

The schema uses `additionalProperties: false` at all levels, which means unknown keys will fail validation. This is strict by design.

## Profile Builder

Two implementations of the profile builder exist, sharing the same logic:

| Location | Input | Used by |
|----------|-------|---------|
| `tools/discover.py::build_profile()` | HTTP API JSON dict | CLI discover tool |
| `Device Catalog Contributor.indigoPlugin/Contents/Server Plugin/profile_builder.py::build_profile()` | Native `indigo.Device` object | Indigo plugin |

Both implementations:
1. Map device class name to `indigo.XxxDevice` string via `_CLASS_NAME_MAP`
2. Read capability flags from standard list for the class, plus scan for extra `supports*` attributes
3. Read state keys and infer types from current values (values themselves discarded)
4. Read plugin prop keys only (no values)
5. Extract protocol by examining `dev.protocol` then inferring from `pluginId` patterns
6. Output a profile dict matching the schema

The duplication is intentional — the CLI version has no Indigo dependency, while the plugin version uses native objects.

## Contribution Workflow

### Path A: Plugin auto-PR

```
User runs "Discover New Profiles" menu item
    -> plugin.discover_profiles()
    -> reads indigo.devices via Python API
    -> checks catalog/_index.json from GitHub for existing profiles
    -> builds profiles via profile_builder.build_profile()
    -> stores in self.pending_profiles

User runs "Submit to Catalog (GitHub)"
    -> plugin.submit_to_github()
    -> GitHubClient.fork_repo()        # creates fork if needed
    -> GitHubClient.create_branch()    # contribute/<name>/<date>
    -> for each class: fetch existing file, merge profiles, commit
    -> _commit_regenerated_indexes()   # updates both index files
    -> GitHubClient.create_pull_request()
    -> CI auto-merge triggers on contribute/* branch
```

### Path B: CLI tool

```
python tools/discover.py --host jarvis.local --contributor alice
    -> IndigoAPI.get_devices()         # HTTP /v2/api/indigo.devices.json
    -> load_existing_profiles()        # reads local catalog files
    -> build_profile() for each new type
    -> prints summary (dry run)

python tools/discover.py --host jarvis.local --apply
    -> merge_profiles_into_catalog()
    -> regenerate_indexes()
    -> user commits and opens PR manually
```

### Path C: Manual GitHub issue

User fills in `.github/ISSUE_TEMPLATE/new-device-profile.md` and a maintainer adds the profile.

## Index Regeneration

Both the plugin and CLI tool regenerate both index files whenever catalog files change. The generation logic:
- Iterates all `by-class/*.json` files
- Builds `_index.json` as `{classes: {baseClass: {file, profileCount, plugins: {}}}}`
- Builds `by-plugin/_index.json` as `{plugins: {pluginId: {pluginName, deviceTypes: []}}}`
- Sorts by pluginId alphabetically, deviceTypes by (baseClass, deviceTypeId)

## CI Pipeline Architecture

Four workflows, each with a specific scope:

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `validate.yml` | push/PR to main | Schema validates `by-class/*.json` if `catalog/` or `schema/` changed |
| `auto-merge.yml` | PR opened/sync | Enables auto-merge for `contribute/*` branches |
| `version-check.yml` | PR to main (plugin files) | Blocks if PluginVersion tag already exists |
| `create-release.yml` | push to main | Creates tagged release with plugin zip if version is new |

The validate workflow skips entirely if no catalog or schema files changed, keeping CI fast for plugin-only changes.
