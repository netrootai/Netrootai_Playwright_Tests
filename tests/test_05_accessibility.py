import pytest

axe_mod = pytest.importorskip("axe_playwright_python.sync_playwright", reason="pip install axe-playwright-python")

pytestmark = pytest.mark.a11y


def test_axe_no_serious_violations(open_page, page, page_path):
    open_page(page_path)
    page.wait_for_timeout(1000)
    results = axe_mod.Axe().run(
        page, options={"runOnly": {"type": "tag", "values": ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]}}
    )
    bad = [v for v in results.response["violations"] if v["impact"] in ("serious", "critical")]
    report = "\n".join(f"[{v['impact']}] {v['id']}: {v['help']} ({len(v['nodes'])} nodes) {v['helpUrl']}" for v in bad)
    assert not bad, f"\n{report}"


def test_images_have_alt_attribute(open_page, page, page_path, assert_empty):
    open_page(page_path)
    missing = page.eval_on_selector_all("img:not([alt])", "els => els.map(e => e.currentSrc || e.src)")
    assert_empty(missing, "<img> without alt (use alt='' for decorative images)")


def test_links_and_buttons_have_accessible_names(open_page, page, page_path, assert_empty):
    open_page(page_path)
    unnamed = page.evaluate(
        """() => [...document.querySelectorAll('a[href], button, [role=button]')]
            .filter(e => e.offsetParent !== null)
            .filter(e => !(e.innerText || '').trim() && !e.getAttribute('aria-label') && !e.getAttribute('aria-labelledby')
                         && !e.getAttribute('title') && !e.querySelector('img[alt]:not([alt=""])'))
            .map(e => e.outerHTML.slice(0, 100))"""
    )
    assert_empty(unnamed, "Interactive elements with no accessible name")


def test_keyboard_tab_reaches_interactive_elements(open_page, page, page_path):
    open_page(page_path)
    focused = set()
    for _ in range(8):
        page.keyboard.press("Tab")
        focused.add(page.evaluate("(() => { const a = document.activeElement; return a ? a.tagName + '|' + (a.href || a.id || a.innerText || '').slice(0, 40) : ''; })()"))
    focused.discard("BODY|")
    assert len(focused) >= 3, f"Keyboard focus moved through too few elements: {focused}"


def test_focus_is_visible(open_page, page, page_path):
    open_page(page_path)
    page.keyboard.press("Tab")
    has_indicator = page.evaluate(
        """() => { const s = getComputedStyle(document.activeElement);
            return (s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0) || s.boxShadow !== 'none'; }"""
    )
    assert has_indicator, "First focused element has no visible focus indicator (outline/box-shadow)"


def test_page_zoom_200_percent_no_overflow(open_page, page):
    """200% zoom is equivalent to a 640px-wide viewport (WCAG 1.4.4 / 1.4.10)."""
    page.set_viewport_size({"width": 640, "height": 360})
    open_page("/")
    page.wait_for_timeout(500)
    assert page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") <= 1
