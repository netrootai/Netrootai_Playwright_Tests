from urllib.parse import urljoin, urlparse

import pytest

pytestmark = pytest.mark.smoke


def test_page_loads(open_page, page, page_path):
    response = open_page(page_path)
    assert response is not None and response.status < 400, f"Bad status: {response and response.status}"
    assert page.title().strip(), "Page has no <title>"
    assert page.locator("body").is_visible()
    assert len(page.inner_text("body").strip()) > 50, "Page looks blank"


def test_no_javascript_errors(open_page, page, page_path, console_errors, assert_empty):
    open_page(page_path)
    page.wait_for_timeout(1500)
    assert_empty(console_errors, "Console / JS errors")


def test_no_failed_same_origin_requests(open_page, page, page_path, bad_responses, assert_empty):
    open_page(page_path)
    page.wait_for_timeout(1500)
    assert_empty(bad_responses, "Same-origin 4xx/5xx responses")


def test_http_redirects_to_https(page, base_url):
    parsed = urlparse(base_url)
    if parsed.scheme != "https":
        pytest.skip("Base URL is not https")
    page.goto(f"http://{parsed.netloc}/")
    assert page.url.startswith("https://"), f"Ended on {page.url}"


def test_unknown_url_returns_404(page, base_url):
    """A 200 for a nonsense URL is a 'soft 404' (bad for SEO, common on SPAs)."""
    response = page.goto(urljoin(base_url, "/this-page-should-not-exist-9f8e7d6c"))
    assert response.status == 404, f"Expected 404, got {response.status}"
    assert page.inner_text("body").strip(), "404 page is blank"


def test_favicon_present(page, open_page, base_url):
    open_page("/")
    if page.locator("link[rel~='icon']").count():
        return
    assert page.request.get(urljoin(base_url, "/favicon.ico")).ok, "No <link rel=icon> and /favicon.ico missing"


def test_page_landmarks(open_page, page, page_path):
    open_page(page_path)
    missing = [
        name
        for name, sel in {
            "header/nav": "header, nav, [role=banner], [role=navigation]",
            "main": "main, [role=main]",
            "footer": "footer, [role=contentinfo]",
        }.items()
        if page.locator(sel).count() == 0
    ]
    assert not missing, f"Missing landmarks: {missing}"


def test_reload_keeps_page_working(open_page, page, page_path):
    open_page(page_path)
    response = page.reload()
    assert response.status < 400
    assert page.locator("body").is_visible()
