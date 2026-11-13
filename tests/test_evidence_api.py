"""Public evidence endpoints expose generated artifacts with bounded paths."""

from pathlib import Path

from fastapi.testclient import TestClient

from retina.server import AppPaths, create_app


def test_provenance_counts_patients_and_grades_from_manifest(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    (data / "manifest.csv").write_text(
        "image,level,patient_id,split\n2_left,1,2,train\n2_right,3,2,train\n9_left,4,9,test\n",
        encoding="utf-8",
    )
    (data / "integrity.json").write_text('{"passed":true}', encoding="utf-8")
    model = tmp_path / "outputs/assignment2"
    model.mkdir(parents=True)
    (model / "run_config.json").write_text('{"device":"cpu"}', encoding="utf-8")
    client = TestClient(create_app(paths=AppPaths.from_root(tmp_path)))

    response = client.get("/api/provenance")

    assert response.status_code == 200
    payload = response.json()
    assert payload["splits"][0] == {
        "split": "train",
        "patients": 1,
        "images": 2,
        "class_counts": [0, 1, 0, 1, 0],
    }
    assert payload["splits"][2]["patients"] == 1
    assert len(payload["manifest_sha256"]) == 64


def test_download_serves_only_named_artifacts(tmp_path: Path) -> None:
    destination = tmp_path / "outputs/assignment1"
    destination.mkdir(parents=True)
    (destination / "pairs.csv").write_text("patient_id,left,right\n7,0,1\n", encoding="utf-8")
    client = TestClient(create_app(paths=AppPaths.from_root(tmp_path)))

    response = client.get("/download/pairs")

    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    assert response.text.startswith("patient_id,")


def test_unknown_download_is_not_a_filesystem_path(tmp_path: Path) -> None:
    client = TestClient(create_app(paths=AppPaths.from_root(tmp_path)))

    response = client.get("/download/pyproject.toml")

    assert response.status_code == 404


def test_missing_provenance_reports_unavailable(tmp_path: Path) -> None:
    client = TestClient(create_app(paths=AppPaths.from_root(tmp_path)))

    response = client.get("/api/provenance")

    assert response.status_code == 503
