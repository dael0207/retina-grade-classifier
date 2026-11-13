"""Read-only, artifact-backed evidence and download routes."""

from __future__ import annotations

import csv
import hashlib
from typing import TYPE_CHECKING, ClassVar, Final, Literal

from fastapi import HTTPException, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter

if TYPE_CHECKING:
    from pathlib import Path

    from fastapi import FastAPI

SPLITS: Final = ("train", "validation", "test")
JSON_VALUE: Final = TypeAdapter[JsonValue](JsonValue)
DOWNLOADS: Final = {
    "assignment1-report": "output/pdf/assignment1_bilateral_analysis.pdf",
    "assignment2-report": "output/pdf/assignment2_ai_classification.pdf",
    "pairs": "outputs/assignment1/pairs.csv",
    "metrics": "outputs/assignment2/metrics.json",
    "manifest": "data/manifest.csv",
    "run-config": "outputs/assignment2/run_config.json",
}


class EvidenceRow(BaseModel):
    """Manifest boundary checked before counting research units."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    image: str
    level: int = Field(ge=0, le=4)
    patient_id: str
    split: Literal["train", "validation", "test"]


class SplitEvidence(BaseModel):
    """Image, patient, and grade counts for one split."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    split: str
    patients: int
    images: int
    class_counts: list[int]


class Provenance(BaseModel):
    """Recorded run evidence alongside counts recomputed from its manifest."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    run: JsonValue
    integrity: JsonValue
    splits: list[SplitEvidence]
    manifest_sha256: str


def _required(path: Path) -> Path:
    if not path.is_file():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="요청한 근거 파일이 아직 생성되지 않았습니다.",
        )
    return path


def load_provenance(root: Path) -> Provenance:
    """Compute cohort counts without inferring patients from eye totals."""
    manifest = _required(root / "data/manifest.csv")
    with manifest.open(encoding="utf-8-sig", newline="") as stream:
        rows = [EvidenceRow.model_validate(row) for row in csv.DictReader(stream)]
    splits: list[SplitEvidence] = []
    for split in SPLITS:
        selected = [row for row in rows if row.split == split]
        splits.append(
            SplitEvidence(
                split=split,
                patients=len({row.patient_id for row in selected}),
                images=len(selected),
                class_counts=[sum(row.level == grade for row in selected) for grade in range(5)],
            ),
        )
    return Provenance(
        run=JSON_VALUE.validate_json(
            _required(root / "outputs/assignment2/run_config.json").read_bytes(),
        ),
        integrity=JSON_VALUE.validate_json(_required(root / "data/integrity.json").read_bytes()),
        splits=splits,
        manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
    )


def add_evidence_routes(app: FastAPI, root: Path) -> None:
    """Attach bounded artifact routes to the local application."""
    examples = root / "outputs/assignment2/examples"
    app.mount("/model-examples", StaticFiles(directory=examples, check_dir=False))

    def get_provenance() -> Provenance:
        return load_provenance(root)

    def get_model_examples() -> FileResponse:
        return FileResponse(_required(examples / "examples.json"), media_type="application/json")

    def download(artifact: str) -> FileResponse:
        relative = DOWNLOADS.get(artifact)
        if relative is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="알 수 없는 결과 파일입니다.")
        path = _required(root / relative)
        return FileResponse(path, filename=path.name)

    app.add_api_route("/api/provenance", get_provenance, methods=["GET"])
    app.add_api_route("/api/model-examples", get_model_examples, methods=["GET"])
    app.add_api_route("/download/{artifact}", download, methods=["GET"])
