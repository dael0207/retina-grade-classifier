"""Typed schemas and failures shared by submission packaging."""

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, TypedDict, override

from pydantic import BaseModel, ConfigDict, field_validator

from retina.package_environment import PackageMetadata


class ManifestFile(TypedDict):
    """Digest evidence for one archived file."""

    path: str
    size: int
    sha256: str


class ManifestDocument(TypedDict):
    """Self-verifying package manifest."""

    format_version: int
    metadata: PackageMetadata
    files: list[ManifestFile]


class ExportedExample(BaseModel):
    """Artifact names and source image referenced by one exported model example."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore")
    image: str
    input_file: str
    sensitivity_file: str

    @field_validator("image", "input_file", "sensitivity_file")
    @classmethod
    def require_local_name(cls, value: str) -> str:
        """Reject paths that could escape their declared package directories."""
        if not value or Path(value).name != value:
            message = f"expected a local artifact name, got {value!r}"
            raise ValueError(message)
        return value


@dataclass(frozen=True, slots=True)
class ArchiveEntry:
    """One local file and its portable path inside a submission ZIP."""

    source: Path
    destination: str


@dataclass(frozen=True, slots=True)
class MissingInputsError(Exception):
    """Raised when final artifacts are not ready for packaging."""

    paths: tuple[Path, ...]

    @override
    def __str__(self) -> str:
        """List every missing required input in one actionable message."""
        return "missing package inputs:\n" + "\n".join(f"- {path}" for path in self.paths)


@dataclass(frozen=True, slots=True)
class DuplicateArchivePathError(Exception):
    """Raised when two sources would overwrite one archived path."""

    path: str

    @override
    def __str__(self) -> str:
        """Identify the conflicting portable path."""
        return f"duplicate archive destination: {self.path}"
