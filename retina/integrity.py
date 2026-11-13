"""Final source-image and patient-split integrity gate before model training."""

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import ClassVar, Final, TypedDict

from PIL import Image
from pydantic import BaseModel, ConfigDict

from retina.download import entries

ROOT: Final = Path(__file__).resolve().parents[1]


class AuditRecord(BaseModel):
    """Parse the download audit once at the CSV boundary."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    image: str
    sha256: str
    original_width: int
    original_height: int
    original_bytes: int
    crc_verified: bool


class IntegritySummary(TypedDict):
    """Reproducibility and leakage findings for the completed local cache."""

    requested_images: int
    verified_originals: int
    original_bytes: int
    manifest_sha256: str
    exact_duplicate_groups: list[list[str]]
    cross_split_duplicate_groups: list[list[str]]
    patient_split_overlap: int
    passed: bool


def verify_image(path: Path, record: AuditRecord) -> None:
    """Require cached bytes and dimensions to be the verified source image."""
    raw = path.read_bytes()
    if (
        not record.crc_verified
        or len(raw) != record.original_bytes
        or hashlib.sha256(raw).hexdigest() != record.sha256
    ):
        message = f"Source byte mismatch: {record.image}"
        raise ValueError(message)
    with Image.open(path) as picture:
        if picture.size != (record.original_width, record.original_height):
            message = f"Source dimension mismatch: {record.image}"
            raise ValueError(message)
        picture.verify()


def verify_cache(root: Path = ROOT) -> IntegritySummary:
    """Check every requested original and reject exact-image or patient leakage."""
    with (root / "data/image_audit.csv").open(encoding="utf-8", newline="") as source:
        records = [AuditRecord.model_validate(row) for row in csv.DictReader(source)]
    requested = {entry.image for entry in entries()}
    audited = {record.image for record in records}
    if audited != requested or len(audited) != len(records):
        message = f"Incomplete or duplicate audit: requested={len(requested)}, rows={len(records)}"
        raise ValueError(message)
    hashes: defaultdict[str, list[str]] = defaultdict(list)
    for record in records:
        verify_image(root / "data/images" / f"{record.image}.jpg", record)
        hashes[record.sha256].append(record.image)
    with (root / "data/manifest.csv").open(encoding="utf-8", newline="") as source:
        manifest = list(csv.DictReader(source))
    image_splits = {row["image"]: row["split"] for row in manifest}
    patient_splits: defaultdict[str, set[str]] = defaultdict(set)
    for row in manifest:
        patient_splits[row["patient_id"]].add(row["split"])
    overlaps = sum(len(splits) > 1 for splits in patient_splits.values())
    duplicates = [names for names in hashes.values() if len(names) > 1]
    leaking = [
        names
        for names in duplicates
        if len({image_splits[name] for name in names if name in image_splits}) > 1
    ]
    result: IntegritySummary = {
        "requested_images": len(requested),
        "verified_originals": len(records),
        "original_bytes": sum(record.original_bytes for record in records),
        "manifest_sha256": hashlib.sha256((root / "data/manifest.csv").read_bytes()).hexdigest(),
        "exact_duplicate_groups": duplicates,
        "cross_split_duplicate_groups": leaking,
        "patient_split_overlap": overlaps,
        "passed": not leaking and overlaps == 0,
    }
    destination = root / "data/integrity.json"
    _ = destination.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if not result["passed"]:
        message = "Data leakage detected; training is blocked"
        raise ValueError(message)
    return result


if __name__ == "__main__":
    _ = verify_cache()
