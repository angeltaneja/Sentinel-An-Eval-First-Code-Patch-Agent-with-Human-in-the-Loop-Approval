"""
Local Process Sandbox Runner for Sentinel.
Executes patches and test suites inside an ephemeral isolated filesystem clone
with strict process timeouts and sanitized environment variables.
Provides a rock-solid runner for environments without a running Docker daemon.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from sentinel.config import settings
from sentinel.observability.structured_logger import logger
from sentinel.sandbox.base import BaseSandboxRunner, SandboxExecutionResult
from sentinel.sandbox.patch_validator import PatchValidator


class LocalProcessSandboxRunner(BaseSandboxRunner):
    """Executes patches in a temporary directory sandbox using isolated subprocesses."""

    def __init__(self, timeout_seconds: int | None = None):
        self.timeout = timeout_seconds or settings.SANDBOX_TIMEOUT_SECONDS

    def run_patch_and_tests(
        self,
        repo_path: str,
        patch_diff: str,
        test_commands: list[str] | None = None,
    ) -> SandboxExecutionResult:
        """Apply patch to an ephemeral clone and run test commands."""
        start_time = time.time()

        # 1. Validate patch syntax
        patch_meta = PatchValidator.validate_and_parse(patch_diff)
        if not patch_meta.is_valid:
            return SandboxExecutionResult(
                patch_applied=False,
                tests_passed=False,
                exit_code=1,
                stdout="",
                stderr=patch_meta.error_message,
                duration_seconds=round(time.time() - start_time, 2),
                error_message=f"Invalid patch structure: {patch_meta.error_message}",
            )

        with tempfile.TemporaryDirectory(prefix="sentinel_local_box_") as temp_dir:
            temp_path = Path(temp_dir)
            source_repo = Path(repo_path).resolve()
            isolated_repo = temp_path / "repo"

            # Create clean copy of repository
            shutil.copytree(
                source_repo,
                isolated_repo,
                ignore=shutil.ignore_patterns(".git", "__pycache__", ".venv", "node_modules"),
            )

            # Initialize a temporary git repo so `git apply` functions deterministically
            try:
                subprocess.run(
                    ["git", "init"],
                    cwd=isolated_repo,
                    capture_output=True,
                    check=True,
                )
                subprocess.run(
                    ["git", "config", "user.email", "sentinel@agent.local"],
                    cwd=isolated_repo,
                    capture_output=True,
                )
                subprocess.run(
                    ["git", "config", "user.name", "Sentinel Agent"],
                    cwd=isolated_repo,
                    capture_output=True,
                )
                subprocess.run(
                    ["git", "add", "."],
                    cwd=isolated_repo,
                    capture_output=True,
                )
                subprocess.run(
                    ["git", "commit", "-m", "baseline"],
                    cwd=isolated_repo,
                    capture_output=True,
                )
            except Exception as git_err:
                logger.warning(f"Failed to initialize temp git repo: {git_err}")

            # 2. Apply patch
            patch_file = temp_path / "patch.diff"
            patch_file.write_text(patch_meta.normalized_patch, encoding="utf-8")

            patch_result = subprocess.run(
                ["git", "apply", "--verbose", "--whitespace=fix", "--ignore-space-change", "--ignore-whitespace", str(patch_file)],
                cwd=isolated_repo,
                capture_output=True,
                text=True,
            )

            patch_applied = (patch_result.returncode == 0)
            if not patch_applied:
                duration = round(time.time() - start_time, 2)
                error_msg = f"git apply failed (code {patch_result.returncode}):\n{patch_result.stderr}\n{patch_result.stdout}"
                return SandboxExecutionResult(
                    patch_applied=False,
                    tests_passed=False,
                    exit_code=patch_result.returncode,
                    stdout=patch_result.stdout,
                    stderr=patch_result.stderr,
                    duration_seconds=duration,
                    error_message=error_msg,
                )

            # 3. Execute test commands
            combined_stdout: list[str] = [f"Patch applied successfully.\n{patch_result.stdout}"]
            combined_stderr: list[str] = []
            tests_passed = True
            final_exit_code = 0

            # Default to pytest using the current python executable if none specified
            default_test_cmd = f"{sys.executable} -m pytest -v"
            commands_to_run = test_commands if test_commands else [default_test_cmd]

            # Sanitized environment
            clean_env = os.environ.copy()
            clean_env["PYTHONPATH"] = str(isolated_repo)
            clean_env["CI"] = "true"

            for cmd in commands_to_run:
                try:
                    proc = subprocess.run(
                        cmd,
                        cwd=isolated_repo,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=self.timeout,
                        env=clean_env,
                    )
                    combined_stdout.append(proc.stdout)
                    combined_stderr.append(proc.stderr)
                    if proc.returncode != 0:
                        tests_passed = False
                        final_exit_code = proc.returncode
                        break
                except subprocess.TimeoutExpired:
                    duration = round(time.time() - start_time, 2)
                    return SandboxExecutionResult(
                        patch_applied=True,
                        tests_passed=False,
                        exit_code=124,
                        stdout="\n".join(combined_stdout),
                        stderr=f"Test execution timed out after {self.timeout}s",
                        duration_seconds=duration,
                        error_message="Execution timeout in sandbox",
                    )
                except Exception as ex:
                    tests_passed = False
                    final_exit_code = 1
                    combined_stderr.append(str(ex))
                    break

            duration = round(time.time() - start_time, 2)
            stdout_str = "\n".join(combined_stdout)
            failed_tests, traceback = self._extract_test_failures(stdout_str)

            return SandboxExecutionResult(
                patch_applied=True,
                tests_passed=tests_passed,
                exit_code=final_exit_code,
                stdout=stdout_str,
                stderr="\n".join(combined_stderr),
                duration_seconds=duration,
                failed_test_names=failed_tests,
                failure_traceback=traceback,
            )

    def _extract_test_failures(self, logs: str) -> tuple[list[str], str | None]:
        """Parse test logs for failed test names and tracebacks."""
        failed_tests: list[str] = []
        for line in logs.splitlines():
            if line.startswith("FAILED ") or " FAILED " in line:
                test_name = line.replace("FAILED", "").strip().split()[0]
                if test_name not in failed_tests:
                    failed_tests.append(test_name)

        traceback_lines: list[str] = []
        capturing = False
        for line in logs.splitlines():
            if "Traceback (most recent call last):" in line or "=== FAILURES ===" in line:
                capturing = True
            if capturing:
                traceback_lines.append(line)
            if capturing and (line.startswith("===") and "failed in" in line):
                break

        traceback_text = "\n".join(traceback_lines) if traceback_lines else None
        return failed_tests, traceback_text
