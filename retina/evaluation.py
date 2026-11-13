"""Five-grade classification metrics for held-out evaluation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

GRADES: tuple[int, ...] = (0, 1, 2, 3, 4)
GRADE_COUNT = 5


@dataclass(frozen=True, slots=True)
class ClassificationMetrics:
    """Serializable metrics that always retain all five grades."""

    accuracy: float
    qwk: float
    macro_f1: float
    recall_by_grade: dict[str, float]
    confusion_matrix: list[list[int]]

    def to_dict(self) -> dict[str, float | dict[str, float] | list[list[int]]]:
        """Return a JSON-compatible representation."""
        return asdict(self)


def classification_metrics(
    truth: Sequence[int],
    predicted: Sequence[int],
) -> ClassificationMetrics:
    """Compute accuracy, quadratic kappa, macro F1, recalls, and confusion."""
    if len(truth) != len(predicted):
        msg = "truth and predicted must have equal length"
        raise ValueError(msg)
    if len(truth) == 0:
        msg = "metrics require at least one sample"
        raise ValueError(msg)
    matrix = [[0 for _ in GRADES] for _ in GRADES]
    for actual, estimate in zip(truth, predicted, strict=True):
        if actual not in GRADES or estimate not in GRADES:
            msg = "metrics only accept grades zero through four"
            raise ValueError(msg)
        matrix[actual][estimate] += 1
    recalls, f1_scores = _per_grade_scores(matrix)
    return ClassificationMetrics(
        accuracy=sum(matrix[grade][grade] for grade in GRADES) / len(truth),
        qwk=_quadratic_kappa(matrix, len(truth)),
        macro_f1=sum(f1_scores) / GRADE_COUNT,
        recall_by_grade={str(grade): value for grade, value in zip(GRADES, recalls, strict=True)},
        confusion_matrix=matrix,
    )


def _per_grade_scores(matrix: list[list[int]]) -> tuple[list[float], list[float]]:
    recalls: list[float] = []
    f1_scores: list[float] = []
    for grade in GRADES:
        true_positive = matrix[grade][grade]
        actual_count = sum(matrix[grade])
        predicted_count = sum(row[grade] for row in matrix)
        recalls.append(true_positive / actual_count if actual_count else 0.0)
        denominator = actual_count + predicted_count
        f1_scores.append(2 * true_positive / denominator if denominator else 0.0)
    return recalls, f1_scores


def _quadratic_kappa(matrix: list[list[int]], sample_count: int) -> float:
    actual = [sum(row) for row in matrix]
    predicted = [sum(row[grade] for row in matrix) for grade in GRADES]
    observed_weighted = 0.0
    expected_weighted = 0.0
    maximum_distance = float((GRADE_COUNT - 1) ** 2)
    for actual_grade in GRADES:
        for predicted_grade in GRADES:
            weight = ((actual_grade - predicted_grade) ** 2) / maximum_distance
            observed_weighted += weight * matrix[actual_grade][predicted_grade]
            expected = actual[actual_grade] * predicted[predicted_grade] / sample_count
            expected_weighted += weight * expected
    return 1.0 - observed_weighted / expected_weighted if expected_weighted else 0.0
