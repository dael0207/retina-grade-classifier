"""Build the two independent coursework submission archives."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Final
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from retina.package_assets import create_assignment1_thumbnails
from retina.package_entries import (
    assignment1_entries,
    assignment1_example_names,
    assignment2_entries,
)
from retina.package_environment import PackageMetadata, environment_snapshot
from retina.package_types import (
    ArchiveEntry,
    DuplicateArchivePathError,
    ManifestDocument,
    ManifestFile,
    MissingInputsError,
)

ROOT: Final = Path(__file__).resolve().parents[1]
DRIVE_URL: Final = "https://drive.google.com/file/d/1bqh0eEzBGFOit9_BJ7bwuoSG25LZXVHg/view"
FIXED_ZIP_TIME: Final = (2026, 11, 13, 0, 0, 0)


def _zip_info(path: str) -> ZipInfo:
    info = ZipInfo(path, FIXED_ZIP_TIME)
    info.compress_type = ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def _validate_entries(entries: tuple[ArchiveEntry, ...]) -> None:
    missing = tuple(entry.source for entry in entries if not entry.source.is_file())
    if missing:
        raise MissingInputsError(paths=missing)
    destinations: set[str] = set()
    for entry in entries:
        portable = PurePosixPath(entry.destination).as_posix()
        if portable in destinations:
            raise DuplicateArchivePathError(path=portable)
        destinations.add(portable)


def write_archive(
    destination: Path,
    entries: tuple[ArchiveEntry, ...],
    package_metadata: PackageMetadata,
) -> None:
    """Write a deterministic archive only after every required input exists."""
    _validate_entries(entries)
    payloads: list[tuple[str, bytes]] = []
    manifest_files: list[ManifestFile] = []
    for entry in sorted(entries, key=lambda item: item.destination):
        portable = PurePosixPath(entry.destination).as_posix()
        payload = entry.source.read_bytes()
        payloads.append((portable, payload))
        manifest_files.append(
            {"path": portable, "size": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
        )
    manifest: ManifestDocument = {
        "format_version": 1,
        "metadata": package_metadata,
        "files": manifest_files,
    }
    manifest_payload = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode(
        "utf-8"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp.zip")
    temporary.unlink(missing_ok=True)
    with ZipFile(temporary, "w") as archive:
        for path, payload in payloads:
            archive.writestr(_zip_info(path), payload)
        archive.writestr(_zip_info("PACKAGE_MANIFEST.json"), manifest_payload)
    _ = temporary.replace(destination)


def build_submissions(root: Path = ROOT) -> tuple[Path, Path]:
    """Preflight both assignments, then write the independent final ZIPs."""
    assignment1 = assignment1_entries(root)
    assignment2 = assignment2_entries(root)
    thumbnail_root = root / "outputs/assignment1/images"
    missing = tuple(
        dict.fromkeys(
            entry.source
            for entry in (*assignment1, *assignment2)
            if not entry.source.is_file() and entry.source.parent != thumbnail_root
        )
    )
    if missing:
        raise MissingInputsError(paths=missing)
    create_assignment1_thumbnails(root, assignment1_example_names(root))
    _validate_entries(assignment1)
    _validate_entries(assignment2)
    snapshot = environment_snapshot()
    output = root / "output/submissions"
    first = output / "assignment1.zip"
    second = output / "assignment2.zip"
    write_archive(
        first,
        assignment1,
        {
            "assignment": 1,
            "purpose": "bilateral analysis",
            "source_url": DRIVE_URL,
            "environment": snapshot,
        },
    )
    write_archive(
        second,
        assignment2,
        {
            "assignment": 2,
            "purpose": "AI classification app",
            "source_url": DRIVE_URL,
            "environment": snapshot,
        },
    )
    return first, second


def main() -> int:
    """Build both archives or print one concise preflight failure."""
    try:
        archives = build_submissions()
    except MissingInputsError as error:
        _ = sys.stderr.write(f"{error}\n")
        return 1
    for archive_path in archives:
        _ = sys.stdout.write(f"created {archive_path}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
