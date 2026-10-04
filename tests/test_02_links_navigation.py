import re
from urllib.parse import urldefrag, urlparse

import pytest

pytestmark = pytest.mark.links

# Sites often block bots on these; treat as "can't tell", not "broken".
BOT_BLOCKED = {401, 403, 405, 406, 429, 999}


def test_internal_pages_not_broken(sitemap, assert_empty):
    broken = [f"{status or 'ERR'} {url}" for url, status in sitemap.pages.items() if status == 0 or status >= 400]
    assert_empty(broken, f"Broken internal pages (crawled {len(sitemap.pages)})")


def test_external_links_reachable(sitemap, page, assert_empty):
    failures = []
    for url, found_on in sitemap.external.items():
        try:
            status = page.request.get(url, timeout=15000, max_redirects=5).status
        except Exception as exc:
            failures.append(f"ERR {url} (on {found_on}): {str(exc)[:80]}")
            continue
        if status >= 400 and status not in BOT_BLOCKED:
            failures.append(f"{status} {url} (on {found_on})")
    assert_empty(failures, "Broken external links")


def test_nav_links_navigate(open_page, page, base_url, assert_empty):
    open_page("/")
    hrefs = page.eval_on_selector_all(
        "header a[href], nav a[href]",
        "els => els.filter(e => e.offsetParent !== null).map(e => e.href)",
    )
    host = urlparse(base_url).netloc
    targets = sorted({urldefrag(h)[0] for h in hrefs if urlparse(h).netloc == host and urlparse(h).scheme.startswith("http")})
    if not targets:
        pytest.skip("No visible internal nav links found")
    failures = []
    for url in targets:
        resp = page.goto(url)
        if resp is None or resp.status >= 400:
            failures.append(f"{resp and resp.status} {url}")
        elif not page.title().strip():
            failures.append(f"no title: {url}")
    assert_empty(failures, "Nav links that failed")


def test_logo_links_home(open_page, page, base_url):
    open_page("/")
    logo = page.locator("header a:has(img), header a:has(svg), a[class*=logo i], a[aria-label*=home i]").first
    if logo.count() == 0:
        pytest.skip("No logo link detected")
    logo.click()
    page.wait_for_load_state("load")
    assert urlparse(page.url).path in ("", "/"), f"Logo went to {page.url}"


def test_external_links_target_blank_safe(open_page, page, page_path, assert_empty):
    open_page(page_path)
    bad = page.eval_on_selector_all(
        "a[target=_blank]",
        """els => els.filter(e => !/(noopener|noreferrer)/.test(e.rel)).map(e => e.href)""",
    )
    assert_empty(bad, "target=_blank links without rel=noopener/noreferrer")


def test_anchor_links_have_targets(open_page, page, page_path, assert_empty):
    open_page(page_path)
    missing = page.evaluate(
        """() => [...document.querySelectorAll('a[href^="#"]')]
            .map(a => a.getAttribute('href'))
            .filter(h => h.length > 1)
            .filter(h => !document.getElementById(decodeURIComponent(h.slice(1))) && !document.getElementsByName(h.slice(1)).length)"""
    )
    assert_empty(sorted(set(missing)), "In-page anchors with no matching target")


def test_no_dead_hash_links(open_page, page, page_path, assert_empty):
    open_page(page_path)
    dead = page.eval_on_selector_all(
        "a[href='#'], a[href=''], a[href^='javascript:']",
        "els => els.map(e => (e.innerText || e.getAttribute('aria-label') || e.outerHTML).trim().slice(0, 60))",
    )
    assert_empty(dead, "Placeholder links (href='#' / javascript:)")


def test_mailto_and_tel_are_valid(open_page, page, page_path, assert_empty):
    open_page(page_path)
    hrefs = page.eval_on_selector_all("a[href^='mailto:'], a[href^='tel:']", "els => els.map(e => e.getAttribute('href'))")
    bad = [
        h for h in hrefs
        if not (re.fullmatch(r"mailto:[^@\s]+@[^@\s]+\.[^@\s?]+(\?.*)?", h) or re.fullmatch(r"tel:\+?[\d\s\-().]{6,}", h))
    ]
    assert_empty(bad, "Malformed mailto:/tel: links")


def test_images_load(open_page, page, page_path, assert_empty):
    open_page(page_path)
    page.evaluate("async () => { for (let y = 0; y < document.body.scrollHeight; y += 600) { window.scrollTo(0, y); await new Promise(r => setTimeout(r, 120)); } }")
    page.wait_for_timeout(800)
    broken = page.evaluate(
        """() => [...document.images]
            .filter(i => i.offsetParent !== null && !/\\.svg(\\?|$)/i.test(i.currentSrc || i.src))
            .filter(i => !i.complete || i.naturalWidth === 0)
            .map(i => i.currentSrc || i.src)"""
    )
    assert_empty(broken, "Images that failed to load")


def test_browser_back_forward(open_page, page, base_url):
    open_page("/")
    link = page.locator(f"header a[href^='/']:visible, nav a[href^='/']:visible").first
    if link.count() == 0:
        pytest.skip("No internal link to click")
    link.click()
    page.wait_for_load_state("load")
    destination = page.url
    page.go_back()
    assert urlparse(page.url).path in ("", "/") or page.url != destination
    page.go_forward()
    assert page.url == destination
