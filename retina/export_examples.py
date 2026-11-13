"""Export deterministic held-out prediction and occlusion-sensitivity examples."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypedDict

import typer
from PIL import Image

from retina.imaging import prepare_image
from retina.model import occlusion_sensitivity


class ExampleRecord(TypedDict):
    """Metadata for one exported held-out example."""

    kind: str
    image: str
    actual: int
    predicted: int
    input_file: str
    sensitivity_file: str
    sensitivity_note: str


@dataclass(frozen=True, slots=True)
class PredictionRow:
    """Prediction fields needed to select and export examples."""

    image: str
    actual: int
    predicted: int


@dataclass(frozen=True, slots=True)
class SelectedExample:
    """Deterministic available example and its correctness category."""

    kind: Literal["correct", "incorrect"]
    row: PredictionRow


def select_example_rows(rows: list[PredictionRow]) -> list[SelectedExample]:
    """Select the first available correct and incorrect rows without assuming both exist."""
    correct = next((row for row in rows if row.actual == row.predicted), None)
    incorrect = next((row for row in rows if row.actual != row.predicted), None)
    selected: list[SelectedExample] = []
    if correct is not None:
        selected.append(SelectedExample("correct", correct))
    if incorrect is not None:
        selected.append(SelectedExample("incorrect", incorrect))
    return selected


def _read_predictions(path: Path) -> list[PredictionRow]:
    with path.open(encoding="utf-8", newline="") as stream:
        source_rows = list(csv.DictReader(stream))
    return [
        PredictionRow(row["image"], int(row["actual"]), int(row["predicted"]))
        for row in source_rows
    ]


def export_examples(
    predictions: str = "outputs/assignment2/predictions.csv",
    image_dir: str = "data/images",
    artifact: str = "outputs/assignment2/model.npz",
    output_dir: str = "outputs/assignment2/examples",
) -> None:
    """Export the first correct and first incorrect test rows without cherry-picking."""
    selected = select_example_rows(_read_predictions(Path(predictions)))
    if not selected:
        msg = "predictions file contains no rows"
        raise ValueError(msg)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    records: list[ExampleRecord] = []
    for example in selected:
        kind = example.kind
        row = example.row
        image_name = row.image
        with Image.open(Path(image_dir) / f"{image_name}.jpg") as source:
            rgb = source.convert("RGB")
        input_name = f"{kind}_{image_name}_input.jpg"
        sensitivity_name = f"{kind}_{image_name}_sensitivity.jpg"
        prepare_image(rgb).save(destination / input_name, quality=92)
        sensitivity = occlusion_sensitivity(rgb, Path(artifact))
        sensitivity.overlay.save(destination / sensitivity_name, quality=92)
        records.append(
            {
                "kind": kind,
                "image": image_name,
                "actual": row.actual,
                "predicted": row.predicted,
                "input_file": input_name,
                "sensitivity_file": sensitivity_name,
                "sensitivity_note": (
                    "Red means masking lowered the predicted-grade score; blue means masking "
                    "raised it. This is model sensitivity, not a verified lesion location."
                ),
            }
        )
    _ = (destination / "examples.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    _ = typer.run(export_examples)
