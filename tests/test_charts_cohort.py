from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from PIL import Image

from retina import charts
from retina.cohort import build_manifest

if TYPE_CHECKING:
    from matplotlib.figure import Figure


@dataclass(frozen=True, slots=True)
class ChartFixture:
    image_count: int = 100
    class_counts: tuple[int, ...] = (50, 20, 15, 10, 5)
    class_percentages: tuple[float, ...] = (50.0, 20.0, 15.0, 10.0, 5.0)
    cross_matrix: tuple[tuple[int, ...], ...] = (
        (20, 2, 1, 0, 0),
        (3, 8, 1, 0, 0),
        (1, 2, 6, 1, 0),
        (0, 0, 1, 4, 1),
        (0, 0, 0, 1, 3),
    )
    difference_counts: tuple[int, ...] = (41, 9, 3, 1, 0)
    discordant_count: int = 13
    discordant_percentage: float = 24.07
    exact_agreement: float = 0.7593
    affected_exact_agreement: float = 0.4211


def test_class_distribution_preserves_numeric_chart_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a summary whose counts differ for every grade.
    captured: list[Figure] = []

    def capture(figure: Figure, _path: Path) -> None:
        captured.append(figure)

    monkeypatch.setattr(charts, "_save", capture)

    # When: the class-distribution chart is rendered.
    charts._class_distribution(ChartFixture(), tmp_path / "chart.png")

    # Then: bar heights and annotations retain the input values.
    axis = captured[0].axes[0]
    assert tuple(patch.get_height() for patch in axis.patches) == (50, 20, 15, 10, 5)
    annotations = {text.get_text() for text in axis.texts}
    assert "50\n(50.0%)" in annotations
    assert "5\n(5.0%)" in annotations


def test_render_charts_writes_four_valid_pngs(tmp_path: Path) -> None:
    # Given: a complete summary and an empty output directory.
    summary = ChartFixture()

    # When: all assignment charts are rendered through the public entry point.
    charts.render_charts(summary, tmp_path)

    # Then: every expected artifact is a readable PNG with nonzero dimensions.
    expected = (
        "01_class_distribution.png",
        "02_bilateral_cross_matrix.png",
        "03_grade_difference.png",
        "04_agreement_comparison.png",
    )
    assert tuple(path.name for path in sorted(tmp_path.glob("*.png"))) == expected
    for filename in expected:
        with Image.open(tmp_path / filename) as rendered:
            assert rendered.format == "PNG"
            assert rendered.width > 0
            assert 0 < rendered.height < 2_000


def test_build_manifest_is_deterministic_in_isolated_paths(tmp_path: Path) -> None:
    # Given: fifty complete patient pairs with ten patients per grade.
    labels = tmp_path / "labels.csv"
    rows = ["image,level"]
    for patient in range(1, 51):
        grade = (patient - 1) // 10
        rows.extend((f"{patient}_left,{grade}", f"{patient}_right,{grade}"))
    _ = labels.write_text("\n".join(rows), encoding="utf-8")
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"

    # When: the same seeded cohort is written twice outside the real data directory.
    first_rows = build_manifest(40, labels_path=labels, destination=first)
    second_rows = build_manifest(40, labels_path=labels, destination=second)

    # Then: bytes, patient isolation, and 70/15/15 patient counts are deterministic.
    assert first.read_bytes() == second.read_bytes()
    assert first_rows == second_rows
    split_patients = {
        split: {row["patient_id"] for row in first_rows if row["split"] == split}
        for split in ("train", "validation", "test")
    }
    assert {split: len(ids) for split, ids in split_patients.items()} == {
        "train": 28,
        "validation": 6,
        "test": 6,
    }
    assert split_patients["train"].isdisjoint(split_patients["validation"])
    assert split_patients["train"].isdisjoint(split_patients["test"])
    assert split_patients["validation"].isdisjoint(split_patients["test"])


@pytest.mark.skipif(
    not Path("data/manifest.csv").is_file(),
    reason="optional v1 artifact check; source-only checkout excludes the original manifest",
)
def test_verified_manifest_bytes_remain_frozen() -> None:
    # Given: the published v1 patient split artifact.
    manifest = Path("data/manifest.csv")

    # When: its content digest is calculated without rewriting it.
    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()

    # Then: type cleanup cannot silently change the protected v1 split.
    assert digest == "e53264f2c60f21308265999176307b46d6f873494a241bb02394ecb63d900e04"
