"""
Unit tests for Patch Evaluation and Blast Radius Metrics.
"""

from sentinel.evaluation.evaluator import PatchEvaluator
from sentinel.sandbox.patch_validator import PatchValidator
from sentinel.state import SandboxResult


def test_patch_validator_parses_unified_diff():
    raw_diff = """```diff
--- a/src/core.py
+++ b/src/core.py
@@ -10,4 +10,5 @@
 def execute():
-    return False
+    # Fixed by Sentinel
+    return True
```"""
    meta = PatchValidator.validate_and_parse(raw_diff)

    assert meta.is_valid
    assert meta.files_touched == ["src/core.py"]
    assert meta.lines_added == 2
    assert meta.lines_deleted == 1
    assert "```" not in meta.normalized_patch


def test_patch_evaluator_composite_score():
    diff = """--- a/src/math.py
+++ b/src/math.py
@@ -1,2 +1,2 @@
-def add(a, b): return 0
+def add(a, b): return a + b
"""
    sandbox_res = SandboxResult(
        patch_applied=True,
        tests_passed=True,
        exit_code=0,
        stdout="1 passed",
        stderr="",
        duration_seconds=1.2,
    )

    report = PatchEvaluator.evaluate(
        repo_path=".",
        patch_diff=diff,
        sandbox_result=sandbox_res,
    )

    assert report.test_pass_rate == 1.0
    assert report.loc_added == 1
    assert report.loc_deleted == 1
    assert report.files_touched == ["src/math.py"]
    assert report.overall_score > 0.8
    assert "Composite Score" in report.summary
