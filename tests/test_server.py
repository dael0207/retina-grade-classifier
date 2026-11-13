from __future__ import annotations

import io
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import retina.server as server_module
from retina.server import AppPaths, PredictionResponse, create_app

if TYPE_CHECKING:
    from pathlib import Path


def _paths(tmp_path: Path) -> AppPaths:
    web = tmp_path / "web"
    _ = web.mkdir()
    _ = (web / "index.html").write_text("<h1>Retina Pair Lab</h1>", encoding="utf-8")
    _ = (web / "showcase.html").write_text("<h1>Showcase</h1>", encoding="utf-8")
    return AppPaths.from_root(tmp_path)


def _jpeg_bytes() -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (24, 24), color=(80, 20, 10)).save(stream, format="JPEG")
    return stream.getvalue()


def test_analysis_returns_generated_json_when_file_exists(tmp_path: Path) -> None:
    # Given
    paths = _paths(tmp_path)
    _ = paths.assignment1.mkdir(parents=True)
    expected = {"schema_version": "1.0", "patient_count": 17_563}
    _ = paths.analysis_summary.write_text(json.dumps(expected), encoding="utf-8")
    client = TestClient(create_app(paths=paths))

    # When
    response = client.get("/api/analysis")

    # Then
    assert response.status_code == 200
    assert response.json() == expected


def test_analysis_returns_actionable_unavailable_state_when_not_generated(
    tmp_path: Path,
) -> None:
    # Given
    client = TestClient(create_app(paths=_paths(tmp_path)))

    # When
    response = client.get("/api/analysis")

    # Then
    assert response.status_code == 503
    assert "분석 결과" in response.json()["detail"]


def test_predict_rejects_non_image_content(tmp_path: Path) -> None:
    # Given
    client = TestClient(create_app(paths=_paths(tmp_path)))

    # When
    response = client.post(
        "/api/predict",
        content=b"not an image",
        headers={"content-type": "text/plain"},
    )

    # Then
    assert response.status_code == 415


def test_predict_verifies_image_and_returns_model_output(tmp_path: Path) -> None:
    # Given
    observed_sizes: list[tuple[int, int]] = []

    def fake_predictor(image: Image.Image) -> PredictionResponse:
        observed_sizes.append(image.size)
        return PredictionResponse(grade=2, scores=[0.1, 0.2, 0.5, 0.15, 0.05])

    client = TestClient(create_app(paths=_paths(tmp_path), predictor=fake_predictor))

    # When
    response = client.post(
        "/api/predict",
        content=_jpeg_bytes(),
        headers={"content-type": "image/jpeg"},
    )

    # Then
    assert response.status_code == 200
    prediction = PredictionResponse.model_validate(response.json())
    assert prediction.grade == 2
    assert len(prediction.scores) == 5
    assert observed_sizes == [(24, 24)]


def test_predict_rejects_spoofed_image_bytes(tmp_path: Path) -> None:
    # Given
    client = TestClient(create_app(paths=_paths(tmp_path)))

    # When
    response = client.post(
        "/api/predict",
        content=b"this is not actually a jpeg",
        headers={"content-type": "image/jpeg"},
    )

    # Then
    assert response.status_code == 400
    assert "이미지" in response.json()["detail"]


@pytest.mark.parametrize("stage", ["decode", "predict"])
def test_prediction_does_not_block_evidence_requests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    # Given: CPU inference is still running in another request.
    started = Event()
    release = Event()

    def wait_for_release() -> None:
        started.set()
        if not release.wait(timeout=10):
            message = "test predictor was not released"
            raise TimeoutError(message)

    original_decoder = server_module._decode_image

    def decoder(payload: bytes) -> Image.Image:
        if stage == "decode":
            wait_for_release()
        return original_decoder(payload)

    def predictor(_image: Image.Image) -> PredictionResponse:
        if stage == "predict":
            wait_for_release()
        return PredictionResponse(grade=0, scores=[1.0, 0.0, 0.0, 0.0, 0.0])

    monkeypatch.setattr(server_module, "_decode_image", decoder)
    with (
        TestClient(create_app(paths=_paths(tmp_path), predictor=predictor)) as client,
        ThreadPoolExecutor(max_workers=2) as executor,
    ):
        prediction = executor.submit(
            client.post,
            "/api/predict",
            content=_jpeg_bytes(),
            headers={"content-type": "image/jpeg"},
        )
        try:
            assert started.wait(timeout=5)
            # When: an evidence request arrives before prediction completes.
            evidence = executor.submit(client.get, "/api/analysis")
            # Then: the evidence route responds without waiting for the model.
            assert evidence.result(timeout=2).status_code == 503
        finally:
            release.set()
        assert prediction.result(timeout=5).status_code == 200
