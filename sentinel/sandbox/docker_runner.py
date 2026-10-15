"""
Docker-based Isolated Sandbox Runner for Sentinel.
Executes patches and test suites inside air-gapped (--network none) Docker containers
with strict CPU, memory, and wall-clock timeout constraints.
"""

import shutil
import tempfile
import time
from pathlib import Path

import docker
from sentinel.config import settings
from sentinel.sandbox.base import BaseSandboxRunner, SandboxExecutionResult
from sentinel.sandbox.patch_validator import PatchValidator


class DockerSandboxRunner(BaseSandboxRunner):
    """Executes patches and runs test suites inside hardened, network-isolated Docker containers."""

    def __init__(
        self,
        image_name: str | None = None,
        timeout_seconds: int | None = None,
        memory_limit: str | None = None,
        cpu_limit: float | None = None,
    ):
        self.image_name = image_name or settings.SANDBOX_DOCKER_IMAGE
        self.timeout = timeout_seconds or settings.SANDBOX_TIMEOUT_SECONDS
        self.memory_limit = memory_limit or settings.SANDBOX_MEMORY_LIMIT
        self.cpu_limit = cpu_limit or settings.SANDBOX_CPU_LIMIT
        self._client: docker.DockerClient | None = None

    def _get_client(self) -> docker.DockerClient:
        """Lazily initialize and verify Docker daemon connection."""
        if self._client is None:
            self._client = docker.from_env()
            self._client.ping()
        return self._client

    def is_available(self) -> bool:
        """Check if Docker daemon is running and reachable."""
        try:
            self._get_client()
            return True
        except Exception:
            return False

    def run_patch_and_tests(
        self,
        repo_path: str,
        patch_diff: str,
        test_commands: list[str] | None = None,
    ) -> SandboxExecutionResult:
        """Apply patch to a temporary repo clone and run tests inside a Docker container."""
        start_time = time.time()
        client = self._get_client()

        # Validate and normalize patch
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

        # Prepare isolated host workspace
        with tempfile.TemporaryDirectory(prefix="sentinel_sandbox_") as temp_dir:
            temp_path = Path(temp_dir)
            source_repo = Path(repo_path).resolve()
            isolated_repo = temp_path / "repo"

            # Copy repository to temporary workspace
            shutil.copytree(
                source_repo,
                isolated_repo,
                ignore=shutil.ignore_patterns(".git", "__pycache__", ".venv", "node_modules"),
            )

            # Write patch file
            patch_file = temp_path / "patch.diff"
            patch_file.write_text(patch_meta.normalized_patch, encoding="utf-8")

            # Script to run inside container:
            # 1. apply patch with git apply or patch command
            # 2. execute test command
            run_script = temp_path / "entrypoint.sh"
            tests_cmd = " && ".join(test_commands) if test_commands else "pytest -v"

            script_content = f"""#!/bin/sh
set -e
cd /workspace/repo
# Try applying patch with git or patch utility
if command -v git >/dev/null 2>&1; then
    git apply --verbose --whitespace=fix /workspace/patch.diff
elif command -v patch >/dev/null 2>&1; then
    patch -p1 < /workspace/patch.diff
else
    echo "Neither git nor patch utility available in container" >&2
    exit 127
fi

echo "--- PATCH APPLIED SUCCESSFULLY ---"
echo "Running test suite..."
{tests_cmd}
"""
            run_script.write_text(script_content.replace("\r\n", "\n"), encoding="utf-8")

            container = None
            try:
                # Launch network-isolated container
                container = client.containers.create(
                    image=self.image_name,
                    command=["/bin/sh", "/workspace/entrypoint.sh"],
                    volumes={
                        str(temp_path): {"bind": "/workspace", "mode": "rw"},
                    },
                    network_mode="none",  # Strict air-gapped isolation
                    mem_limit=self.memory_limit,
                    nano_cpus=int(self.cpu_limit * 1e9),
                    working_dir="/workspace/repo",
                )

                container.start()

                # Poll container with timeout guard
                exit_status = container.wait(timeout=self.timeout)
                exit_code = exit_status.get("StatusCode", 1)

                logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
                duration = round(time.time() - start_time, 2)

                patch_applied = "--- PATCH APPLIED SUCCESSFULLY ---" in logs
                tests_passed = (exit_code == 0) and patch_applied

                failed_tests, traceback = self._extract_test_failures(logs)

                return SandboxExecutionResult(
                    patch_applied=patch_applied,
                    tests_passed=tests_passed,
                    exit_code=exit_code,
                    stdout=logs,
                    stderr="",
                    duration_seconds=duration,
                    failed_test_names=failed_tests,
                    failure_traceback=traceback,
                )

            except docker.errors.ContainerError as ce:
                duration = round(time.time() - start_time, 2)
                return SandboxExecutionResult(
                    patch_applied=False,
                    tests_passed=False,
                    exit_code=ce.exit_status,
                    stdout=ce.container.logs().decode("utf-8", errors="replace"),
                    stderr=str(ce),
                    duration_seconds=duration,
                    error_message=f"Container execution error: {ce}",
                )
            except Exception as e:
                duration = round(time.time() - start_time, 2)
                return SandboxExecutionResult(
                    patch_applied=False,
                    tests_passed=False,
                    exit_code=1,
                    stdout="",
                    stderr=str(e),
                    duration_seconds=duration,
                    error_message=f"Docker sandbox failure: {e}",
                )
            finally:
                if container:
                    try:
                        container.remove(force=True)
                    except Exception:
                        pass

    def _extract_test_failures(self, logs: str) -> tuple[list[str], str | None]:
        """Parse pytest / test logs for failed test function names and stack traces."""
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
