"""
GENERATE Node: Synthesizes a unified diff code patch using retrieved context and plan.
"""

import hashlib
import time
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from sentinel.config import settings
from sentinel.observability.langfuse_tracer import tracer
from sentinel.observability.structured_logger import logger
from sentinel.sandbox.patch_validator import PatchValidator
from sentinel.state import SentinelState

GENERATE_SYSTEM_PROMPT = """You are Sentinel's Principal Patch Engineer.
Your mission is to generate a pristine, minimal, and fully functioning unified diff patch that resolves the target issue.

Rules for your patch:
1. Output MUST be a valid unified diff (git format).
2. Start directly with diff header lines (e.g. `--- a/file.py` and `+++ b/file.py`).
3. Include standard hunk headers (e.g. `@@ -line,count +line,count @@`).
4. Modify ONLY the necessary lines. Minimize blast radius.
5. Do NOT include markdown explanations or conversation before or after the diff.
"""


def generate_node(state: SentinelState) -> dict[str, Any]:
    """Generate a unified diff patch for the target repository."""
    start_time = time.time()
    issue_number = state.get("issue_number", 0)
    issue_title = state.get("issue_title", "")
    issue_body = state.get("issue_body", "")
    plan = state.get("plan") or {}
    chunks = state.get("retrieved_chunks", [])
    retry_count = state.get("retry_count", 0)
    sandbox_result = state.get("sandbox_result")

    logger.info(f"[GENERATE] Generating patch for issue #{issue_number} (Retry: {retry_count})")

    # Format context chunks
    context_blocks: list[str] = []
    for c in chunks[:6]:
        context_blocks.append(
            f"--- File: {c.get('file_path')} (Lines {c.get('start_line')}-{c.get('end_line')}) ---\n"
            f"{c.get('content')}"
        )
    formatted_context = "\n\n".join(context_blocks)

    # Build repair context if coming from a previous failed run
    repair_context = ""
    if retry_count > 0 and sandbox_result:
        repair_context = f"""
PREVIOUS ATTEMPT FAILED:
Exit Code: {sandbox_result.get('exit_code')}
Error / Traceback:
{sandbox_result.get('failure_traceback') or sandbox_result.get('stderr') or sandbox_result.get('stdout', '')[:1000]}

Failed Tests: {sandbox_result.get('failed_test_names', [])}
Analyze the failure carefully and produce a corrected patch that fixes the errors.
"""

    prompt = f"""Target Issue #{issue_number}: {issue_title}

Description:
{issue_body}

Plan Strategy:
{plan.get('strategy', 'Resolve issue safely.')}

Candidate Files:
{', '.join(plan.get('candidate_files', []))}

{repair_context}

Relevant Code Context:
{formatted_context}

Produce the unified diff patch now:
"""

    patch_text = ""
    if settings.OPENAI_API_KEY:
        try:
            from langchain_openai import ChatOpenAI

            llm = ChatOpenAI(
                model=settings.LLM_MODEL,
                temperature=0.1,
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
            )

            callbacks = tracer.get_langchain_callbacks(
                trace_name="sentinel-generate-patch",
                session_id=f"issue-{issue_number}-r{retry_count}",
            )

            messages = [
                SystemMessage(content=GENERATE_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ]

            response = llm.invoke(messages, config={"callbacks": callbacks})
            patch_text = response.content
        except Exception as e:
            logger.warning(f"[GENERATE] Patch generation API error: {e}")

    # Fallback diff if no API key or empty response
    if not patch_text.strip():
        # Clean dummy fallback patch for deterministic testing
        first_file = "src/main.py"
        if chunks:
            first_file = chunks[0].get("file_path", first_file)
        patch_text = f"""--- a/{first_file}
+++ b/{first_file}
@@ -1,3 +1,4 @@
+# Patched by Sentinel
"""

    # Validate and normalize
    meta = PatchValidator.validate_and_parse(patch_text)
    clean_diff = meta.normalized_patch

    # Compute SHA-256 fingerprint for diff cycle detection
    diff_hash = hashlib.sha256(clean_diff.encode("utf-8")).hexdigest()

    diff_history = list(state.get("diff_history", []))
    diff_hashes = list(state.get("diff_hashes", []))

    diff_history.append(clean_diff)
    diff_hashes.append(diff_hash)

    duration_ms = (time.time() - start_time) * 1000
    logger.log_transition(
        "RETRIEVE" if retry_count == 0 else "REPAIR",
        "GENERATE",
        str(issue_number),
        duration_ms,
        {"diff_hash": diff_hash[:8], "lines_added": meta.lines_added, "lines_deleted": meta.lines_deleted},
    )

    return {
        "current_patch": clean_diff,
        "diff_history": diff_history,
        "diff_hashes": diff_hashes,
        "status": "generated",
    }
