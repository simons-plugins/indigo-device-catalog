"""
Download and parse the existing device catalog from GitHub.

Uses only Python stdlib (urllib.request) - no external dependencies.
"""

import json
import ssl
import urllib.error
import urllib.request

REPO_OWNER = "simons-plugins"
REPO_NAME = "indigo-device-catalog"
BRANCH = "main"

RAW_BASE_URL = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{BRANCH}"
INDEX_URL = f"{RAW_BASE_URL}/catalog/_index.json"


def _make_request(url, token=None, timeout=30):
    """Make an HTTPS GET request and return parsed JSON."""
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "IndigoDeviceCatalogContributor/1.0")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    resp = urllib.request.urlopen(req, context=ctx, timeout=timeout)
    return json.loads(resp.read())


def fetch_catalog_index(github_token=None):
    """
    Download _index.json from the catalog repository.

    Returns the parsed index dict, or None if the fetch fails.
    """
    try:
        return _make_request(INDEX_URL, token=github_token)
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError):
        return None


def fetch_class_file(filename, github_token=None):
    """
    Download a by-class catalog file (e.g. 'relay.json') from GitHub.

    Returns the parsed dict, or None if the fetch fails.
    """
    url = f"{RAW_BASE_URL}/catalog/by-class/{filename}"
    try:
        return _make_request(url, token=github_token)
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError):
        return None


def get_existing_profile_keys(index_data):
    """
    Extract all (pluginId, deviceTypeId) pairs from the catalog index.

    Returns a set of tuples.
    """
    existing = set()
    if not index_data or "classes" not in index_data:
        return existing

    for class_info in index_data["classes"].values():
        plugins = class_info.get("plugins", {})
        for plugin_id, plugin_info in plugins.items():
            for device_type_id in plugin_info.get("deviceTypeIds", []):
                existing.add((plugin_id, device_type_id))

    return existing
