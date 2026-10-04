"""Generic form tests. All POST requests are intercepted and mocked, so NOTHING is sent to your real backend."""
from urllib.parse import urljoin, urlparse
import pytest

pytestmark = pytest.mark.forms

FIELD_SELECTOR = "input:not([type=hidden]):not([type=submit]):not([type=button]):not([type=image]), textarea, select"
XSS = "<img src=x onerror=alert('xss')>"


@pytest.fixture
def mocked_posts(page):
    posts = []

    def handler(route):
        req = route.request
        if req.method in ("POST", "PUT", "PATCH"):
            posts.append(req)
            route.fulfill(status=200, content_type="application/json", body='{"ok": true, "success": true}')
        else:
            route.continue_()

    page.route("**/*", handler)
    return posts


def _first_form(page, open_page, page_path):
    open_page(page_path)
    forms = page.locator("form:visible")
    if forms.count() == 0:
        pytest.skip(f"No visible form on {page_path}")
    return forms.first


def _fill_valid(form):
    for i in range(form.locator(FIELD_SELECTOR).count()):
        el = form.locator(FIELD_SELECTOR).nth(i)
        if not el.is_visible():
            continue
        kind = (el.get_attribute("type") or el.evaluate("e => e.tagName.toLowerCase()")).lower()
        name = ((el.get_attribute("name") or "") + (el.get_attribute("placeholder") or "")).lower()
        if kind == "email":
            el.fill("qa+autotest@example.com")
        elif kind == "tel":
            el.fill("+911234567890")
        elif kind == "number":
            el.fill("5")
        elif kind == "url":
            el.fill("https://example.com")
        elif kind in ("checkbox", "radio"):
            el.check()
        elif kind == "select":
            if el.locator("option").count() > 1:
                el.select_option(index=1)
        elif kind in ("text", "textarea", "search"):
            el.fill("QA Tester" if "name" in name else "Automated test message - please ignore")


def test_form_fields_have_labels(open_page, page, page_path, assert_empty):
    form = _first_form(page, open_page, page_path)
    unlabeled = form.locator(FIELD_SELECTOR).evaluate_all(
        """els => els.filter(e => e.offsetParent !== null)
            .filter(e => !(e.labels && e.labels.length) && !e.getAttribute('aria-label') && !e.getAttribute('aria-labelledby') && !e.title)
            .map(e => e.outerHTML.slice(0, 90))"""
    )
    assert_empty(unlabeled, "Form fields without a <label>/aria-label (placeholder alone is not enough)")


def test_empty_submit_is_blocked(open_page, page, page_path, mocked_posts):
    form = _first_form(page, open_page, page_path)
    if form.locator("[required], [aria-required=true]").count() == 0:
        pytest.skip("Form has no required fields")
    url_before = page.url
    form.locator("button[type=submit], input[type=submit], button:not([type])").first.click()
    page.wait_for_timeout(1000)
    assert not mocked_posts, "Form submitted with empty required fields"
    assert page.url == url_before


def test_invalid_email_is_rejected(open_page, page, page_path, mocked_posts):
    form = _first_form(page, open_page, page_path)
    email = form.locator("input[type=email]:visible").first
    if email.count() == 0:
        pytest.skip("No email field")
    email.fill("not-an-email")
    assert email.evaluate("e => e.validity.valid") is False, "Browser accepted an invalid email"


def test_xss_payload_not_executed(open_page, page, page_path, mocked_posts):
    form = _first_form(page, open_page, page_path)
    fired = []
    page.on("dialog", lambda d: (fired.append(d.message), d.dismiss()))
    _fill_valid(form)
    for el in form.locator("input[type=text]:visible, textarea:visible").all():
        el.fill(XSS)
    form.locator("button[type=submit], input[type=submit], button:not([type])").first.click()
    page.wait_for_timeout(1500)
    assert not fired, f"XSS payload executed an alert: {fired}"


def test_valid_submission_sends_request(open_page, page, page_path, mocked_posts):
    form = _first_form(page, open_page, page_path)
    _fill_valid(form)
    form.locator("button[type=submit], input[type=submit], button:not([type])").first.click()
    page.wait_for_timeout(2000)
    assert mocked_posts, "Valid submission did not trigger a POST/PUT/PATCH (check your selectors or add a site-specific test)"


def test_form_actions_are_safe(open_page, page, page_path, base_url, assert_empty):
    """Reject insecure, script-based, or unexpected cross-site form destinations."""
    form = _first_form(page, open_page, page_path)
    origin = urlparse(base_url).netloc
    problems = []
    action = (form.get_attribute("action") or page.url).strip()
    method = (form.get_attribute("method") or "get").lower()
    target = urlparse(urljoin(page.url, action))
    if target.scheme not in ("http", "https"):
        problems.append(f"unsupported action {action!r}")
    elif target.scheme != "https":
        problems.append(f"insecure action {target.geturl()}")
    elif target.netloc != origin:
        problems.append(f"cross-site action {target.geturl()}")
    if method not in ("get", "post"):
        problems.append(f"unexpected method {method!r}")
    assert_empty(problems, "Unsafe form actions")


def test_password_fields_are_not_sent_with_get(open_page, page, page_path):
    form = _first_form(page, open_page, page_path)
    if form.locator("input[type=password]").count() == 0:
        pytest.skip("No password field")
    method = (form.get_attribute("method") or "get").lower()
    assert method == "post", f"Password form uses {method.upper()}, exposing credentials in the URL"
