# Schema versioning

The device profile schema lives at `schema/device-profile.schema.json`.

## Current version

**`1.0.0`**

Consumers should check the `schemaVersion` field in any profile file (optional) or pin against this document.

## Bump rules (semver)

- **Major** — breaking changes: adding a required field, changing a field type, removing a field, renaming `baseClass` enum values.
- **Minor** — additive, backward-compatible: new optional field, new enum value, new capability flag.
- **Patch** — doc/description changes only; no structural change.

## When bumping

1. Update the `$id` URL path segment (`/v1/` → `/v2/` for major only)
2. Update `schemaVersion` references in consumer tooling (`tools/validate.py`, iOS/web clients)
3. Update this file
4. Add a migration note if breaking

## Consumer guidance

Clients that parse the catalog should:

1. Fetch the schema or at least read a known profile file
2. Check `schemaVersion` is within their supported major range
3. Fail loudly on mismatch rather than silently mis-parse

Tooling that generates new profiles should emit the current `schemaVersion` in the top-level by-class file. The validator does not yet reject files that omit the field — it's advisory for now, enforced from `2.0.0` onwards.
