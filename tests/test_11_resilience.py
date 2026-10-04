"""Graceful-degradation and loaded-resource checks that do not mutate production data."""
from urllib.parse import urlparse

import pytest

pytestmark = pytest.mark.resilience


def test_homepage_is_usable_without_javascript(browser, base_url):
    """A marketing site should retain a meaningful, crawlable HTML fallback."""
    context = browser.new_context(java_script_enabled=False)
    page = context.new_page()
    try:
        response = page.goto(base_url, wait_until="domcontentloaded")
        assert response is not None and response.status < 400
        assert page.locator("body").inner_text().strip(), "No useful no-JavaScript fallback content"
        assert page.locator("h1").count(), "No H1 available without JavaScript"
    finally:
        context.close()


def test_first_party_script_responses_are_javascript(page, base_url, assert_empty):
    """Detect HTML error pages or misconfigured responses served as JavaScript."""
    origin = urlparse(base_url).netloc
    scripts = []
    page.on(
        "response",
        lambda response: scripts.append(response)
        if response.request.resource_type == "script" and urlparse(response.url).netloc == origin
        else None,
    )
    page.goto(base_url, wait_until="load")
    invalid = []
    for response in scripts:
        content_type = response.headers.get("content-type", "").lower()
        if not response.ok or ("javascript" not in content_type and "ecmascript" not in content_type):
            invalid.append(f"{response.status} {content_type or 'missing content type'} {response.url}")
    assert_empty(invalid, "Invalid first-party script responses")
