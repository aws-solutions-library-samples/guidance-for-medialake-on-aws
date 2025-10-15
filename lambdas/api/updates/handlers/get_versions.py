"""
Handler for GET /updates/versions endpoint.
Fetches available versions (branches and tags) from GitHub repository.
"""

import logging
import os
from typing import Any, Dict

from aws_lambda_powertools.event_handler.exceptions import InternalServerError
from models.responses import GitHubVersion, VersionsResponseData
from utils.github_client import GitHubClient
from utils.response import create_success_response

logger = logging.getLogger(__name__)


def handle_get_versions() -> Dict[str, Any]:
    """
    Handle GET /updates/versions request.

    Returns:
        Standardized API response with available versions

    Raises:
        InternalServerError: If GitHub API fails or other errors occur
    """
    try:
        logger.info("  → handle_get_versions: Starting...")

        # Get GitHub repository URL from environment
        repo_url = os.environ.get(
            "GITHUB_REPO_URL",
            "https://github.com/aws-solutions-library-samples/guidance-for-medialake-on-aws",
        )
        timeout = int(os.environ.get("GITHUB_API_TIMEOUT", "30"))

        logger.info(f"  → Repository URL: {repo_url}")
        logger.info(f"  → Timeout: {timeout}s")

        # Initialize GitHub client
        logger.info("  → Initializing GitHub client...")
        github_client = GitHubClient(repo_url, timeout)
        logger.info("  → ✓ GitHub client initialized")

        # Fetch branches and tags
        logger.info("  → Fetching branches from GitHub...")
        branches_data = github_client.get_branches()
        logger.info(f"  → ✓ Fetched {len(branches_data)} branches")

        logger.info("  → Fetching tags from GitHub...")
        tags_data = github_client.get_tags()
        logger.info(f"  → ✓ Fetched {len(tags_data)} tags")

        # Convert to response models
        logger.info("  → Converting branches to response models...")
        branches = []
        for i, branch_data in enumerate(branches_data):
            logger.debug(
                f"    - Processing branch {i+1}/{len(branches_data)}: {branch_data.get('name')}"
            )
            branch = GitHubVersion(
                name=branch_data["name"],
                type=branch_data["type"],
                sha=branch_data["sha"],
                date=branch_data["date"],
                message=branch_data.get("message"),
                is_default=branch_data.get("is_default"),
                is_latest=None,  # Not applicable for branches
            )
            branches.append(branch)
        logger.info(f"  → ✓ Converted {len(branches)} branches")

        logger.info("  → Converting tags to response models...")
        tags = []
        for i, tag_data in enumerate(tags_data):
            logger.debug(
                f"    - Processing tag {i+1}/{len(tags_data)}: {tag_data.get('name')}"
            )
            tag = GitHubVersion(
                name=tag_data["name"],
                type=tag_data["type"],
                sha=tag_data["sha"],
                date=tag_data["date"],
                message=tag_data.get("message"),
                is_default=None,  # Not applicable for tags
                is_latest=tag_data.get("is_latest"),
            )
            tags.append(tag)
        logger.info(f"  → ✓ Converted {len(tags)} tags")

        # Create response data
        logger.info("  → Creating response data...")
        response_data = VersionsResponseData(branches=branches, tags=tags)
        logger.info("  → ✓ Response data created")

        logger.info(
            f"  → ✓ handle_get_versions completed: {len(branches)} branches, {len(tags)} tags"
        )

        response = create_success_response(response_data.model_dump())
        logger.info(f"  → Response structure: {list(response.keys())}")
        return response

    except Exception as e:
        logger.error(f"  → ✗ Failed to fetch versions from GitHub: {str(e)}")
        logger.exception("  → Full exception details:")
        raise InternalServerError(f"Failed to fetch available versions: {str(e)}")
