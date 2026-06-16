# CLAUDE.md — Device Catalog Contributor

Indigo plugin that discovers device capabilities and contributes profiles to the community device catalog.

## Versioning & Release

### Version bump is required for every PR

The `PluginVersion` in `Device Catalog Contributor.indigoPlugin/Contents/Info.plist` must be bumped in every PR. CI runs a version-check that fails if the version already exists as a git tag. **Do not merge with failing checks.**

Version format: `YYYY.R.patch` (e.g. `2024.2.1`). Bump the patch for fixes/docs, minor for features.

On merge to main, the `create-release` workflow automatically creates a GitHub release with a `.zip` bundle of the plugin.

### PR checklist

1. Bump `PluginVersion` in `Info.plist`
2. Push and create PR
3. Wait for version-check CI to pass
4. Merge only after all checks are green

## Plugin Overview

- **Bundle ID**: `com.simons-plugins.device-catalog-contributor`
- **Python**: 3.10+ (Indigo 2023+)
- **Repo also contains**: The device catalog itself (`catalog/`, `schema/`, `tools/`)

### CI Workflows

- `validate.yml` — Validates catalog JSON against schema on changes to `catalog/` or `schema/`
- `ingest-contribution.yml` — When a maintainer adds the `ingest-contribution` label to an issue, downloads the attached contribution JSON, merges it via `tools/merge_contribution.py`, validates, and opens a `contribute/` PR for review
- `auto-merge.yml` — Auto-merges PRs from `contribute/` branches
- `version-check.yml` — Blocks PRs if PluginVersion hasn't been bumped
- `create-release.yml` — Auto-creates tagged release with plugin `.zip` on merge

## Plugin Structure

```
Device Catalog Contributor.indigoPlugin/
└── Contents/
    ├── Info.plist
    └── Server Plugin/
        ├── plugin.py            # Main plugin logic
        ├── profile_builder.py   # Builds device capability profiles
        ├── catalog_client.py    # Catalog API client
        ├── github_client.py     # GitHub PR client for contributions
        ├── PluginConfig.xml     # Plugin preferences
        └── MenuItems.xml        # Plugin menu items
```

## Catalog Structure

```
catalog/
  _index.json              # Master index of all profiles
  by-class/                # Profiles grouped by Indigo base class
    thermostat.json, dimmer.json, relay.json, sensor.json, etc.
  by-plugin/
    _index.json            # Cross-reference: plugin → device types
schema/
  device-profile.schema.json   # JSON Schema for validation
tools/
  validate.py              # Schema validation script
  discover.py              # Device discovery tool
```

## Testing

```bash
# Validate catalog
python tools/validate.py

# Copy plugin to Indigo server
cp -r "Device Catalog Contributor.indigoPlugin" "/Volumes/Macintosh HD-1/Library/Application Support/Perceptive Automation/Indigo 2025.1/Plugins/"
```
