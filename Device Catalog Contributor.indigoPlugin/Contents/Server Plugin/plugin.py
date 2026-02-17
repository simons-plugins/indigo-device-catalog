"""
Device Catalog Contributor - Indigo Plugin

Discovers device types on your Indigo server and contributes privacy-scrubbed
profiles to the indigo-device-catalog repository.
"""

import json
import os
from collections import defaultdict
from datetime import date

try:
    import indigo
except ImportError:
    pass

from profile_builder import (
    CLASS_CAPABILITIES,
    CLASS_COMMANDS,
    CLASS_TO_FILE,
    build_profile,
    get_device_class_name,
)
from catalog_client import fetch_catalog_index, fetch_class_file, get_existing_profile_keys
from github_client import GitHubClient


class Plugin(indigo.PluginBase):

    def __init__(self, plugin_id, plugin_display_name, plugin_version, plugin_prefs, **kwargs):
        super().__init__(plugin_id, plugin_display_name, plugin_version, plugin_prefs, **kwargs)
        self.debug = plugin_prefs.get("showDebugInfo", False)
        self.pending_profiles = {}  # dev_class -> list of profile dicts

    def startup(self):
        self.logger.info("Device Catalog Contributor started")
        self.debug = self.pluginPrefs.get("showDebugInfo", False)

    def shutdown(self):
        self.logger.info("Device Catalog Contributor stopped")

    def closedPrefsConfigUi(self, values_dict, user_cancelled):
        if not user_cancelled:
            self.debug = values_dict.get("showDebugInfo", False)

    # ------------------------------------------------------------------
    # Menu callbacks
    # ------------------------------------------------------------------

    def discover_profiles(self):
        """Discover device types not yet in the catalog."""
        contributor = self.pluginPrefs.get("contributorName", "community")
        token = self.pluginPrefs.get("githubToken", "")

        # Step 1: Fetch existing catalog from GitHub
        self.logger.info("Fetching existing catalog from GitHub...")
        index_data = fetch_catalog_index(github_token=token or None)
        if index_data:
            existing = get_existing_profile_keys(index_data)
            self.logger.info(f"Catalog has {len(existing)} existing profile(s)")
        else:
            existing = set()
            self.logger.warning(
                "Could not fetch catalog from GitHub. "
                "Discovery will proceed but may find profiles that already exist."
            )

        # Step 2: Iterate all devices and find new (pluginId, deviceTypeId) combos
        seen = {}  # (pluginId, deviceTypeId) -> first device found
        for dev in indigo.devices:
            plugin_id = getattr(dev, "pluginId", "")
            device_type_id = getattr(dev, "deviceTypeId", "")
            if not plugin_id or not device_type_id:
                continue

            key = (plugin_id, device_type_id)
            if key not in existing and key not in seen:
                seen[key] = dev

        if not seen:
            self.logger.info("Catalog is up to date! No new device types found.")
            self.pending_profiles = {}
            return

        # Step 3: Build profiles for new device types
        new_profiles = defaultdict(list)
        for (plugin_id, device_type_id), dev in sorted(seen.items()):
            try:
                dev_class = get_device_class_name(dev)
                profile = build_profile(dev, contributor)
                new_profiles[dev_class].append(profile)
                self.logger.debug(f"  New: {plugin_id} / {device_type_id} ({dev_class})")
            except Exception as exc:
                self.logger.error(f"  Error building profile for {plugin_id}/{device_type_id}: {exc}")

        self.pending_profiles = dict(new_profiles)
        total = sum(len(v) for v in self.pending_profiles.values())
        classes = len(self.pending_profiles)
        self.logger.info(f"Found {total} new profile(s) across {classes} device class(es)")
        self.logger.info(
            'Use "Export Profiles to File" to save, or "Submit to Catalog (GitHub)" to create a PR.'
        )

    def export_profiles(self):
        """Export discovered profiles to a JSON file on the Desktop."""
        if not self.pending_profiles:
            self.logger.error(
                'No profiles to export. Run "Discover New Profiles" first.'
            )
            return

        # Build the export structure: one entry per class with full catalog format
        export = {}
        for dev_class, profiles in sorted(self.pending_profiles.items()):
            filename = CLASS_TO_FILE.get(dev_class, "custom.json")
            export[filename] = {
                "$schema": "../../schema/device-profile.schema.json",
                "baseClass": dev_class,
                "classCapabilities": CLASS_CAPABILITIES.get(dev_class, []),
                "profiles": sorted(profiles, key=lambda p: (p["pluginId"], p["deviceTypeId"])),
            }
            commands = CLASS_COMMANDS.get(dev_class)
            if commands:
                export[filename]["classCommands"] = commands

        # Write to Desktop
        desktop = os.path.expanduser("~/Desktop")
        output_path = os.path.join(desktop, "indigo-device-catalog-contribution.json")
        with open(output_path, "w") as f:
            json.dump(export, f, indent=2)

        total = sum(len(v) for v in self.pending_profiles.values())
        self.logger.info(f"Exported {total} profile(s) to {output_path}")
        self.logger.info(
            "To contribute: create an issue at "
            "https://github.com/simons-plugins/indigo-device-catalog/issues "
            "and attach this file."
        )

    def submit_to_github(self):
        """Submit discovered profiles as a PR to the catalog repository."""
        if not self.pending_profiles:
            self.logger.error(
                'No profiles to submit. Run "Discover New Profiles" first.'
            )
            return

        token = self.pluginPrefs.get("githubToken", "")
        if not token:
            self.logger.error(
                "GitHub token not configured. Go to Plugins > Device Catalog Contributor > Configure "
                "and add a GitHub personal access token with 'repo' scope. "
                'Or use "Export Profiles to File" instead.'
            )
            return

        contributor = self.pluginPrefs.get("contributorName", "community")
        today = date.today().isoformat()
        total = sum(len(v) for v in self.pending_profiles.values())

        try:
            client = GitHubClient(token)

            # Step 1: Fork the repo (or use existing fork)
            self.logger.info("Forking catalog repository...")
            fork_owner = client.fork_repo()
            self.logger.debug(f"Fork owner: {fork_owner}")

            # Step 2: Get main branch SHA and create contribution branch
            main_sha = client.get_main_sha()
            branch_name = f"contribute/{contributor}/{today}"
            self.logger.info(f"Creating branch: {branch_name}")
            try:
                client.create_branch(fork_owner, branch_name, main_sha)
            except Exception as exc:
                # Branch might already exist from a previous attempt
                self.logger.debug(f"Branch creation note: {exc}")

            # Step 3: For each class, merge new profiles into the existing file
            pr_body_lines = [f"## New Device Profiles\n\nContributed by **{contributor}**\n"]
            for dev_class, profiles in sorted(self.pending_profiles.items()):
                filename = CLASS_TO_FILE.get(dev_class, "custom.json")
                file_path = f"catalog/by-class/{filename}"

                # Download existing file from upstream main
                existing_content, existing_sha = client.get_file_contents(file_path)

                if existing_content:
                    data = json.loads(existing_content)
                    data["profiles"].extend(profiles)
                else:
                    data = {
                        "$schema": "../../schema/device-profile.schema.json",
                        "baseClass": dev_class,
                        "classCapabilities": CLASS_CAPABILITIES.get(dev_class, []),
                        "profiles": list(profiles),
                    }
                    commands = CLASS_COMMANDS.get(dev_class)
                    if commands:
                        data["classCommands"] = commands

                data["profiles"] = sorted(
                    data["profiles"],
                    key=lambda p: (p["pluginId"], p["deviceTypeId"]),
                )

                # Get the SHA from the fork's branch (may differ from upstream after previous commits)
                _, fork_sha = client.get_file_contents(file_path, ref=branch_name, owner=fork_owner)

                new_content = json.dumps(data, indent=2)
                message = f"Add {len(profiles)} {dev_class} profile(s) from {contributor}"
                client.create_or_update_file(
                    fork_owner, branch_name, file_path, new_content, message,
                    sha=fork_sha or existing_sha,
                )
                self.logger.info(f"  Updated {filename}: +{len(profiles)} profile(s)")

                for p in profiles:
                    pr_body_lines.append(f"- **{p['pluginName']}**: `{p['deviceTypeId']}` ({dev_class})")

            # Step 4: Regenerate _index.json
            self._commit_regenerated_indexes(client, fork_owner, branch_name, contributor)

            # Step 5: Open PR
            pr_body_lines.append(f"\n---\n*Auto-generated by Device Catalog Contributor plugin*")
            pr_title = f"Add {total} device profile(s) from {contributor}"
            pr_body = "\n".join(pr_body_lines)
            pr_url = client.create_pull_request(fork_owner, branch_name, pr_title, pr_body)

            self.logger.info(f"Pull request created: {pr_url}")

        except Exception as exc:
            self.logger.error(f"GitHub submission failed: {exc}")
            self.logger.exception(exc)
            self.logger.info(
                'You can still use "Export Profiles to File" and submit manually.'
            )

    # ------------------------------------------------------------------
    # Index regeneration for GitHub submissions
    # ------------------------------------------------------------------

    def _commit_regenerated_indexes(self, client, fork_owner, branch_name, contributor):
        """Regenerate and commit _index.json and by-plugin/_index.json."""
        today = date.today().isoformat()

        # Read all by-class files from the fork branch to build the index
        index = {"generated": today, "classes": {}}
        plugin_index = {"generated": today, "plugins": {}}

        for dev_class, file_info in sorted(CLASS_TO_FILE.items()):
            # CLASS_TO_FILE has duplicates (Device and MultiIODevice both map to custom.json)
            # so we deduplicate by filename
            pass

        # Get the list of class files by reading each known filename
        seen_files = set()
        for dev_class_name, filename in CLASS_TO_FILE.items():
            if filename in seen_files:
                continue
            seen_files.add(filename)

            file_path = f"catalog/by-class/{filename}"
            content, _ = client.get_file_contents(file_path, ref=branch_name, owner=fork_owner)
            if not content:
                continue

            data = json.loads(content)
            base_class = data.get("baseClass", dev_class_name)
            profiles = data.get("profiles", [])

            class_entry = {
                "file": f"by-class/{filename}",
                "profileCount": len(profiles),
                "plugins": {},
            }
            for p in profiles:
                pid = p["pluginId"]
                if pid not in class_entry["plugins"]:
                    class_entry["plugins"][pid] = {
                        "pluginName": p.get("pluginName", pid),
                        "deviceTypeIds": [],
                    }
                class_entry["plugins"][pid]["deviceTypeIds"].append(p["deviceTypeId"])

                if pid not in plugin_index["plugins"]:
                    plugin_index["plugins"][pid] = {
                        "pluginName": p.get("pluginName", pid),
                        "deviceTypes": [],
                    }
                plugin_index["plugins"][pid]["deviceTypes"].append({
                    "baseClass": base_class,
                    "deviceTypeId": p["deviceTypeId"],
                })

            index["classes"][base_class] = class_entry

        # Sort plugin index
        plugin_index["plugins"] = dict(sorted(plugin_index["plugins"].items()))
        for pid in plugin_index["plugins"]:
            plugin_index["plugins"][pid]["deviceTypes"] = sorted(
                plugin_index["plugins"][pid]["deviceTypes"],
                key=lambda x: (x["baseClass"], x["deviceTypeId"]),
            )

        # Commit _index.json
        _, sha = client.get_file_contents("catalog/_index.json", ref=branch_name, owner=fork_owner)
        client.create_or_update_file(
            fork_owner, branch_name, "catalog/_index.json",
            json.dumps(index, indent=2),
            f"Regenerate catalog index ({contributor})",
            sha=sha,
        )

        # Commit by-plugin/_index.json
        _, sha = client.get_file_contents("catalog/by-plugin/_index.json", ref=branch_name, owner=fork_owner)
        client.create_or_update_file(
            fork_owner, branch_name, "catalog/by-plugin/_index.json",
            json.dumps(plugin_index, indent=2),
            f"Regenerate plugin index ({contributor})",
            sha=sha,
        )

        self.logger.debug("Regenerated index files on branch")
