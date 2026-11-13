"""Command-line entry point for the two submission-ready PDF reports."""

from retina.report_assignment1 import build_assignment1
from retina.report_assignment2 import build_assignment2
from retina.report_data import ROOT, load_json_array, load_json_required
from retina.report_manifest import summarize_manifest


def main() -> None:
    """Generate both PDFs only from verified local artifacts."""
    assignment1 = load_json_required(
        ROOT / "outputs/assignment1/summary.json",
        frozenset({"image_count", "patient_count", "class_counts", "weighted_kappa"}),
    )
    examples = load_json_required(
        ROOT / "outputs/assignment1/examples.json",
        frozenset({"pairs", "selection_rule"}),
    )
    assignment2 = load_json_required(
        ROOT / "outputs/assignment2/metrics.json",
        frozenset(
            {"dataset", "validation_candidates", "selected_model", "test", "majority_baseline_test"}
        ),
    )
    assignment2_examples = load_json_array(ROOT / "outputs/assignment2/examples/examples.json")
    run_config = load_json_required(
        ROOT / "outputs/assignment2/run_config.json",
        frozenset({"python", "torch", "torchvision", "scikit_learn", "manifest_sha256"}),
    )
    manifest = summarize_manifest(ROOT / "data/manifest.csv")
    destination = ROOT / "output/pdf"
    destination.mkdir(parents=True, exist_ok=True)
    build_assignment1(assignment1, examples, destination / "assignment1_bilateral_analysis.pdf")
    build_assignment2(
        assignment2,
        assignment2_examples,
        run_config,
        manifest,
        destination / "assignment2_ai_classification.pdf",
    )


if __name__ == "__main__":
    main()
