#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "playwright>=1.65.0",
# ]
# ///

# ─── How to run ───
# 1. Start the local server on port 8765.
# 2. Run: uv run scripts/qa_ui.py
# ──────────────────

"""Capture responsive and interaction evidence for the local research app."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

from playwright.sync_api import Browser, sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.qa_interactions import (  # noqa: E402 - supports direct PEP 723 execution
    CaptureConfig,
    assert_no_horizontal_overflow,
    capture_filters_and_download,
    capture_prediction_states,
    capture_reduced_motion,
)

ROOT: Final = PROJECT_ROOT
OUTPUT: Final = ROOT / "output" / "qa"
CHROME: Final = Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe")
BASE_URL: Final = "http://127.0.0.1:8765"
CONFIG: Final = CaptureConfig(root=ROOT, output=OUTPUT, base_url=BASE_URL)


@dataclass(frozen=True, slots=True)
class ViewportEvidence:
    """Paths and overflow evidence captured at one viewport width."""

    viewport: int
    scroll_width: int
    analysis: str
    model: str
    showcase: str
    offline: str


def _capture_viewport(browser: Browser, viewport: int) -> ViewportEvidence:
    context = browser.new_context(viewport={"width": viewport, "height": 900})
    page = context.new_page()
    _ = page.goto(f"{BASE_URL}/#analysis", wait_until="networkidle")
    scroll_width = assert_no_horizontal_overflow(page, viewport)
    analysis = OUTPUT / f"analysis-{viewport}.png"
    _ = page.screenshot(path=analysis, full_page=True)
    page.get_by_role("tab", name="과제 2 · 등급 분류").click()
    model = OUTPUT / f"model-{viewport}.png"
    _ = page.screenshot(path=model, full_page=True)
    _ = assert_no_horizontal_overflow(page, viewport)
    _ = page.goto(f"{BASE_URL}/showcase", wait_until="networkidle")
    showcase = OUTPUT / f"showcase-{viewport}.png"
    _ = page.screenshot(path=showcase, full_page=True)
    _ = assert_no_horizontal_overflow(page, viewport)
    viewer = ROOT / "outputs" / "assignment1" / "viewer.html"
    _ = page.goto(viewer.as_uri(), wait_until="load")
    offline = OUTPUT / f"assignment1-offline-{viewport}.png"
    _ = page.screenshot(path=offline, full_page=True)
    _ = assert_no_horizontal_overflow(page, viewport)
    context.close()
    return ViewportEvidence(
        viewport=viewport,
        scroll_width=scroll_width,
        analysis=str(analysis.relative_to(ROOT)),
        model=str(model.relative_to(ROOT)),
        showcase=str(showcase.relative_to(ROOT)),
        offline=str(offline.relative_to(ROOT)),
    )


def _capture_fullsize_chart(browser: Browser) -> str:
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    viewer = ROOT / "outputs" / "assignment1" / "viewer.html"
    _ = page.goto(viewer.as_uri(), wait_until="load")
    with page.expect_popup() as popup_info:
        page.get_by_role("link", name="원본 크기로 보기").first.click()
    popup = popup_info.value
    popup.wait_for_load_state("load")
    chart = OUTPUT / "assignment1-chart-fullsize.png"
    _ = popup.screenshot(path=chart, full_page=True)
    context.close()
    return str(chart.relative_to(ROOT))


def main() -> None:
    """Capture every required responsive and interaction state."""
    _ = OUTPUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=CHROME)
        viewports = [_capture_viewport(browser, width) for width in (375, 768, 1280)]
        invalid, valid, valid_375, valid_768, sensitivity = capture_prediction_states(
            browser,
            CONFIG,
        )
        analysis_filter, offline_filter, download_name, task_tabs = capture_filters_and_download(
            browser, CONFIG
        )
        reduced_motion = capture_reduced_motion(browser, CONFIG)
        fullsize_chart = _capture_fullsize_chart(browser)
        browser.close()
    evidence = {
        "viewports": [asdict(item) for item in viewports],
        "interactions": {
            "analysis_gap_filter": analysis_filter,
            "offline_gap_filter": offline_filter,
            "prediction_invalid": invalid,
            "prediction_valid": valid,
            "prediction_valid_375": valid_375,
            "prediction_valid_768": valid_768,
            "prediction_sensitivity": sensitivity,
            "download_name": download_name,
            "reduced_motion": reduced_motion,
            "keyboard_task_tabs": task_tabs,
            "keyboard_task_state": "End/Home/ArrowRight/ArrowLeft: selection, focus, hash, panel",
            "keyboard_gap_state": "End/Home/ArrowRight/ArrowLeft: selection and single tab stop",
            "keyboard_image_mode_state": "End/Home/ArrowRight/ArrowLeft: image and single tab stop",
        },
        "prediction_invalid": invalid,
        "prediction_valid": valid,
        "prediction_sensitivity": sensitivity,
        "drop_tested": True,
        "fullsize_chart": fullsize_chart,
    }
    _ = (OUTPUT / "evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
