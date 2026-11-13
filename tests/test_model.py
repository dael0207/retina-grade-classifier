from __future__ import annotations

import json
from typing import TYPE_CHECKING

import numpy as np
import pytest
from PIL import Image

from retina.evaluation import classification_metrics
from retina.model import (
    LinearClassifier,
    MobileNetEmbedder,
    load_model,
    occlusion_sensitivity,
    predict_image,
    preprocessing_tensor,
    save_model,
)
from retina.training import ManifestRow, validate_patient_splits

if TYPE_CHECKING:
    from pathlib import Path


def test_model_round_trip_preserves_predictions(tmp_path: Path) -> None:
    # Given
    classifier = LinearClassifier(
        coefficients=((1.0, 0.0), (0.0, 1.0)),
        intercepts=(0.1, -0.1),
        classes=(0, 2),
        feature_mean=(0.0, 0.0),
        feature_scale=(1.0, 1.0),
    )
    features = ((0.9, 0.2),)
    expected = classifier.predict(features)
    destination = tmp_path / "model.npz"

    # When
    save_model(classifier, destination)
    actual = load_model(destination).predict(features)

    # Then
    assert actual.grades == expected.grades
    np.testing.assert_allclose(actual.scores, expected.scores)


def test_preprocessing_matches_mobilenet_input_contract() -> None:
    # Given
    image = Image.new("RGB", (320, 240), color=(20, 40, 60))

    # When
    tensor = preprocessing_tensor(image)

    # Then
    assert tuple(tensor.shape) == (3, 224, 224)
    assert tensor.dtype.is_floating_point


def test_patient_split_leakage_is_rejected() -> None:
    # Given
    rows = [
        ManifestRow("1_left", 0, "1", "train"),
        ManifestRow("1_right", 1, "1", "validation"),
    ]

    # When / Then
    with pytest.raises(ValueError, match="patient split leakage"):
        validate_patient_splits(rows)


def test_metrics_keep_all_five_grades_in_confusion_matrix() -> None:
    # Given
    truth = np.array([0, 0, 2, 4], dtype=np.int64)
    predicted = np.array([0, 1, 2, 3], dtype=np.int64)

    # When
    metrics = classification_metrics(truth, predicted)

    # Then
    assert len(metrics.confusion_matrix) == 5
    assert all(len(row) == 5 for row in metrics.confusion_matrix)
    assert set(metrics.recall_by_grade) == {"0", "1", "2", "3", "4"}


def test_qwk_matches_known_ordinal_example() -> None:
    # Given
    truth = np.array([0, 0, 1, 2, 2, 3, 4], dtype=np.int64)
    predicted = np.array([0, 1, 1, 2, 3, 4, 4], dtype=np.int64)

    # When
    metrics = classification_metrics(truth, predicted)

    # Then
    assert metrics.qwk == pytest.approx(0.8985507246376812)
    assert metrics.macro_f1 == pytest.approx(0.5333333333333333)


def test_invalid_coefficient_vector_is_rejected_without_index_error() -> None:
    # Given / When / Then
    with pytest.raises(ValueError, match="matrix"):
        LinearClassifier(
            coefficients=(),
            intercepts=(0.0,),
            classes=(0,),
            feature_mean=(0.0,),
            feature_scale=(1.0,),
        )


def test_invalid_artifact_array_shape_is_rejected_without_index_error(tmp_path: Path) -> None:
    # Given
    destination = tmp_path / "invalid.npz"
    np.savez_compressed(
        destination,
        format_version=np.array([1], dtype=np.int64),
        extractor=np.array(["torchvision-mobilenet-v3-small-default-classifier-2"]),
        coefficients=np.array([1.0, 2.0], dtype=np.float32),
        intercepts=np.array([0.0], dtype=np.float32),
        classes=np.array([0], dtype=np.int64),
        feature_mean=np.array([0.0, 0.0], dtype=np.float32),
        feature_scale=np.array([1.0, 1.0], dtype=np.float32),
    )

    # When / Then
    with pytest.raises(ValueError, match="array shapes"):
        load_model(destination)


def test_real_image_inference_returns_stable_five_score_schema(tmp_path: Path) -> None:
    # Given
    feature_count = 1024
    classifier = LinearClassifier(
        coefficients=tuple(tuple(0.0 for _ in range(feature_count)) for _ in range(5)),
        intercepts=(0.0, 1.0, 2.0, 3.0, 4.0),
        classes=(0, 1, 2, 3, 4),
        feature_mean=tuple(0.0 for _ in range(feature_count)),
        feature_scale=tuple(1.0 for _ in range(feature_count)),
    )
    destination = tmp_path / "model.npz"
    save_model(classifier, destination)
    embedder = MobileNetEmbedder()
    provenance = embedder.save_backbone(tmp_path / "backbone.pth")
    (tmp_path / "backbone_provenance.json").write_text(json.dumps(provenance), encoding="utf-8")
    image = Image.new("RGB", (320, 320), color=(30, 80, 20))

    # When
    result = predict_image(image, destination).to_json()
    sensitivity = occlusion_sensitivity(image, destination)

    # Then
    assert result["grade"] == 4
    assert len(result["scores"]) == 5
    assert sum(result["scores"]) == pytest.approx(1.0)
    assert sensitivity.score_changes.shape == (4, 4)
    assert sensitivity.overlay.size == (320, 320)
