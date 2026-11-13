"""Report generation contracts."""

import json
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path
from textwrap import dedent

import pytest
from PIL import Image as PILImage

import retina.report_assignment1 as assignment1_module
import retina.report_assignment2_cases as assignment2_cases_module
import retina.report_images as report_images_module
from retina.report_assignment1 import build_assignment1
from retina.report_assignment2 import build_assignment2
from retina.report_data import JsonValue, ReportDataError, load_json_array, load_json_required
from retina.report_layout import confusion_rows, percentage
from retina.report_manifest import SplitSummary, summarize_manifest


def _pdf_text(path: Path) -> str:
    executable = shutil.which("pdftotext")
    if executable is None:
        pytest.skip("pdftotext is required only for rendered-PDF extraction tests")
    result = subprocess.run(  # noqa: S603
        [executable, "-layout", "-enc", "UTF-8", str(path), "-"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return " ".join(result.stdout.split())


def _write_image(path: Path, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    PILImage.new("RGB", (40, 40), color).save(path)


def _metric(
    confusion_matrix: Sequence[Sequence[int]],
    recalls: tuple[float, float, float, float, float],
) -> dict[str, JsonValue]:
    matrix_value: list[JsonValue] = []
    for row in confusion_matrix:
        typed_row: list[JsonValue] = []
        typed_row.extend(row)
        matrix_value.append(typed_row)
    return {
        "accuracy": 0.42,
        "qwk": 0.12,
        "macro_f1": 0.23,
        "recall_by_grade": {str(index): value for index, value in enumerate(recalls)},
        "confusion_matrix": matrix_value,
    }


def test_load_json_rejects_missing_required_keys(tmp_path: Path) -> None:
    # Given an incomplete result artifact.
    source = tmp_path / "metrics.json"
    _ = source.write_text(json.dumps({"dataset": {}}), encoding="utf-8")
    # When loading it for a report, then the missing contract is explicit.
    with pytest.raises(ReportDataError, match="selected_model"):
        _ = load_json_required(source, frozenset({"dataset", "selected_model"}))


def test_metric_percentage_formats_real_fraction() -> None:
    # Given a metric stored as a fraction.
    # When formatting it, then it remains precise and readable in Korean reports.
    assert percentage(0.5857988) == "58.58%"


def test_load_json_array_rejects_object(tmp_path: Path) -> None:
    source = tmp_path / "examples.json"
    _ = source.write_text(json.dumps({"kind": "correct"}), encoding="utf-8")
    with pytest.raises(ReportDataError, match="Invalid JSON"):
        _ = load_json_array(source)


def test_confusion_table_rejects_non_square_matrix() -> None:
    # Given an invalid confusion matrix.
    # When building table rows, then malformed model evidence is rejected.
    with pytest.raises(ValueError, match="5 x 5"):
        _ = confusion_rows([[1, 2], [3, 4]])


def test_manifest_summary_uses_fixture_rows(tmp_path: Path) -> None:
    source = tmp_path / "manifest.csv"
    _ = source.write_text(
        dedent(
            """\
            image,level,patient_id,split
            a_left,4,a,train
            a_right,3,a,train
            b_left,2,b,validation
            c_left,1,c,test
            """
        ),
        encoding="utf-8",
    )
    summary = summarize_manifest(source)
    assert summary["train"] == SplitSummary(2, 1, (0, 0, 0, 1, 1))
    assert summary["validation"] == SplitSummary(1, 1, (0, 0, 1, 0, 0))
    assert summary["test"] == SplitSummary(1, 1, (0, 1, 0, 0, 0))


def test_assignment1_render_uses_modified_summary_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(assignment1_module, "ROOT", tmp_path)
    monkeypatch.setattr(report_images_module, "ROOT", tmp_path)
    for chart_name in (
        "01_class_distribution.png",
        "02_bilateral_cross_matrix.png",
        "03_grade_difference.png",
        "04_agreement_comparison.png",
    ):
        _write_image(tmp_path / "outputs/assignment1" / chart_name, (30, 120, 100))
    pairs: list[JsonValue] = []
    for gap in (0, 2, 3, 4):
        left_name = f"fixture_{gap}_left"
        right_name = f"fixture_{gap}_right"
        _write_image(tmp_path / "data/images" / f"{left_name}.jpg", (80, 30, 30))
        _write_image(tmp_path / "data/images" / f"{right_name}.jpg", (30, 30, 80))
        pairs.append(
            {
                "patient_id": 9000 + gap,
                "left_image": left_name,
                "right_image": right_name,
                "left_grade": 0,
                "right_grade": gap,
                "difference": gap,
            }
        )
    summary: dict[str, JsonValue] = {
        "image_count": 77770,
        "patient_count": 38885,
        "exact_agreement": 0.90,
        "affected_exact_agreement": 0.4567,
        "weighted_kappa": 0.7654,
        "class_counts": [7777, 11111, 22222, 12345, 24315],
        "class_percentages": [10.0, 14.29, 28.57, 15.87, 31.27],
        "cross_matrix": [
            [4321, 0, 0, 0, 0],
            [0, 3210, 0, 0, 0],
            [0, 0, 2109, 0, 0],
            [0, 0, 0, 1098, 0],
            [0, 0, 0, 0, 987],
        ],
        "difference_counts": [35000, 2000, 1000, 500, 385],
        "discordant_count": 3885,
        "discordant_percentage": 9.99,
        "large_gap_count": 1885,
        "affected_patient_count": 12345,
    }
    examples: dict[str, JsonValue] = {"pairs": pairs}
    destination = tmp_path / "assignment1-fixture.pdf"
    build_assignment1(summary, examples, destination)
    text = _pdf_text(destination)
    for rendered_value in ("77,770", "38,885", "7,777", "10.00%", "4,321", "12,345"):
        assert rendered_value in text


def test_assignment2_render_uses_modified_manifest_and_run_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(assignment2_cases_module, "ROOT", tmp_path)
    support_matrix = [
        [17, 0, 0, 0, 0],
        [18, 0, 0, 0, 0],
        [0, 0, 19, 0, 0],
        [20, 0, 0, 0, 0],
        [0, 0, 0, 0, 21],
    ]
    candidate_matrix = [[1, 0, 0, 0, 0] for _ in range(5)]
    metrics: dict[str, JsonValue] = {
        "dataset": {"train": 515, "validation": 540, "test": 95},
        "validation_candidates": {
            "unweighted": _metric(candidate_matrix, (0.1, 0.2, 0.3, 0.4, 0.5)),
            "balanced": _metric(candidate_matrix, (0.2, 0.3, 0.4, 0.5, 0.6)),
        },
        "selected_model": "balanced",
        "test": _metric(support_matrix, (1.0, 0.0, 1.0, 0.0, 1.0)),
        "majority_baseline_test": _metric(support_matrix, (1.0, 0.0, 0.0, 0.0, 0.0)),
    }
    examples: list[JsonValue] = []
    for kind, image_name, actual, predicted in (("correct", "fixture_correct", 0, 0),):
        input_name = f"{kind}_input.jpg"
        sensitivity_name = f"{kind}_sensitivity.jpg"
        _write_image(tmp_path / "outputs/assignment2/examples" / input_name, (50, 60, 70))
        _write_image(tmp_path / "outputs/assignment2/examples" / sensitivity_name, (90, 30, 30))
        examples.append(
            {
                "kind": kind,
                "image": image_name,
                "actual": actual,
                "predicted": predicted,
                "input_file": input_name,
                "sensitivity_file": sensitivity_name,
            }
        )
    run_config: dict[str, JsonValue] = {
        "python": "9.9.9",
        "torch": "8.8.8+fixture",
        "torchvision": "7.7.7+fixture",
        "scikit_learn": "6.6.6",
        "manifest_sha256": "fixture-sha-123",
    }
    manifest = {
        "train": SplitSummary(515, 251, (101, 102, 103, 104, 105)),
        "validation": SplitSummary(540, 252, (106, 107, 108, 109, 110)),
        "test": SplitSummary(95, 253, (17, 18, 19, 20, 21)),
    }
    destination = tmp_path / "assignment2-fixture.pdf"
    build_assignment2(metrics, examples, run_config, manifest, destination)
    text = _pdf_text(destination)
    for rendered_value in (
        "515",
        "251명",
        "101",
        "9.9.9",
        "FIXTURE-SHA-123",
        "0 17",
        "4 21",
    ):
        assert rendered_value in text
