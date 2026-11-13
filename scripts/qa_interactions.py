"""Interaction-state capture helpers for the browser QA script."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

if TYPE_CHECKING:
    from pathlib import Path

    from playwright.sync_api import Browser, Locator, Page


@dataclass(frozen=True, slots=True)
class CaptureConfig:
    """Shared locations used by browser interaction captures."""

    root: Path
    output: Path
    base_url: str


class InteractionStateError(RuntimeError):
    """Raised when a required keyboard state does not settle."""

    @override
    def __str__(self) -> str:
        """Describe the failed interaction state."""
        return "required keyboard interaction state did not settle"


class DownloadError(RuntimeError):
    """Raised when the expected artifact download fails."""

    @override
    def __str__(self) -> str:
        """Describe the failed artifact download."""
        return "pairs download failed"


def assert_no_horizontal_overflow(page: Page, viewport: int) -> int:
    """Return document width or fail when it exceeds the viewport."""
    root = page.locator("html")
    handle = root.evaluate_handle(
        "element => element.setAttribute('data-qa-scroll-width', String(element.scrollWidth))",
    )
    handle.dispose()
    raw_width = root.get_attribute("data-qa-scroll-width")
    if raw_width is None:
        message = "browser did not expose the scroll width"
        raise RuntimeError(message)
    scroll_width = int(raw_width)
    if scroll_width > viewport:
        message = f"horizontal overflow: viewport={viewport}, scrollWidth={scroll_width}"
        raise RuntimeError(message)
    return scroll_width


def prepare_full_page_capture(page: Page) -> None:
    """Neutralize fixed layers that Chrome duplicates while stitching."""
    handle = page.locator("html").evaluate_handle("() => window.scrollTo(0, 0)")
    handle.dispose()
    style = page.add_style_tag(
        content=".topbar-wrap{position:relative!important}.skip-link{position:absolute!important}",
    )
    style.dispose()


def capture_prediction_states(browser: Browser, config: CaptureConfig) -> tuple[str, ...]:
    """Capture invalid drop, live demo output, image-mode keys, and responsive results."""
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    _ = page.goto(f"{config.base_url}/#model", wait_until="networkidle")
    upload_well = page.locator("#upload-well")
    _drop_file(upload_well, page, "not-retina.txt", "text/plain", b"invalid")
    page.locator("#upload-error").get_by_text("JPEG 또는 PNG").wait_for(state="visible")
    invalid = config.output / "prediction-invalid.png"
    _ = page.screenshot(path=invalid, full_page=True)
    demo = page.locator(".demo-button").first
    demo.wait_for(state="visible")
    demo.click()
    page.locator("#result-content").wait_for(state="visible", timeout=240_000)
    page.locator("#result-context").get_by_text("실제 라벨").wait_for(state="visible")
    prepare_full_page_capture(page)
    valid = config.output / "prediction-valid-demo.png"
    _ = page.screenshot(path=valid, full_page=True)
    original = page.locator("#view-original")
    sensitivity_mode = page.locator("#view-sensitivity")
    original.focus()
    original.press("End")
    focused_id = page.locator(":focus").get_attribute("id")
    if sensitivity_mode.get_attribute("aria-pressed") != "true" or focused_id != "view-sensitivity":
        raise InteractionStateError
    page.locator("#sensitivity-image").wait_for(state="visible")
    sensitivity = config.output / "prediction-sensitivity.png"
    _ = page.screenshot(path=sensitivity, full_page=True)
    sensitivity_mode.press("Home")
    original.press("ArrowRight")
    sensitivity_mode.press("ArrowLeft")
    original.press("End")
    sensitivity_mode.press("Home")
    responsive: list[str] = []
    for width in (375, 768):
        page.set_viewport_size({"width": width, "height": 900})
        _ = assert_no_horizontal_overflow(page, width)
        shot = config.output / f"prediction-valid-demo-{width}.png"
        _ = page.screenshot(path=shot, full_page=True)
        responsive.append(str(shot.relative_to(config.root)))
    context.close()
    return (
        str(invalid.relative_to(config.root)),
        str(valid.relative_to(config.root)),
        responsive[0],
        responsive[1],
        str(sensitivity.relative_to(config.root)),
    )


def capture_filters_and_download(browser: Browser, config: CaptureConfig) -> tuple[str, ...]:
    """Capture task-tab keys, gap-filter keys, offline filter, and one download."""
    context = browser.new_context(viewport={"width": 1280, "height": 900}, accept_downloads=True)
    page = context.new_page()
    _ = page.goto(f"{config.base_url}/#analysis", wait_until="networkidle")
    analysis_tab = page.locator("#tab-analysis")
    model_tab = page.locator("#tab-model")
    analysis_tab.focus()
    analysis_tab.press("End")
    task_state = (
        model_tab.get_attribute("aria-selected") == "true"
        and page.locator(":focus").get_attribute("id") == "tab-model"
        and page.url.rsplit("#", 1)[-1] == "model"
        and page.locator("#panel-model").is_visible()
    )
    if not task_state:
        raise InteractionStateError
    prepare_full_page_capture(page)
    task_tabs = config.output / "keyboard-task-tabs.png"
    _ = page.screenshot(path=task_tabs, full_page=True)
    model_tab.press("Home")
    analysis_tab.press("ArrowRight")
    model_tab.press("ArrowLeft")
    all_gap = page.locator('[data-gap="all"]')
    gap = page.locator('[data-gap="4"]')
    all_gap.focus()
    all_gap.press("End")
    if (
        gap.get_attribute("aria-pressed") != "true"
        or page.locator(":focus").get_attribute("data-gap") != "4"
    ):
        raise InteractionStateError
    page.locator("#gap-filter-status").get_by_text("2개").wait_for(state="visible")
    page.locator("#case-title").get_by_text("등급 차이 4").wait_for(state="visible")
    prepare_full_page_capture(page)
    analysis = config.output / "analysis-gap-4.png"
    _ = page.screenshot(path=analysis, full_page=True)
    gap.press("Home")
    all_gap.press("ArrowRight")
    page.locator('[data-gap="0"]').press("ArrowLeft")
    page.locator("#gap-filter-status").get_by_text("10개").wait_for(state="visible")
    with page.expect_download() as download_info:
        page.get_by_role("link", name="양안 쌍 CSV").click()
    download = download_info.value
    if download.failure() is not None:
        raise DownloadError
    viewer = config.root / "outputs" / "assignment1" / "viewer.html"
    _ = page.goto(viewer.as_uri(), wait_until="load")
    page.locator('[data-gap="4"]').click()
    page.locator("#case-filter-count").get_by_text("2개").wait_for(state="visible")
    page.locator("#case-title").get_by_text("등급 차이 4").wait_for(state="visible")
    offline = config.output / "assignment1-offline-gap-4.png"
    _ = page.screenshot(path=offline, full_page=True)
    page.get_by_role("button", name="전체").click()
    page.locator("#case-filter-count").get_by_text("10개").wait_for(state="visible")
    context.close()
    return (
        str(analysis.relative_to(config.root)),
        str(offline.relative_to(config.root)),
        download.suggested_filename,
        str(task_tabs.relative_to(config.root)),
    )


def capture_reduced_motion(browser: Browser, config: CaptureConfig) -> str:
    """Capture a settled reduced-motion filter transition."""
    context = browser.new_context(viewport={"width": 768, "height": 900}, reduced_motion="reduce")
    page = context.new_page()
    _ = page.goto(f"{config.base_url}/#analysis", wait_until="networkidle")
    page.locator('[data-gap="2"]').click()
    page.locator("#case-title").get_by_text("등급 차이 2").wait_for(state="visible")
    page.locator(".retina-image.is-changing").wait_for(state="detached")
    prepare_full_page_capture(page)
    shot = config.output / "analysis-reduced-motion.png"
    _ = page.screenshot(path=shot, full_page=True)
    context.close()
    return str(shot.relative_to(config.root))


def _drop_file(upload_well: Locator, page: Page, name: str, mime_type: str, content: bytes) -> None:
    encoded = base64.b64encode(content).decode("ascii")
    transfer = page.evaluate_handle(
        """payload => {
          const bytes = Uint8Array.from(atob(payload.content), char => char.charCodeAt(0));
          const transfer = new DataTransfer();
          transfer.items.add(new File([bytes], payload.name, {type: payload.mimeType}));
          return transfer;
        }""",
        {"name": name, "mimeType": mime_type, "content": encoded},
    )
    upload_well.dispatch_event("dragenter", {"dataTransfer": transfer})
    upload_well.dispatch_event("dragover", {"dataTransfer": transfer})
    upload_well.dispatch_event("drop", {"dataTransfer": transfer})
    transfer.dispose()
