"""
GitHub API client for fork/branch/commit/PR operations.

Uses only Python stdlib (urllib.request) - no external dependencies.
All operations use the GitHub REST API v3.
"""

import base64
import json
import ssl
import urllib.error
import urllib.request

API_BASE = "https://api.github.com"


class GitHubClient:
    """Minimal GitHub API client for contributing device profiles."""

    def __init__(self, token, repo_owner="simons-plugins", repo_name="indigo-device-catalog"):
        self.token = token
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self._ssl_ctx = ssl.create_default_context()

    def _request(self, method, url, data=None):
        """Make an authenticated GitHub API request."""
        if not url.startswith("http"):
            url = f"{API_BASE}{url}"

        body = None
        if data is not None:
            body = json.dumps(data).encode("utf-8")

        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("User-Agent", "IndigoDeviceCatalogContributor/1.0")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        if body:
            req.add_header("Content-Type", "application/json")

        resp = urllib.request.urlopen(req, context=self._ssl_ctx, timeout=30)
        resp_body = resp.read()
        if resp_body:
            return json.loads(resp_body)
        return {}

    def get_authenticated_user(self):
        """Get the authenticated user's login."""
        data = self._request("GET", "/user")
        return data["login"]

    def fork_repo(self):
        """
        Fork the upstream repo under the authenticated user's account.

        Returns the fork owner's login. If the fork already exists, returns
        the existing fork owner.
        """
        url = f"/repos/{self.repo_owner}/{self.repo_name}/forks"
        try:
            data = self._request("POST", url, {})
            return data["owner"]["login"]
        except urllib.error.HTTPError as e:
            if e.code == 422:
                # Fork likely already exists
                return self.get_authenticated_user()
            raise

    def get_main_sha(self):
        """Get the SHA of the main branch head on the upstream repo."""
        url = f"/repos/{self.repo_owner}/{self.repo_name}/git/ref/heads/main"
        data = self._request("GET", url)
        return data["object"]["sha"]

    def create_branch(self, fork_owner, branch_name, base_sha):
        """Create a new branch on the fork."""
        url = f"/repos/{fork_owner}/{self.repo_name}/git/refs"
        data = self._request("POST", url, {
            "ref": f"refs/heads/{branch_name}",
            "sha": base_sha,
        })
        return data["ref"]

    def get_file_contents(self, path, ref="main", owner=None):
        """
        Download a file from the repo. Returns (content_str, sha) or (None, None).
        """
        owner = owner or self.repo_owner
        url = f"/repos/{owner}/{self.repo_name}/contents/{path}?ref={ref}"
        try:
            data = self._request("GET", url)
            content = base64.b64decode(data["content"]).decode("utf-8")
            return content, data["sha"]
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None, None
            raise

    def create_or_update_file(self, fork_owner, branch, path, content, message, sha=None):
        """
        Create or update a file on the fork via the Contents API.

        If sha is provided, this updates an existing file. Otherwise creates new.
        """
        url = f"/repos/{fork_owner}/{self.repo_name}/contents/{path}"
        payload = {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha

        return self._request("PUT", url, payload)

    def create_pull_request(self, fork_owner, branch, title, body):
        """Open a PR from the fork branch to the upstream main branch."""
        url = f"/repos/{self.repo_owner}/{self.repo_name}/pulls"
        data = self._request("POST", url, {
            "title": title,
            "body": body,
            "head": f"{fork_owner}:{branch}",
            "base": "main",
        })
        return data["html_url"]
