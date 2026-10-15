"""
Unit tests for Sandbox Runners.
"""

from sentinel.sandbox.docker_runner import DockerSandboxRunner
from sentinel.sandbox.local_runner import LocalProcessSandboxRunner


def test_docker_runner_initialization_and_availability():
    runner = DockerSandboxRunner()
    # On environments without docker daemon, is_available gracefully returns False
    is_avail = runner.is_available()
    assert isinstance(is_avail, bool)


def test_local_runner_invalid_patch():
    runner = LocalProcessSandboxRunner()
    result = runner.run_patch_and_tests(
        repo_path=".",
        patch_diff="this is not a valid git diff",
    )
    assert not result.patch_applied
    assert not result.tests_passed
    assert "Invalid patch structure" in result.error_message
