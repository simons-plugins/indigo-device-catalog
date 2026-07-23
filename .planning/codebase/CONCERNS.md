# CONCERNS.md — Known Concerns, Gaps, and Risks

## Catalog Coverage Gaps

### Thin coverage on structured device classes

- **Thermostat**: only 4 profiles across 4 plugins — a heavily-used class with many MQTT, Z-Wave, and HTTP plugins missing
- **Sprinkler**: 1 profile (Netro only) — RainBird, Rachio, Hunter, and other popular controllers are absent
- **Speed control**: 1 profile (Home Assistant fan) — Lutron, Z-Wave fan controllers, HVAC controls all missing
- **Dimmer**: 5 profiles — large gap given how many Z-Wave, Zigbee, and Insteon dimmer plugins exist

### No coverage for key Indigo built-in device classes

- **`indigo.MultiIODevice`**: listed in schema `baseClass` enum but no profiles exist and it maps to `custom.json` without a dedicated file — easy to confuse with `indigo.Device`
- Built-in relay/dimmer devices (no plugin, `pluginId == ""`) are likely not catalogable under the current model since a profile requires a non-empty `pluginId`

### No `SpeedControl` for Insteon

The Insteon fan linc is a very common Indigo speed control device but is not in the catalog. Insteon is end-of-life as a company, so this may be lower priority.

## Schema Versioning

There is **no schema versioning** mechanism. The schema has an `$id` URI but:
- No version field in the schema itself
- No version in by-class files beyond the relative `$schema` path
- A breaking schema change (e.g. adding a required field) would immediately invalidate all existing catalog files
- No migration tooling exists

Risk: if a consumer pins to the current schema shape and the schema changes, their parsing breaks with no warning.

## Breaking Change Risks

### Adding required fields to profiles

The schema uses `additionalProperties: false` on profile objects. Adding a new required field to the schema immediately fails validation on all existing profiles. This makes backward-compatible schema evolution difficult.

Mitigation options (not yet implemented):
- Mark new required fields as optional with a default
- Version the schema and maintain separate validation paths

### Capability flag completeness

`classCapabilities` lists the "expected" flags per class, but:
- Extra plugin-specific `supports*` flags are allowed in the schema (the `capabilities` object accepts any string key)
- Consumers cannot distinguish "flag is false" from "flag was not measured at discovery time"
- There is no "unknown" sentinel — missing flags default to not-present in the profile

### State type inference fragility

Types are inferred from the value at discovery time:
- A state that is `0` at discovery is typed as `"integer"` — if it can also be `0.5`, the type is wrong
- A state that starts as a bool-like integer (`0`/`1`) may be typed `"integer"` when semantically boolean
- No mechanism for contributors to override inferred types

## Auto-Merge Safety

`auto-merge.yml` auto-merges all `contribute/*` PRs once CI passes. This means:
- Malicious profiles could be merged without human review (if they pass schema validation)
- The validate step only checks schema conformance, not content reasonableness
- Any contributor with a GitHub account can submit profiles that bypass human review

Current mitigations: schema validation prevents malformed JSON; the privacy model means no personal data can leak. Risk is low for this catalog (structural metadata only), but worth noting.

## Index Staleness

`_index.json` and `by-plugin/_index.json` are committed alongside catalog changes, but:
- If a PR manually edits a `by-class/*.json` without regenerating indexes, they fall out of sync
- The validation script (`tools/validate.py`) does not check index consistency
- No CI check verifies that indexes match the catalog files

This could cause iOS/web clients to read stale profile counts or miss newly added plugins.

## Plugin: No Offline Fallback in catalog_client.py

`catalog_client.py` fetches the live catalog from GitHub at plugin runtime. If the fetch fails (no internet, rate limited, GitHub outage), it falls back to `existing = set()`, meaning all local devices will appear as "new" profiles. On re-submission, this could create duplicate PRs.

The plugin does check for existing keys from the fetched index before building profiles, but there is no local cache of the catalog on disk.

## Plugin: No Devices.xml

The plugin has no `Devices.xml`, meaning it creates no Indigo devices of its own. If a future version needed to track submission state across restarts (e.g. "these profiles were already submitted"), it would need either a devices model or persistent file storage.

## Duplicate Detection in validate.py

`validate.py` catches duplicate `(pluginId, deviceTypeId)` pairs across class files but NOT within a single file. The merge functions sort profiles but do not deduplicate — if `merge_profiles_into_catalog()` is called twice for the same profiles, duplicates would silently accumulate.

## No Rate Limiting on GitHub API Calls

`github_client.py` makes sequential API calls without retry logic or rate limit handling. The GitHub REST API has a rate limit of 5,000 requests/hour for authenticated users. A very large submission (many class files) could theoretically exhaust the limit, though this is unlikely in practice.

## No Semver / Deprecation Story for Catalog Entries

Once a profile is in the catalog, there is no mechanism to:
- Mark it as deprecated (e.g. plugin abandoned)
- Update it when a plugin adds new capabilities
- Remove it if the plugin is incompatible with new Indigo versions

Profiles are append-only in practice.
