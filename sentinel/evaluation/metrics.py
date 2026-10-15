"""
Quantitative metrics calculation for code patches.
Measures blast radius, diff size, and tests pass rate.
"""


from sentinel.sandbox.patch_validator import PatchValidator


class PatchMetricsCalculator:
    """Calculates quantitative quality and safety metrics for a code patch."""

    @staticmethod
    def calculate_blast_radius(patch_diff: str) -> tuple[int, int, list[str], float]:
        """
        Compute LOC added, LOC deleted, touched files, and blast radius penalty.
        Blast radius score is normalized from 0.0 (catastrophic) to 1.0 (surgical).
        """
        meta = PatchValidator.validate_and_parse(patch_diff)
        total_loc = meta.lines_added + meta.lines_deleted
        file_count = len(meta.files_touched)

        # Blast radius scoring:
        # A surgical fix usually touches 1-3 files and under 100 LOC.
        # Score drops as file count and LOC explode.
        loc_penalty = max(0.0, 1.0 - (total_loc / 300.0))
        file_penalty = max(0.0, 1.0 - (max(0, file_count - 1) * 0.2))
        blast_score = round(0.6 * loc_penalty + 0.4 * file_penalty, 3)

        return meta.lines_added, meta.lines_deleted, meta.files_touched, blast_score
