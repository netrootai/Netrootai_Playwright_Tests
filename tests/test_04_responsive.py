from pathlib import Path

import pytest

pytestmark = pytest.mark.responsive

VIEWPORTS = {
    "mobile-375": (375, 667),
    "mobile-small-320": (320, 568),
    "tablet-768": (768, 1024),
    "laptop-1366": (1366, 768),
    "desktop-1920": (1920, 1080),
}

OFFENDERS_JS = """() => {
  const w = document.documentElement.clientWidth;
  return [...document.querySelectorAll('body *')]
    .filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.right > w + 1 && getComputedStyle(e).position !== 'fixed'; })
    .slice(0, 8)
    .map(e => e.tagName.toLowerCase() + (e.className && typeof e.className === 'string' ? '.' + e.className.trim().split(/\\s+/).join('.') : ''));
}"""


@pytest.mark.parametrize("vp", VIEWPORTS, ids=VIEWPORTS)
def test_no_horizontal_scroll(page, open_page, page_path, vp):
    page.set_viewport_size(dict(zip(("width", "height"), VIEWPORTS[vp])))
    open_page(page_path)
    page.wait_for_timeout(800)
    overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    if overflow > 1:
        pytest.fail(f"Horizontal overflow of {overflow}px at {vp}. Likely culprits: {page.evaluate(OFFENDERS_JS)}")


@pytest.mark.parametrize("vp", VIEWPORTS, ids=VIEWPORTS)
def test_screenshot_for_visual_review(page, open_page, browser_name, vp):
    """Saves full-page screenshots to test-results/screens/ for a quick manual look."""
    page.set_viewport_size(dict(zip(("width", "height"), VIEWPORTS[vp])))
    open_page("/")
    page.wait_for_timeout(800)
    out = Path("test-results/screens")
    out.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(out / f"home-{browser_name}-{vp}.png"), full_page=True)
    assert page.locator("h1:visible").count() >= 1, "No visible <h1> above/below the fold"


def test_mobile_navigation_usable(page, open_page):
    page.set_viewport_size({"width": 375, "height": 667})
    open_page("/")
    visible_links = "header a[href]:visible, nav a[href]:visible"
    if page.locator(visible_links).count():
        return
    toggle = page.locator("header button:visible, nav button:visible, [aria-label*='menu' i]:visible, [aria-controls]:visible")
    assert toggle.count(), "No visible nav links and no menu toggle on mobile"
    toggle.first.click()
    page.wait_for_timeout(500)
    assert page.locator(visible_links).count(), "Menu toggle did not reveal any navigation links"


def test_text_not_tiny_on_mobile(page, open_page):
    page.set_viewport_size({"width": 375, "height": 667})
    open_page("/")
    small = page.evaluate(
        """() => [...document.querySelectorAll('p, li, a, span')]
            .filter(e => e.offsetParent !== null && e.innerText && e.innerText.trim().length > 20)
            .filter(e => parseFloat(getComputedStyle(e).fontSize) < 12)
            .slice(0, 5).map(e => e.innerText.trim().slice(0, 40))"""
    )
    assert not small, f"Text under 12px on mobile: {small}"
