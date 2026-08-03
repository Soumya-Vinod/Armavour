from __future__ import annotations

from playwright.sync_api import sync_playwright

from harness.extract import extract_elements


def test_extract_elements_includes_nearby_container_context_text() -> None:
    html = """
    <div class="da-row" id="item-urgent">
      <div>
        Deal Headphones
        <span class="fu-cue"> Deal ends in 05:00 · 30 people viewing now</span>
      </div>
      <div class="da-right">
        <span>Rs 1299</span>
        <button class="fa-btn da-buy" id="buy-item-urgent">Buy</button>
      </div>
    </div>
    """

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.set_content(html)

        elements, _ = extract_elements(page)

        browser.close()

    assert elements == [
        {
            "index": 0,
            "id": "buy-item-urgent",
            "role": "button",
            "text": "Buy",
            "context_text": "Deal Headphones Deal ends in 05:00 · 30 people viewing now Rs 1299",
            "checked": None,
            "visible": True,
        }
    ]


def test_extract_elements_context_text_is_empty_when_no_extra_text_exists() -> None:
    html = """
    <div>
      <button id="solo-buy">Buy</button>
    </div>
    """

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.set_content(html)

        elements, _ = extract_elements(page)

        browser.close()

    assert elements == [
        {
            "index": 0,
            "id": "solo-buy",
            "role": "button",
            "text": "Buy",
            "context_text": "",
            "checked": None,
            "visible": True,
        }
    ]
