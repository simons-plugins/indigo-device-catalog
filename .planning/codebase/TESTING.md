# TESTING.md — Testing and Validation

## Test Coverage Summary

There is no formal test suite (no pytest, no unittest). Validation is handled by:
1. A dedicated validation script (`tools/validate.py`)
2. Four GitHub Actions CI workflows
3. Manual testing of the contributor plugin against a live Indigo server

## Schema Validation Script

**`tools/validate.py`** — the primary quality gate for catalog data.

```bash
# Install dependency
pip install jsonschema

# Run validation
python tools/validate.py
```

What it checks:
1. Each `catalog/by-class/*.json` file is valid JSON (catches syntax errors)
2. Each file validates against `schema/device-profile.schema.json` (JSON Schema Draft-07)
3. No duplicate `(pluginId, deviceTypeId)` pairs across any class files
4. `catalog/_index.json` exists and is valid JSON (structural check only, not schema-validated)

Exit codes:
- `0` — all checks pass
- `1` — one or more errors found

Output format:
```
Validating catalog/by-class/relay.json...
  OK (25 profiles)
...
Validated 7 class files, 120 profiles total
PASSED
```

Duplicate detection is cross-file — a profile in `relay.json` and `sensor.json` with the same `(pluginId, deviceTypeId)` would be caught.

## CI Workflows

### validate.yml

- Trigger: push or PR to `main`
- Condition: only runs if `catalog/` or `schema/` files changed (uses `git diff --name-only origin/main...HEAD`)
- Steps: checkout, detect changes, setup Python 3.12, `pip install jsonschema`, `python tools/validate.py`
- This check must pass for a PR to merge

Optimization: PRs that only change plugin code (e.g. `Device Catalog Contributor.indigoPlugin/**`) skip the validation job entirely, keeping CI fast.

### version-check.yml

- Trigger: PR to `main` when plugin files change
- Extracts `PluginVersion` from `Info.plist` using `grep` + `sed`
- Checks that the version string does not already exist as a git tag
- Fails with a clear error message if the version is stale
- Must pass before merging any PR that touches plugin code

### auto-merge.yml

- Trigger: PR opened or synchronized
- Condition: `startsWith(github.head_ref, 'contribute/')`
- Action: runs `gh pr merge --auto --merge` to enable auto-merge
- The actual merge happens once all required checks pass (validate.yml must be green)
- Permissions: `contents: write`, `pull-requests: write`

### create-release.yml

- Trigger: push to `main`
- Extracts `PluginVersion` from `Info.plist`
- Checks if tag already exists (idempotent — skips if already tagged)
- Creates a `.zip` of the plugin bundle: `zip -r "Device Catalog Contributor.indigoPlugin.zip" "Device Catalog Contributor.indigoPlugin"`
- Creates a GitHub release with auto-generated release notes and the zip as artifact
- Tag format matches `PluginVersion` directly (e.g. `2024.2.1`)

## Manual Testing (Contributor Plugin)

No automated tests for the plugin. To test manually:

```bash
# Copy plugin to Indigo server
cp -r "Device Catalog Contributor.indigoPlugin" \
  "/Volumes/Macintosh HD-1/Library/Application Support/Perceptive Automation/Indigo 2025.1/Plugins/"

# Then in Indigo: Plugins -> Manage Plugins -> enable
# Then: Plugins -> Device Catalog Contributor -> Discover New Profiles
# Watch Event Log for output
```

Key test scenarios:
1. **Discover with empty catalog** — all devices should appear as new
2. **Discover against live catalog** — existing profiles should be skipped
3. **Export to file** — check `~/Desktop/indigo-device-catalog-contribution.json` is valid JSON
4. **Submit via GitHub** — requires a valid GitHub token; verify fork is created, branch is named correctly, PR is opened
5. **No GitHub token** — submit should log a helpful error, export should still work

## Discover Tool Testing

```bash
# Dry run (no writes)
python tools/discover.py --host jarvis.local --no-tls

# With apply (writes to local catalog)
python tools/discover.py --host jarvis.local --apply --contributor testuser

# Validate result
python tools/validate.py
```

## What Is Not Tested

- The `catalog_client.py` network fetch is not mocked — it either works against live GitHub or fails silently
- The `github_client.py` GitHub API operations have no unit tests
- Profile builder correctness (type inference, capability extraction) is tested only by running against real devices
- Index regeneration correctness is verified only by running `discover.py --apply` and inspecting the output

## Branch Protection Assumptions

The validate and version-check workflows are assumed to be configured as required checks in the repository's branch protection rules. The auto-merge workflow relies on required checks being defined — it enables auto-merge but the merge only completes once all required checks pass.
