"""
TEMPLATE for flows unique to Netroot.AI. I couldn't read the live site, so edit the selectors below
(use `playwright codegen https://netrootai.com` to record them) and remove the skip markers.
"""
import re

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.skip(reason="Fill in selectors for your site, then delete this line")


def test_hero_headline_and_primary_cta(page, open_page):
    open_page("/")
    expect(page.get_by_role("heading", level=1)).to_be_visible()
    cta = page.get_by_role("link", name=re.compile("get started|book a demo|contact", re.I)).first
    expect(cta).to_be_visible()
    cta.click()
    expect(page).not_to_have_url("https://netrootai.com/")


def test_contact_form_end_to_end(page, open_page):
    open_page("/contact")
    page.get_by_label("Name").fill("QA Tester")
    page.get_by_label("Email").fill("qa+autotest@example.com")
    page.get_by_label("Message").fill("Automated test - please ignore")
    with page.expect_response(lambda r: r.request.method == "POST") as resp:
        page.get_by_role("button", name=re.compile("send|submit", re.I)).click()
    assert resp.value.ok
    expect(page.get_by_text(re.compile("thank you|received", re.I))).to_be_visible()


def test_pricing_or_product_sections_render(page, open_page):
    open_page("/")
    for section in ("Features", "Pricing", "About"):
        expect(page.get_by_role("heading", name=re.compile(section, re.I)).first).to_be_visible()
