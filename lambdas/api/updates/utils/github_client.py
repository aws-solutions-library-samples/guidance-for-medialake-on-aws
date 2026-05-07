"""
GitHub API client for fetching repository information.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class GitHubClient:
    """Client for interacting with GitHub API."""

    def __init__(self, repo_url: str, timeout: int = 30):
        """
        Initialize GitHub client.

        Args:
            repo_url: GitHub repository URL
            timeout: Request timeout in seconds
        """
        self.repo_url = repo_url
        self.timeout = timeout
        self.session = requests.Session()

        # Extract owner and repo from URL
        # Expected format: https://github.com/owner/repo
        parts = repo_url.rstrip("/").split("/")
        if len(parts) >= 2:
            self.owner = parts[-2]
            self.repo = parts[-1]
        else:
            raise ValueError(f"Invalid GitHub repository URL: {repo_url}")

        self.api_base = "https://api.github.com"

        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 1.0  # Minimum seconds between requests

    def _make_request(
        self, endpoint: str, params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make a rate-limited request to GitHub API.

        Args:
            endpoint: API endpoint
            params: Query parameters

        Returns:
            JSON response data

        Raises:
            requests.RequestException: If request fails
        """
        # Rate limiting
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last)

        url = f"{self.api_base}{endpoint}"

        try:
            response = self.session.get(
                url,
                params=params or {},
                timeout=self.timeout,
                headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "MediaLake-AutoUpgrade/1.0",
                },
            )

            self.last_request_time = time.time()

            # Handle rate limiting
            if response.status_code == 403 and "rate limit" in response.text.lower():
                reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
                current_time = int(time.time())
                wait_time = max(0, reset_time - current_time + 1)

                logger.warning(
                    f"GitHub API rate limit exceeded. Waiting {wait_time} seconds."
                )
                time.sleep(wait_time)

                # Retry the request
                response = self.session.get(
                    url, params=params or {}, timeout=self.timeout
                )

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"GitHub API request failed: {e}")
            raise

    def get_branches(self) -> List[Dict[str, Any]]:
        """
        Get all branches from the repository.

        Returns:
            List of branch information
        """
        try:
            endpoint = f"/repos/{self.owner}/{self.repo}/branches"
            branches = self._make_request(endpoint)

            # Get default branch info
            repo_info = self._make_request(f"/repos/{self.owner}/{self.repo}")
            default_branch = repo_info.get("default_branch")

            result = []
            for branch in branches:
                commit_info = branch.get("commit", {})

                result.append(
                    {
                        "name": branch["name"],
                        "type": "branch",
                        "sha": commit_info.get("sha", ""),
                        "date": self._parse_date(
                            commit_info.get("commit", {})
                            .get("committer", {})
                            .get("date")
                        ),
                        "message": commit_info.get("commit", {}).get("message"),
                        "is_default": branch["name"] == default_branch,
                    }
                )

            return result

        except Exception as e:
            logger.error(f"Failed to fetch branches: {e}")
            raise

    def get_tags(self) -> List[Dict[str, Any]]:
        """
        Get all tags from the repository.

        Returns:
            List of tag information
        """
        try:
            endpoint = f"/repos/{self.owner}/{self.repo}/tags"
            tags = self._make_request(endpoint)

            # Get latest release info to identify latest tag
            latest_release = None
            try:
                latest_release = self._make_request(
                    f"/repos/{self.owner}/{self.repo}/releases/latest"
                )
            except requests.exceptions.HTTPError:
                # No releases found, that's okay
                pass

            latest_tag = latest_release.get("tag_name") if latest_release else None

            result = []
            for i, tag in enumerate(tags):
                commit_info = tag.get("commit", {})

                # Get commit details for date and message
                commit_sha = commit_info.get("sha")
                commit_details = {}
                if commit_sha:
                    try:
                        commit_details = self._make_request(
                            f"/repos/{self.owner}/{self.repo}/commits/{commit_sha}"
                        )
                    except Exception:
                        # If we can't get commit details, continue without them
                        pass

                result.append(
                    {
                        "name": tag["name"],
                        "type": "tag",
                        "sha": commit_sha or "",
                        "date": self._parse_date(
                            commit_details.get("commit", {})
                            .get("committer", {})
                            .get("date")
                        ),
                        "message": commit_details.get("commit", {}).get("message"),
                        "is_latest": tag["name"] == latest_tag
                        or (i == 0 and latest_tag is None),
                    }
                )

            return result

        except Exception as e:
            logger.error(f"Failed to fetch tags: {e}")
            raise

    def _parse_date(self, date_str: Optional[str]) -> str:
        """
        Parse GitHub date string to ISO format.

        Args:
            date_str: GitHub date string

        Returns:
            ISO 8601 formatted date string
        """
        if not date_str:
            return datetime.now(timezone.utc).isoformat()

        try:
            # GitHub returns dates in ISO format, but ensure consistent formatting
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt.isoformat()
        except (ValueError, AttributeError):
            return datetime.now(timezone.utc).isoformat()
