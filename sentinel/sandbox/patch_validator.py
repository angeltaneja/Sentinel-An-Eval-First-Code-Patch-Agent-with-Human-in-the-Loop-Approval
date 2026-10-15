"""
Unified Diff Patch Validator and Normalizer.
Parses, sanitizes, and extracts metadata from generated git patches.
"""

import re
from dataclasses import dataclass


@dataclass
class PatchMetadata:
    """Metadata extracted from a unified diff."""
    is_valid: bool
    files_touched: list[str]
    lines_added: int
    lines_deleted: int
    normalized_patch: str
    error_message: str = ""


class PatchValidator:
    """Sanitizes LLM outputs and validates unified diff structure."""

    @staticmethod
    def clean_patch_text(raw_patch: str) -> str:
        """Strip markdown code fence blocks if present."""
        cleaned = raw_patch.strip()
        # Remove ```diff ... ``` or ```patch ... ``` or ``` ... ```
        fence_match = re.search(r"```(?:diff|patch)?\s*\n(.*?)\n```", cleaned, re.DOTALL)
        if fence_match:
            cleaned = fence_match.group(1).strip()
        elif cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
        return cleaned

    @classmethod
    def validate_and_parse(cls, raw_patch: str) -> PatchMetadata:
        """Verify unified diff format and extract affected files and line statistics."""
        cleaned = cls.clean_patch_text(raw_patch)
        if not cleaned:
            return PatchMetadata(
                is_valid=False,
                files_touched=[],
                lines_added=0,
                lines_deleted=0,
                normalized_patch="",
                error_message="Empty patch text provided.",
            )

        lines = cleaned.splitlines()
        files_touched: list[str] = []
        lines_added = 0
        lines_deleted = 0
        has_hunk_header = False

        for line in lines:
            if line.startswith("--- a/") or line.startswith("--- "):
                target = line.split(maxsplit=1)[1].strip()
                target = target.removeprefix("a/")
                if target != "/dev/null" and target not in files_touched:
                    files_touched.append(target)
            elif line.startswith("+++ b/") or line.startswith("+++ "):
                target = line.split(maxsplit=1)[1].strip()
                target = target.removeprefix("b/")
                if target != "/dev/null" and target not in files_touched:
                    files_touched.append(target)
            elif line.startswith("@@ ") and " @@" in line:
                has_hunk_header = True
            elif line.startswith("+") and not line.startswith("+++"):
                lines_added += 1
            elif line.startswith("-") and not line.startswith("---"):
                lines_deleted += 1

        if not has_hunk_header and not files_touched:
            return PatchMetadata(
                is_valid=False,
                files_touched=[],
                lines_added=0,
                lines_deleted=0,
                normalized_patch=cleaned,
                error_message="Patch is missing unified diff hunk headers (@@ -x,y +x,y @@).",
            )

        return PatchMetadata(
            is_valid=True,
            files_touched=files_touched,
            lines_added=lines_added,
            lines_deleted=lines_deleted,
            normalized_patch=cleaned + "\n",
            error_message="",
        )
