"""
Sandbox subsystem: isolated container and process runners, patch validation.
"""

from sentinel.sandbox.base import BaseSandboxRunner, SandboxExecutionResult
from sentinel.sandbox.docker_runner import DockerSandboxRunner
from sentinel.sandbox.factory import get_sandbox_runner
from sentinel.sandbox.local_runner import LocalProcessSandboxRunner
from sentinel.sandbox.patch_validator import PatchMetadata, PatchValidator

__all__ = [
    "BaseSandboxRunner",
    "DockerSandboxRunner",
    "LocalProcessSandboxRunner",
    "PatchMetadata",
    "PatchValidator",
    "SandboxExecutionResult",
    "get_sandbox_runner",
]
