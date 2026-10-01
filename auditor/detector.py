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

    step0 = next((s for s in trace.steps if s.step_index == 0), trace.steps[0])
    # Baseline is step 0 (or initial observation step if it already contained cart items)
    baseline_step = trace.steps[0] if (trace.steps[0].cart_state and trace.steps[0].cart_state.get("items")) else step0
    baseline_cart = baseline_step.cart_state or {}
    baseline_items_raw = baseline_cart.get("items") or []

    # 1. Check if baseline cart already contains a pre-sneaked item (e.g. pre-selected donation)
    for raw_item in baseline_items_raw:
        name, price = _extract_item_info(raw_item)
        if any(kw in name.lower() for kw in sneaked_keywords):
            price_val = int(price) if isinstance(price, (int, float)) and float(price).is_integer() else price
            price_str = f" (Rs {price_val})" if price is not None else ""
            return Detection(
                pattern="basket_sneaking",
                detected=True,
                confidence="high",
                evidence=f"Cart gained {name}{price_str} at step {baseline_step.step_index} without agent action.",
                step_index=baseline_step.step_index,
                detection_method="deterministic",
            )

    # 2. Baseline comparison: check if subsequent steps gained items not in baseline
    baseline_items: dict[str, tuple[str, int | float | None]] = {}
    for raw_item in baseline_items_raw:
        name, price = _extract_item_info(raw_item)
        if name:
            baseline_items[name.lower()] = (name, price)

    for step in trace.steps:
        if step.step_index <= baseline_step.step_index:
            continue

        curr_cart = step.cart_state or {}
        curr_items_raw = curr_cart.get("items") or []

        curr_item_map: dict[str, tuple[str, int | float | None]] = {}
        for raw_item in curr_items_raw:
            name, price = _extract_item_info(raw_item)
            if name:
                curr_item_map[name.lower()] = (name, price)

        # Only evaluate additions if the cart GREW in item count between baseline and current step.
        # If cart count is the same or smaller, the change is a substitution/removal, not an addition.
        if len(curr_item_map) <= len(baseline_items):
            continue

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
                        evidence = f"Cart gained {item_name} ({price_str}) between step {baseline_step.step_index} and step {step.step_index} without agent action."
                    else:
                        evidence = f"Cart gained {item_name} between step {baseline_step.step_index} and step {step.step_index} without agent action."

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


def _extract_product_identities(steps: list[AuditStep]) -> tuple[list[str], list[str]]:
    """Extract product names and IDs from steps' DOM and cart states.

    Returns (names, ids) using a priority cascade:
      1. Cart state item names (highest signal — already parsed from cart context)
      2. data-product / data-id / data-item-id attributes
      3. Elements with class product-name / item-name / product-title
      4. <h1> text (usually the product title on product pages)
      5. <h2> text (fallback, with stopword filtering)
    """
    attr_id_regex = re.compile(
        r'(?:data-product|data-id|data-item-id|data-product-id|data-sku)\s*=\s*["\']([^"\']+)["\']',
        re.IGNORECASE,
    )
    h1_regex = re.compile(r'<h1[^>]*>(.*?)</h1>', re.IGNORECASE | re.DOTALL)
    h2_regex = re.compile(r'<h2[^>]*>(.*?)</h2>', re.IGNORECASE | re.DOTALL)
    class_regex = re.compile(
        r'<[a-zA-Z0-9]+[^>]*class=["\'][^"\']*(?:product-name|item-name|product-title)[^"\']*["\'][^>]*>(.*?)</[a-zA-Z0-9]+>',
        re.IGNORECASE | re.DOTALL,
    )

    # Headings that are page chrome, not product names
    _CHROME_STOPWORDS = {
        "product", "products", "your order", "order summary", "your booking",
        "your cart", "cart", "checkout", "shop", "shopping cart", "order",
        "order details", "payment", "shipping", "billing", "review",
        "search results", "home", "menu", "navigation", "footer",
    }

    def _clean_html(raw: str) -> str:
        clean = re.sub(r'<[^>]+>', ' ', raw).strip()
        return ' '.join(clean.split())

    def _is_chrome(text: str) -> bool:
        return text.lower().strip() in _CHROME_STOPWORDS or len(text) < 2

    names: list[str] = []
    ids: list[str] = []

    for step in steps:
        # Priority 1: Cart state item names
        if step.cart_state and step.cart_state.get("items"):
            for item in step.cart_state["items"]:
                if isinstance(item, dict) and item.get("name"):
                    iname = str(item["name"]).strip()
                    if iname and iname not in names and not _is_chrome(iname):
                        names.append(iname)
                elif isinstance(item, str) and item.strip() and item.strip() not in names:
                    if not _is_chrome(item.strip()):
                        names.append(item.strip())

        dom = step.dom_snapshot or ""

        # Priority 2: data-product / data-id attributes
        for match in attr_id_regex.finditer(dom):
            val = match.group(1).strip()
            if val and val not in ids:
                ids.append(val)

        # Priority 3: Elements with product-name / item-name class
        for match in class_regex.finditer(dom):
            clean = _clean_html(match.group(1))
            if clean and clean not in names and len(clean) < 100 and not _is_chrome(clean):
                names.append(clean)

        # Priority 4: <h1> text
        for match in h1_regex.finditer(dom):
            clean = _clean_html(match.group(1))
            if clean and clean not in names and len(clean) < 100 and not _is_chrome(clean):
                names.append(clean)

        # Priority 5: <h2> text (with stricter filtering)
        for match in h2_regex.finditer(dom):
            clean = _clean_html(match.group(1))
            if clean and clean not in names and len(clean) < 100 and not _is_chrome(clean):
                names.append(clean)

    return names, ids


def _extract_item_prices(step: AuditStep) -> list[tuple[str, float]]:
    """Extract (name, price) pairs from a step's cart state and DOM.

    Returns per-item prices, not totals. This is critical for bait-and-switch
    where the total may not change but the item does.
    """
    pairs: list[tuple[str, float]] = []

    # From cart state items
    if step.cart_state and step.cart_state.get("items"):
        for item in step.cart_state["items"]:
            if isinstance(item, dict) and item.get("name") and item.get("price") is not None:
                pairs.append((str(item["name"]).strip(), float(item["price"])))

    # Fallback: inline DOM price extraction near product-like text
    if not pairs and step.dom_snapshot:
        price_re = re.compile(
            r'(?:₹|Rs\.?|INR|\$|€|£|¥)\s*(\d+(?:,\d+)*(?:\.\d+)?)',
            re.IGNORECASE,
        )
        for m in price_re.finditer(step.dom_snapshot):
            try:
                val = float(m.group(1).replace(',', ''))
                if val > 0:
                    # Use a context window around the price to get an approximate name
                    start = max(0, m.start() - 200)
                    context = step.dom_snapshot[start:m.start()]
                    # Strip HTML tags from context
                    context_text = re.sub(r'<[^>]+>', ' ', context).strip()
                    # Take the last meaningful phrase before the price
                    parts = [p.strip() for p in context_text.split('\n') if p.strip()]
                    name = parts[-1] if parts else ""
                    if name and len(name) < 100:
                        pairs.append((name, val))
                        break  # take only the first price found in DOM fallback
            except (ValueError, IndexError):
                continue

    return pairs


def detect_bait_and_switch(trace: AuditTrace) -> Detection:
    """Detect product substitution by comparing first-seen vs last-seen product identity.

    Bait-and-switch is an information asymmetry attack: the site shows product A
    at listing and substitutes product B at checkout. We detect this by finding
    the first and last steps in the trace that contain product signals, and
    comparing their identities.
    """
    if len(trace.steps) < 2:
        return Detection(
            pattern="bait_and_switch",
            detected=False,
            confidence="high",
            evidence="Insufficient steps to compare listing vs checkout specs",
            step_index=0,
            detection_method="deterministic",
        )

    # ── Find first and last steps with product signals ──
    # Instead of fixed windows (first 3 / last 3) which overlap in short traces,
    # scan all steps and find the earliest and latest with a product identity.

    first_product_step = None
    last_product_step = None

    for step in trace.steps:
        names, ids = _extract_product_identities([step])
        prices = _extract_item_prices(step)
        has_signal = bool(names or ids or prices)

        if has_signal and first_product_step is None:
            first_product_step = step
        if has_signal:
            last_product_step = step

    # Need two distinct steps with product info to compare
    if first_product_step is None or last_product_step is None:
        return Detection(
            pattern="bait_and_switch",
            detected=False,
            confidence="low",
            evidence="Could not extract product identity from any step in the trace",
            step_index=0,
            detection_method="deterministic",
        )

    if first_product_step.step_index == last_product_step.step_index:
        return Detection(
            pattern="bait_and_switch",
            detected=False,
            confidence="medium",
            evidence="Product identity found in only one step; no transition to compare",
            step_index=0,
            detection_method="deterministic",
        )

    first_names, first_ids = _extract_product_identities([first_product_step])
    last_names, last_ids = _extract_product_identities([last_product_step])

    # Check 1: Product ID changed
    if first_ids and last_ids and first_ids[0] != last_ids[0]:
        return Detection(
            pattern="bait_and_switch",
            detected=True,
            confidence="high",
            evidence=f"Product ID changed from '{first_ids[0]}' (step {first_product_step.step_index}) to '{last_ids[0]}' (step {last_product_step.step_index}).",
            step_index=last_product_step.step_index,
            detection_method="deterministic",
        )

    # Check 2: Product name changed
    if first_names and last_names and first_names[0].lower() != last_names[0].lower():
        return Detection(
            pattern="bait_and_switch",
            detected=True,
            confidence="high",
            evidence=f"Product changed from '{first_names[0]}' (step {first_product_step.step_index}) to '{last_names[0]}' (step {last_product_step.step_index}).",
            step_index=last_product_step.step_index,
            detection_method="deterministic",
        )

    # Check 3: Per-item price changed (not total — total can change due to fees/add-ons)
    first_prices = _extract_item_prices(first_product_step)
    last_prices = _extract_item_prices(last_product_step)

    if first_prices and last_prices:
        _, p_first = first_prices[0]
        last_name, p_last = last_prices[0]
        if abs(p_first - p_last) > 0.01:
            p_first_val = int(p_first) if float(p_first).is_integer() else p_first
            p_last_val = int(p_last) if float(p_last).is_integer() else p_last
            return Detection(
                pattern="bait_and_switch",
                detected=True,
                confidence="medium",
                evidence=f"Item price changed from Rs {p_first_val} (step {first_product_step.step_index}) to Rs {p_last_val} (step {last_product_step.step_index}).",
                step_index=last_product_step.step_index,
                detection_method="deterministic",
            )

    # Check 4: Fallback — total price changed (less specific, may overlap with drip_pricing)
    first_total = (first_product_step.cart_state or {}).get("total")
    last_total = (last_product_step.cart_state or {}).get("total")

    if first_total is not None and last_total is not None:
        if abs(float(first_total) - float(last_total)) > 0.01:
            ft = int(first_total) if isinstance(first_total, (int, float)) and float(first_total).is_integer() else first_total
            lt = int(last_total) if isinstance(last_total, (int, float)) and float(last_total).is_integer() else last_total
            return Detection(
                pattern="bait_and_switch",
                detected=True,
                confidence="low",
                evidence=f"Cart total changed from Rs {ft} (step {first_product_step.step_index}) to Rs {lt} (step {last_product_step.step_index}).",
                step_index=last_product_step.step_index,
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
    """Scan DOM for sponsored/ad items by visible text content, aria-label, or title attributes."""
    if not trace.steps:
        return Detection(
            pattern="disguised_advertisement",
            detected=False,
            confidence="medium",
            evidence="No steps available to scan for disguised advertisements",
            step_index=0,
            detection_method="deterministic",
        )

    text_node_regex = re.compile(r'>\s*(?:Sponsored|Promoted|Ad)\s*<', re.IGNORECASE)
    attr_regex = re.compile(r'(?:aria-label|title)\s*=\s*["\'][^"\']*\b(?:Sponsored|Promoted|Ad)\b[^"\']*["\']', re.IGNORECASE)

    for step in trace.steps:
        dom = step.dom_snapshot
        text_match = text_node_regex.search(dom)
        attr_match = attr_regex.search(dom)

        if text_match or attr_match:
            matched_cue = text_match.group(0).strip(">< \t\r\n") if text_match else "label/title attribute"
            return Detection(
                pattern="disguised_advertisement",
                detected=True,
                confidence="medium",
                evidence=f"Disguised advertisement indicator '{matched_cue}' detected in DOM at step {step.step_index}.",
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
    """Detect subscription cancellation friction, missing affordance, or mandatory card entry during cancellation."""
    if not trace.steps:
        return Detection(
            pattern="subscription_trap",
            detected=False,
            confidence="high",
            evidence="No steps available to scan for subscription trap",
            step_index=0,
            detection_method="deterministic",
        )

    # 0. Context guard: only run cancellation-friction detector if page looks like a subscription flow
    subscription_signals = (
        "subscription",
        "recurring",
        "monthly",
        "annual",
        "annually",
        "billing",
        "auto-renew",
        "per month",
        "per year",
        "/mo",
        "/yr",
        "/month",
        "/year",
        "membership",
    )
    is_subscription_flow = False
    for step in trace.steps:
        dom = step.dom_snapshot or ""
        # Strip script and style content so CSS comments/class names don't produce false signals
        clean_text = re.sub(r'<(?:style|script)[^>]*>.*?</(?:style|script)>', ' ', dom, flags=re.DOTALL | re.IGNORECASE).lower()
        if any(sig in clean_text for sig in subscription_signals):
            is_subscription_flow = True
            break

    if not is_subscription_flow:
        return Detection(
            pattern="subscription_trap",
            detected=False,
            confidence="high",
            evidence="Page context does not indicate a subscription management flow",
            step_index=0,
            detection_method="deterministic",
        )

    cancel_keywords = ("cancel", "unsubscribe", "end subscription", "stop subscription")
    cancel_affordance_regex = re.compile(
        r'<(?:button|a|input)[^>]*>[^<]*(?:cancel|unsubscribe|end subscription|stop subscription)[^<]*</(?:button|a)>|'
        r'<input[^>]+value=["\'][^"\']*(?:cancel|unsubscribe|end subscription|stop subscription)[^"\']*["\']',
        re.IGNORECASE,
    )
    card_input_regex = re.compile(
        r'(?:card[_-]?number|cvv|expiry|cardholder|card[_-]?name)',
        re.IGNORECASE,
    )

    # 1. Check if card details form appears before / during cancellation flow
    for step in trace.steps:
        dom = step.dom_snapshot or ""
        if card_input_regex.search(dom):
            if any(kw in dom.lower() for kw in cancel_keywords):
                return Detection(
                    pattern="subscription_trap",
                    detected=True,
                    confidence="high",
                    evidence=f"Payment/card details required during cancellation flow at step {step.step_index}.",
                    step_index=step.step_index,
                    detection_method="deterministic",
                )

    # 2. Count steps required to reach a cancellation confirmation
    cancel_steps = [
        step
        for step in trace.steps
        if any(kw in (step.dom_snapshot or "").lower() for kw in cancel_keywords)
    ]
    if len(cancel_steps) > 2:
        return Detection(
            pattern="subscription_trap",
            detected=True,
            confidence="high",
            evidence=f"Cancellation required {len(cancel_steps)} steps (threshold: 2)",
            step_index=cancel_steps[-1].step_index,
            detection_method="deterministic",
        )

    # 3. Check if cancel affordance is discoverable in first 3 steps
    early_steps = trace.steps[: min(3, len(trace.steps))]
    has_early_affordance = any(
        cancel_affordance_regex.search(step.dom_snapshot or "")
        or any(kw in (step.dom_snapshot or "").lower() for kw in cancel_keywords)
        for step in early_steps
    )
    if not has_early_affordance and len(trace.steps) >= 3:
        return Detection(
            pattern="subscription_trap",
            detected=True,
            confidence="medium",
            evidence="No cancel affordance found in first 3 steps",
            step_index=min(2, len(trace.steps) - 1),
            detection_method="deterministic",
        )

    return Detection(
        pattern="subscription_trap",
        detected=False,
        confidence="high",
        evidence="No subscription cancellation friction or traps detected",
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
    """Evaluate confirm shaming for steps containing emotionally loaded guilt-framing decline language."""
    guilt_substrings = (
        "cold-blooded",
        "don't care about",
        "dont care about",
        "heartless",
        "selfish",
        "don't care",
        "dont care",
        "don't want to fund",
        "dont want to fund",
        "won't",
        "wont",
        "refuse",
    )
    guilt_phrase_regex = re.compile(
        r"\b(?:yes|no),?\s*i\s+(?:am\s+)?[a-z\s-]{2,}",
        re.IGNORECASE,
    )

    def _has_guilt_language(dom_lower: str) -> bool:
        if any(sub in dom_lower for sub in guilt_substrings):
            return True
        for match in guilt_phrase_regex.finditer(dom_lower):
            phrase = match.group(0)
            if any(term in phrase for term in ("cold-blooded", "heartless", "selfish", "care", "refuse", "bad", "shame", "cheap", "hate")):
                return True
        return False

    candidate_steps = [
        s for s in trace.steps
        if _has_guilt_language(s.dom_snapshot.lower())
    ]
    return _run_judge_detector("confirm_shaming", trace, candidate_steps)


def detect_interface_interference(trace: AuditTrace) -> Detection:
    """Evaluate interface interference for steps with asymmetric CTA button styling."""
    primary_classes = ("ii-primary", "ii-primary-lg")
    secondary_classes = ("ii-muted-sm", "ii-muted-link", "ii-risk", "ii-hidden-x")

    def _has_cta_asymmetry(dom: str) -> bool:
        dom_lower = dom.lower()

        # Check for ii-actions container
        container_regex = re.compile(
            r'<div[^>]*class=["\'][^"\']*\bii-actions\b[^"\']*["\'][^>]*>(.*?)</div>',
            re.IGNORECASE | re.DOTALL,
        )
        containers = container_regex.findall(dom)

        for container in containers:
            cont_lower = container.lower()
            has_primary = (
                any(cls in cont_lower for cls in primary_classes)
                or ("<button" in cont_lower and "autofocus" in cont_lower)
            )
            has_secondary = (
                any(cls in cont_lower for cls in secondary_classes)
                or "<a" in cont_lower
                or "ii-hidden-x" in dom_lower
            )
            if has_primary and has_secondary:
                return True

        return False

    candidate_steps = [
        s for s in trace.steps
        if _has_cta_asymmetry(s.dom_snapshot)
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
