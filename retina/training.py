"""Patient-isolated feature extraction, model selection, and held-out evaluation."""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import typer

from model_runtime.classifier import fit_logistic
from model_runtime.versions import runtime_versions
from retina.evaluation import classification_metrics
from retina.model import FloatMatrix, IntVector, LinearClassifier, MobileNetEmbedder
from retina.run_metadata import PackageVersions, RunDefinition, RunRecorder
from retina.training_outputs import CandidateResult, OutputBundle, write_outputs

Split = Literal["train", "validation", "test"]
SEED = 20261113


@dataclass(frozen=True, slots=True)
class ManifestRow:
    """One validated image entry in a patient-level data split."""

    image: str
    level: int
    patient_id: str
    split: Split


@dataclass(frozen=True, slots=True)
class CandidateData:
    """Training and validation values shared by model candidates."""

    train_features: FloatMatrix
    train_labels: IntVector
    validation_features: FloatMatrix
    validation_labels: IntVector


def read_manifest(source: Path) -> list[ManifestRow]:
    """Read the strict manifest schema and reject invalid rows or duplicates."""
    rows: list[ManifestRow] = []
    with source.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if set(reader.fieldnames or ()) != {"image", "level", "patient_id", "split"}:
            msg = "manifest columns must be image,level,patient_id,split"
            raise ValueError(msg)
        for raw in reader:
            level = int(raw["level"])
            if level not in range(5):
                msg = f"invalid grade: {level}"
                raise ValueError(msg)
            rows.append(
                ManifestRow(raw["image"], level, raw["patient_id"], _parse_split(raw["split"]))
            )
    validate_patient_splits(rows)
    if len({row.image for row in rows}) != len(rows):
        msg = "manifest contains duplicate image names"
        raise ValueError(msg)
    return rows


def _parse_split(raw: str) -> Split:
    if raw == "train":
        return "train"
    if raw == "validation":
        return "validation"
    if raw == "test":
        return "test"
    msg = f"invalid split: {raw}"
    raise ValueError(msg)


def validate_patient_splits(rows: list[ManifestRow]) -> None:
    """Reject any patient whose images occur in more than one split."""
    patient_splits: dict[str, set[Split]] = {}
    for row in rows:
        patient_splits.setdefault(row.patient_id, set()).add(row.split)
    leaked = sorted(patient for patient, splits in patient_splits.items() if len(splits) > 1)
    if leaked:
        msg = f"patient split leakage: {', '.join(leaked[:5])}"
        raise ValueError(msg)


def _rows_for_split(rows: list[ManifestRow], split: Split) -> list[ManifestRow]:
    selected = [row for row in rows if row.split == split]
    if not selected:
        msg = f"manifest has no rows for {split}"
        raise ValueError(msg)
    return selected


def _fit_candidate(name: str, data: CandidateData, *, balanced: bool) -> CandidateResult:
    fitted = fit_logistic(data.train_features, data.train_labels, balanced=balanced, seed=SEED)
    if fitted.classes != tuple(range(5)):
        msg = "training subset must contain all five grades"
        raise ValueError(msg)
    classifier = LinearClassifier(
        fitted.coefficients,
        fitted.intercepts,
        fitted.classes,
        fitted.feature_mean,
        fitted.feature_scale,
    )
    predictions = classifier.predict(data.validation_features).grades
    return CandidateResult(
        name=name,
        metrics=classification_metrics(data.validation_labels, predictions),
        classifier=classifier,
    )


def _extract_split(
    embedder: MobileNetEmbedder,
    rows: list[ManifestRow],
    image_dir: Path,
    *,
    batch_size: int,
) -> tuple[FloatMatrix, IntVector]:
    paths = [image_dir / f"{row.image}.jpg" for row in rows]
    missing = [path for path in paths if not path.is_file()]
    if missing:
        msg = f"missing image: {missing[0]}"
        raise FileNotFoundError(msg)
    return embedder.embed_paths(paths, batch_size=batch_size), tuple(row.level for row in rows)


def train(
    manifest: str = "data/manifest.csv",
    image_dir: str = "data/images",
    output_dir: str = "outputs/assignment2",
    batch_size: int = 16,
) -> None:
    """Train, select on validation, then evaluate the selected model once on test."""
    manifest_path = Path(manifest)
    image_directory = Path(image_dir)
    output_directory = Path(output_dir)
    rows = read_manifest(manifest_path)
    versions = runtime_versions()
    recorder = RunRecorder.start(
        RunDefinition(
            command=(sys.executable, *sys.argv),
            manifest=manifest_path,
            image_dir=image_directory,
            output_dir=output_directory,
            batch_size=batch_size,
            seed=SEED,
            device="cpu",
        ),
        PackageVersions(
            versions.python,
            versions.torch,
            versions.torchvision,
            versions.scikit_learn,
        ),
        rows,
    )
    MobileNetEmbedder.configure_threads(6)
    split_rows = {split: _rows_for_split(rows, split) for split in ("train", "validation", "test")}
    embedder = MobileNetEmbedder(device="cpu")
    provenance = embedder.save_backbone(output_directory / "backbone.pth")
    _ = (output_directory / "backbone_provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    recorder.event("backbone_saved", sha256=provenance["sha256"])
    features: dict[str, FloatMatrix] = {}
    labels: dict[str, IntVector] = {}
    for split in ("train", "validation", "test"):
        recorder.event("embedding_started", split=split, images=len(split_rows[split]))
        features[split], labels[split] = _extract_split(
            embedder, split_rows[split], image_directory, batch_size=batch_size
        )
        recorder.event("embedding_completed", split=split, images=len(split_rows[split]))
    candidate_data = CandidateData(
        features["train"], labels["train"], features["validation"], labels["validation"]
    )
    candidates = [
        _fit_candidate("unweighted", candidate_data, balanced=False),
        _fit_candidate("balanced", candidate_data, balanced=True),
    ]
    selected = max(candidates, key=lambda item: (item.metrics.qwk, item.metrics.macro_f1))
    recorder.event("model_selected", model=selected.name)
    test_prediction = selected.classifier.predict(features["test"])
    test_metrics = classification_metrics(labels["test"], test_prediction.grades)
    majority_grade = Counter(labels["train"]).most_common(1)[0][0]
    majority_metrics = classification_metrics(
        labels["test"], tuple(majority_grade for _ in labels["test"])
    )
    recorder.event("test_evaluated", images=len(labels["test"]), qwk=test_metrics.qwk)
    artifacts = write_outputs(
        OutputBundle(
            output_directory,
            split_rows,
            features,
            tuple(candidates),
            selected,
            test_prediction,
            test_metrics,
            majority_metrics,
        )
    )
    recorder.complete(selected_model=selected.name, artifacts=artifacts)


if __name__ == "__main__":
    _ = typer.run(train)
