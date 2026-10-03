from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from auditor.audit_runner import AuditConfig, AuditStep, AuditTrace
from auditor.detector import (
    ALL_PATTERNS,
    AuditReport,
    Detection,
    detect_basket_sneaking,
    detect_confirm_shaming,
    detect_disguised_advertisement,
    detect_drip_pricing,
    detect_false_urgency,
    detect_subscription_trap,
    detect_violations,
)
from auditor.field import (
    RobotsStatus,
    check_robots_txt,
    is_payment_page,
    log_audit_end,
    log_audit_start,
)
from auditor.storage import (
    generate_timestamp_id,
    get_step_dir,
    save_audit_report,
    save_step_evidence,
)
from auditor.validate import PatternMetrics, ValidationReport, print_validation_report


# --- STORAGE TESTS ---

def test_storage_dir_creation_and_evidence_saving(tmp_path: Path) -> None:
    timestamp_id = generate_timestamp_id()
    assert len(timestamp_id) > 10

    step_dir = get_step_dir("test_site", timestamp_id, 0, evidence_dir=tmp_path)
    assert step_dir.exists()

    screenshot = b"\x89PNG\r\n\x1a\nfake_image_bytes"
    dom = "<html><body><h1>Test Page</h1></body></html>"

    img_path, html_path = save_step_evidence(
        site_id="test_site",
        timestamp_id=timestamp_id,
        step_index=0,
        screenshot=screenshot,
        dom_snapshot=dom,
        evidence_dir=tmp_path,
    )

    assert img_path.exists()
    assert html_path.exists()
    assert img_path.read_bytes() == screenshot
    assert html_path.read_text(encoding="utf-8") == dom

    # Overwrite protection test
    with pytest.raises(FileExistsError):
        save_step_evidence("test_site", timestamp_id, 0, screenshot, dom, evidence_dir=tmp_path)


def test_save_audit_report(tmp_path: Path) -> None:
    timestamp_id = generate_timestamp_id()
    report = AuditReport(
        site_id="test_site",
        audit_trace_id=timestamp_id,
        detections=[
            Detection("basket_sneaking", True, "high", "Item added", 1, "deterministic")
        ],
        summary={"basket_sneaking": True},
    )

    report_path = save_audit_report("test_site", timestamp_id, report, evidence_dir=tmp_path)
    assert report_path.exists()

    saved_data = json.loads(report_path.read_text(encoding="utf-8"))
    assert saved_data["site_id"] == "test_site"
    assert saved_data["summary"]["basket_sneaking"] is True


# --- FIELD TESTS ---

def test_robots_txt_fallback() -> None:
    # Testing unreachable/fake URL returns fallback RobotsStatus
    status = check_robots_txt("http://nonexistent-domain-12345.local/test")
    assert status.disallows_crawling is False
    assert status.crawl_delay is None
    assert isinstance(status.to_dict(), dict)


class DummyPage:
    def __init__(self, url: str, dom_text: str, inputs: list[dict] = None) -> None:
        self.url = url
        self._dom_text = dom_text
        self._inputs = inputs or []

    def evaluate(self, script: str) -> bool:
        if "innerText" in script:
            return self._dom_text.lower()
        if "querySelectorAll" in script:
            for inp in self._inputs:
                combined = f"{inp.get('name', '')} {inp.get('id', '')} {inp.get('type', '')}".lower()
                if any(kw in combined for kw in ("cvv", "card_number", "upi", "vpa")):
                    return True
            return False
        return False


def test_is_payment_page_detection() -> None:
    # URL signal
    page1 = DummyPage("https://example.com/checkout/payment", "select payment mode")
    assert is_payment_page(page1) is True

    # Input field signal
    page2 = DummyPage("https://example.com/checkout", "enter info", [{"name": "card_number", "type": "text"}])
    assert is_payment_page(page2) is True

    # Text keyword signal
    page3 = DummyPage("https://example.com/order", "please pay via upi to confirm order")
    assert is_payment_page(page3) is True

    # Non-payment page
    page4 = DummyPage("https://example.com/products", "browse cool products", [{"name": "search", "type": "text"}])
    assert is_payment_page(page4) is False


def test_log_audit_start_and_end(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    status = RobotsStatus("http://a.com", "http://a.com/robots.txt", False, 1.0, datetime.now(timezone.utc), "")
    config = AuditConfig(site_id="demo_site", is_real_site=False)

    log_audit_start("demo_site", "http://a.com", status, config)
    assert "AUDIT_START" in caplog.text

    report = AuditReport("demo_site", "123", [], {"basket_sneaking": False})
    log_audit_end("demo_site", report, "max_steps")
    assert "AUDIT_END" in caplog.text


# --- AUDIT RUNNER & DETECTOR TESTS ---

def test_detector_rules() -> None:
    step0 = AuditStep(
        step_index=0,
        url="http://testbed.local/page1",
        dom_snapshot="<html><body>Listing page. Item price Rs 500</body></html>",
        screenshot=b"img0",
        action_taken={"action": "click", "index": 0},
        reasoning="Click product",
        cart_state={"total": 500.0, "items": ["Item A"]},
        timestamp=datetime.now(timezone.utc),
    )

    step1 = AuditStep(
        step_index=1,
        url="http://testbed.local/page2",
        dom_snapshot="<html><body>Cart page. <div><span>Sponsored</span> Ad Item</div> Hurry! Only 2 left in stock!</body></html>",
        screenshot=b"img1",
        action_taken={"action": "click", "index": 1},
        reasoning="Proceed to checkout",
        cart_state={"total": 600.0, "items": ["Item A", "Extra Warranty"]},
        timestamp=datetime.now(timezone.utc),
    )

    trace = AuditTrace(
        site_id="testbed_site",
        url="http://testbed.local",
        timestamp_id="20260815T200000Z",
        steps=[step0, step1],
    )

    # Basket sneaking test
    bs_det = detect_basket_sneaking(trace)
    assert bs_det.detected is True
    assert "Extra Warranty" in bs_det.evidence

    # Drip pricing test
    dp_det = detect_drip_pricing(trace)
    assert dp_det.detected is True
    assert "500" in dp_det.evidence and "600" in dp_det.evidence

    # False urgency test
    fu_det = detect_false_urgency(trace)
    assert fu_det.detected is True
    assert "Hurry" in fu_det.evidence or "2 left" in fu_det.evidence

    # Disguised ad test
    ad_det = detect_disguised_advertisement(trace)
    assert ad_det.detected is True

    # Full audit report test
    report = detect_violations(trace)
    assert len(report.detections) == len(ALL_PATTERNS)
    assert report.summary["basket_sneaking"] is True
    assert report.summary["drip_pricing"] is True


def test_missing_rubric_graceful_handling() -> None:
    step0 = AuditStep(
        step_index=0,
        url="http://testbed.local/page",
        dom_snapshot="<html><body><button>No thanks</button></body></html>",
        screenshot=b"img0",
        action_taken={"action": "click", "index": 0},
        reasoning="Decline offer",
        cart_state=None,
        timestamp=datetime.now(timezone.utc),
    )
    trace = AuditTrace("site", "url", "id", [step0])

    # Calling judge detector when rubric is stubbed or missing handles gracefully per Amendment 2
    cs_det = detect_confirm_shaming(trace)
    assert cs_det.detection_method == "judge"
    assert cs_det.detected is False
    assert cs_det.confidence == "low"


# --- VALIDATION METRICS TESTS ---

def test_validation_metrics_calculation(capsys: pytest.CaptureFixture[str]) -> None:
    pm = PatternMetrics(pattern="basket_sneaking", tp=4, fp=1, fn=1, tn=4)
    pm.calculate_scores()
    assert pm.precision == 0.8
    assert pm.recall == 0.8
    assert pm.f1 == 0.8

    report = ValidationReport(per_pattern={"basket_sneaking": pm})
    report.calculate_overall()
    assert report.overall_f1 == 0.8

    print_validation_report(report)
    captured = capsys.readouterr().out
    assert "ARMVOUR AUDITOR VALIDATION REPORT" in captured
    assert "basket_sneaking" in captured


def test_zero_evaluation_metrics_reporting(capsys: pytest.CaptureFixture[str]) -> None:
    pm = PatternMetrics(pattern="basket_sneaking", tp=0, fp=0, fn=0, tn=0)
    pm.calculate_scores()
    assert pm.precision == 0.0
    assert pm.recall == 0.0
    assert pm.f1 == 0.0

    report = ValidationReport(per_pattern={"basket_sneaking": pm})
    report.calculate_overall()
    assert report.overall_precision == 0.0
    assert report.overall_recall == 0.0
    assert report.overall_f1 == 0.0

    print_validation_report(report)
    captured = capsys.readouterr().out
    assert "NO EPISODES EVALUATED" in captured
    assert "NO DATA / ERRORED" in captured


def test_subscription_trap_context_guard_suppresses_fp_on_non_subscription_pages() -> None:
    # 4-step e-commerce trace with no cancel button in first 3 steps and a "Cancel order" button
    steps = [
        AuditStep(
            step_index=i,
            url=f"http://shop.local/step{i}",
            dom_snapshot=(
                f"<html><head><style>/* subscription trap styles */</style></head>"
                f"<body><h1>Product {i}</h1><button>Add to Cart</button></body></html>"
                if i < 3
                else "<html><head><style>/* subscription */</style></head><body><button>Cancel order</button></body></html>"
            ),
            screenshot=b"img",
            action_taken={"action": "click"},
            reasoning=f"Step {i}",
            cart_state=None,
            timestamp=datetime.now(timezone.utc),
        )
        for i in range(4)
    ]
    trace = AuditTrace(
        site_id="shop_site",
        url="http://shop.local",
        timestamp_id="20260909T100000Z",
        steps=steps,
    )
    det = detect_subscription_trap(trace)
    assert det.detected is False
    assert "Page context does not indicate a subscription management flow" in det.evidence


def test_subscription_trap_detects_in_subscription_flow() -> None:
    # Subscription page with recurring/monthly signal and excessive cancellation friction (3 cancel steps)
    steps = [
        AuditStep(
            step_index=i,
            url=f"http://service.local/cancel_step{i}",
            dom_snapshot="<html><body><h1>Manage Subscription</h1><p>Monthly billing: Rs 199/mo</p><button>Cancel subscription</button></body></html>",
            screenshot=b"img",
            action_taken={"action": "click"},
            reasoning=f"Cancel step {i}",
            cart_state=None,
            timestamp=datetime.now(timezone.utc),
        )
        for i in range(3)
    ]
    trace = AuditTrace(
        site_id="subscription_service",
        url="http://service.local",
        timestamp_id="20260909T100000Z",
        steps=steps,
    )
    det = detect_subscription_trap(trace)
    assert det.detected is True
    assert "Cancellation required 3 steps" in det.evidence


def test_basket_sneaking_distinguishes_substitution_from_sneaked_addition() -> None:
    # 1. Substitution (bait and switch): count remains 1 (Item A -> Item B). Should NOT flag.
    step0 = AuditStep(
        step_index=0,
        url="http://shop.local/step0",
        dom_snapshot="<html><body>Product page</body></html>",
        screenshot=b"img",
        action_taken={"action": "click", "value": "add-btn"},
        reasoning="Add product to cart",
        cart_state={"total": 999.0, "items": [{"name": "Wireless Earbuds (Basic)", "price": 999.0}]},
        timestamp=datetime.now(timezone.utc),
    )
    step1_sub = AuditStep(
        step_index=1,
        url="http://shop.local/step1",
        dom_snapshot="<html><body>Checkout page</body></html>",
        screenshot=b"img",
        action_taken={"action": "click"},
        reasoning="Proceed with purchase",
        cart_state={"total": 1799.0, "items": [{"name": "Wireless Earbuds (Pro)", "price": 1799.0}]},
        timestamp=datetime.now(timezone.utc),
    )
    trace_sub = AuditTrace(
        site_id="shop_sub",
        url="http://shop.local",
        timestamp_id="20260909T100000Z",
        steps=[step0, step1_sub],
    )
    det_sub = detect_basket_sneaking(trace_sub)
    assert det_sub.detected is False
    assert "No unrequested items were added to the cart" in det_sub.evidence

    # 2. Sneaked addition: count grows from 1 to 2 (Item A -> Item A + Mystery Item). Should flag.
    step1_sneak = AuditStep(
        step_index=1,
        url="http://shop.local/step1",
        dom_snapshot="<html><body>Checkout page</body></html>",
        screenshot=b"img",
        action_taken={"action": "click"},
        reasoning="Proceed with purchase",
        cart_state={"total": 1049.0, "items": [{"name": "Wireless Earbuds (Basic)", "price": 999.0}, {"name": "Mystery Add-on", "price": 50.0}]},
        timestamp=datetime.now(timezone.utc),
    )
    trace_sneak = AuditTrace(
        site_id="shop_sneak",
        url="http://shop.local",
        timestamp_id="20260909T100000Z",
        steps=[step0, step1_sneak],
    )
    det_sneak = detect_basket_sneaking(trace_sneak)
    assert det_sneak.detected is True
    assert "Mystery Add-on" in det_sneak.evidence


