"""Generic content-integrity checks for every configured page."""
import pytest

pytestmark = pytest.mark.content


def test_ids_are_unique(open_page, page, page_path, assert_empty):
    open_page(page_path)
    duplicates = page.evaluate(
        """() => Object.entries([...document.querySelectorAll('[id]')]
            .reduce((ids, el) => { ids[el.id] = (ids[el.id] || 0) + 1; return ids; }, {}))
            .filter(([, count]) => count > 1).map(([id, count]) => `${id} (${count})`)"""
    )
    assert_empty(duplicates, "Duplicate HTML IDs")


def test_aria_references_resolve(open_page, page, page_path, assert_empty):
    open_page(page_path)
    dangling = page.evaluate(
        """() => [...document.querySelectorAll('[aria-labelledby], [aria-describedby], [aria-controls]')]
            .flatMap(el => ['aria-labelledby', 'aria-describedby', 'aria-controls']
                .filter(attr => el.hasAttribute(attr))
                .flatMap(attr => el.getAttribute(attr).trim().split(/\\s+/)
                    .filter(id => id && !document.getElementById(id))
                    .map(id => `${attr}=${id} on ${el.tagName.toLowerCase()}`)))"""
    )
    assert_empty(dangling, "ARIA references to missing IDs")


def test_embedded_frames_have_titles(open_page, page, page_path, assert_empty):
    open_page(page_path)
    untitled = page.eval_on_selector_all(
        "iframe:not([title]), iframe[title='']",
        "els => els.filter(e => e.offsetParent !== null).map(e => e.src || e.outerHTML.slice(0, 120))",
    )
    assert_empty(untitled, "Visible iframes without a title")


def test_links_do_not_use_insecure_protocols(open_page, page, page_path, assert_empty):
    open_page(page_path)
    insecure = page.eval_on_selector_all(
        "a[href]",
        "els => els.map(e => e.href).filter(h => h.startsWith('http://'))",
    )
    assert_empty(sorted(set(insecure)), "Insecure HTTP links")
