# Netroot.AI – Playwright + pytest website test suite

## Setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install --with-deps
```

## Run
```bash
pytest                                          # everything, headless Chromium
pytest -m smoke                                 # one category (smoke|links|seo|responsive|a11y|forms|perf|security)
pytest --browser chromium --browser firefox --browser webkit
pytest --headed --slowmo 300                    # watch it run
pytest -n 4 --html=report.html --self-contained-html
pytest --base-url https://staging.example.com   # point at another environment
EXTRA_PAGES="/about,/pricing,/contact" pytest   # run per-page tests on more pages
ALLOW_NOINDEX=1 pytest --base-url <staging>     # staging may block crawlers
```
Failures keep a trace, screenshot and video in `test-results/` (open traces with `playwright show-trace <zip>`).

## What's covered
| File | Scenarios |
|---|---|
| test_01_smoke | status, blank page, JS console errors, failed requests, HTTP→HTTPS, 404 handling, favicon, landmarks, reload |
| test_02_links_navigation | crawl + broken internal/external links, nav, logo, target=_blank, anchors, dead `#` links, mailto/tel, images, back/forward |
| test_03_seo_meta | title, description, h1, heading order, lang, viewport, canonical, OG/Twitter, noindex, robots.txt, sitemap, JSON-LD |
| test_04_responsive | 5 viewports: overflow, screenshots, mobile menu, tiny text |
| test_05_accessibility | axe-core WCAG 2.x A/AA, alt text, accessible names, keyboard, focus ring, 200% zoom |
| test_06_forms | labels, required validation, invalid email, XSS, valid submit (POSTs are mocked) |
| test_07_performance | load time, LCP, CLS, weight, request count, compression, caching |
| test_08_security | HSTS, nosniff, framing, mixed content, cookies, exposed files, source maps |
| test_09_site_specific_template | your own CTA / contact / pricing flows (fill in) |

Thresholds are env-configurable (`MAX_LOAD_MS`, `MAX_LCP_MS`, `MAX_CLS`, `MAX_PAGE_KB`, `MAX_REQUESTS`, `MAX_CRAWL`).
