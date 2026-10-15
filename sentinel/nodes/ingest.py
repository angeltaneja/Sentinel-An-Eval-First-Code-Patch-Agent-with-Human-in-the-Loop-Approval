"""
INGEST Node: Ingests GitHub issue metadata, comments, and repository structure.
"""

import time
from typing import Any

import httpx

from sentinel.config import settings
from sentinel.observability.structured_logger import logger
from sentinel.state import SentinelState


def ingest_node(state: SentinelState) -> dict[str, Any]:
    """
    Fetch issue body, title, comments, and repository tree via GitHub API.
    Supports offline/mock payloads when running locally.
    """
    start_time = time.time()
    repo_name = state.get("repo_name", "")
    issue_number = state.get("issue_number", 0)

    logger.info(f"[INGEST] Fetching issue #{issue_number} for repository '{repo_name}'")

    issue_title = state.get("issue_title", "")
    issue_body = state.get("issue_body", "")
    issue_author = state.get("issue_author", "unknown")
    issue_comments = state.get("issue_comments", [])

    # If GitHub token and repo_name provided, fetch live details
    if settings.GITHUB_TOKEN and repo_name and "/" in repo_name and issue_number > 0:
        headers = {
            "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
        }
        try:
            with httpx.Client(timeout=15.0) as client:
                # 1. Fetch Issue
                issue_url = f"https://api.github.com/repos/{repo_name}/issues/{issue_number}"
                resp = client.get(issue_url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    issue_title = data.get("title", issue_title)
                    issue_body = data.get("body", issue_body) or ""
                    issue_author = data.get("user", {}).get("login", issue_author)

                # 2. Fetch Comments
                comments_url = f"https://api.github.com/repos/{repo_name}/issues/{issue_number}/comments"
                c_resp = client.get(comments_url, headers=headers)
                if c_resp.status_code == 200:
                    issue_comments = [
                        {"author": c.get("user", {}).get("login"), "body": c.get("body")}
                        for c in c_resp.json()
                    ]
        except Exception as e:
            logger.warning(f"[INGEST] GitHub API request failed: {e}. Utilizing provided state.")

    duration_ms = (time.time() - start_time) * 1000
    logger.log_transition("START", "INGEST", str(issue_number), duration_ms)

    return {
        "issue_title": issue_title,
        "issue_body": issue_body,
        "issue_author": issue_author,
        "issue_comments": issue_comments,
        "diff_history": [],
        "diff_hashes": [],
        "retry_count": 0,
        "status": "ingested",
    }
