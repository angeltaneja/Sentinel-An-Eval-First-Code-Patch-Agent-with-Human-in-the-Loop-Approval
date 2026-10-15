"""
Evaluation Coordinator for Sentinel.
Synthesizes test outcomes, blast radius, and static analysis into an EvalReport.
"""

from sentinel.evaluation.linter import PatchLinter
from sentinel.evaluation.metrics import PatchMetricsCalculator
from sentinel.state import EvalReport, SandboxResult


class PatchEvaluator:
    """Evaluates patch viability, scope blast radius, syntax validity, and test results."""

    @classmethod
    def evaluate(
        cls,
        repo_path: str,
        patch_diff: str,
        sandbox_result: SandboxResult | None = None,
    ) -> EvalReport:
        """Compute comprehensive scorecard."""
        loc_added, loc_deleted, files_touched, blast_score = (
            PatchMetricsCalculator.calculate_blast_radius(patch_diff)
        )

        lint_passed, lint_violations, syntax_valid = PatchLinter.lint_files(
            repo_path=repo_path,
            files_to_lint=files_touched,
        )

        test_pass_rate = 0.0
        if sandbox_result and sandbox_result.tests_passed or sandbox_result and sandbox_result.patch_applied and sandbox_result.exit_code == 0:
            test_pass_rate = 1.0

        # Weighted composite score (0.0 to 1.0)
        lint_score = 1.0 if lint_passed else (0.5 if syntax_valid else 0.0)
        overall_score = round(
            (0.60 * test_pass_rate) + (0.25 * blast_score) + (0.15 * lint_score),
            3,
        )

        # Markdown executive summary
        summary = f"""### 🛡️ Sentinel Evaluation Scorecard
- **Composite Score**: **{overall_score:.2f} / 1.00**
- **Test Suite Status**: {"✅ PASSED" if test_pass_rate == 1.0 else "❌ FAILED"}
- **Blast Radius**: {len(files_touched)} files touched | +{loc_added} / -{loc_deleted} LOC (Score: {blast_score:.2f})
- **Linter & Syntax**: {"✅ Clean" if lint_passed else "⚠️ Violations Detected"} (Syntax Valid: {syntax_valid})
- **Files Modified**: {', '.join(files_touched) if files_touched else 'None'}
"""

        return EvalReport(
            test_pass_rate=test_pass_rate,
            loc_added=loc_added,
            loc_deleted=loc_deleted,
            files_touched=files_touched,
            lint_passed=lint_passed,
            lint_violations=lint_violations,
            syntax_valid=syntax_valid,
            overall_score=overall_score,
            summary=summary,
        )
