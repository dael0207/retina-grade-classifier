"""Manifest-derived evidence for the assignment 2 report."""

import csv
from dataclasses import dataclass
from pathlib import Path

from retina.report_data import ReportDataError


@dataclass(frozen=True, slots=True)
class SplitSummary:
    """Image, patient, and grade counts for one manifest split."""

    image_count: int
    patient_count: int
    grade_counts: tuple[int, int, int, int, int]


def summarize_manifest(path: Path) -> dict[str, SplitSummary]:
    """Read the immutable manifest and derive report counts without constants."""
    if not path.exists():
        message = f"Required report artifact is missing: {path}"
        raise ReportDataError(message)
    grade_counts = {name: [0, 0, 0, 0, 0] for name in ("train", "validation", "test")}
    patients = {name: set[str]() for name in grade_counts}
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        required = {"image", "level", "patient_id", "split"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            message = f"Manifest columns are invalid: {path}"
            raise ReportDataError(message)
        for line_number, row in enumerate(reader, start=2):
            split = row["split"]
            if split not in grade_counts:
                message = f"Invalid split on manifest line {line_number}: {split}"
                raise ReportDataError(message)
            try:
                grade = int(row["level"])
            except ValueError as error:
                message = f"Invalid grade on manifest line {line_number}"
                raise ReportDataError(message) from error
            if grade not in range(5):
                message = f"Invalid grade on manifest line {line_number}: {grade}"
                raise ReportDataError(message)
            grade_counts[split][grade] += 1
            patients[split].add(row["patient_id"])
    summaries: dict[str, SplitSummary] = {}
    for split, counts in grade_counts.items():
        typed_counts = (counts[0], counts[1], counts[2], counts[3], counts[4])
        summaries[split] = SplitSummary(sum(counts), len(patients[split]), typed_counts)
    return summaries
