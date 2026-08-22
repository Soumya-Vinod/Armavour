import sys
sys.path.insert(0, ".")
from playwright.sync_api import sync_playwright
from harness.adapters.computeruse import Adapter
from auditor.audit_runner import AuditConfig, run_audit
from auditor.detector import detect_all

patterns_to_check = [
    ("drip_pricing", "moderate"),
    ("nagging", "moderate"), 
    ("forced_action", "moderate"),
    ("subscription_trap", "moderate"),
]

config = AuditConfig(
    site_id="debug",
    is_real_site=False,
    max_steps=10,
    stop_before_payment=False,
    rate_limit_delay_s=0,
    user_agent="Mozilla/5.0",
    evidence_dir="./debug_evidence"
)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    
    for pattern, intensity in patterns_to_check:
        print(f"\n{'='*60}")
        print(f"Pattern: {pattern} / {intensity}")
        page = browser.new_page()
        url = f"http://localhost:5173/?pattern={pattern}&intensity={intensity}&language=en"
        adapter = Adapter()
        trace = run_audit(url, "Complete purchase", config, adapter, page)
        
        print(f"Steps: {len(trace.steps)}, Stopped: {trace.stopped_reason}")
        for i, step in enumerate(trace.steps):
            print(f"  Step {i}: cart={step.cart_state}, action={step.action_taken}")
        
        report = detect_all(trace)
        for d in report.detections:
            if d.pattern == pattern:
                print(f"Detection: detected={d.detected}, confidence={d.confidence}")
                print(f"Evidence: {d.evidence}")
        
        page.close()
    
    browser.close()