"""Serialization of trained model artifacts, metrics, and prediction rows."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, TypedDict

from retina.model import (
    BatchPrediction,
    FloatMatrix,
    LinearClassifier,
    save_model,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    from retina.evaluation import ClassificationMetrics


class PredictionRecord(Protocol):
    """Manifest fields serialized alongside predictions."""

    @property
    def image(self) -> str:
        """Return the image identifier."""
        ...

    @property
    def level(self) -> int:
        """Return the ground-truth grade."""
        ...

    @property
    def patient_id(self) -> str:
        """Return the patient identifier."""
        ...

    @property
    def split(self) -> str:
        """Return the split name."""
        ...


@dataclass(frozen=True, slots=True)
class CandidateResult:
    """Validation result and fitted classifier for one model candidate."""

    name: str
    metrics: ClassificationMetrics
    classifier: LinearClassifier


@dataclass(frozen=True, slots=True)
class OutputBundle:
    """Values required to serialize one completed training run."""

    output_dir: Path
    split_rows: Mapping[str, Sequence[PredictionRecord]]
    features: Mapping[str, FloatMatrix]
    candidates: tuple[CandidateResult, ...]
    selected: CandidateResult
    test_prediction: BatchPrediction
    test_metrics: ClassificationMetrics
    majority_metrics: ClassificationMetrics


class MetricsDocument(TypedDict):
    """Stable metrics.json schema consumed by reports and the web app."""

    dataset: dict[str, int]
    validation_candidates: dict[str, dict[str, float | dict[str, float] | list[list[int]]]]
    selected_model: str
    test: dict[str, float | dict[str, float] | list[list[int]]]
    majority_baseline_test: dict[str, float | dict[str, float] | list[list[int]]]


def write_outputs(bundle: OutputBundle) -> tuple[Path, ...]:
    """Write the complete classifier output set and return primary artifacts."""
    model_path = bundle.output_dir / "model.npz"
    metrics_path = bundle.output_dir / "metrics.json"
    predictions_path = bundle.output_dir / "predictions.csv"
    save_model(bundle.selected.classifier, model_path)
    document: MetricsDocument = {
        "dataset": {split: len(rows) for split, rows in bundle.split_rows.items()},
        "validation_candidates": {item.name: item.metrics.to_dict() for item in bundle.candidates},
        "selected_model": bundle.selected.name,
        "test": bundle.test_metrics.to_dict(),
        "majority_baseline_test": bundle.majority_metrics.to_dict(),
    }
    _ = metrics_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for candidate in bundle.candidates:
        prediction = candidate.classifier.predict(bundle.features["validation"])
        _write_predictions(
            bundle.output_dir / f"validation_{candidate.name}_predictions.csv",
            bundle.split_rows["validation"],
            prediction,
        )
    _write_predictions(predictions_path, bundle.split_rows["test"], bundle.test_prediction)
    return model_path, bundle.output_dir / "backbone.pth", metrics_path, predictions_path


def _write_predictions(
    destination: Path,
    rows: Sequence[PredictionRecord],
    prediction: BatchPrediction,
) -> None:
    with destination.open("w", encoding="utf-8", newline="") as stream:
        fields = [
            "image",
            "patient_id",
            "split",
            "actual",
            "predicted",
            *[f"score_{grade}" for grade in range(5)],
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for index, row in enumerate(rows):
            record: dict[str, str | int | float] = {
                "image": row.image,
                "patient_id": row.patient_id,
                "split": row.split,
                "actual": row.level,
                "predicted": prediction.grades[index],
            }
            record.update({f"score_{grade}": prediction.scores[index][grade] for grade in range(5)})
            writer.writerow(record)
