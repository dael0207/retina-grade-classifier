"""Paired-eye label analysis for assignment 1."""

from __future__ import annotations

import csv
import math
import sys
from collections import Counter
from dataclasses import dataclass
from enum import StrEnum, unique
from operator import attrgetter
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, ClassVar, Final, NewType, override

from pydantic import BaseModel, ConfigDict, Field

from retina.charts import render_charts
from retina.viewer import render_viewer

if TYPE_CHECKING:
    from collections.abc import Sequence

GRADE_COUNT: Final = 5
SCHEMA_VERSION: Final = "1.0"
PatientId = NewType("PatientId", int)
Grade = NewType("Grade", int)
FiveInts = Annotated[tuple[int, ...], Field(min_length=GRADE_COUNT, max_length=GRADE_COUNT)]
FiveFloats = Annotated[tuple[float, ...], Field(min_length=GRADE_COUNT, max_length=GRADE_COUNT)]


@unique
class EyeSide(StrEnum):
    """Side of a paired retinal image."""

    LEFT = "left"
    RIGHT = "right"


@dataclass(frozen=True, slots=True)
class DatasetValidationError(Exception):
    """Raised when label rows cannot form unambiguous patient pairs."""

    detail: str

    @override
    def __str__(self) -> str:
        """Return the actionable validation detail."""
        return self.detail


class LabelRow(BaseModel):
    """Validated representation of one external CSV row."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    image: str = Field(min_length=3)
    level: int = Field(ge=0, lt=GRADE_COUNT)


@dataclass(frozen=True, slots=True)
class EyeRecord:
    """Parsed internal label record."""

    patient_id: PatientId
    side: EyeSide
    image: str
    grade: Grade


@dataclass(frozen=True, slots=True)
class PatientPair:
    """One patient's left and right image labels."""

    patient_id: PatientId
    left_image: str
    right_image: str
    left_grade: Grade
    right_grade: Grade

    @property
    def difference(self) -> int:
        """Return the absolute distance between the two ordinal grades."""
        return abs(int(self.left_grade) - int(self.right_grade))


class AnalysisSummary(BaseModel):
    """Stable JSON contract for assignment 1 statistics."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    schema_version: str = SCHEMA_VERSION
    image_count: int
    patient_count: int
    class_counts: FiveInts
    class_percentages: FiveFloats
    cross_matrix: Annotated[
        tuple[FiveInts, ...], Field(min_length=GRADE_COUNT, max_length=GRADE_COUNT)
    ]
    difference_counts: FiveInts
    discordant_count: int
    discordant_percentage: float
    large_gap_count: int
    exact_agreement: float
    exact_agreement_ci95: tuple[float, float]
    affected_patient_count: int
    affected_exact_agreement: float
    weighted_kappa: float


class ExamplePair(BaseModel):
    """One deterministic image pair selected for visual inspection."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    patient_id: int
    left_image: str
    right_image: str
    left_grade: int
    right_grade: int
    difference: int


class ExampleSet(BaseModel):
    """Stable JSON contract for selected visual examples."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    selection_rule: str
    pairs: tuple[ExamplePair, ...]


def _parse_image_name(image: str) -> tuple[PatientId, EyeSide]:
    stem, separator, raw_side = image.rpartition("_")
    if not separator or not stem.isdecimal():
        raise DatasetValidationError(detail=f"invalid image name: {image!r}")
    try:
        side = EyeSide(raw_side)
    except ValueError as error:
        raise DatasetValidationError(detail=f"invalid eye side: {image!r}") from error
    return PatientId(int(stem)), side


def load_labels(path: Path) -> tuple[EyeRecord, ...]:
    """Read and parse the external label CSV at the trust boundary."""
    records: list[EyeRecord] = []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["image", "level"]:
            raise DatasetValidationError(detail=f"unexpected columns: {reader.fieldnames}")
        for row_number, raw in enumerate(reader, start=2):
            try:
                row = LabelRow.model_validate(raw)
            except ValueError as error:
                raise DatasetValidationError(detail=f"invalid row {row_number}: {error}") from error
            patient_id, side = _parse_image_name(row.image)
            records.append(EyeRecord(patient_id, side, row.image, Grade(row.level)))
    if not records:
        raise DatasetValidationError(detail="label file is empty")
    return tuple(records)


def pair_records(records: Sequence[EyeRecord]) -> tuple[PatientPair, ...]:
    """Pair complete left and right records, rejecting ambiguity."""
    grouped: dict[PatientId, dict[EyeSide, EyeRecord]] = {}
    for record in records:
        eyes = grouped.setdefault(record.patient_id, {})
        if record.side in eyes:
            raise DatasetValidationError(
                detail=f"duplicate {record.side.value} eye for patient {record.patient_id}"
            )
        eyes[record.side] = record
    pairs: list[PatientPair] = []
    for patient_id in sorted(grouped, key=int):
        eyes = grouped[patient_id]
        if set(eyes) != {EyeSide.LEFT, EyeSide.RIGHT}:
            raise DatasetValidationError(detail=f"missing eye for patient {patient_id}")
        left, right = eyes[EyeSide.LEFT], eyes[EyeSide.RIGHT]
        pairs.append(PatientPair(patient_id, left.image, right.image, left.grade, right.grade))
    return tuple(pairs)


def _wilson_interval(successes: int, total: int) -> tuple[float, float]:
    z = 1.959963984540054
    proportion = successes / total
    denominator = 1 + z**2 / total
    centre = (proportion + z**2 / (2 * total)) / denominator
    margin = (
        z * math.sqrt(proportion * (1 - proportion) / total + z**2 / (4 * total**2)) / denominator
    )
    return centre - margin, centre + margin


def _quadratic_weighted_kappa(matrix: list[list[int]]) -> float:
    total = sum(sum(row) for row in matrix)
    left = [sum(row) for row in matrix]
    right = [
        sum(matrix[row][column] for row in range(GRADE_COUNT)) for column in range(GRADE_COUNT)
    ]
    observed = 0.0
    expected = 0.0
    scale = float((GRADE_COUNT - 1) ** 2)
    for row in range(GRADE_COUNT):
        for column in range(GRADE_COUNT):
            weight = (row - column) ** 2 / scale
            observed += weight * matrix[row][column]
            expected += weight * left[row] * right[column] / total
    return 1.0 - observed / expected if expected else 1.0


def analyze_records(records: Sequence[EyeRecord]) -> AnalysisSummary:
    """Compute image and patient-level paired-eye statistics."""
    pairs = pair_records(records)
    class_counter = Counter(int(record.grade) for record in records)
    difference_counter = Counter(pair.difference for pair in pairs)
    matrix = [[0 for _ in range(GRADE_COUNT)] for _ in range(GRADE_COUNT)]
    for pair in pairs:
        matrix[int(pair.left_grade)][int(pair.right_grade)] += 1
    exact_count = difference_counter[0]
    affected = [pair for pair in pairs if max(pair.left_grade, pair.right_grade) > 0]
    affected_exact = sum(pair.difference == 0 for pair in affected)
    image_count, patient_count = len(records), len(pairs)
    return AnalysisSummary(
        image_count=image_count,
        patient_count=patient_count,
        class_counts=tuple(class_counter[index] for index in range(GRADE_COUNT)),
        class_percentages=tuple(
            100 * class_counter[index] / image_count for index in range(GRADE_COUNT)
        ),
        cross_matrix=tuple(tuple(row) for row in matrix),
        difference_counts=tuple(difference_counter[index] for index in range(GRADE_COUNT)),
        discordant_count=patient_count - exact_count,
        discordant_percentage=100 * (patient_count - exact_count) / patient_count,
        large_gap_count=sum(difference_counter[index] for index in range(2, GRADE_COUNT)),
        exact_agreement=exact_count / patient_count,
        exact_agreement_ci95=_wilson_interval(exact_count, patient_count),
        affected_patient_count=len(affected),
        affected_exact_agreement=affected_exact / len(affected),
        weighted_kappa=_quadratic_weighted_kappa(matrix),
    )


def select_examples(pairs: Sequence[PatientPair]) -> ExampleSet:
    """Select deterministic low- and high-severity examples for every gap."""
    selected: list[PatientPair] = []
    for difference in range(GRADE_COUNT):
        candidates = tuple(pair for pair in pairs if pair.difference == difference)
        low = min(
            candidates,
            key=lambda pair: (max(pair.left_grade, pair.right_grade), int(pair.patient_id)),
        )
        high = min(
            (pair for pair in candidates if pair.patient_id != low.patient_id),
            key=lambda pair: (-max(pair.left_grade, pair.right_grade), int(pair.patient_id)),
        )
        selected.extend((low, high))
    return ExampleSet(
        selection_rule=(
            "등급 차이 0~4별 2쌍; 각 차이에서 최대 등급이 가장 낮은 쌍과 가장 "
            "높은 쌍, 동률이면 ID 오름차순"
        ),
        pairs=tuple(
            ExamplePair(
                patient_id=int(pair.patient_id),
                left_image=pair.left_image,
                right_image=pair.right_image,
                left_grade=int(pair.left_grade),
                right_grade=int(pair.right_grade),
                difference=pair.difference,
            )
            for pair in selected
        ),
    )


def run(labels_path: Path, output_dir: Path) -> AnalysisSummary:
    """Run assignment 1 analysis and write all output artifacts."""
    records = load_labels(labels_path)
    pairs = pair_records(records)
    summary = analyze_records(records)
    examples = select_examples(pairs)
    output_dir.mkdir(parents=True, exist_ok=True)
    _ = (output_dir / "summary.json").write_text(
        summary.model_dump_json(indent=2), encoding="utf-8"
    )
    _ = (output_dir / "examples.json").write_text(
        examples.model_dump_json(indent=2), encoding="utf-8"
    )
    with (output_dir / "pairs.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            ("patient_id", "left_image", "right_image", "left_grade", "right_grade", "difference")
        )
        fields = attrgetter("patient_id", "left_image", "right_image", "left_grade", "right_grade")
        writer.writerows((*fields(pair), pair.difference) for pair in pairs)
    render_charts(summary, output_dir)
    render_viewer(
        output_dir / "summary.json", output_dir / "examples.json", output_dir / "viewer.html"
    )
    return summary


if __name__ == "__main__":
    arguments = sys.argv[1:]
    labels_path = Path(arguments[0]) if arguments else Path("trainLabels.csv")
    output_dir = Path(arguments[1]) if len(arguments) > 1 else Path("outputs/assignment1")
    _ = sys.stdout.write(f"{run(labels_path, output_dir).model_dump_json(indent=2)}\n")
