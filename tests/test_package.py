import json
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from retina.package import write_archive
from retina.package_assets import prepare_thumbnail
from retina.package_entries import (
    assignment1_entries,
    assignment2_entries,
    assignment2_example_entries,
)
from retina.package_types import ArchiveEntry, MissingInputsError
from retina.server import AppPaths, create_app


def test_write_archive_is_reproducible_and_contains_manifest(tmp_path: Path) -> None:
    # Given: two source artifacts with stable archive names.
    first = tmp_path / "source-a.txt"
    second = tmp_path / "source-b.bin"
    _ = first.write_text("alpha", encoding="utf-8")
    _ = second.write_bytes(b"beta")
    entries = (
        ArchiveEntry(first, "docs/a.txt"),
        ArchiveEntry(second, "data/b.bin"),
    )

    # When: identical inputs are packaged twice.
    output_a = tmp_path / "a.zip"
    output_b = tmp_path / "b.zip"
    write_archive(output_a, entries, {"purpose": "test"})
    write_archive(output_b, entries, {"purpose": "test"})

    # Then: ZIP bytes and package contents are deterministic.
    assert sha256(output_a.read_bytes()).digest() == sha256(output_b.read_bytes()).digest()
    with ZipFile(output_a) as archive:
        assert archive.namelist() == ["data/b.bin", "docs/a.txt", "PACKAGE_MANIFEST.json"]
        assert archive.read("docs/a.txt") == b"alpha"


def test_write_archive_rejects_missing_source(tmp_path: Path) -> None:
    # Given: an archive entry whose source is absent.
    entries = (ArchiveEntry(tmp_path / "missing.txt", "missing.txt"),)

    # When / Then: packaging fails before creating a partial submission.
    with pytest.raises(MissingInputsError, match=r"missing\.txt"):
        write_archive(tmp_path / "submission.zip", entries, {})
    assert not (tmp_path / "submission.zip").exists()


def test_prepare_thumbnail_crops_black_margin_and_preserves_ratio() -> None:
    # Given: a wide retinal-like region surrounded by black margins.
    source = Image.new("RGB", (1_400, 1_000), "black")
    draw = ImageDraw.Draw(source)
    draw.rectangle((200, 200, 1_199, 799), fill=(120, 50, 30))

    # When: the viewer thumbnail is prepared.
    thumbnail = prepare_thumbnail(source)

    # Then: margins are removed, aspect ratio remains wide, and size is bounded.
    assert thumbnail.size == (960, 576)


def test_assignment1_uses_analysis_only_dependency_manifest(tmp_path: Path) -> None:
    # Given: the package entry list can be inspected without reading image metadata.
    examples = tmp_path / "outputs/assignment1/examples.json"
    examples.parent.mkdir(parents=True)
    _ = examples.write_text('{"pairs": []}', encoding="utf-8")

    # When: the standalone analysis package is described.
    entries = assignment1_entries(tmp_path)
    destinations = {entry.destination: entry.source for entry in entries}

    # Then: it exposes a lightweight manifest instead of the app environment.
    assert destinations["requirements.txt"] == tmp_path / "assignment1-requirements.txt"
    assert destinations["README.md"] == tmp_path / "docs/assignment1_package_readme.md"
    assert "pyproject.toml" not in destinations
    assert "INSTALL.ps1" not in destinations


def test_assignment2_examples_follow_exported_metadata(tmp_path: Path) -> None:
    # Given: an export manifest with IDs that differ from the original run.
    example_dir = tmp_path / "outputs/assignment2/examples"
    example_dir.mkdir(parents=True)
    _ = (example_dir / "examples.json").write_text(
        """[
          {"input_file":"correct_42_right_input.jpg",
           "sensitivity_file":"correct_42_right_sensitivity.jpg",
           "image":"42_right"},
          {"input_file":"incorrect_900_left_input.jpg",
           "sensitivity_file":"incorrect_900_left_sensitivity.jpg",
           "image":"900_left"}
        ]""",
        encoding="utf-8",
    )

    # When: package entries are derived from the export manifest.
    entries = assignment2_example_entries(tmp_path)

    # Then: the current exported files, not historical IDs, define the package.
    assert [entry.destination for entry in entries] == [
        "outputs/assignment2/examples/examples.json",
        "outputs/assignment2/examples/correct_42_right_input.jpg",
        "outputs/assignment2/examples/correct_42_right_sensitivity.jpg",
        "data/images/42_right.jpg",
        "outputs/assignment2/examples/incorrect_900_left_input.jpg",
        "outputs/assignment2/examples/incorrect_900_left_sensitivity.jpg",
        "data/images/900_left.jpg",
    ]


def test_assignment2_examples_reject_missing_referenced_artifact(tmp_path: Path) -> None:
    # Given: metadata references an image that was not exported.
    example_dir = tmp_path / "outputs/assignment2/examples"
    example_dir.mkdir(parents=True)
    metadata = (
        '[{"image":"current","input_file":"current_input.jpg","sensitivity_file":"missing.jpg"}]'
    )
    _ = (example_dir / "examples.json").write_text(metadata, encoding="utf-8")
    _ = (example_dir / "current_input.jpg").write_bytes(b"jpeg")
    source_dir = tmp_path / "data/images"
    source_dir.mkdir(parents=True)
    _ = (source_dir / "current.jpg").write_bytes(b"jpeg")

    # When / Then: archive preflight names the missing dynamic artifact.
    with pytest.raises(MissingInputsError, match=r"missing\.jpg"):
        write_archive(tmp_path / "examples.zip", assignment2_example_entries(tmp_path), {})


def test_assignment2_contains_fresh_reproduction_sources(tmp_path: Path) -> None:
    # Given: the two manifests needed to resolve dynamic package entries.
    bilateral = tmp_path / "outputs/assignment1/examples.json"
    bilateral.parent.mkdir(parents=True)
    _ = bilateral.write_text('{"selection_rule":"test","pairs":[]}', encoding="utf-8")
    model_examples = tmp_path / "outputs/assignment2/examples/examples.json"
    model_examples.parent.mkdir(parents=True)
    _ = model_examples.write_text(
        json.dumps(
            [
                {
                    "image": "new_id",
                    "input_file": "new_input.jpg",
                    "sensitivity_file": "new_sensitivity.jpg",
                }
            ]
        ),
        encoding="utf-8",
    )
    test_source = tmp_path / "tests/test_package.py"
    test_source.parent.mkdir()
    _ = test_source.write_text("# package test source\n", encoding="utf-8")
    runtime_source = tmp_path / "model_runtime/classifier.pyi"
    runtime_source.parent.mkdir()
    _ = runtime_source.write_text("class Classifier: ...\n", encoding="utf-8")
    web_source = tmp_path / "web/modules/prediction.js"
    web_source.parent.mkdir(parents=True)
    _ = web_source.write_text("export {};\n", encoding="utf-8")

    # When: the runnable assignment package is described.
    destinations = {entry.destination for entry in assignment2_entries(tmp_path)}

    # Then: locked setup, download routes, viewer template, tests and source docs are retained.
    assert {
        "uv.lock",
        "DATA_LICENSE.md",
        "output/pdf/assignment1_bilateral_analysis.pdf",
        "output/pdf/assignment2_ai_classification.pdf",
        "retina/templates/assignment1_viewer.html",
        "docs/assignment1_package_readme.md",
        "docs/assignment2_package_readme.md",
        "tests/test_package.py",
        "model_runtime/classifier.pyi",
        "web/modules/prediction.js",
        "data/images/new_id.jpg",
    } <= destinations


def test_assignment2_package_keeps_pairs_download_working(tmp_path: Path) -> None:
    source = tmp_path / "source"
    analysis = source / "outputs/assignment1"
    analysis.mkdir(parents=True)
    payload = b"patient_id,left,right\n7,0,1\n"
    (analysis / "pairs.csv").write_bytes(payload)
    (analysis / "examples.json").write_text('{"pairs":[]}', encoding="utf-8")
    examples = source / "outputs/assignment2/examples"
    examples.mkdir(parents=True)
    (examples / "examples.json").write_text("[]", encoding="utf-8")
    extracted = tmp_path / "extracted"
    for entry in assignment2_entries(source):
        if entry.source.is_file():
            target = extracted / entry.destination
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(entry.source.read_bytes())
    client = TestClient(create_app(paths=AppPaths.from_root(extracted)))

    response = client.get("/download/pairs")

    assert response.status_code == 200
    assert response.content == payload
