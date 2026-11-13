"""NumPy-backed artifact I/O isolated from the typed domain package."""

from __future__ import annotations

from array import array
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

import numpy as np
from numpy.lib.npyio import NpzFile

if TYPE_CHECKING:
    from pathlib import Path

VECTOR_DIMENSIONS: Final = 1
MATRIX_DIMENSIONS: Final = 2


@dataclass(frozen=True, slots=True)
class ArtifactData:
    """Inert classifier values stored in the NPZ artifact."""

    format_version: int
    extractor: str
    coefficients: tuple[tuple[float, ...], ...]
    intercepts: tuple[float, ...]
    classes: tuple[int, ...]
    feature_mean: tuple[float, ...]
    feature_scale: tuple[float, ...]


def save_artifact(path: Path, data: ArtifactData) -> None:
    """Write classifier values as compressed non-executable arrays."""
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        format_version=np.array([data.format_version], dtype=np.int64),
        extractor=np.array([data.extractor]),
        coefficients=np.asarray(data.coefficients, dtype=np.float32),
        intercepts=np.asarray(data.intercepts, dtype=np.float32),
        classes=np.asarray(data.classes, dtype=np.int64),
        feature_mean=np.asarray(data.feature_mean, dtype=np.float32),
        feature_scale=np.asarray(data.feature_scale, dtype=np.float32),
    )


def load_artifact(path: Path) -> ArtifactData:
    """Load classifier values from a non-pickle NPZ archive."""
    with path.open("rb") as stream, NpzFile(stream, allow_pickle=False) as archive:
        coefficients: np.ndarray[tuple[int, ...], np.dtype[np.generic]] = archive["coefficients"]
        intercepts: np.ndarray[tuple[int, ...], np.dtype[np.generic]] = archive["intercepts"]
        classes: np.ndarray[tuple[int, ...], np.dtype[np.generic]] = archive["classes"]
        feature_mean: np.ndarray[tuple[int, ...], np.dtype[np.generic]] = archive["feature_mean"]
        feature_scale: np.ndarray[tuple[int, ...], np.dtype[np.generic]] = archive["feature_scale"]
        shapes_are_valid = (
            coefficients.ndim == MATRIX_DIMENSIONS
            and intercepts.ndim == VECTOR_DIMENSIONS
            and classes.ndim == VECTOR_DIMENSIONS
            and feature_mean.ndim == VECTOR_DIMENSIONS
            and feature_scale.ndim == VECTOR_DIMENSIONS
        )
        if not shapes_are_valid:
            msg = "model artifact has incompatible array shapes"
            raise ValueError(msg)
        dtypes_are_valid = (
            coefficients.dtype == np.dtype(np.float32)
            and intercepts.dtype == np.dtype(np.float32)
            and classes.dtype == np.dtype(np.int64)
            and feature_mean.dtype == np.dtype(np.float32)
            and feature_scale.dtype == np.dtype(np.float32)
        )
        if not dtypes_are_valid:
            msg = "model artifact has incompatible array dtypes"
            raise ValueError(msg)
        version_values = array("q")
        version_values.frombytes(archive["format_version"].tobytes())
        extractor = archive["extractor"].tobytes().decode("utf-32-le").rstrip("\0")
        coefficient_values = array("f")
        coefficient_values.frombytes(coefficients.tobytes())
        intercept_values = array("f")
        intercept_values.frombytes(intercepts.tobytes())
        class_values = array("q")
        class_values.frombytes(classes.tobytes())
        mean_values = array("f")
        mean_values.frombytes(feature_mean.tobytes())
        scale_values = array("f")
        scale_values.frombytes(feature_scale.tobytes())
        columns = coefficients.shape[1]
        return ArtifactData(
            format_version=version_values[0],
            extractor=extractor,
            coefficients=tuple(
                tuple(coefficient_values[row * columns + column] for column in range(columns))
                for row in range(coefficients.shape[0])
            ),
            intercepts=tuple(intercept_values),
            classes=tuple(class_values),
            feature_mean=tuple(mean_values),
            feature_scale=tuple(scale_values),
        )
