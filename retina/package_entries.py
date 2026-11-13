"""Declare the evidence and runnable assets included in each submission."""

from pathlib import Path, PurePosixPath
from typing import Final

from pydantic import TypeAdapter

from retina.download import Examples
from retina.package_types import ArchiveEntry, ExportedExample, MissingInputsError

ROOT: Final = Path(__file__).resolve().parents[1]
PYTHON_SUFFIXES: Final = frozenset((".py", ".pyi"))
WEB_SUFFIXES: Final = frozenset((".css", ".html", ".js", ".json", ".svg"))


def _entry(root: Path, relative: str, destination: str | None = None) -> ArchiveEntry:
    return ArchiveEntry(root / relative, destination or PurePosixPath(relative).as_posix())


def _source_entries(root: Path, directory: str, suffixes: frozenset[str]) -> list[ArchiveEntry]:
    return [
        _entry(root, path.relative_to(root).as_posix())
        for path in sorted((root / directory).rglob("*"))
        if path.is_file() and path.suffix in suffixes
    ]


def assignment1_example_names(root: Path = ROOT) -> tuple[str, ...]:
    """Read the current bilateral image names selected by assignment 1 analysis."""
    source = root / "outputs/assignment1/examples.json"
    if not source.is_file():
        raise MissingInputsError(paths=(source,))
    examples = Examples.model_validate_json(source.read_text(encoding="utf-8"))
    return tuple(name for pair in examples.pairs for name in (pair.left_image, pair.right_image))


def assignment2_example_entries(root: Path = ROOT) -> tuple[ArchiveEntry, ...]:
    """Resolve current model-example artifacts exclusively from their export manifest."""
    source = root / "outputs/assignment2/examples/examples.json"
    if not source.is_file():
        raise MissingInputsError(paths=(source,))
    records = TypeAdapter(tuple[ExportedExample, ...]).validate_json(
        source.read_text(encoding="utf-8")
    )
    files = [_entry(root, "outputs/assignment2/examples/examples.json")]
    for record in records:
        files.extend(
            (
                _entry(root, f"outputs/assignment2/examples/{record.input_file}"),
                _entry(root, f"outputs/assignment2/examples/{record.sensitivity_file}"),
                _entry(root, f"data/images/{record.image}.jpg"),
            )
        )
    return tuple(files)


def assignment1_entries(root: Path = ROOT) -> tuple[ArchiveEntry, ...]:
    """List the standalone bilateral-analysis submission contents."""
    files = [
        _entry(root, "output/pdf/assignment1_bilateral_analysis.pdf", "report.pdf"),
        *(
            _entry(root, f"outputs/assignment1/{name}")
            for name in (
                "viewer.html",
                "01_class_distribution.png",
                "02_bilateral_cross_matrix.png",
                "03_grade_difference.png",
                "04_agreement_comparison.png",
                "summary.json",
                "examples.json",
                "pairs.csv",
            )
        ),
        *(
            _entry(root, name)
            for name in (
                "trainLabels.csv",
                "data-inventory.csv",
                "zip-directory.bin",
                "docs/assignment1_report.md",
                "retina/__init__.py",
                "retina/analysis.py",
                "retina/charts.py",
                "retina/viewer.py",
                "retina/templates/assignment1_viewer.html",
                "tests/test_analysis.py",
                "tests/test_viewer.py",
            )
        ),
        _entry(root, "docs/assignment1_package_readme.md", "README.md"),
        _entry(root, "assignment1-requirements.txt", "requirements.txt"),
    ]
    files.extend(
        _entry(root, f"outputs/assignment1/images/{name}.jpg")
        for name in assignment1_example_names(root)
    )
    return tuple(files)


def assignment2_entries(root: Path = ROOT) -> tuple[ArchiveEntry, ...]:
    """List the runnable AI application and model evidence contents."""
    files = [
        _entry(root, "output/pdf/assignment2_ai_classification.pdf", "report.pdf"),
        _entry(root, "output/pdf/assignment1_bilateral_analysis.pdf"),
        _entry(root, "output/pdf/assignment2_ai_classification.pdf"),
        *(
            _entry(root, name)
            for name in (
                "QA_SUMMARY.md",
                "DESIGN.md",
                ".gitignore",
                ".gitattributes",
                "START_APP.bat",
                "INSTALL.ps1",
                "REPRODUCE.ps1",
                "pyproject.toml",
                "uv.lock",
                "DATA_LICENSE.md",
                "docs/REFERENCE_COMPARISON.md",
                "docs/REFERENCE_UPGRADE_PLAN.md",
                "docs/assignment1_report.md",
                "docs/assignment1_package_readme.md",
                "docs/assignment2_report.md",
                "docs/assignment2_package_readme.md",
                "docs/UI_QA.md",
                "assignment1-requirements.txt",
                "retina/templates/assignment1_viewer.html",
                "trainLabels.csv",
                "data-inventory.csv",
                "zip-directory.bin",
                "data/manifest.csv",
                "data/image_audit.csv",
                "data/integrity.json",
            )
        ),
        _entry(root, "docs/assignment2_package_readme.md", "README.md"),
        *(
            _entry(root, f"outputs/assignment1/{name}")
            for name in (
                "summary.json",
                "examples.json",
                "pairs.csv",
                "01_class_distribution.png",
                "02_bilateral_cross_matrix.png",
                "03_grade_difference.png",
                "04_agreement_comparison.png",
            )
        ),
        *(
            _entry(root, f"outputs/assignment2/{name}")
            for name in (
                "model.npz",
                "backbone.pth",
                "backbone_provenance.json",
                "metrics.json",
                "predictions.csv",
                "validation_unweighted_predictions.csv",
                "validation_balanced_predictions.csv",
                "run_config.json",
                "training.log",
            )
        ),
        *assignment2_example_entries(root),
    ]
    reproducibility = "outputs/assignment2/reproducibility.json"
    if (root / reproducibility).is_file():
        files.append(_entry(root, reproducibility))
    files.extend(_source_entries(root, "retina", PYTHON_SUFFIXES))
    files.extend(_source_entries(root, "model_runtime", PYTHON_SUFFIXES))
    files.extend(_source_entries(root, "typings", frozenset((".pyi",))))
    files.extend(_source_entries(root, "web", WEB_SUFFIXES))
    files.extend(_source_entries(root, "scripts", frozenset((".py", ".ps1"))))
    files.extend(_source_entries(root, ".github/workflows", frozenset((".yml", ".yaml"))))
    files.extend(
        _entry(root, path.relative_to(root).as_posix())
        for path in sorted((root / "tests").glob("test_*.py"))
    )
    files.extend(
        _entry(root, f"data/images/{name}.jpg") for name in assignment1_example_names(root)
    )
    return tuple(dict.fromkeys(files))
