# INTEGRATIONS.md — External Integrations and Consumption

## How the Catalog Is Consumed

### iOS App (Domio)

The catalog JSON can be bundled directly into the iOS app's resources (mentioned explicitly in README.md). At runtime:

1. App loads `catalog/_index.json` to enumerate available classes and plugins
2. For a discovered device, app reads `pluginId` and `deviceTypeId` from Indigo WebSocket API
3. App looks up the matching profile in the relevant `by-class/*.json` file
4. Profile `capabilities` flags determine which controls to render (e.g. does this thermostat support cool setpoint?)
5. Profile `states` map provides expected state keys and their data types for parsing
6. No code changes required when new device types are added to the catalog

Delivery options for iOS:
- **Bundled at build time**: include `catalog/` directory in app bundle, re-bundle on catalog updates
- **Runtime fetch**: fetch from `raw.githubusercontent.com` (same URL pattern the plugin uses)

### Web Clients

Same JSON lookup pattern as iOS. No SDK or client library needed — plain HTTP GET on the raw GitHub URLs.

### Indigo Plugin (self-referential)

`catalog_client.py` fetches the live catalog from GitHub at plugin runtime:

```
https://raw.githubusercontent.com/simons-plugins/indigo-device-catalog/main/catalog/_index.json
```

This is used to check which `(pluginId, deviceTypeId)` pairs already exist before building new profiles. If the fetch fails, discovery falls back to an empty existing set (may re-find already-cataloged profiles).

## GitHub as Delivery Mechanism

There is no CDN, no GitHub Pages deployment, and no npm package. The catalog is consumed directly from:

- **Raw GitHub URLs**: `https://raw.githubusercontent.com/simons-plugins/indigo-device-catalog/main/catalog/...`
- **Cloned/bundled**: consumers clone or download the repo and use files locally

The `catalog/_index.json` is the intended entry point for consumers — it provides a lightweight summary (profile counts, plugin lists) without requiring all by-class files to be loaded upfront.

## Indigo Server HTTP API (inbound to catalog tooling)

`tools/discover.py` connects outbound to a local or remote Indigo server:

- **Endpoint**: `https://<host>:8176/v2/api/indigo.devices.json` (device list)
- **Endpoint**: `https://<host>:8176/v2/api/indigo.devices/<id>.json` (device detail)
- **Endpoint**: `https://<host>:8176/v2/api/indigo.plugins.json` (plugin names, optional)
- Self-signed TLS is accepted (`ssl.CERT_NONE`)
- Optional Bearer token auth via `--api-key`

The contributor plugin does NOT use the HTTP API — it accesses devices directly through `indigo.devices` (native Python API), which is faster and more reliable for in-process use.

## GitHub API (contributor plugin outbound)

The `submit_to_github` flow uses GitHub REST API v3:

| Operation | Endpoint |
|-----------|----------|
| Get authenticated user | `GET /user` |
| Fork upstream repo | `POST /repos/simons-plugins/indigo-device-catalog/forks` |
| Get main branch SHA | `GET /repos/.../git/ref/heads/main` |
| Create branch on fork | `POST /repos/<fork>/indigo-device-catalog/git/refs` |
| Read existing file | `GET /repos/.../contents/<path>?ref=<branch>` |
| Write file | `PUT /repos/<fork>/indigo-device-catalog/contents/<path>` |
| Open pull request | `POST /repos/simons-plugins/indigo-device-catalog/pulls` |

Token requires `repo` scope (configured in PluginConfig.xml). Token is stored in plugin prefs (marked `secure="true"`).

## No Push / Webhook Inbound

The catalog repo has no inbound webhooks, no serverless functions, and no backend relay. All writes go through GitHub PR flow. The `auto-merge.yml` workflow handles automated merging of `contribute/*` branches without human review.

## Indigo API Version Compatibility

The `discover.py` CLI uses `/v2/api/` endpoints. These endpoints were introduced in Indigo 2022+ and require the web server to be enabled (`Preferences > Web Server`). The API returns JSON device summaries; detail fetches use the per-device endpoint.

For the contributor plugin, no HTTP API is used at all — `indigo.devices` iteration is used instead, which works regardless of whether the web server is enabled.

## Related Projects in Workspace

The catalog is referenced by or relates to several other workspace projects:

- **domio code** (iOS app) — the primary intended consumer of the catalog for runtime device rendering
- **indigo-plugin-factory** — generated plugins could auto-submit their device profiles to the catalog as part of the generation pipeline (not yet implemented)
- **Indigo-skill** — Claude Code skill for Indigo plugin development; may reference the catalog when suggesting device type patterns
- **heatmiser / netro / UK-Trains** — all have entries in the catalog (heatmiser-neo thermostat/relay/sensor, Netro sprinkler/sensor, UK Trains custom device)

## Consumption Pattern for iOS (Domio)

Recommended lookup flow at app startup:

1. Fetch or load `catalog/_index.json` — check profile counts to decide if a bundle update is needed
2. For each device returned by the Indigo WebSocket API:
   - Read `pluginId` and `deviceTypeId` from the device object
   - Look up the matching class from `_index.json` to know which file to load
   - Load `catalog/by-class/<class>.json` (lazy-loaded per class)
   - Find the profile where `pluginId` and `deviceTypeId` match
3. Use `capabilities` to decide which UI controls to render
4. Use `states` to know expected state key types for parsing WebSocket updates

For unknown `(pluginId, deviceTypeId)` combinations not in the catalog, clients should fall back to base-class defaults (e.g. all thermostats support on/off; presence of heat/cool setpoints is unknown — default to showing both).

## Versioning and Staleness

The catalog has no version number of its own — `_index.json` records a `generated` date only. There is no semantic versioning, no changelog for catalog entries, and no mechanism for consumers to detect breaking changes to profile structure. Consumers should treat each field as optional and degrade gracefully if a field is absent.
