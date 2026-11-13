from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from retina.run_metadata import (
    PackageVersions,
    RunDefinition,
    RunRecorder,
    SplitRecord,
)

if TYPE_CHECKING:
    from pathlib import Path


class FixedClock:
    def __init__(self) -> None:
        self._next = datetime(2026, 11, 13, 8, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        current = self._next
        self._next += timedelta(seconds=1)
        return current


def test_run_recorder_emits_actual_events_counts_supports_hashes_and_versions(
    tmp_path: Path,
) -> None:
    # Given
    manifest = tmp_path / "manifest.csv"
    manifest.write_text("image,level,patient_id,split\na,0,p1,train\n", encoding="utf-8")
    artifact = tmp_path / "model.npz"
    artifact.write_bytes(b"model-v1")
    definition = RunDefinition(
        command=("python", "-m", "retina.training"),
        manifest=manifest,
        image_dir=tmp_path / "images",
        output_dir=tmp_path,
        batch_size=16,
        seed=20261113,
        device="cpu",
    )
    versions = PackageVersions("3.12.0", "2.12.1+cpu", "0.27.1+cpu", "1.8.0")
    rows = [
        SplitRecord("a", 0, "p1", "train"),
        SplitRecord("b", 4, "p2", "test"),
    ]
    recorder = RunRecorder.start(definition, versions, rows, clock=FixedClock())

    # When
    recorder.event("embeddings_complete", split="train", images=1)
    recorder.complete(selected_model="balanced", artifacts=(artifact,))

    # Then
    config = json.loads((tmp_path / "run_config.json").read_text(encoding="utf-8"))
    metadata = json.loads((tmp_path / "reproducibility.json").read_text(encoding="utf-8"))
    log = (tmp_path / "training.log").read_text(encoding="utf-8")
    assert config["status"] == "complete"
    assert config["versions"]["torch"] == "2.12.1+cpu"
    assert config["torch"] == "2.12.1+cpu"
    assert config["python"] == "3.12.0"
    assert config["random_seed"] == 20261113
    assert config["manifest_sha256"] == hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert config["started_at_local"] == "2026-11-13T08:00:00+00:00"
    assert config["finished_at_local"] == "2026-11-13T08:00:03+00:00"
    assert metadata["split_image_counts"] == {"test": 1, "train": 1, "validation": 0}
    assert metadata["grade_supports"]["test"] == {"0": 0, "1": 0, "2": 0, "3": 0, "4": 1}
    assert metadata["manifest_sha256"] == hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert metadata["artifact_sha256"]["model.npz"] == hashlib.sha256(b"model-v1").hexdigest()
    assert "embeddings_complete" in log
    assert "run_completed" in log
