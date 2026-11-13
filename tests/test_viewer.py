from pathlib import Path

from retina.viewer import render_viewer


def test_render_viewer_uses_current_analysis_files(tmp_path: Path) -> None:
    # Given: fresh analysis values and a newly selected example.
    summary = tmp_path / "summary.json"
    examples = tmp_path / "examples.json"
    _ = summary.write_text(
        """{
          "patient_count": 123,
          "exact_agreement": 0.5,
          "discordant_count": 61,
          "weighted_kappa": 0.25
        }""",
        encoding="utf-8",
    )
    _ = examples.write_text(
        """{
          "selection_rule": "current rule",
          "pairs": [{
            "patient_id": 999,
            "left_image": "999_left</script>",
            "right_image": "999_right",
            "left_grade": 1,
            "right_grade": 3,
            "difference": 2
          }]
        }""",
        encoding="utf-8",
    )
    destination = tmp_path / "viewer.html"

    # When: the offline viewer is regenerated.
    render_viewer(summary, examples, destination)
    rendered = destination.read_text(encoding="utf-8")

    # Then: current values replace stale embedded data and script content is safe.
    assert "123" in rendered
    assert "50.00%" in rendered
    assert '"patient_id":999' in rendered
    assert "ID 10" not in rendered
    assert "\\u003c/script\\u003e" in rendered
    assert 'class="zoom"' in rendered
    assert 'data-gap="4"' in rendered
    assert "--paper:#f3f5f2" in rendered
