from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from auditor.audit_runner import AuditStep, AuditTrace
from harness.judge import judge

logger = logging.getLogger(__name__)

ALL_PATTERNS = [
    "basket_sneaking",
    "drip_pricing",
    "bait_and_switch",
    "false_urgency",
    "disguised_advertisement",
    "nagging",
    "subscription_trap",
    "forced_action",
    "confirm_shaming",
    "interface_interference",
    "trick_question",
]


@dataclass
class Detection:
    pattern: str
    detected: bool
    confidence: str  # "high" / "medium" / "low"
    evidence: str
    step_index: int
    detection_method: str  # "deterministic" / "judge"

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern": self.pattern,
            "detected": self.detected,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "step_index": self.step_index,
            "detection_method": self.detection_method,
        }


@dataclass
class AuditReport:
    site_id: str
    audit_trace_id: str
    detections: list[Detection]
    summary: dict[str, bool]

    def to_dict(self) -> dict[str, Any]:
        return {
            "site_id": self.site_id,
            "audit_trace_id": self.audit_trace_id,
            "detections": [d.to_dict() for d in self.detections],
            "summary": self.summary,
        }


# --- DETERMINISTIC DETECTORS ---


def detect_basket_sneaking(trace: AuditTrace) -> Detection:
    """Compare cart state at step 0 vs subsequent steps for unauthorized added items."""
    if not trace.steps:
        return Detection(
            pattern="basket_sneaking",
            detected=False,
            confidence="high",
            evidence="Insufficient steps to compare cart progression",
            step_index=0,
            detection_method="deterministic",
        )

    sneaked_keywords = ("donation", "charity", "contribution", "tip", "warranty", "protection", "insurance")

    def _extract_item_info(item: Any) -> tuple[str, int | float | None]:
        if isinstance(item, dict):
            name = str(item.get("name", "")).strip()
            price = item.get("price")
            return name, price
        elif isinstance(item, str):
            return item.strip(), None
        return str(item).strip(), None

    step0_cart = trace.steps[0].cart_state or {}
    step0_items = step0_cart.get("items") or []

    # 1. Check if step 0 cart already contains a pre-sneaked item (e.g. pre-selected donation)
    for raw_item in step0_items:
        name, price = _extract_item_info(raw_item)
        if any(kw in name.lower() for kw in sneaked_keywords):
            price_val = int(price) if isinstance(price, (int, float)) and float(price).is_integer() else price
            price_str = f" (Rs {price_val})" if price is not None else ""
            return Detection(
                pattern="basket_sneaking",
                detected=True,
                confidence="high",
                evidence=f"Cart gained {name}{price_str} at step 0 without agent action.",
                step_index=0,
                detection_method="deterministic",
            )

    # 2. Baseline comparison: check if subsequent steps gained items not in step 0
    baseline_items: dict[str, tuple[str, int | float | None]] = {}
    for raw_item in step0_items:
        name, price = _extract_item_info(raw_item)
        if name:
            baseline_items[name.lower()] = (name, price)

    for i in range(1, len(trace.steps)):
        step = trace.steps[i]
        curr_cart = step.cart_state or {}
        curr_items_raw = curr_cart.get("items") or []

        curr_item_map: dict[str, tuple[str, int | float | None]] = {}
        for raw_item in curr_items_raw:
            name, price = _extract_item_info(raw_item)
            if name:
                curr_item_map[name.lower()] = (name, price)

        for name_key, (item_name, item_price) in curr_item_map.items():
            if name_key not in baseline_items:
                action = step.action_taken
                reasoning = step.reasoning.lower()
                action_str = str(action).lower()
                action_type = str(action.get("action", "")).lower()

                agent_added = (action_type == "click" or "add" in action_str) and (
                    name_key in reasoning or name_key in action_str
                )

                if not agent_added:
                    if item_price is not None:
                        val = int(item_price) if isinstance(item_price, (int, float)) and float(item_price).is_integer() else item_price
                        price_str = f"Rs {val}"
                        evidence = f"Cart gained {item_name} ({price_str}) between step 0 and step {step.step_index} without agent action."
                    else:
                        evidence = f"Cart gained {item_name} between step 0 and step {step.step_index} without agent action."

                    return Detection(
                        pattern="basket_sneaking",
                        detected=True,
                        confidence="high",
                        evidence=evidence,
                        step_index=step.step_index,
                        detection_method="deterministic",
                    )

    return Detection(
        pattern="basket_sneaking",
        detected=False,
        confidence="high",
        evidence="No unrequested items were added to the cart",
        step_index=0,
        detection_method="deterministic",
    )


def detect_drip_pricing(trace: AuditTrace) -> Detection:
    """Track displayed total price across steps. Flag unexpected price increases or unexplained upfront fees."""
    if not trace.steps:
        return Detection(
            pattern="drip_pricing",
            detected=False,
            confidence="high",
            evidence="Insufficient steps to monitor price deltas",
            step_index=0,
            detection_method="deterministic",
        )

    prev_total = None
    prev_step_idx = 0
    fee_keywords = ("fee", "fees", "charge", "drip", "handling", "service fee", "processing")

    for step in trace.steps:
        cart = step.cart_state or {}
        total = cart.get("total")
        items = cart.get("items") or []

        if total is not None and isinstance(total, (int, float)):
            # Check 1: Step-to-step price increase without item addition
            if prev_total is not None and total > prev_total:
                action_text = (step.reasoning + " " + str(step.action_taken)).lower()
                if "add" not in action_text and "select" not in action_text:
                    return Detection(
                        pattern="drip_pricing",
                        detected=True,
                        confidence="high",
                        evidence=f"Displayed total increased from Rs {prev_total} to Rs {total} between step {prev_step_idx} and step {step.step_index} without item addition.",
                        step_index=step.step_index,
                        detection_method="deterministic",
                    )

            # Check 2: Total > sum of advertised (non-fee) item prices
            advertised_prices = []
            for raw_item in items:
                if isinstance(raw_item, dict):
                    name = str(raw_item.get("name", "")).strip()
                    price = raw_item.get("price")
                else:
                    name = str(raw_item).strip()
                    price = None

                if name and not any(kw in name.lower() for kw in fee_keywords):
                    if isinstance(price, (int, float)):
                        advertised_prices.append(price)

            if advertised_prices:
                advertised_sum = sum(advertised_prices)
                if total > advertised_sum:
                    unexplained_fee = total - advertised_sum
                    unexplained_val = int(unexplained_fee) if float(unexplained_fee).is_integer() else unexplained_fee
                    adv_val = int(advertised_sum) if float(advertised_sum).is_integer() else advertised_sum
                    tot_val = int(total) if float(total).is_integer() else total
                    return Detection(
                        pattern="drip_pricing",
                        detected=True,
                        confidence="high",
                        evidence=f"Displayed total (Rs {tot_val}) exceeds sum of advertised item prices (Rs {adv_val}) with unexplained fee of Rs {unexplained_val}.",
                        step_index=step.step_index,
                        detection_method="deterministic",
                    )

            prev_total = total
            prev_step_idx = step.step_index

    return Detection(
        pattern="drip_pricing",
        detected=False,
        confidence="high",
        evidence="No unannounced total price increases or unexplained fees were observed",
        step_index=0,
        detection_method="deterministic",
    )


def detect_bait_and_switch(trace: AuditTrace) -> Detection:
    """Compare product/price shown on listing (steps 0-2) vs checkout (last 3 steps)."""
    if len(trace.steps) < 2:
        return Detection(
            pattern="bait_and_switch",
            detected=False,
            confidence="high",
            evidence="Insufficient steps to compare listing vs checkout specs",
            step_index=0,
            detection_method="deterministic",
        )

    listing_steps = trace.steps[: min(3, len(trace.steps))]
    checkout_steps = trace.steps[max(0, len(trace.steps) - 3) :]

    listing_prices = [
        s.cart_state.get("total")
        for s in listing_steps
        if s.cart_state and s.cart_state.get("total")
    ]
    checkout_prices = [
        s.cart_state.get("total")
        for s in checkout_steps
        if s.cart_state and s.cart_state.get("total")
    ]

    if listing_prices and checkout_prices:
        p_list = listing_prices[0]
        p_check = checkout_prices[-1]
        if abs(p_list - p_check) > 0.01:
            return Detection(
                pattern="bait_and_switch",
                detected=True,
                confidence="high",
                evidence=f"Product shown as Rs {p_list} at listing, Rs {p_check} at checkout.",
                step_index=checkout_steps[-1].step_index,
                detection_method="deterministic",
            )

    return Detection(
        pattern="bait_and_switch",
        detected=False,
        confidence="high",
        evidence="Product and price remained consistent from listing to checkout",
        step_index=0,
        detection_method="deterministic",
    )


def detect_false_urgency(trace: AuditTrace) -> Detection:
    """Regex DOM scan for urgency text patterns across all steps."""
    urgency_regex = re.compile(
        r"(only\s+\d+\s+left|hurry|limited\s+time|ends\s+in\s+\d+|selling\s+fast|\d+\s+people\s+viewing|offer\s+expires)",
        re.IGNORECASE,
    )

    for step in trace.steps:
        match = urgency_regex.search(step.dom_snapshot)
        if match:
            found_text = match.group(0).strip()
            return Detection(
                pattern="false_urgency",
                detected=True,
                confidence="medium",
                evidence=f"Urgency cue detected in DOM: '{found_text}' at step {step.step_index}.",
                step_index=step.step_index,
                detection_method="deterministic",
            )

    return Detection(
        pattern="false_urgency",
        detected=False,
        confidence="medium",
        evidence="No false urgency text patterns found in DOM snapshots",
        step_index=0,
        detection_method="deterministic",
    )


def detect_disguised_advertisement(trace: AuditTrace) -> Detection:
    """Scan DOM for sponsored/ad items styled identically to organic items."""
    ad_regex = re.compile(r'(class=["\'][^"\']*(?:sponsored|promoted|ad-card)[^"\']*["\'])', re.IGNORECASE)

    for step in trace.steps:
        match = ad_regex.search(step.dom_snapshot)
        if match:
            return Detection(
                pattern="disguised_advertisement",
                detected=True,
                confidence="medium",
                evidence=f"Sponsored item identified without visual distinction at step {step.step_index}.",
                step_index=step.step_index,
                detection_method="deterministic",
            )

    return Detection(
        pattern="disguised_advertisement",
        detected=False,
        confidence="medium",
        evidence="No disguised advertisements detected in DOM",
        step_index=0,
        detection_method="deterministic",
    )


def detect_nagging(trace: AuditTrace) -> Detection:
    """Scan DOM snapshots for repeated modal/overlay content across steps."""
    if not trace.steps:
        return Detection(
            pattern="nagging",
            detected=False,
            confidence="high",
            evidence="No steps available to scan for nagging modals",
            step_index=0,
            detection_method="deterministic",
        )

    # Regex matching elements containing "modal", "overlay", "popup", "interstitial", "dialog", "nag", or "prompt" in class, id, or role
    modal_element_regex = re.compile(
        r'<([a-zA-Z0-9]+)[^>]*(?:class|id|role)\s*=\s*["\'][^"\']*(?:modal|overlay|popup|interstitial|dialog|nag|prompt)[^"\']*["\'][^>]*>(.*?)</\1>',
        re.IGNORECASE | re.DOTALL,
    )

    modal_text_steps: dict[str, set[int]] = {}

    for step in trace.steps:
        dom = step.dom_snapshot
        extracted_texts: list[str] = []

        # Match explicit modal/overlay/popup/interstitial/dialog/nag/prompt elements
        matches = modal_element_regex.findall(dom)
        for _, inner_html in matches:
            text = re.sub(r'<[^>]+>', ' ', inner_html)
            clean_text = ' '.join(text.split()).strip()
            if len(clean_text) >= 10:
                extracted_texts.append(clean_text)

        for text in extracted_texts:
            if text not in modal_text_steps:
                modal_text_steps[text] = set()
            modal_text_steps[text].add(step.step_index)
            if len(modal_text_steps[text]) >= 2:
                n_steps = len(modal_text_steps[text])
                snippet = text[:100]
                return Detection(
                    pattern="nagging",
                    detected=True,
                    confidence="high",
                    evidence=f"Modal/overlay text repeated across {n_steps} steps: {snippet}",
                    step_index=step.step_index,
                    detection_method="deterministic",
                )

    return Detection(
        pattern="nagging",
        detected=False,
        confidence="high",
        evidence="No repeating prompt/modal overlays detected across steps",
        step_index=0,
        detection_method="deterministic",
    )


def detect_subscription_trap(trace: AuditTrace) -> Detection:
    """Scan checkout steps for pre-selected recurring billing options."""
    if not trace.steps:
        return Detection(
            pattern="subscription_trap",
            detected=False,
            confidence="high",
            evidence="No steps available to scan for subscription trap",
            step_index=0,
            detection_method="deterministic",
        )

    recurring_keywords = ("monthly", "annual", "annually", "recurring", "auto-renew", "subscription", "per month", "per year")
    checked_input_regex = re.compile(
        r'<input[^>]+(?:type=["\'](?:radio|checkbox)["\']|checked)[^>]*>',
        re.IGNORECASE,
    )

    for step in trace.steps:
        dom = step.dom_snapshot
        inputs = checked_input_regex.findall(dom)
        for inp in inputs:
            inp_lower = inp.lower()
            is_checked = "checked" in inp_lower or "aria-checked=\"true\"" in inp_lower
            if is_checked:
                pos = dom.find(inp)
                if pos != -1:
                    snippet = dom[max(0, pos - 250) : min(len(dom), pos + 350)].lower()
                    if any(kw in snippet for kw in recurring_keywords):
                        return Detection(
                            pattern="subscription_trap",
                            detected=True,
                            confidence="high",
                            evidence=f"Pre-selected recurring billing option found in DOM at step {step.step_index}.",
                            step_index=step.step_index,
                            detection_method="deterministic",
                        )

    return Detection(
        pattern="subscription_trap",
        detected=False,
        confidence="high",
        evidence="No pre-selected recurring billing options found at checkout",
        step_index=0,
        detection_method="deterministic",
    )


def detect_forced_action(trace: AuditTrace) -> Detection:
    """Scan steps for mandatory non-purchase form fields or early mandatory data collection."""
    if not trace.steps:
        return Detection(
            pattern="forced_action",
            detected=False,
            confidence="medium",
            evidence="No steps available to scan for forced action",
            step_index=0,
            detection_method="deterministic",
        )

    target_fields = ("phone", "mobile", "email", "name", "address")
    forced_keywords = ("create account", "sign up to continue", "download app", "share location", "take survey")
    payment_indicators = ("card_number", "cvv", "upi", "vpa", "expiry", "cardholder", "payment", "place order", "pay now")

    input_regex = re.compile(r'<input[^>]*>', re.IGNORECASE)

    for step in trace.steps:
        dom_lower = step.dom_snapshot.lower()

        # Check if step has payment DOM content
        has_payment_dom = any(pay_kw in dom_lower for pay_kw in payment_indicators)

        # 1. Check for required non-payment form fields in early steps (steps 0-2) or before payment DOM
        if step.step_index <= 2 or not has_payment_dom:
            inputs = input_regex.findall(step.dom_snapshot)
            for inp in inputs:
                inp_lower = inp.lower()
                is_valid_type = any(f'type="{t}"' in inp_lower or f"type='{t}'" in inp_lower for t in ("tel", "email", "text")) or "type=" not in inp_lower

                if is_valid_type:
                    matched_field = None
                    for field in target_fields:
                        if field in inp_lower:
                            matched_field = field
                            break

                    pos = step.dom_snapshot.find(inp)
                    surrounding = step.dom_snapshot[max(0, pos - 150) : min(len(step.dom_snapshot), pos + 200)].lower()
                    if not matched_field:
                        for field in target_fields:
                            if field in surrounding:
                                matched_field = field
                                break

                    if matched_field:
                        is_required = (
                            "required" in inp_lower
                            or "aria-required=\"true\"" in inp_lower
                            or "*" in inp_lower
                            or "*" in surrounding
                            or "required" in surrounding
                            or "must provide" in surrounding
                        )
                        if is_required:
                            return Detection(
                                pattern="forced_action",
                                detected=True,
                                confidence="high",
                                evidence=f"Mandatory {matched_field} field required before purchase at step {step.step_index}",
                                step_index=step.step_index,
                                detection_method="deterministic",
                            )

        # 2. Check if agent trace contains "fill" action on non-payment fields in early steps (steps 0-2)
        if step.step_index <= 2:
            action = step.action_taken or {}
            action_type = str(action.get("action", "")).lower()
            reasoning = step.reasoning.lower()
            action_str = str(action).lower()

            if action_type in ("fill", "type") or "fill" in reasoning or "type" in reasoning:
                for field in target_fields:
                    if (field in action_str or field in reasoning) and not any(p in action_str or p in reasoning for p in ("card", "cvv", "expiry", "pay")):
                        return Detection(
                            pattern="forced_action",
                            detected=True,
                            confidence="high",
                            evidence=f"Mandatory {field} field required before purchase at step {step.step_index}",
                            step_index=step.step_index,
                            detection_method="deterministic",
                        )

        # 3. Keyword check in pre-checkout steps
        if step.step_index < len(trace.steps) - 1:
            for kw in forced_keywords:
                if kw in dom_lower:
                    return Detection(
                        pattern="forced_action",
                        detected=True,
                        confidence="medium",
                        evidence=f"Mandatory non-purchase requirement '{kw}' found at step {step.step_index}.",
                        step_index=step.step_index,
                        detection_method="deterministic",
                    )

    return Detection(
        pattern="forced_action",
        detected=False,
        confidence="medium",
        evidence="No mandatory non-purchase actions detected before checkout",
        step_index=0,
        detection_method="deterministic",
    )


# --- JUDGE-BASED DETECTORS ---


def _is_rubric_available(pattern: str) -> bool:
    """Check if rubric exists and contains actual judge template prompt."""
    rubric_path = Path("docs/rubrics") / f"{pattern}.md"
    if not rubric_path.exists():
        return False
    try:
        content = rubric_path.read_text(encoding="utf-8").strip()
        if content.startswith("STATUS: PENDING") or "## Judge prompt (template)" not in content:
            return False
        return True
    except Exception:
        return False


def _run_judge_detector(pattern: str, trace: AuditTrace, candidate_steps: list[AuditStep]) -> Detection:
    """Safely run LLM judge on candidate steps for a given pattern (handles missing/pending rubrics)."""
    if not _is_rubric_available(pattern):
        logger.info("Rubric not available or pending for pattern %s; skipping judge LLM call", pattern)
        return Detection(
            pattern=pattern,
            detected=False,
            confidence="low",
            evidence=f"rubric_not_available: {pattern}",
            step_index=0,
            detection_method="judge",
        )

    if not candidate_steps:
        return Detection(
            pattern=pattern,
            detected=False,
            confidence="low",
            evidence=f"No candidate UI elements found for {pattern}",
            step_index=0,
            detection_method="judge",
        )

    target_step = candidate_steps[-1]
    trace_strings = [
        f"Step {s.step_index}: reasoning='{s.reasoning}' action={s.action_taken} url={s.url}"
        for s in trace.steps
    ]

    try:
        res = judge(
            pattern=pattern,
            trace=trace_strings,
            final_screen=target_step.screenshot,
            task_prompt=f"Audit purchase flow on {trace.site_id}",
        )
        judge_flag = res.get("judge_flag", False)
        judge_evidence = res.get("judge_evidence", "")

        if judge_evidence.startswith("parse_error") or judge_evidence.startswith("rubric_not_found"):
            return Detection(
                pattern=pattern,
                detected=False,
                confidence="low",
                evidence=f"rubric_not_available: {pattern}",
                step_index=0,
                detection_method="judge",
            )

        return Detection(
            pattern=pattern,
            detected=judge_flag,
            confidence="high" if judge_flag else "low",
            evidence=judge_evidence or f"Judge flag={judge_flag} for {pattern}",
            step_index=target_step.step_index,
            detection_method="judge",
        )
    except FileNotFoundError:
        logger.info("Missing rubric for pattern %s; treating as rubric_not_available", pattern)
        return Detection(
            pattern=pattern,
            detected=False,
            confidence="low",
            evidence=f"rubric_not_available: {pattern}",
            step_index=0,
            detection_method="judge",
        )
    except Exception as exc:
        logger.info("Judge execution error for pattern %s: %s; treating as rubric_not_available", pattern, exc)
        return Detection(
            pattern=pattern,
            detected=False,
            confidence="low",
            evidence=f"rubric_not_available: {pattern}",
            step_index=0,
            detection_method="judge",
        )


def detect_confirm_shaming(trace: AuditTrace) -> Detection:
    """Evaluate confirm shaming for steps containing decline/cancel options."""
    shame_keywords = ("no thanks", "decline", "cancel", "remove", "don't want", "skip")
    candidate_steps = [
        s for s in trace.steps
        if any(kw in s.dom_snapshot.lower() for kw in shame_keywords)
    ]
    return _run_judge_detector("confirm_shaming", trace, candidate_steps)


def detect_interface_interference(trace: AuditTrace) -> Detection:
    """Evaluate interface interference for steps with multiple CTAs."""
    candidate_steps = [
        s for s in trace.steps
        if s.dom_snapshot.lower().count("<button") >= 2 or s.dom_snapshot.lower().count("role=\"button\"") >= 2
    ]
    return _run_judge_detector("interface_interference", trace, candidate_steps)


def detect_trick_question(trace: AuditTrace) -> Detection:
    """Evaluate trick question for steps containing checkbox/toggle inputs."""
    candidate_steps = [
        s for s in trace.steps
        if "type=\"checkbox\"" in s.dom_snapshot.lower() or "role=\"checkbox\"" in s.dom_snapshot.lower() or "type=\"radio\"" in s.dom_snapshot.lower()
    ]
    return _run_judge_detector("trick_question", trace, candidate_steps)


# --- MAIN DETECTOR ENTRYPOINT ---


def detect_violations(trace: AuditTrace) -> AuditReport:
    """Run all 11 CCPA-13 pattern detectors against an AuditTrace."""
    detections: list[Detection] = [
        detect_basket_sneaking(trace),
        detect_drip_pricing(trace),
        detect_bait_and_switch(trace),
        detect_false_urgency(trace),
        detect_disguised_advertisement(trace),
        detect_nagging(trace),
        detect_subscription_trap(trace),
        detect_forced_action(trace),
        detect_confirm_shaming(trace),
        detect_interface_interference(trace),
        detect_trick_question(trace),
    ]

    summary = {d.pattern: d.detected for d in detections}

    return AuditReport(
        site_id=trace.site_id,
        audit_trace_id=trace.timestamp_id,
        detections=detections,
        summary=summary,
    )


def detect_all(trace: AuditTrace) -> AuditReport:
    """Alias for detect_violations to run all pattern detectors on an AuditTrace."""
    return detect_violations(trace)
