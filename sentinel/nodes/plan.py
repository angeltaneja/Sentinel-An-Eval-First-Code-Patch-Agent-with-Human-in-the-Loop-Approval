"""
PLAN Node: Proposes an approach, target candidate files, and test validation strategy.
"""

import json
import time
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from sentinel.config import settings
from sentinel.observability.langfuse_tracer import tracer
from sentinel.observability.structured_logger import logger
from sentinel.state import PlanOutput, SentinelState

PLAN_SYSTEM_PROMPT = """You are Sentinel's Senior Staff Architect.
Analyze the provided GitHub issue and repository description.
Formulate a precise, minimal repair plan.

Respond STRICTLY with a valid JSON object matching this schema:
{
  "analysis": "Root cause explanation and architectural requirements",
  "candidate_files": ["path/to/file1.py", "path/to/file2.py"],
  "strategy": "Step-by-step description of modifications to make",
  "test_targets": ["pytest tests/test_target.py", "pytest"]
}
Do not include any Markdown fences (e.g. ```json) in your raw response. Output pure JSON only.
"""


def plan_node(state: SentinelState) -> dict[str, Any]:
    """Execute LLM planning step to determine files to modify and test strategy."""
    start_time = time.time()
    issue_number = state.get("issue_number", 0)
    issue_title = state.get("issue_title", "")
    issue_body = state.get("issue_body", "")

    logger.info(f"[PLAN] Synthesizing plan for issue #{issue_number}: {issue_title}")

    prompt_content = f"Issue Title: {issue_title}\n\nIssue Description:\n{issue_body}"

    plan_dict: dict[str, Any] = {}

    if settings.OPENAI_API_KEY:
        try:
            from langchain_openai import ChatOpenAI

            llm = ChatOpenAI(
                model=settings.LLM_MODEL,
                temperature=0.0,
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
            )

            callbacks = tracer.get_langchain_callbacks(
                trace_name="sentinel-plan",
                session_id=f"issue-{issue_number}",
            )

            messages = [
                SystemMessage(content=PLAN_SYSTEM_PROMPT),
                HumanMessage(content=prompt_content),
            ]

            response = llm.invoke(messages, config={"callbacks": callbacks})
            raw_text = response.content.strip()

            # Clean json fences if returned
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1]
                raw_text = raw_text.removeprefix("json")

            parsed = json.loads(raw_text.strip())
            plan_obj = PlanOutput(**parsed)
            plan_dict = plan_obj.model_dump()
        except Exception as e:
            logger.warning(f"[PLAN] LLM planning encountered error: {e}. Falling back to default plan heuristic.")

    # Fallback heuristic if LLM is unavailable or failed
    if not plan_dict:
        plan_dict = PlanOutput(
            analysis=f"Analysis of issue: {issue_title}",
            candidate_files=[],
            strategy="Locate relevant symbols and apply minimal non-breaking fix.",
            test_targets=["pytest"],
        ).model_dump()

    duration_ms = (time.time() - start_time) * 1000
    logger.log_transition("INGEST", "PLAN", str(issue_number), duration_ms, {"files": plan_dict.get("candidate_files")})

    return {
        "plan": plan_dict,
        "status": "planned",
    }
