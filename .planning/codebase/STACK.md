# STACK.md — Technology Stack

## Catalog Format

- **JSON** — all catalog data is plain JSON (no YAML, TOML, or XML)
- **JSON Schema Draft-07** — schema validation via `$schema: https://json-schema.org/draft-07/schema#`
- Schema hosted in-repo at `schema/device-profile.schema.json`
- Each `by-class/*.json` file references the schema via relative path `../../schema/device-profile.schema.json`

## Validation Tools

- **Python 3.10+** — all tooling scripts
- **jsonschema** (PyPI) — sole external dependency, used by `tools/validate.py` for schema validation
- No build system (no Makefile, no pyproject.toml, no package.json)
- Tools are standalone scripts, no shared library layer

## Contributor Plugin

- **Language**: Python 3.10+ (Indigo 2023+ requirement)
- **Framework**: Indigo plugin SDK (`indigo.PluginBase`)
- **Bundle ID**: `com.simons-plugins.device-catalog-contributor`
- **Version format**: `YYYY.R.patch` (e.g. `2024.2.1`)
- **Dependencies**: none bundled — plugin uses only Python stdlib (`urllib.request`, `json`, `ssl`, `base64`, `collections`, `datetime`)
- **No `Contents/Packages/`** — all external calls use stdlib HTTP, avoiding bundled dependencies

## Discovery Tool (CLI)

- `tools/discover.py` — standalone Python 3 script, zero external dependencies
- Connects to Indigo's HTTP API (`/v2/api/indigo.devices.json`) directly
- Supports self-signed TLS certificates (common for local Indigo installs)
- Dry-run by default; `--apply` flag writes to catalog files

## GitHub Integration

- `github_client.py` — pure stdlib REST client against GitHub API v3
- Uses `urllib.request` + Bearer token auth
- Endpoint: `https://api.github.com` (hardcoded)
- API version header: `X-GitHub-Api-Version: 2022-11-28`
- File content encoded as base64 per GitHub Contents API spec

## CI / Automation

- **GitHub Actions** — all CI runs on `ubuntu-latest`
- Python 3.12 in CI (installed via `actions/setup-python@v5`)
- `softprops/action-gh-release@v1` for release creation
- `actions/checkout@v4` throughout

## No Frontend / Build Step

- Catalog is static JSON — no bundler, no transpile step, no CDN pipeline
- No Node.js tooling
- Consumers (iOS app, web clients) read raw JSON from GitHub raw URLs or bundled files

## Python Environment Notes

Both `tools/` scripts are designed to run with the system Python 3. No virtual environment is required for `discover.py` (zero external deps). For `validate.py` only `jsonschema` is needed:

```bash
pip install jsonschema
python tools/validate.py
```

On macOS with Indigo's Python framework installed at:
`/Library/Frameworks/Python.framework/Versions/Current/bin/python3`

The contributor plugin runs under Indigo's embedded Python 3.10+ interpreter. It cannot `import` third-party packages unless they are bundled in `Contents/Packages/` — the plugin deliberately avoids this by using stdlib-only code.

## Indigo Plugin SDK Version

- `ServerApiVersion: 3.6` (in `Info.plist`)
- Inherits from `indigo.PluginBase`
- Plugin lifecycle: `__init__`, `startup`, `shutdown`, `closedPrefsConfigUi`
- No `runConcurrentThread` — the plugin is purely menu-driven, no polling loop
- No `deviceCreated`, `deviceUpdated`, or similar device lifecycle callbacks

## Raw Data Generation (historical, one-time)

The `.raw/` directory contains the scripts used to seed the initial catalog from a live Indigo installation:
- `generate_catalog.py` — generated `by-class/*.json` from raw device data
- `extract_from_logs.py` — extracted device details from Indigo event logs
- `deduplicate.py` — removed duplicate entries

These were one-time bootstrap scripts and are not part of any ongoing workflow.
