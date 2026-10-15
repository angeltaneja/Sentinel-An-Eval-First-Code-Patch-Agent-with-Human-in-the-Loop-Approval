"""
COMMIT Node: Applies patch, commits to branch, and opens a DRAFT pull request via GitHub API.
Only executed after explicit human approval.
"""

import subprocess
import time
from typing import Any

import httpx

from sentinel.config import settings
from sentinel.observability.structured_logger import logger
from sentinel.sandbox.patch_validator import PatchValidator
from sentinel.state import SentinelState


def commit_node(state: SentinelState) -> dict[str, Any]:
    """Execute draft PR creation and branch commit upon human approval."""
    start_time = time.time()
    issue_number = state.get("issue_number", 0)
    repo_name = state.get("repo_name", "")
    repo_path = state.get("repo_path", ".")
    patch_diff = state.get("current_patch", "")
    approval = state.get("human_approval") or {}
    eval_report = state.get("eval_report") or {}

    is_approved = approval.get("approved", False)

    if not is_approved:
        reason = approval.get("feedback") or "No reason specified."
        logger.warning(f"[COMMIT] Patch for issue #{issue_number} REJECTED by reviewer. Reason: {reason}")
        return {
            "status": "rejected",
            "error_message": f"Rejected by human reviewer: {reason}",
        }

    branch_name = f"sentinel/fix-issue-{issue_number}"
    logger.info(f"[COMMIT] Creating branch '{branch_name}' and opening Draft Pull Request...")

    # Apply patch locally in repo if git is present
    try:
        clean_patch = PatchValidator.clean_patch_text(patch_diff)
        patch_file = f"{repo_path}/.sentinel_approved.patch"
        with open(patch_file, "w", encoding="utf-8") as f:
            f.write(clean_patch + "\n")

        subprocess.run(["git", "checkout", "-b", branch_name], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "apply", "--whitespace=fix", ".sentinel_approved.patch"], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
        commit_msg = f"fix(issue-{issue_number}): automated patch proposed by Sentinel\n\nApproved by {approval.get('reviewer', 'human')}"
        subprocess.run(["git", "commit", "-m", commit_msg], cwd=repo_path, capture_output=True)
    except Exception as git_err:
        logger.warning(f"[COMMIT] Local git operations note: {git_err}")

    # Prepare Draft PR payload
    pr_body = f"""## 🛡️ Sentinel Patch Proposal (Human Approved)
Closes #{issue_number}

### 📋 Review & Approval
- **Reviewer**: `{approval.get('reviewer', 'human')}`
- **Reviewer Feedback**: {approval.get('feedback') or 'Approved'}
- **Composite Quality Score**: **{eval_report.get('overall_score', 1.0):.2f} / 1.00**

### 🧪 Evaluation Summary
- **Tests**: {"✅ Passed" if eval_report.get('test_pass_rate') == 1.0 else "❌ Failed"}
- **Blast Radius**: {eval_report.get('loc_added', 0)} added / {eval_report.get('loc_deleted', 0)} deleted LOC
- **Files Modified**: {', '.join(eval_report.get('files_touched', []))}

---
*Created automatically by Sentinel (Proposal Engine with Guardrails).*
"""

    pr_url = f"https://github.com/{repo_name}/pull/mock-{issue_number}"
    pr_number = 9999

    # Open live Draft PR if GitHub token and repo_name are configured
    if settings.GITHUB_TOKEN and repo_name and "/" in repo_name:
        headers = {
            "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
        }
        api_url = f"https://api.github.com/repos/{repo_name}/pulls"
        payload = {
            "title": f"[Sentinel Draft] Fix for Issue #{issue_number}: {state.get('issue_title')}",
            "body": pr_body,
            "head": branch_name,
            "base": "main",
            "draft": True,  # Opens as DRAFT PR
        }
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(api_url, headers=headers, json=payload)
                if resp.status_code in (200, 201):
                    pr_data = resp.json()
                    pr_url = pr_data.get("html_url", pr_url)
                    pr_number = pr_data.get("number", pr_number)
                    logger.info(f"[COMMIT] Successfully opened DRAFT PR #{pr_number}: {pr_url}")
                else:
                    logger.warning(f"[COMMIT] GitHub Draft PR creation status {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.warning(f"[COMMIT] GitHub Draft PR API error: {e}")

    pr_result = {
        "pr_url": pr_url,
        "pr_number": pr_number,
        "branch_name": branch_name,
        "status": "draft_opened",
    }

    duration_ms = (time.time() - start_time) * 1000
    logger.log_transition("HUMAN_GATE", "COMMIT", str(issue_number), duration_ms, pr_result)

    return {
        "pr_result": pr_result,
        "status": "committed",
    }
