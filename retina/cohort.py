"""Create a reproducible patient-level subset and isolated evaluation partitions."""

import csv
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Final, Protocol, TypedDict

SEED: Final = 20261113
ROOT: Final = Path(__file__).resolve().parents[1]


class ManifestRow(TypedDict):
    """One selected eye and its patient-level partition."""

    image: str
    level: int
    patient_id: str
    split: str


class TrainTestSplit(Protocol):
    """Typed boundary for scikit-learn's list-preserving split function."""

    def __call__(
        self,
        values: list[str],
        *,
        train_size: int | None = None,
        test_size: float | None = None,
        stratify: list[int],
        random_state: int,
    ) -> list[list[str]]:
        """Return train and test values while preserving list element types."""
        ...


if TYPE_CHECKING:
    train_test_split: TrainTestSplit
else:
    from sklearn.model_selection import train_test_split


def build_manifest(
    patients: int = 1000,
    labels_path: Path = ROOT / "trainLabels.csv",
    destination: Path = ROOT / "data" / "manifest.csv",
) -> list[ManifestRow]:
    """Stratify by maximum bilateral grade, then preserve both eyes in each split."""
    grouped: defaultdict[str, list[tuple[str, int]]] = defaultdict(list)
    with labels_path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            grouped[row["image"].rsplit("_", 1)[0]].append((row["image"], int(row["level"])))
    ids = sorted(grouped, key=int)
    grades = [max(level for _, level in grouped[patient]) for patient in ids]
    selected, _unused = train_test_split(
        ids,
        train_size=patients,
        stratify=grades,
        random_state=SEED,
    )
    selected_grades = [max(level for _, level in grouped[patient]) for patient in selected]
    train, held = train_test_split(
        selected,
        test_size=0.3,
        stratify=selected_grades,
        random_state=SEED,
    )
    held_grades = [max(level for _, level in grouped[patient]) for patient in held]
    validation, test = train_test_split(
        held,
        test_size=0.5,
        stratify=held_grades,
        random_state=SEED,
    )
    manifest: list[ManifestRow] = []
    for split, patient_ids in (("train", train), ("validation", validation), ("test", test)):
        for patient in sorted(patient_ids, key=int):
            for image, level in sorted(grouped[patient]):
                manifest.append(
                    ManifestRow(image=image, level=level, patient_id=patient, split=split)
                )
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=["image", "level", "patient_id", "split"])
        writer.writeheader()
        writer.writerows(manifest)
    return manifest


if __name__ == "__main__":
    _ = build_manifest()
