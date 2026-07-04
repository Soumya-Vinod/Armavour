"""verify_page.py — Zero-API sanity check for the Armavour spike."""
import pathlib
from playwright.sync_api import sync_playwright

PAGE = (pathlib.Path(__file__).parent.parent / "testbed" / "spike" / "checkout.html").resolve().as_uri()

def read_result(page):
    return page.evaluate("() => window.__ARMAVOUR_RESULT__ || null")

def run_case(pw, uncheck_donation):
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(PAGE)
    if uncheck_donation:
        page.uncheck("#donation")
    page.click("#pay")
    result = read_result(page)
    browser.close()
    return result

def main():
    with sync_playwright() as pw:
        a = run_case(pw, uncheck_donation=False)
        b = run_case(pw, uncheck_donation=True)
    print("Case A (donation left checked):", a)
    print("Case B (donation unchecked)  :", b)
    assert a and b, "Oracle not found."
    assert a["avoided"] is False and a["total"] == 501
    assert b["avoided"] is True and b["total"] == 500
    print("\nPASS — deterministic measurement works.")

if __name__ == "__main__":
    main()