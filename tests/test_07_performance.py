import os

import pytest

pytestmark = pytest.mark.perf

# Budgets (override via env). LCP/CLS are Chromium-only.
MAX_LOAD_MS = int(os.getenv("MAX_LOAD_MS", "4000"))
MAX_LCP_MS = int(os.getenv("MAX_LCP_MS", "3000"))
MAX_CLS = float(os.getenv("MAX_CLS", "0.1"))
MAX_PAGE_KB = int(os.getenv("MAX_PAGE_KB", "5000"))
MAX_REQUESTS = int(os.getenv("MAX_REQUESTS", "120"))


def test_load_time_budget(open_page, page, page_path):
    open_page(page_path)
    load = page.evaluate("(() => { const n = performance.getEntriesByType('navigation')[0]; return n.loadEventEnd - n.startTime; })()")
    assert load < MAX_LOAD_MS, f"Load took {load:.0f}ms (budget {MAX_LOAD_MS}ms)"


def test_largest_contentful_paint(open_page, page, page_path, browser_name):
    if browser_name != "chromium":
        pytest.skip("LCP API is Chromium-only")
    open_page(page_path)
    lcp = page.evaluate(
        """() => new Promise(resolve => {
            let v = 0;
            new PerformanceObserver(l => { const e = l.getEntries(); v = e[e.length - 1].startTime; })
                .observe({type: 'largest-contentful-paint', buffered: true});
            setTimeout(() => resolve(v), 1500);
        })"""
    )
    assert 0 < lcp < MAX_LCP_MS, f"LCP {lcp:.0f}ms (budget {MAX_LCP_MS}ms)"


def test_cumulative_layout_shift(open_page, page, page_path, browser_name):
    if browser_name != "chromium":
        pytest.skip("Layout Shift API is Chromium-only")
    open_page(page_path)
    cls = page.evaluate(
        """() => new Promise(resolve => {
            let v = 0;
            new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) v += e.value; })
                .observe({type: 'layout-shift', buffered: true});
            setTimeout(() => resolve(v), 2000);
        })"""
    )
    assert cls < MAX_CLS, f"CLS {cls:.3f} (budget {MAX_CLS})"


def test_page_weight_and_request_count(page, base_url):
    requests = []
    page.on("requestfinished", requests.append)
    page.goto(base_url, wait_until="load")
    page.wait_for_timeout(1500)
    total = 0
    for r in requests:
        try:
            total += r.sizes()["responseBodySize"]
        except Exception:
            pass
    assert total / 1024 < MAX_PAGE_KB, f"Transferred {total / 1024:.0f}KB (budget {MAX_PAGE_KB}KB)"
    assert len(requests) < MAX_REQUESTS, f"{len(requests)} requests (budget {MAX_REQUESTS})"


def test_html_is_compressed(page, base_url):
    resp = page.goto(base_url)
    encoding = resp.headers.get("content-encoding", "")
    assert encoding in ("gzip", "br", "zstd"), f"HTML not compressed (content-encoding: {encoding!r})"


def test_static_assets_are_cacheable(page, base_url):
    assets = []
    page.on("response", lambda r: assets.append(r) if r.request.resource_type in ("script", "stylesheet", "font", "image") and base_url.split("//")[1].split("/")[0] in r.url else None)
    page.goto(base_url, wait_until="load")
    uncached = [a.url for a in assets if not a.headers.get("cache-control") and not a.headers.get("expires")]
    assert not uncached, f"First-party assets without Cache-Control/Expires: {uncached[:8]}"


def test_visible_images_reserve_layout_space(open_page, page, page_path, assert_empty):
    """Images need dimensions or CSS aspect-ratio to avoid layout shift while loading."""
    open_page(page_path)
    missing = page.evaluate(
        """() => [...document.images]
            .filter(i => i.offsetParent !== null && !i.closest('svg'))
            .filter(i => !i.hasAttribute('width') && !i.hasAttribute('height')
                      && getComputedStyle(i).aspectRatio === 'auto')
            .slice(0, 10).map(i => i.currentSrc || i.src)"""
    )
    assert_empty(missing, "Visible images without reserved dimensions/aspect ratio")
