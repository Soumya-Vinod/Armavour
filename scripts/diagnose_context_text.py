import os
import sys
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

sys.path.insert(0, ".")

from harness.extract import extract_elements

load_dotenv()

BASE_URL = (os.getenv("BASE_URL") or "http://localhost:5173").rstrip("/")
INTENSITIES = ["subtle", "moderate", "aggressive"]


def run_diagnostics():
    output_lines = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for intensity in INTENSITIES:
            url = f"{BASE_URL}/?pattern=false_urgency&intensity={intensity}&language=en"
            output_lines.append("=" * 80)
            output_lines.append(f"INTENSITY: {intensity}")
            output_lines.append(f"URL: {url}")
            output_lines.append("=" * 80)

            page = browser.new_page()
            page.goto(url)
            page.wait_for_selector("#fu-list", timeout=5000)

            elements, _ = extract_elements(page)
            output_lines.append("\n--- EXTRACTED ELEMENTS ---")
            for elem in elements:
                output_lines.append(f"ID:           {elem['id']}")
                output_lines.append(f"Role:         {elem['role']}")
                output_lines.append(f"Text:         {elem['text']}")
                output_lines.append(f"Context Text: {elem['context_text']}")
                output_lines.append("-" * 40)

            content = page.content()
            output_lines.append("\n--- PAGE CONTENT (first 3000 chars) ---")
            output_lines.append(content[:3000])
            output_lines.append("\n")

            page.close()
        browser.close()

    full_output = "\n".join(output_lines)
    print(full_output)
    return full_output


if __name__ == "__main__":
    run_diagnostics()
