"""Scikit-learn fitting isolated behind immutable Python values."""

from __future__ import annotations

from array import array
from dataclasses import dataclass
from typing import Protocol, Self

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler


class _Standardizer(Protocol):
    """Narrow ndarray contract used from scikit-learn's standard scaler."""

    mean_: np.ndarray[tuple[int], np.dtype[np.float64]] | None
    scale_: np.ndarray[tuple[int], np.dtype[np.float64]] | None

    def fit(self, X: np.ndarray[tuple[int, int], np.dtype[np.float32]]) -> Self: ...  # noqa: N803

    def transform(
        self,
        X: np.ndarray[tuple[int, int], np.dtype[np.float32]],  # noqa: N803
    ) -> np.ndarray[tuple[int, int], np.dtype[np.float32]]: ...


class _LogisticHead(Protocol):
    """Narrow ndarray contract used from scikit-learn's logistic head."""

    coef_: np.ndarray[tuple[int, int], np.dtype[np.float64]]
    intercept_: np.ndarray[tuple[int], np.dtype[np.float64]]
    classes_: np.ndarray[tuple[int], np.dtype[np.int64]]

    def fit(
        self,
        X: np.ndarray[tuple[int, int], np.dtype[np.float32]],  # noqa: N803
        y: np.ndarray[tuple[int], np.dtype[np.int64]],
    ) -> Self: ...


def _standardizer() -> _Standardizer:
    """Create the scaler behind the ndarray-only contract used here."""
    return StandardScaler()


def _logistic_head(*, balanced: bool, seed: int) -> _LogisticHead:
    """Create the linear head behind the ndarray-only contract used here."""
    return LogisticRegression(
        class_weight="balanced" if balanced else None,
        max_iter=1_000,
        random_state=seed,
        solver="lbfgs",
    )


@dataclass(frozen=True, slots=True)
class FitResult:
    """Fitted linear head and standardization statistics."""

    coefficients: tuple[tuple[float, ...], ...]
    intercepts: tuple[float, ...]
    classes: tuple[int, ...]
    feature_mean: tuple[float, ...]
    feature_scale: tuple[float, ...]


def fit_logistic(
    features: tuple[tuple[float, ...], ...],
    labels: tuple[int, ...],
    *,
    balanced: bool,
    seed: int,
) -> FitResult:
    """Fit a standardized multinomial logistic-regression candidate."""
    matrix = np.asarray(features, dtype=np.float32)
    target = np.asarray(labels, dtype=np.int64)
    scaler = _standardizer()
    _ = scaler.fit(matrix)
    model = _logistic_head(balanced=balanced, seed=seed)
    _ = model.fit(scaler.transform(matrix), target)
    if scaler.mean_ is None or scaler.scale_ is None:
        msg = "standard scaler did not produce fitted statistics"
        raise RuntimeError(msg)
    coefficients: np.ndarray[tuple[int, int], np.dtype[np.float64]] = model.coef_
    intercepts: np.ndarray[tuple[int], np.dtype[np.float64]] = model.intercept_
    classes: np.ndarray[tuple[int], np.dtype[np.int64]] = model.classes_
    feature_mean: np.ndarray[tuple[int], np.dtype[np.float64]] = np.asarray(
        scaler.mean_, dtype=np.float64
    )
    feature_scale: np.ndarray[tuple[int], np.dtype[np.float64]] = np.asarray(
        scaler.scale_, dtype=np.float64
    )
    coefficient_values = array("d")
    coefficient_values.frombytes(coefficients.tobytes())
    intercept_values = array("d")
    intercept_values.frombytes(intercepts.tobytes())
    class_values = array("q")
    class_values.frombytes(classes.tobytes())
    mean_values = array("d")
    mean_values.frombytes(feature_mean.tobytes())
    scale_values = array("d")
    scale_values.frombytes(feature_scale.tobytes())
    columns = coefficients.shape[1]
    return FitResult(
        coefficients=tuple(
            tuple(coefficient_values[row * columns + column] for column in range(columns))
            for row in range(coefficients.shape[0])
        ),
        intercepts=tuple(intercept_values),
        classes=tuple(class_values),
        feature_mean=tuple(mean_values),
        feature_scale=tuple(scale_values),
    )
