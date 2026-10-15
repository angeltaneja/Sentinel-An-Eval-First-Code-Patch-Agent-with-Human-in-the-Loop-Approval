"""
Sandbox Runner Factory for Sentinel.
Automatically negotiates between Docker sandbox and Local isolated process sandbox.
"""

from sentinel.config import settings
from sentinel.observability.structured_logger import logger
from sentinel.sandbox.base import BaseSandboxRunner
from sentinel.sandbox.docker_runner import DockerSandboxRunner
from sentinel.sandbox.local_runner import LocalProcessSandboxRunner


def get_sandbox_runner(backend: str = "auto") -> BaseSandboxRunner:
    """Return the configured sandbox runner with automatic environmental fallback."""
    target_backend = backend or settings.SANDBOX_BACKEND

    if target_backend == "docker":
        runner = DockerSandboxRunner()
        if not runner.is_available():
            raise RuntimeError(
                "Docker sandbox backend was explicitly requested, but Docker daemon is unreachable."
            )
        return runner

    if target_backend == "local":
        return LocalProcessSandboxRunner()

    # "auto" detection
    docker_runner = DockerSandboxRunner()
    if docker_runner.is_available():
        logger.info("Docker daemon detected. Operating with hardened Docker sandbox.")
        return docker_runner

    logger.warning(
        "Docker daemon not reachable. Falling back to local isolated process sandbox."
    )
    return LocalProcessSandboxRunner()
