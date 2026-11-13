"""Generate the no-server assignment 1 viewer from current analysis artifacts."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Final, override

from pydantic import BaseModel, ConfigDict

TEMPLATE_PATH: Final = Path(__file__).with_name("templates") / "assignment1_viewer.html"
DESTINATION_ARGUMENT_COUNT: Final = 3


class ViewerSummary(BaseModel):
    """Analysis values displayed in the standalone viewer header."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore")
    patient_count: int
    exact_agreement: float
    discordant_count: int
    weighted_kappa: float


class ViewerPair(BaseModel):
    """One bilateral case available in the standalone viewer carousel."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore")
    patient_id: int
    left_image: str
    right_image: str
    left_grade: int
    right_grade: int
    difference: int


class ViewerExamples(BaseModel):
    """Current deterministic example selection embedded for offline use."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore")
    selection_rule: str
    pairs: tuple[ViewerPair, ...]


@dataclass(frozen=True, slots=True)
class ViewerTemplateError(RuntimeError):
    """Raised when the checked-in template no longer exposes a required token."""

    token: str

    @override
    def __str__(self) -> str:
        return f"viewer template token is missing: {self.token}"


def _safe_script_json(examples: ViewerExamples) -> str:
    payload = json.dumps(
        examples.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":")
    )
    return (
        payload.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def render_viewer(summary_path: Path, examples_path: Path, destination: Path) -> None:
    """Render a self-contained HTML viewer from the latest JSON outputs."""
    summary = ViewerSummary.model_validate_json(summary_path.read_text(encoding="utf-8"))
    examples = ViewerExamples.model_validate_json(examples_path.read_text(encoding="utf-8"))
    replacements = {
        "{{PATIENT_COUNT}}": f"{summary.patient_count:,}",
        "{{EXACT_AGREEMENT_PERCENT}}": f"{summary.exact_agreement:.2%}",
        "{{DISCORDANT_COUNT}}": f"{summary.discordant_count:,}",
        "{{WEIGHTED_KAPPA}}": f"{summary.weighted_kappa:.3f}",
        "{{EXAMPLES_JSON}}": _safe_script_json(examples),
    }
    rendered = TEMPLATE_PATH.read_text(encoding="utf-8")
    for token, value in replacements.items():
        if token not in rendered:
            raise ViewerTemplateError(token)
        rendered = rendered.replace(token, value)
    destination.parent.mkdir(parents=True, exist_ok=True)
    _ = destination.write_text(rendered, encoding="utf-8")


def main() -> int:
    """Regenerate the default viewer or paths supplied on the command line."""
    arguments = sys.argv[1:]
    summary = Path(arguments[0]) if arguments else Path("outputs/assignment1/summary.json")
    examples = (
        Path(arguments[1]) if len(arguments) > 1 else Path("outputs/assignment1/examples.json")
    )
    destination = (
        Path(arguments[2])
        if len(arguments) >= DESTINATION_ARGUMENT_COUNT
        else Path("outputs/assignment1/viewer.html")
    )
    render_viewer(summary, examples, destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
