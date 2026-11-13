"""Installed package versions isolated from runtime package imports."""

from __future__ import annotations

import platform
from dataclasses import dataclass
from importlib.metadata import version


@dataclass(frozen=True, slots=True)
class RuntimeVersions:
    """Installed package versions relevant to model reproducibility."""

    python: str
    torch: str
    torchvision: str
    scikit_learn: str


def runtime_versions() -> RuntimeVersions:
    """Read installed machine-learning package versions."""
    return RuntimeVersions(
        python=platform.python_version(),
        torch=version("torch"),
        torchvision=version("torchvision"),
        scikit_learn=version("scikit-learn"),
    )
