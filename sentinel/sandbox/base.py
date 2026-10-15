"""
Base interfaces and data structures for Sandbox Runners.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class SandboxExecutionResult:
    """Standardized result of patch application and test suite execution."""
    patch_applied: bool
    tests_passed: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    failed_test_names: list[str] = field(default_factory=list)
    failure_traceback: str | None = None
    error_message: str | None = None


class BaseSandboxRunner(ABC):
    """Abstract interface for executing code patches and tests in isolation."""

    @abstractmethod
    def run_patch_and_tests(
        self,
        repo_path: str,
        patch_diff: str,
        test_commands: list[str] | None = None,
    ) -> SandboxExecutionResult:
        """Apply patch to a clean copy of repo and execute test suite."""
