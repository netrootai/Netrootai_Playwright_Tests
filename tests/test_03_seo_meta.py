import json
import os
import xml.etree.ElementTree as ET
from urllib.parse import urljoin

import pytest

pytestmark = pytest.mark.seo


def _meta(page, selector):
    loc = page.locator(selector)
    return (loc.first.get_attribute("content") or "").strip() if loc.count() else ""


def test_title_length(open_page, page, page_path):
    open_page(page_path)
    title = page.title().strip()
    assert 10 <= len(title) <= 70, f"Title length {len(title)}: {title!r}"


def test_meta_description(open_page, page, page_path):
    open_page(page_path)
    desc = _meta(page, "meta[name=description]")
    assert 50 <= len(desc) <= 170, f"Description length {len(desc)}: {desc!r}"


def test_single_h1(open_page, page, page_path):
    open_page(page_path)
    assert page.locator("h1:visible").count() == 1, f"Found {page.locator('h1:visible').count()} visible <h1>"


def test_heading_hierarchy_has_no_skips(open_page, page, page_path):
    open_page(page_path)
    levels = page.eval_on_selector_all("h1,h2,h3,h4,h5,h6", "els => els.map(e => +e.tagName[1])")
    skips = [(a, b) for a, b in zip(levels, levels[1:]) if b - a > 1]
    assert not skips, f"Heading level jumps (from, to): {skips}"


def test_html_lang_and_viewport(open_page, page, page_path):
    open_page(page_path)
    assert page.locator("html").get_attribute("lang"), "<html lang> missing"
    assert "width=device-width" in _meta(page, "meta[name=viewport]"), "viewport meta missing/incorrect"


def test_canonical_url(open_page, page, page_path):
    open_page(page_path)
    href = page.locator("link[rel=canonical]").first.get_attribute("href") if page.locator("link[rel=canonical]").count() else None
    assert href and href.startswith("http"), f"Canonical missing or not absolute: {href!r}"


def test_open_graph_and_twitter_tags(open_page, page, page_path, assert_empty):
    open_page(page_path)
    required = {
        "og:title": "meta[property='og:title']",
        "og:description": "meta[property='og:description']",
        "og:image": "meta[property='og:image']",
        "og:url": "meta[property='og:url']",
        "twitter:card": "meta[name='twitter:card']",
    }
    assert_empty([k for k, sel in required.items() if not _meta(page, sel)], "Missing social tags")


def test_not_blocking_search_engines(open_page, page, page_path):
    if os.getenv("ALLOW_NOINDEX"):
        pytest.skip("ALLOW_NOINDEX set (staging)")
    open_page(page_path)
    robots = _meta(page, "meta[name=robots]").lower()
    assert "noindex" not in robots, f"Page has meta robots: {robots}"


def test_robots_txt(page, base_url):
    resp = page.request.get(urljoin(base_url, "/robots.txt"))
    assert resp.ok, f"/robots.txt -> {resp.status}"
    body = resp.text().lower()
    assert "user-agent" in body, "robots.txt has no User-agent directive (maybe HTML fallback?)"
    if not os.getenv("ALLOW_NOINDEX"):
        compact = [line.replace(" ", "") for line in body.splitlines()]
        assert "disallow:/" not in compact, "robots.txt blocks the entire site"


def test_sitemap_xml(page, base_url):
    resp = page.request.get(urljoin(base_url, "/sitemap.xml"))
    assert resp.ok, f"/sitemap.xml -> {resp.status}"
    root = ET.fromstring(resp.body())
    assert root.tag.endswith(("urlset", "sitemapindex")), f"Unexpected root: {root.tag}"


def test_structured_data_is_valid_json(open_page, page, page_path, assert_empty):
    open_page(page_path)
    errors = []
    for raw in page.eval_on_selector_all("script[type='application/ld+json']", "els => els.map(e => e.textContent)"):
        try:
            json.loads(raw)
        except ValueError as exc:
            errors.append(str(exc))
    assert_empty(errors, "Invalid JSON-LD blocks")
