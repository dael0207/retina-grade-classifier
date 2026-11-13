"""Grid occlusion visualization for model-output sensitivity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from PIL import Image, ImageDraw

from retina.imaging import prepare_image

FloatVector = tuple[float, ...]
FloatMatrix = tuple[FloatVector, ...]
MIN_GRID = 2
MAX_GRID = 8


class PredictionBatch(Protocol):
    """Prediction values required by sensitivity analysis."""

    @property
    def grades(self) -> tuple[int, ...]:
        """Return predicted grades."""
        ...

    @property
    def scores(self) -> FloatMatrix:
        """Return score rows aligned to five grades."""
        ...


class Classifier(Protocol):
    """Classifier capability required by sensitivity analysis."""

    def predict(self, features: FloatMatrix) -> PredictionBatch:
        """Predict grades and scores from embeddings."""
        ...


class PreparedEmbedder(Protocol):
    """Prepared-image embedding capability required by sensitivity analysis."""

    def embed_prepared_images(self, images: list[Image.Image]) -> FloatMatrix:
        """Extract embeddings from prepared images."""
        ...


@dataclass(frozen=True, slots=True)
class ScoreGrid:
    """Immutable score-change grid with NumPy-compatible shape access."""

    values: FloatMatrix

    @property
    def shape(self) -> tuple[int, int]:
        """Return row and column counts."""
        return (len(self.values), len(self.values[0]) if self.values else 0)


@dataclass(frozen=True, slots=True)
class SensitivityResult:
    """Occlusion score changes and overlay for the model's predicted grade."""

    grade: int
    baseline_score: float
    score_changes: ScoreGrid
    overlay: Image.Image


def build_occlusion_sensitivity(
    image: Image.Image,
    classifier: Classifier,
    embedder: PreparedEmbedder,
    *,
    grid_size: int = 4,
) -> SensitivityResult:
    """Mask each cell and compare the predicted-grade score with the baseline."""
    if grid_size < MIN_GRID or grid_size > MAX_GRID:
        msg = "grid_size must be between 2 and 8"
        raise ValueError(msg)
    prepared = prepare_image(image)
    cell_width = prepared.width // grid_size
    cell_height = prepared.height // grid_size
    occluded = _occluded_variants(prepared, grid_size, cell_width, cell_height)
    prediction = classifier.predict(embedder.embed_prepared_images([prepared, *occluded]))
    grade = prediction.grades[0]
    baseline = prediction.scores[0][grade]
    flat_changes = tuple(baseline - row[grade] for row in prediction.scores[1:])
    rows = tuple(
        flat_changes[start : start + grid_size] for start in range(0, len(flat_changes), grid_size)
    )
    grid = ScoreGrid(rows)
    return SensitivityResult(
        grade=grade,
        baseline_score=baseline,
        score_changes=grid,
        overlay=_render_overlay(prepared, grid, cell_width, cell_height),
    )


def _occluded_variants(
    prepared: Image.Image,
    grid_size: int,
    cell_width: int,
    cell_height: int,
) -> list[Image.Image]:
    images: list[Image.Image] = []
    for row in range(grid_size):
        for column in range(grid_size):
            variant = prepared.copy()
            draw = ImageDraw.Draw(variant)
            draw.rectangle(
                (
                    column * cell_width,
                    row * cell_height,
                    (column + 1) * cell_width,
                    (row + 1) * cell_height,
                ),
                fill="black",
            )
            images.append(variant)
    return images


def _render_overlay(
    prepared: Image.Image,
    grid: ScoreGrid,
    cell_width: int,
    cell_height: int,
) -> Image.Image:
    maximum = max((abs(value) for row in grid.values for value in row), default=0.0)
    overlay = prepared.convert("RGBA")
    colors = Image.new("RGBA", prepared.size, color=(0, 0, 0, 0))
    color_draw = ImageDraw.Draw(colors)
    if maximum > 0:
        for row, values in enumerate(grid.values):
            for column, change in enumerate(values):
                strength = int(150 * abs(change) / maximum)
                color = (220, 50, 47, strength) if change >= 0 else (38, 139, 210, strength)
                color_draw.rectangle(
                    (
                        column * cell_width,
                        row * cell_height,
                        (column + 1) * cell_width,
                        (row + 1) * cell_height,
                    ),
                    fill=color,
                )
    return Image.alpha_composite(overlay, colors).convert("RGB")
