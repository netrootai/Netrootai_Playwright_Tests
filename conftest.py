"""Shared fixtures for the Netroot.AI website test suite."""
import os
import re
from urllib.parse import urldefrag, urljoin, urlparse

import pytest

# Pages tested by every parametrized test. Add more with:
#   EXTRA_PAGES="/about,/pricing,/contact" pytest
PAGES = ["/"] + [p.strip() for p in os.getenv("EXTRA_PAGES", "").split(",") if p.strip()]
MAX_CRAWL = int(os.getenv("MAX_CRAWL", "25"))
ASSET_RE = re.compile(r"\.(pdf|zip|png|jpe?g|gif|svg|webp|avif|mp4|webm|ico|xml|txt|json)$", re.I)


def pytest_generate_tests(metafunc):
    if "page_path" in metafunc.fixturenames:
        metafunc.parametrize("page_path", PAGES, ids=PAGES)


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {**browser_context_args, "locale": "en-US", "viewport": {"width": 1366, "height": 768}}


@pytest.fixture
def open_page(page, base_url):
    """open_page('/about') -> navigates and returns the main response."""

    def _open(path="/", wait_until="load"):
        return page.goto(urljoin(base_url, path), wait_until=wait_until)

    return _open


@pytest.fixture
def assert_empty():
    """Soft-assert helper: report ALL problems at once instead of the first one."""

    def _check(items, title):
        assert not items, f"{title} ({len(items)}):\n  " + "\n  ".join(map(str, items))

    return _check


@pytest.fixture
def console_errors(page):
    errors = []
    page.on("console", lambda m: errors.append(f"console: {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    return errors


@pytest.fixture
def bad_responses(page, base_url):
    """Same-origin responses with a 4xx/5xx status."""
    origin = urlparse(base_url).netloc
    bad = []
    page.on(
        "response",
        lambda r: bad.append(f"{r.status} {r.url}")
        if urlparse(r.url).netloc == origin and r.status >= 400
        else None,
    )
    return bad


class SiteMap:
    def __init__(self):
        self.pages = {}      # url -> HTTP status
        self.external = {}   # external url -> page it was found on


@pytest.fixture(scope="session")
def sitemap(browser, base_url):
    """Crawl internal pages (BFS, up to MAX_CRAWL) using a real browser, so JS-rendered links are found."""
    origin = urlparse(base_url).netloc
    site, queue = SiteMap(), [base_url]
    context = browser.new_context()
    page = context.new_page()
    while queue and len(site.pages) < MAX_CRAWL:
        url = queue.pop(0)
        if url in site.pages:
            continue
        try:
            resp = page.goto(url, wait_until="load", timeout=30000)
            site.pages[url] = resp.status if resp else 0
        except Exception:
            site.pages[url] = 0
            continue
        if site.pages[url] >= 400:
            continue
        for href in page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)"):
            href, _ = urldefrag(href)
            parsed = urlparse(href)
            if parsed.scheme not in ("http", "https"):
                continue
            if parsed.netloc == origin:
                if href not in site.pages and href not in queue and not ASSET_RE.search(parsed.path):
                    queue.append(href)
            else:
                site.external.setdefault(href, url)
    context.close()
    return site
