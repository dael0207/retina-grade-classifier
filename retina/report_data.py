"""Typed boundaries for report input artifacts."""

from pathlib import Path
from typing import Final

from pydantic import TypeAdapter, ValidationError

ROOT: Final = Path(__file__).resolve().parents[1]
type JsonValue = str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]
JSON_OBJECT: Final = TypeAdapter(dict[str, JsonValue])
JSON_ARRAY: Final = TypeAdapter(list[JsonValue])


class ReportDataError(RuntimeError):
    """Required analysis evidence is missing or malformed."""


def load_json_required(path: Path, required: frozenset[str]) -> dict[str, JsonValue]:
    """Load a report artifact and enforce its top-level contract."""
    if not path.exists():
        message = f"Required report artifact is missing: {path}"
        raise ReportDataError(message)
    try:
        data = JSON_OBJECT.validate_json(path.read_bytes())
    except ValidationError as error:
        message = f"Invalid JSON report artifact: {path}"
        raise ReportDataError(message) from error
    missing = required - data.keys()
    if missing:
        message = f"Missing required keys in {path}: {', '.join(sorted(missing))}"
        raise ReportDataError(message)
    return data


def load_json_array(path: Path) -> list[JsonValue]:
    """Load a required top-level JSON array used by a report."""
    if not path.exists():
        message = f"Required report artifact is missing: {path}"
        raise ReportDataError(message)
    try:
        return JSON_ARRAY.validate_json(path.read_bytes())
    except ValidationError as error:
        message = f"Invalid JSON report artifact: {path}"
        raise ReportDataError(message) from error
