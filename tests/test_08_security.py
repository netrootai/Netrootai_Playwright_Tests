"""Basic security hygiene checks. Run only against sites you own."""
import re
import warnings
from urllib.parse import urljoin, urlparse

import pytest

pytestmark = pytest.mark.security


@pytest.fixture
def home_headers(page, base_url):
    return {k.lower(): v for k, v in page.request.get(base_url).headers.items()}


def test_hsts_enabled(home_headers):
    hsts = home_headers.get("strict-transport-security", "")
    assert "max-age" in hsts, "Missing Strict-Transport-Security header"
    assert int(re.search(r"max-age=(\d+)", hsts).group(1)) >= 15552000, f"HSTS max-age too low: {hsts}"


def test_content_type_options(home_headers):
    assert home_headers.get("x-content-type-options", "").lower() == "nosniff"


def test_clickjacking_protection(home_headers):
    csp = home_headers.get("content-security-policy", "")
    assert home_headers.get("x-frame-options") or "frame-ancestors" in csp, "Need X-Frame-Options or CSP frame-ancestors"


def test_recommended_headers_present(home_headers):
    """Not hard failures; surfaced as pytest warnings."""
    for header in ("content-security-policy", "referrer-policy", "permissions-policy"):
        if header not in home_headers:
            warnings.warn(f"Recommended header missing: {header}")


def test_no_server_version_leak(home_headers):
    assert "x-powered-by" not in home_headers, f"X-Powered-By leaks stack: {home_headers['x-powered-by']}"
    assert not re.search(r"\d+\.\d+", home_headers.get("server", "")), f"Server header leaks version: {home_headers['server']}"


def test_no_mixed_content(page, base_url):
    if not base_url.startswith("https"):
        pytest.skip("not https")
    insecure = []
    page.on("request", lambda r: insecure.append(r.url) if r.url.startswith("http://") else None)
    page.goto(base_url, wait_until="load")
    page.wait_for_timeout(1000)
    assert not insecure, f"Insecure sub-requests: {insecure[:8]}"


def test_cookie_flags(page, base_url, context):
    page.goto(base_url, wait_until="load")
    page.wait_for_timeout(1000)
    problems = []
    for c in context.cookies():
        if base_url.startswith("https") and not c["secure"]:
            problems.append(f"{c['name']}: missing Secure")
        if c["sameSite"] == "None" and not c["secure"]:
            problems.append(f"{c['name']}: SameSite=None without Secure")
        if re.search(r"sess|token|auth|jwt", c["name"], re.I) and not c["httpOnly"]:
            problems.append(f"{c['name']}: session/auth cookie missing HttpOnly")
    assert not problems, "\n  ".join(problems)


SENSITIVE = {
    "/.env": r"^\s*[A-Z_]+\s*=",
    "/.git/config": r"\[core\]",
    "/.git/HEAD": r"ref:\s*refs/",
    "/.DS_Store": r"Bud1",
    "/package.json": r'"dependencies"',
    "/config.json": r'"(password|secret|api_?key)"',
    "/backup.zip": r"^PK",
    "/server-status": r"Apache Server Status",
}


@pytest.mark.parametrize("path", SENSITIVE)
def test_sensitive_files_not_exposed(page, base_url, path):
    resp = page.request.get(urljoin(base_url, path))
    if resp.status == 200:
        body = resp.text()[:4000]
        assert not re.search(SENSITIVE[path], body, re.M), f"{path} is publicly readable!"


def test_no_source_maps_in_production(page, base_url):
    maps = []
    page.on("response", lambda r: maps.append(r.url) if r.url.split("?")[0].endswith(".map") and r.ok else None)
    page.goto(base_url, wait_until="load")
    page.wait_for_timeout(1000)
    assert not maps, f"Source maps publicly served: {maps[:5]}"


def test_security_txt_hint(page, base_url):
    resp = page.request.get(urljoin(base_url, "/.well-known/security.txt"))
    if not resp.ok:
        warnings.warn("No /.well-known/security.txt (optional, but recommended)")


def test_content_security_policy_is_enforced(home_headers):
    """A report-only policy observes problems but does not protect visitors."""
    assert "content-security-policy-report-only" not in home_headers, "CSP is report-only, not enforced"


def test_permissions_policy_disables_high_risk_features(home_headers):
    """Advisory: fail only when a Permissions-Policy exists but leaves risky features unrestricted."""
    policy = home_headers.get("permissions-policy", "")
    if not policy:
        warnings.warn("No Permissions-Policy header")
        return
    unrestricted = [feature for feature in ("geolocation", "camera", "microphone") if f"{feature}=*" in policy]
    assert not unrestricted, f"Permissions-Policy leaves high-risk features unrestricted: {unrestricted}"
