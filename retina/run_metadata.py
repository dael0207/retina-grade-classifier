"""Typed, event-driven metadata for reproducible training runs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, ClassVar, Literal, Protocol, final

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path

Split = Literal["train", "validation", "test"]
RunStatus = Literal["running", "complete"]
DetailValue = str | int | float
SPLITS: tuple[Split, ...] = ("train", "validation", "test")
GRADES: tuple[int, ...] = (0, 1, 2, 3, 4)


class ManifestRecord(Protocol):
    """Minimum manifest fields needed to describe a cohort."""

    @property
    def image(self) -> str:
        """Return the image identifier."""
        ...

    @property
    def level(self) -> int:
        """Return the five-grade label."""
        ...

    @property
    def patient_id(self) -> str:
        """Return the patient identifier."""
        ...

    @property
    def split(self) -> Split:
        """Return the assigned split."""
        ...


@dataclass(frozen=True, slots=True)
class SplitRecord:
    """Concrete manifest record used by metadata tests and callers."""

    image: str
    level: int
    patient_id: str
    split: Split


@dataclass(frozen=True, slots=True)
class PackageVersions:
    """Runtime versions that materially affect reproducibility."""

    python: str
    torch: str
    torchvision: str
    scikit_learn: str


@dataclass(frozen=True, slots=True)
class RunDefinition:
    """Inputs and execution settings fixed before training begins."""

    command: tuple[str, ...]
    manifest: Path
    image_dir: Path
    output_dir: Path
    batch_size: int
    seed: int
    device: str


def utc_now() -> datetime:
    """Return an aware UTC timestamp for production event recording."""
    return datetime.now(UTC)


class FrozenDocument(BaseModel):
    """Immutable JSON document boundary."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)


class VersionDocument(FrozenDocument):
    """Serializable package versions."""

    python: str
    torch: str
    torchvision: str
    scikit_learn: str


class RunConfigDocument(FrozenDocument):
    """Training configuration with legacy-compatible flat provenance fields."""

    status: RunStatus
    command: str
    started_at: str
    finished_at: str | None
    started_at_local: str
    finished_at_local: str | None
    manifest: str
    manifest_sha256: str
    image_dir: str
    output_dir: str
    batch_size: int
    seed: int
    random_seed: int
    final_test_evaluations: int
    device: str
    selected_model: str | None
    python: str
    torch: str
    torchvision: str
    scikit_learn: str
    versions: VersionDocument
    split_image_counts: dict[Split, int]
    grade_supports: dict[Split, dict[str, int]]


class ReproducibilityDocument(FrozenDocument):
    """Hashes and cohort counts emitted after successful training."""

    manifest_sha256: str
    integrity_sha256: str | None
    split_image_counts: dict[Split, int]
    split_patient_counts: dict[Split, int]
    grade_supports: dict[Split, dict[str, int]]
    artifact_sha256: dict[str, str]
    versions: VersionDocument


@final
class RunRecorder:
    """Mutable event recorder whose purpose is to persist a live training run."""

    def __init__(
        self,
        definition: RunDefinition,
        versions: PackageVersions,
        rows: Sequence[ManifestRecord],
        clock: Callable[[], datetime],
    ) -> None:
        """Aggregate cohort counts and establish the start timestamp."""
        self._definition = definition
        self._versions = versions
        self._clock = clock
        self._started_at = clock()
        self._split_counts: dict[Split, int] = dict.fromkeys(SPLITS, 0)
        self._patient_counts: dict[Split, set[str]] = {split: set() for split in SPLITS}
        self._grade_supports: dict[Split, dict[str, int]] = {
            split: {str(grade): 0 for grade in GRADES} for split in SPLITS
        }
        for row in rows:
            self._split_counts[row.split] += 1
            _ = self._patient_counts[row.split].add(row.patient_id)
            self._grade_supports[row.split][str(row.level)] += 1

    @classmethod
    def start(
        cls,
        definition: RunDefinition,
        versions: PackageVersions,
        rows: Sequence[ManifestRecord],
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> RunRecorder:
        """Create output files and record the actual run start event."""
        definition.output_dir.mkdir(parents=True, exist_ok=True)
        recorder = cls(definition, versions, rows, clock)
        log_path = definition.output_dir / "training.log"
        _ = log_path.write_text("", encoding="utf-8")
        recorder._write_config(status="running", finished_at=None, selected_model=None)
        recorder.event("run_started")
        return recorder

    def event(self, name: str, **details: DetailValue) -> None:
        """Append one timestamped event immediately so failures retain evidence."""
        document = {"timestamp": self._clock().isoformat(), "event": name, "details": details}
        with (self._definition.output_dir / "training.log").open(
            "a", encoding="utf-8", newline=""
        ) as stream:
            _ = stream.write(json.dumps(document, ensure_ascii=False) + "\n")

    def complete(self, *, selected_model: str, artifacts: tuple[Path, ...]) -> None:
        """Record completion and write hashes only after artifacts exist."""
        finished_at = self._clock()
        self.event("run_completed", selected_model=selected_model)
        self._write_config(
            status="complete", finished_at=finished_at, selected_model=selected_model
        )
        artifact_hashes = {path.name: _sha256(path) for path in artifacts}
        integrity_path = self._definition.manifest.with_name("integrity.json")
        metadata = ReproducibilityDocument(
            manifest_sha256=_sha256(self._definition.manifest),
            integrity_sha256=_sha256(integrity_path) if integrity_path.is_file() else None,
            split_image_counts=self._split_counts,
            split_patient_counts={
                split: len(patients) for split, patients in self._patient_counts.items()
            },
            grade_supports=self._grade_supports,
            artifact_sha256=artifact_hashes,
            versions=_versions_document(self._versions),
        )
        _write_json(self._definition.output_dir / "reproducibility.json", metadata)

    def _write_config(
        self,
        *,
        status: RunStatus,
        finished_at: datetime | None,
        selected_model: str | None,
    ) -> None:
        started_at = self._started_at.isoformat()
        finished = finished_at.isoformat() if finished_at is not None else None
        versions = _versions_document(self._versions)
        document = RunConfigDocument(
            status=status,
            command=" ".join(self._definition.command),
            started_at=started_at,
            finished_at=finished,
            started_at_local=started_at,
            finished_at_local=finished,
            manifest=str(self._definition.manifest),
            manifest_sha256=_sha256(self._definition.manifest),
            image_dir=str(self._definition.image_dir),
            output_dir=str(self._definition.output_dir),
            batch_size=self._definition.batch_size,
            seed=self._definition.seed,
            random_seed=self._definition.seed,
            final_test_evaluations=1 if status == "complete" else 0,
            device=self._definition.device,
            selected_model=selected_model,
            python=versions.python,
            torch=versions.torch,
            torchvision=versions.torchvision,
            scikit_learn=versions.scikit_learn,
            versions=versions,
            split_image_counts=self._split_counts,
            grade_supports=self._grade_supports,
        )
        _write_json(self._definition.output_dir / "run_config.json", document)


def _versions_document(versions: PackageVersions) -> VersionDocument:
    return VersionDocument(
        python=versions.python,
        torch=versions.torch,
        torchvision=versions.torchvision,
        scikit_learn=versions.scikit_learn,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, document: FrozenDocument) -> None:
    _ = path.write_text(document.model_dump_json(indent=2), encoding="utf-8")
