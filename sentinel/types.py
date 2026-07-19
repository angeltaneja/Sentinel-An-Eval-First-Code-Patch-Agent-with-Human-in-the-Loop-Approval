# Typed result dataclasses
from dataclasses import dataclass

@dataclass
class PatchEvaluationResult:
    patch_id: str
    syntax_valid: bool
    test_pass: bool
