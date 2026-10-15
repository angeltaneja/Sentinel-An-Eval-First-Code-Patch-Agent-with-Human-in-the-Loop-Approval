"""
Linter and Static Analysis Runner for Sentinel.
Validates code syntax and style on affected files using Ruff and AST parsing.
"""

import ast
import shutil
import subprocess
from pathlib import Path

from sentinel.observability.structured_logger import logger


class PatchLinter:
    """Runs static analysis and lint checks over modified repository files."""

    @staticmethod
    def lint_files(repo_path: str, files_to_lint: list[str]) -> tuple[bool, list[str], bool]:
        """
        Lint files in repo.
        Returns: (lint_passed, violations_list, syntax_valid)
        """
        violations: list[str] = []
        syntax_valid = True
        base_dir = Path(repo_path).resolve()

        # 1. AST Syntax validation for Python files
        for rel_file in files_to_lint:
            target_path = base_dir / rel_file
            if not target_path.exists():
                continue

            if target_path.suffix.lower() == ".py":
                try:
                    code_text = target_path.read_text(encoding="utf-8", errors="replace")
                    ast.parse(code_text, filename=rel_file)
                except SyntaxError as syn_err:
                    syntax_valid = False
                    violations.append(f"Syntax Error in {rel_file}:{syn_err.lineno}: {syn_err.msg}")

        # 2. Ruff check if ruff executable is available
        ruff_bin = shutil.which("ruff")
        if ruff_bin and files_to_lint:
            try:
                valid_paths = [str(base_dir / f) for f in files_to_lint if (base_dir / f).exists()]
                if valid_paths:
                    result = subprocess.run(
                        [ruff_bin, "check", "--no-fix", *valid_paths],
                        cwd=base_dir,
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode != 0 and result.stdout:
                        for line in result.stdout.splitlines():
                            if line.strip():
                                violations.append(line.strip())
            except Exception as e:
                logger.warning(f"Ruff execution skipped or failed: {e}")

        lint_passed = (len(violations) == 0) and syntax_valid
        return lint_passed, violations, syntax_valid
