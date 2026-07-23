# STRUCTURE.md — Directory and File Structure

## Top-Level Layout

```
indigo-device-catalog/
├── catalog/                              # The catalog itself
├── schema/                               # JSON Schema definition
├── tools/                                # CLI utilities
├── Device Catalog Contributor.indigoPlugin/  # Indigo plugin bundle
├── .github/                              # CI workflows and issue templates
├── .raw/                                 # Scratch data used to seed the catalog (not tracked in CI)
├── README.md
├── CONTRIBUTING.md
├── CLAUDE.md
└── LICENSE                              # MIT
```

## catalog/

```
catalog/
├── _index.json                   # Master startup manifest
├── by-class/
│   ├── custom.json               # indigo.Device + indigo.MultiIODevice (50 profiles)
│   ├── dimmer.json               # indigo.DimmerDevice (5 profiles)
│   ├── relay.json                # indigo.RelayDevice (25 profiles)
│   ├── sensor.json               # indigo.SensorDevice (34 profiles)
│   ├── speed-control.json        # indigo.SpeedControlDevice (1 profile)
│   ├── sprinkler.json            # indigo.SprinklerDevice (1 profile)
│   └── thermostat.json           # indigo.ThermostatDevice (4 profiles)
└── by-plugin/
    └── _index.json               # Cross-reference: pluginId -> deviceTypes
```

Total at time of mapping: ~120 profiles across 6 class files and ~45 distinct plugins.

`_index.json` structure:
```json
{
  "generated": "YYYY-MM-DD",
  "classes": {
    "indigo.RelayDevice": {
      "file": "by-class/relay.json",
      "profileCount": 25,
      "plugins": {
        "com.example.plugin": {
          "pluginName": "...",
          "deviceTypeIds": ["typeA", "typeB"]
        }
      }
    }
  }
}
```

## schema/

```
schema/
└── device-profile.schema.json    # JSON Schema Draft-07 for by-class files
```

The schema validates the top-level structure of each `by-class/*.json` file (not individual profiles in isolation). It does not validate `_index.json` — that file is validated only as parseable JSON.

## tools/

```
tools/
├── discover.py     # CLI: connect to Indigo HTTP API, find new profiles, optionally write to catalog
└── validate.py     # CLI: validate all by-class/*.json against schema, check for duplicate profiles
```

`discover.py` flags:
- `--host` — Indigo server hostname (default: localhost)
- `--port` — web server port (default: 8176)
- `--no-tls` — use HTTP instead of HTTPS
- `--api-key` — Bearer token for Indigo API auth
- `--contributor` — attribution name in profile metadata
- `--apply` — write to catalog (default is dry run)

## Device Catalog Contributor.indigoPlugin/

```
Device Catalog Contributor.indigoPlugin/
└── Contents/
    ├── Info.plist                        # Bundle metadata, PluginVersion, CFBundleIdentifier
    └── Server Plugin/
        ├── plugin.py                     # Main plugin class (indigo.PluginBase)
        ├── profile_builder.py            # Builds profiles from native indigo.Device objects
        ├── catalog_client.py             # Fetches existing catalog from raw.githubusercontent.com
        ├── github_client.py              # GitHub REST API client (fork, branch, commit, PR)
        ├── PluginConfig.xml              # UI: contributor name, GitHub token, debug flag
        └── MenuItems.xml                 # 3 menu items: Discover, Export, Submit
```

Note: no `Contents/Packages/` (no bundled dependencies). No `Devices.xml` or `Actions.xml` — the plugin creates no Indigo devices and defines no actions.

Plugin menu items:
- **Discover New Profiles** — iterates `indigo.devices`, compares to live catalog, builds pending profiles
- **Export Profiles to File** — writes pending profiles as JSON to `~/Desktop/indigo-device-catalog-contribution.json`
- **Submit to Catalog (GitHub)** — forks repo, creates branch, commits profiles, opens PR

Plugin config fields:
- `contributorName` — attribution string (default: "community")
- `githubToken` — optional, secure field; required only for "Submit to Catalog"
- `showDebugInfo` — debug logging toggle

## .github/

```
.github/
├── ISSUE_TEMPLATE/
│   └── new-device-profile.md     # Structured issue template for manual profile submissions
└── workflows/
    ├── validate.yml              # Schema validation on catalog/schema changes
    ├── auto-merge.yml            # Auto-merges contribute/* PRs
    ├── version-check.yml         # Blocks PRs if PluginVersion tag already exists
    └── create-release.yml        # Creates tagged release with plugin zip on merge to main
```

## .raw/ (scratch / not CI-tracked)

```
.raw/
├── generate_catalog.py           # Original seed script used to generate catalog from live Indigo data
├── extract_from_logs.py          # Extracted device info from Indigo logs
├── deduplicate.py                # Deduplication utility
├── batch-*.json                  # Raw device batches from initial discovery
├── details-batch-*.json          # Per-device detail data from initial scrape
├── all-device-details.json       # Merged raw data
├── plugins.json                  # Plugin list from initial scrape
├── representatives.json          # One device per (pluginId, deviceTypeId) combo
└── _tmp_devices/                 # Temp files during initial catalog generation
```

The `.raw/` directory is local scratch data not committed to CI or consumed by any automated workflow. It documents how the initial catalog was seeded from a live Indigo installation.
