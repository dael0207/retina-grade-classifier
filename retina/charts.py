"""Publication-ready Korean charts for paired-eye analysis."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Final, Literal, Protocol

import matplotlib as mpl

mpl.use("Agg")

import numpy as np
from matplotlib.colors import LinearSegmentedColormap

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from matplotlib.axis import Tick
    from matplotlib.colorbar import Colorbar
    from matplotlib.colors import Colormap
    from matplotlib.container import BarContainer
    from matplotlib.image import AxesImage
    from matplotlib.spines import Spines
    from matplotlib.text import Text
    from matplotlib.transforms import Transform
    from numpy.typing import NDArray


class AnalysisData(Protocol):
    """Values consumed by assignment 1 chart renderers."""

    image_count: int
    class_counts: tuple[int, ...]
    class_percentages: tuple[float, ...]
    cross_matrix: tuple[tuple[int, ...], ...]
    difference_counts: tuple[int, ...]
    discordant_count: int
    discordant_percentage: float
    exact_agreement: float
    affected_exact_agreement: float


class _ChartAxes(Protocol):
    spines: Spines
    transAxes: Transform  # noqa: N815 - Matplotlib's public attribute name.

    def bar(
        self, x: Sequence[int], height: Sequence[int], *, color: Sequence[str], width: float
    ) -> BarContainer: ...
    def barh(
        self, y: Sequence[str], width: Sequence[float], *, color: Sequence[str], height: float
    ) -> BarContainer: ...
    def imshow(self, data: NDArray[np.float64], *, cmap: Colormap) -> AxesImage: ...
    def set_title(self, label: str, *, loc: Literal["left"], pad: float) -> Text: ...
    def text(  # noqa: PLR0913 - Mirrors the external plotting API.
        self,
        x: float,
        y: float,
        value: str,
        *,
        transform: Transform | None = None,
        color: str,
        fontsize: int | None = None,
        horizontalalignment: Literal["center"] | None = None,
        verticalalignment: Literal["bottom", "center"] | None = None,
        fontweight: Literal["bold"] | None = None,
    ) -> Text: ...
    def set_xticks(
        self, ticks: Sequence[int], labels: Sequence[str] | None = None
    ) -> list[Tick]: ...
    def set_yticks(self, ticks: Sequence[int], labels: Sequence[str]) -> list[Tick]: ...
    def set_xlabel(self, label: str) -> Text: ...
    def set_ylabel(self, label: str) -> Text: ...
    def grid(
        self,
        *,
        axis: Literal["x", "y"],
        color: str,
        linewidth: int = 1,
    ) -> None: ...
    def set_axisbelow(self, enabled: bool) -> None: ...
    def set_xlim(self, left: float, right: float) -> tuple[float, float]: ...
    def set_ylim(self, bottom: float, top: float) -> tuple[float, float]: ...
    def invert_yaxis(self) -> None: ...


class _ChartFigure(Protocol):
    def subplots(self) -> _ChartAxes: ...
    def savefig(self, path: Path, *, dpi: int, bbox_inches: str, facecolor: str) -> None: ...
    def colorbar(
        self, image: AxesImage, *, ax: _ChartAxes, shrink: float, label: str
    ) -> Colorbar: ...


class _FigureFactory(Protocol):
    def __call__(self, *, figsize: tuple[float, float]) -> _ChartFigure: ...


if TYPE_CHECKING:
    _figure_factory: _FigureFactory
else:
    from matplotlib import figure as matplotlib_figure

    _figure_factory: _FigureFactory = matplotlib_figure.Figure


NAVY: Final = "#17324D"
TEAL: Final = "#20A39E"
ORANGE: Final = "#F4A261"
CORAL: Final = "#E76F51"
PALE: Final = "#E8F1F5"
GRADE_NAMES: Final = ("0 없음", "1 경증", "2 중등도", "3 중증", "4 증식성")


def _configure_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "Malgun Gothic",
            "axes.unicode_minus": False,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.titleweight": "bold",
            "axes.titlesize": 16,
            "axes.labelsize": 11,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
        }
    )


def _save(figure: _ChartFigure, path: Path) -> None:
    figure.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")


def _class_distribution(summary: AnalysisData, path: Path) -> None:
    figure = _figure_factory(figsize=(10, 5.8))
    axis = figure.subplots()
    positions = list(range(5))
    bars = axis.bar(
        positions, summary.class_counts, color=[NAVY, TEAL, "#5BB8B1", ORANGE, CORAL], width=0.68
    )
    _ = axis.set_title("당뇨망막병증 등급별 이미지 분포", loc="left", pad=18)
    _ = axis.text(
        0,
        1.02,
        f"학습 이미지 {summary.image_count:,}장 · 0등급 비중 {summary.class_percentages[0]:.1f}%",
        transform=axis.transAxes,
        color="#526271",
    )
    _ = axis.set_xticks(positions, GRADE_NAMES)
    _ = axis.set_ylabel("이미지 수")
    axis.spines[["top", "right", "left"]].set_visible(False)
    axis.grid(axis="y", color=PALE, linewidth=1)
    axis.set_axisbelow(True)
    for bar, count, percentage in zip(
        bars.patches, summary.class_counts, summary.class_percentages, strict=True
    ):
        _ = axis.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + min(450, max(summary.class_counts) * 0.02),
            f"{count:,}\n({percentage:.1f}%)",
            horizontalalignment="center",
            verticalalignment="bottom",
            fontsize=9,
            color=NAVY,
        )
    _ = axis.set_ylim(0, max(summary.class_counts) * 1.16)
    _save(figure, path)


def _cross_matrix(summary: AnalysisData, path: Path) -> None:
    matrix = np.asarray(summary.cross_matrix, dtype=np.int64)
    log_matrix = np.log1p(matrix)
    cmap = LinearSegmentedColormap.from_list("retina", ["#F5FAFC", "#8ED1CC", NAVY])
    figure = _figure_factory(figsize=(7.4, 6.6))
    axis = figure.subplots()
    image = axis.imshow(log_matrix, cmap=cmap)
    _ = axis.set_title("같은 ID의 좌·우 눈 등급 교차표", loc="left", pad=18)
    _ = axis.text(
        0,
        1.02,
        "색상은 큰 빈도 차이를 읽기 쉽도록 log(개수+1)로 표현",
        transform=axis.transAxes,
        color="#526271",
        fontsize=9,
    )
    _ = axis.set_xlabel("오른쪽 눈 등급")
    _ = axis.set_ylabel("왼쪽 눈 등급")
    _ = axis.set_xticks(list(range(5)), [str(grade) for grade in range(5)])
    _ = axis.set_yticks(list(range(5)), [str(grade) for grade in range(5)])
    color_threshold = (
        max(math.log1p(value) for row_values in summary.cross_matrix for value in row_values) * 0.55
    )
    for row in range(5):
        for column in range(5):
            value = summary.cross_matrix[row][column]
            color = "white" if math.log1p(value) > color_threshold else NAVY
            _ = axis.text(
                column,
                row,
                f"{value:,}",
                horizontalalignment="center",
                verticalalignment="center",
                color=color,
                fontsize=9,
                fontweight="bold",
            )
    _ = figure.colorbar(image, ax=axis, shrink=0.72, label="log(개수+1)")
    _save(figure, path)


def _difference_distribution(summary: AnalysisData, path: Path) -> None:
    figure = _figure_factory(figsize=(9, 5.5))
    axis = figure.subplots()
    positions = list(range(5))
    colors = [TEAL, "#72C3BD", ORANGE, CORAL, "#9D4E5C"]
    bars = axis.bar(positions, summary.difference_counts, color=colors, width=0.7)
    _ = axis.set_title("양안 등급의 절대 차이", loc="left", pad=18)
    _ = axis.text(
        0,
        1.02,
        f"등급이 다른 ID {summary.discordant_count:,}명 ({summary.discordant_percentage:.2f}%)",
        transform=axis.transAxes,
        color="#526271",
    )
    _ = axis.set_xlabel("|왼쪽 등급 - 오른쪽 등급|")
    _ = axis.set_ylabel("ID 수")
    _ = axis.set_xticks(positions)
    axis.spines[["top", "right", "left"]].set_visible(False)
    axis.grid(axis="y", color=PALE)
    axis.set_axisbelow(True)
    for bar, count in zip(bars.patches, summary.difference_counts, strict=True):
        _ = axis.text(
            bar.get_x() + bar.get_width() / 2,
            count + min(280, max(summary.difference_counts) * 0.02),
            f"{count:,}",
            horizontalalignment="center",
            color=NAVY,
            fontweight="bold",
        )
    _ = axis.set_ylim(0, max(summary.difference_counts) * 1.14)
    _save(figure, path)


def _agreement_comparison(summary: AnalysisData, path: Path) -> None:
    values = [100 * summary.exact_agreement, 100 * summary.affected_exact_agreement]
    figure = _figure_factory(figsize=(8.8, 4.8))
    axis = figure.subplots()
    bars = axis.barh(
        ["전체 ID", "적어도 한쪽 1등급 이상"], values, color=[NAVY, CORAL], height=0.48
    )
    _ = axis.set_title("분석 집단에 따른 정확 일치율", loc="left", pad=18)
    _ = axis.text(
        0,
        1.02,
        "0등급 양안 쌍이 전체 일치율을 높이는 영향을 분리",
        transform=axis.transAxes,
        color="#526271",
    )
    _ = axis.set_xlim(0, 100)
    _ = axis.set_xlabel("좌·우 등급 정확 일치율 (%)")
    axis.spines[["top", "right", "left"]].set_visible(False)
    axis.grid(axis="x", color=PALE)
    axis.set_axisbelow(True)
    for bar, value in zip(bars.patches, values, strict=True):
        _ = axis.text(
            value + 1.2,
            bar.get_y() + bar.get_height() / 2,
            f"{value:.1f}%",
            verticalalignment="center",
            color=NAVY,
            fontweight="bold",
        )
    axis.invert_yaxis()
    _save(figure, path)


def render_charts(summary: AnalysisData, output_dir: Path) -> None:
    """Write the four assignment charts to the output directory."""
    _configure_style()
    _class_distribution(summary, output_dir / "01_class_distribution.png")
    _cross_matrix(summary, output_dir / "02_bilateral_cross_matrix.png")
    _difference_distribution(summary, output_dir / "03_grade_difference.png")
    _agreement_comparison(summary, output_dir / "04_agreement_comparison.png")
