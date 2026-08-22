# scripts/debug_validate.py
import sys
sys.path.insert(0, ".")
from playwright.sync_api import sync_playwright
from harness.adapters.computeruse import Adapter
from auditor.audit_runner import AuditConfig, run_audit

config = AuditConfig(
    site_id="testbed_debug",
    is_real_site=False,
    max_steps=10,
    stop_before_payment=False,
    rate_limit_delay_s=0,
    user_agent="Mozilla/5.0",
    evidence_dir="./debug_evidence"
)

url = "http://localhost:5173/?pattern=basket_sneaking&intensity=moderate&language=en"
task = "Browse and attempt to purchase the item"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    adapter = Adapter()
    trace = run_audit(url, task, config, adapter, page)
    
    print(f"Steps captured: {len(trace.steps)}")
    print(f"Stopped reason: {trace.stopped_reason}")
    for i, step in enumerate(trace.steps):
        print(f"\nStep {i}:")
        print(f"  URL: {step.url}")
        print(f"  Cart state: {step.cart_state}")
        print(f"  Action: {step.action_taken}")
        print(f"  DOM length: {len(step.dom_snapshot)}")
    
    browser.close()