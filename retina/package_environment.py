"""Capture the actual runtime used to create submission archives."""

import platform
import sys
from importlib import metadata
from typing import Final, TypedDict

PACKAGES: Final = (
    "numpy",
    "scikit-learn",
    "torch",
    "torchvision",
    "matplotlib",
    "Pillow",
    "pydantic",
    "fastapi",
    "uvicorn",
    "reportlab",
)


class EnvironmentDocument(TypedDict):
    """Actual interpreter and dependency versions used during packaging."""

    python: str
    platform: str
    packages: dict[str, str]


class PackageMetadata(TypedDict, total=False):
    """Stable top-level package description embedded in the manifest."""

    purpose: str
    assignment: int
    source_url: str
    environment: EnvironmentDocument


def environment_snapshot() -> EnvironmentDocument:
    """Read installed versions without claiming cross-platform lock portability."""
    versions: dict[str, str] = {}
    for package in PACKAGES:
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = "not-installed"
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "packages": versions,
    }
