from pathlib import Path

import pytest

from retina.analysis import (
    DatasetValidationError,
    EyeRecord,
    EyeSide,
    Grade,
    PatientId,
    analyze_records,
    load_labels,
    pair_records,
    run,
    select_examples,
)


def _record(patient: int, side: EyeSide, grade: int) -> EyeRecord:
    return EyeRecord(
        patient_id=PatientId(patient),
        side=side,
        image=f"{patient}_{side.value}",
        grade=Grade(grade),
    )


def test_analyze_records_computes_pair_level_metrics() -> None:
    # Given: three complete patient pairs with one exact and two discordant pairs.
    records = (
        _record(1, EyeSide.LEFT, 0),
        _record(1, EyeSide.RIGHT, 0),
        _record(2, EyeSide.LEFT, 1),
        _record(2, EyeSide.RIGHT, 2),
        _record(3, EyeSide.LEFT, 4),
        _record(3, EyeSide.RIGHT, 1),
    )

    # When: the paired-eye analysis is computed.
    summary = analyze_records(records)

    # Then: counts and agreement metrics use patients as the denominator.
    assert summary.image_count == 6
    assert summary.patient_count == 3
    assert summary.class_counts == (2, 2, 1, 0, 1)
    assert summary.difference_counts == (1, 1, 0, 1, 0)
    assert summary.discordant_count == 2
    assert abs(summary.exact_agreement - 1 / 3) < 1e-12
    assert summary.affected_patient_count == 2
    assert summary.affected_exact_agreement == 0.0
    assert summary.weighted_kappa < 1.0


def test_pair_records_rejects_duplicate_side() -> None:
    # Given: one patient has two left-eye rows.
    records = (
        _record(1, EyeSide.LEFT, 0),
        _record(1, EyeSide.LEFT, 1),
        _record(1, EyeSide.RIGHT, 0),
    )

    # When / Then: pairing rejects the ambiguous patient record.
    with pytest.raises(DatasetValidationError, match="duplicate"):
        _ = pair_records(records)


def test_pair_records_rejects_missing_eye() -> None:
    # Given: one patient has only a left eye.
    records = (_record(1, EyeSide.LEFT, 0),)

    # When / Then: pairing reports the incomplete pair.
    with pytest.raises(DatasetValidationError, match="missing"):
        _ = pair_records(records)


def test_select_examples_covers_low_and_high_severity_per_gap() -> None:
    # Given: every difference includes low- and high-severity candidates.
    records: list[EyeRecord] = []
    patient = 1
    for difference in range(5):
        for left, right in ((0, difference), (4 - difference, 4)):
            records.extend(
                (
                    _record(patient, EyeSide.LEFT, left),
                    _record(patient, EyeSide.RIGHT, right),
                )
            )
            patient += 1

    # When: deterministic teaching examples are selected.
    examples = select_examples(pair_records(records))

    # Then: each gap contributes a low-maximum and high-maximum pair.
    assert len(examples.pairs) == 10
    for difference in range(5):
        selected = examples.pairs[difference * 2 : difference * 2 + 2]
        assert [pair.difference for pair in selected] == [difference, difference]
        assert max(selected[0].left_grade, selected[0].right_grade) <= max(
            selected[1].left_grade, selected[1].right_grade
        )


@pytest.mark.skipif(
    not Path("trainLabels.csv").is_file(),
    reason="optional source-data check; source-only checkout excludes the original labels",
)
def test_real_dataset_matches_verified_invariants() -> None:
    # Given: the provided label CSV.
    labels_path = Path("trainLabels.csv")

    # When: its rows are loaded and analyzed through the production path.
    summary = analyze_records(load_labels(labels_path))

    # Then: the archive inventory and analysis agree on all core totals.
    assert summary.image_count == 35_126
    assert summary.patient_count == 17_563
    assert summary.class_counts == (25_810, 2_443, 5_292, 873, 708)
    assert summary.discordant_count == 2_240
    assert summary.large_gap_count == 755


def test_run_regenerates_offline_viewer_from_current_outputs(tmp_path: Path) -> None:
    # Given: a complete synthetic label file and a stale viewer artifact.
    labels = tmp_path / "labels.csv"
    rows = ["image,level"]
    patient = 100
    for difference in range(5):
        for left, right in ((0, difference), (4 - difference, 4)):
            rows.extend((f"{patient}_left,{left}", f"{patient}_right,{right}"))
            patient += 1
    _ = labels.write_text("\n".join(rows), encoding="utf-8")
    output = tmp_path / "outputs"
    output.mkdir()
    _ = (output / "viewer.html").write_text("STALE VIEWER", encoding="utf-8")

    # When: assignment 1 analysis is rerun.
    _ = run(labels, output)
    rendered = (output / "viewer.html").read_text(encoding="utf-8")

    # Then: the viewer is rebuilt from this run's summary and example selection.
    assert "STALE VIEWER" not in rendered
    assert "10" in rendered
    assert '"patient_id":100' in rendered
