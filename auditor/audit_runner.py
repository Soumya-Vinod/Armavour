from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright

from auditor.field import (
    archive_evidence,
    check_robots_txt,
    is_payment_page,
    log_audit_end,
    log_audit_start,
)
from auditor.storage import generate_timestamp_id
from harness.extract import PageExtractionError, extract_elements

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)


@dataclass
class AuditConfig:
    site_id: str
    is_real_site: bool = False
    max_steps: int = 20
    stop_before_payment: bool = True
    rate_limit_delay_s: float = 2.0
    user_agent: str = "Armavour-Auditor/1.0 (+https://github.com/Soumya-Vinod/Armavour)"
    evidence_dir: str = "results/audits"


@dataclass
class AuditStep:
    step_index: int
    url: str
    dom_snapshot: str
    screenshot: bytes
    action_taken: dict[str, Any]
    reasoning: str
    cart_state: dict[str, Any] | None
    timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_index": self.step_index,
            "url": self.url,
            "dom_snapshot_length": len(self.dom_snapshot),
            "screenshot_bytes": len(self.screenshot),
            "action_taken": self.action_taken,
            "reasoning": self.reasoning,
            "cart_state": self.cart_state,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class AuditTrace:
    site_id: str
    url: str
    timestamp_id: str
    steps: list[AuditStep] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    stopped_reason: str = "max_steps"  # max_steps / payment_page_detected / agent_done / error

    def to_dict(self) -> dict[str, Any]:
        return {
            "site_id": self.site_id,
            "url": self.url,
            "timestamp_id": self.timestamp_id,
            "steps": [s.to_dict() for s in self.steps],
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "stopped_reason": self.stopped_reason,
        }


def parse_cart_state(page: Page) -> dict[str, Any] | None:
    """Best-effort extraction of current cart items and total price from DOM."""
    try:
        cart_info = page.evaluate(
            """() => {
                const PRICE_RE = /(?:₹|Rs\\.?|INR|\\$|€|£|¥)\\s*(\\d+(?:,\\d+)*(?:\\.\\d+)?)/i;
                const SKIP_TEXT_RE = /^(total|subtotal|order\\s*summary|your\\s*booking|grand\\s*total|amount\\s*due)/i;
                const ACTION_WORDS = ["do not", "pay more", "decline", "cancel", "remove", "refuse"];
                const CURRENCY_TOKEN_RE = /[₹$€£¥]|Rs\\.?|INR/i;

                let total = null;
                let items = [];

                // ── Pass 0: window.__ARMAVOUR_CART__ (testbed fast-path) ──
                if (window.__ARMAVOUR_CART__) {
                    const rawCart = window.__ARMAVOUR_CART__;
                    if (rawCart && typeof rawCart === 'object') {
                        let cartTotal = rawCart.total !== undefined ? rawCart.total : null;
                        let cartItems = [];
                        if (Array.isArray(rawCart.items)) {
                            cartItems = rawCart.items.map(it => {
                                if (typeof it === 'string') {
                                    return { name: it, price: null };
                                } else if (it && typeof it === 'object') {
                                    return { name: it.name || String(it), price: typeof it.price === 'number' ? it.price : null };
                                }
                                return { name: String(it), price: null };
                            });
                        }
                        return { total: cartTotal, items: cartItems };
                    }
                }

                // ── Pass 1: JSON-LD structured data (schema.org/Product) ──
                // Most SEO-compliant sites (Shopify, Amazon, WooCommerce) embed this.
                try {
                    const ldScripts = document.querySelectorAll('script[type="application/ld+json"]');
                    for (const s of ldScripts) {
                        let data;
                        try { data = JSON.parse(s.textContent || ''); } catch(_) { continue; }
                        const entries = Array.isArray(data) ? data : [data];
                        for (const entry of entries) {
                            if (!entry || typeof entry !== 'object') continue;
                            const typ = (entry['@type'] || '').toLowerCase();
                            if (typ === 'product' || typ === 'offer') {
                                const name = entry.name || '';
                                let price = null;
                                if (entry.offers && typeof entry.offers === 'object') {
                                    const o = Array.isArray(entry.offers) ? entry.offers[0] : entry.offers;
                                    price = parseFloat(o.price) || null;
                                } else if (entry.price !== undefined) {
                                    price = parseFloat(entry.price) || null;
                                }
                                if (name) items.push({ name: String(name).trim(), price });
                            }
                        }
                    }
                } catch (_) { /* JSON-LD is best-effort */ }

                // ── Pass 2: Total price from DOM ──
                const totalElements = Array.from(document.querySelectorAll(
                    '#total, .total, .subtotal, [id*="total"], [class*="total"], ' +
                    '[id*="subtotal"], [class*="subtotal"], [class*="grand-total"], ' +
                    '[class*="amount-due"], [class*="order-total"]'
                ));
                for (const el of totalElements) {
                    const text = (el.innerText || '').trim();
                    const match = text.match(PRICE_RE);
                    if (match) {
                        const parsedVal = parseFloat(match[1].replace(/,/g, ''));
                        if (!isNaN(parsedVal) && parsedVal > 0) {
                            total = parsedVal;
                            break;
                        }
                    }
                }

                // ── Pass 3: Cart items via selector-based scan ──
                const itemSelectors = [
                    '[data-item]',
                    '[data-product]',
                    '[data-cart-item]',
                    '[data-line-item]',
                    '[data-testid*="item"]',
                    '.cart-item',
                    '.order-item',
                    '.checkout-item',
                    '.product-item',
                    '.line-item',
                    '.line',
                    '[class*="cart-item"]',
                    '[class*="order-item"]',
                    '[class*="line-item"]',
                    '[class*="summary-line"]',
                    '[class*="product-row"]',
                    'li',
                    'tr'
                ];

                const containers = Array.from(document.querySelectorAll(
                    '#cart, .cart, #order-summary, .order-summary, aside, ' +
                    '[class*="cart"], [class*="summary"], [class*="basket"], ' +
                    '[class*="checkout"], [id*="cart"], [id*="basket"], ' +
                    'form[action*="cart"], form[action*="checkout"]'
                ));
                let candidates = [];

                if (containers.length > 0) {
                    for (const c of containers) {
                        for (const sel of itemSelectors) {
                            const found = Array.from(c.querySelectorAll(sel));
                            candidates.push(...found);
                        }
                        // ── Pass 3b: Price-bearing child heuristic ──
                        // If selector-based scan found nothing inside this container,
                        // try all direct children that contain a currency token.
                        // An element inside a cart region with a price is almost
                        // certainly an item row, regardless of tag/class.
                        if (candidates.length === 0) {
                            for (const child of c.children) {
                                const childText = (child.innerText || '').trim();
                                if (childText && CURRENCY_TOKEN_RE.test(childText)) {
                                    candidates.push(child);
                                }
                            }
                        }
                    }
                } else {
                    for (const sel of [
                        '[data-item]', '[data-product]', '[data-cart-item]',
                        '[data-line-item]', '.cart-item', '[id*="cart-item"]',
                        '.line', '.line-item'
                    ]) {
                        candidates.push(...Array.from(document.querySelectorAll(sel)));
                    }
                }

                // Deduplicate candidates by DOM identity
                const seen = new Set();
                candidates = candidates.filter(el => {
                    if (seen.has(el)) return false;
                    seen.add(el);
                    return true;
                });

                const seenNames = new Set();
                for (const el of candidates) {
                    if (el.id === 'total' || el.classList.contains('total') || el.classList.contains('subtotal')) {
                        continue;
                    }
                    const text = (el.innerText || '').trim();
                    if (!text) continue;

                    if (SKIP_TEXT_RE.test(text)) {
                        continue;
                    }

                    let itemPrice = null;
                    const priceMatch = text.match(PRICE_RE);
                    if (priceMatch) {
                        const pv = parseFloat(priceMatch[1].replace(/,/g, ''));
                        if (!isNaN(pv)) {
                            itemPrice = pv;
                        }
                    }

                    let namePart = text.split('\\n')[0].trim();
                    namePart = namePart.replace(/(?:₹|Rs\\.?|INR|\\$|€|£|¥)\\s*\\d+(?:,\\d+)*(?:\\.\\d+)?/gi, '').trim();
                    namePart = namePart.replace(/^[-:\\s]+|[-:\\s]+$/g, '').trim();

                    if (!namePart) {
                        namePart = text.split('\\n')[0].trim();
                    }

                    const nameKey = namePart.toLowerCase();
                    if (ACTION_WORDS.some(w => nameKey.includes(w))) {
                        continue;
                    }
                    if (nameKey && !seenNames.has(nameKey) && nameKey !== 'total' && nameKey !== 'subtotal') {
                        seenNames.add(nameKey);
                        items.push({ name: namePart, price: itemPrice });
                    }
                }

                return { total: total, items: items };
            }"""
        )
        if not cart_info or not isinstance(cart_info, dict):
            logger.warning("cart_state_parse_empty: returned empty or non-dict result")
            return {"total": None, "items": []}

        total = cart_info.get("total")
        if total is not None and isinstance(total, (int, float)):
            total = int(total) if float(total).is_integer() else float(total)
        else:
            total = None

        raw_items = cart_info.get("items") or []
        formatted_items: list[dict[str, Any]] = []
        action_words = ("do not", "pay more", "decline", "cancel", "remove", "refuse")
        for it in raw_items:
            if isinstance(it, dict):
                name = str(it.get("name", "")).strip()
                if any(w in name.lower() for w in action_words):
                    continue
                price = it.get("price")
                if price is not None and isinstance(price, (int, float)):
                    price = int(price) if float(price).is_integer() else float(price)
                else:
                    price = None
                if name:
                    formatted_items.append({"name": name, "price": price})
            elif isinstance(it, str) and it.strip():
                if any(w in it.lower() for w in action_words):
                    continue
                formatted_items.append({"name": it.strip(), "price": None})

        if not formatted_items:
            logger.warning("cart_state_parse_empty: no items parsed from DOM")

        return {"total": total, "items": formatted_items}
    except Exception as exc:
        logger.warning("cart_state_parse_failed: %s", exc)
        return {"total": None, "items": []}


def run_audit(
    url: str,
    task: str,
    config: AuditConfig,
    adapter: Any,
    page: Page | None = None,
) -> AuditTrace:
    """Drive an agent through a purchase flow step by step, capturing evidence at every step."""
    timestamp_id = generate_timestamp_id()
    started_at = datetime.now(timezone.utc)
    robots_status = check_robots_txt(url, config.user_agent)
    log_audit_start(config.site_id, url, robots_status, config)

    if not hasattr(adapter, "provider_latency_seconds"):
        setattr(adapter, "provider_latency_seconds", 0.0)

    own_browser = False
    playwright_instance = None
    browser_instance = None

    cm = None
    if page is None:
        own_browser = True
        cm = sync_playwright()
        playwright_instance = cm.__enter__()
        browser_instance = playwright_instance.chromium.launch(headless=True)
        context = browser_instance.new_context(user_agent=config.user_agent)
        page = context.new_page()

    trace = AuditTrace(
        site_id=config.site_id,
        url=url,
        timestamp_id=timestamp_id,
        started_at=started_at,
    )
    stopped_reason = "max_steps"
    trace_history: list[dict[str, Any]] = []

    try:
        try:
            page.goto(url, wait_until="domcontentloaded")
        except PlaywrightError as exc:
            logger.warning("Page navigation failed for url=%s: %s", url, exc)
            trace.completed_at = datetime.now(timezone.utc)
            trace.stopped_reason = "error"
            log_audit_end(config.site_id, trace, "error")
            return trace

        # ── Initial observation step ──
        # Capture the page state BEFORE any agent action.
        # Critical for bait-and-switch: the substitution happens on the first
        # user action, so post-action snapshots never see the original listing.
        # This preserves the "what was advertised" baseline.
        try:
            initial_dom = page.content()
            initial_cart = parse_cart_state(page)
            try:
                initial_screenshot = page.screenshot()
            except Exception:
                initial_screenshot = b""
            initial_step = AuditStep(
                step_index=-1,
                url=page.url or url,
                dom_snapshot=initial_dom,
                screenshot=initial_screenshot,
                action_taken={"action": "observe"},
                reasoning="Initial page observation before any agent action",
                cart_state=initial_cart,
                timestamp=datetime.now(timezone.utc),
            )
            trace.steps.append(initial_step)
        except Exception as exc:
            logger.debug("Initial observation step failed (non-fatal): %s", exc)

        for step_idx in range(config.max_steps):
            current_url = page.url or url

            # BEFORE each step: Check payment page indicator guard
            if config.stop_before_payment and is_payment_page(page):
                stopped_reason = "payment_page_detected"
                logger.info("Audit stopped before payment: step=%d url=%s", step_idx, current_url)
                break

            # Rate limiting delay on real sites
            if config.is_real_site and step_idx > 0 and config.rate_limit_delay_s > 0:
                logger.info("Rate limit delay: sleeping %.1fs before step %d", config.rate_limit_delay_s, step_idx)
                time.sleep(config.rate_limit_delay_s)

            # Extract elements from DOM
            try:
                elements, handle_map = extract_elements(page)
            except PageExtractionError as exc:
                logger.warning("Step %d element extraction failed: %s", step_idx, exc)
                stopped_reason = "error"
                break

            # Filter out pre-checked checkboxes with donation/charity/optional labels
            filtered_elements = []
            filtered_handle_map = {}
            for el in elements:
                is_checkbox = el.get("role") in ("checkbox", "input") or str(el.get("role", "")).lower() == "checkbox"
                is_checked = el.get("checked") is True
                combined_text = (
                    str(el.get("text", "")) + " " +
                    str(el.get("context_text", "")) + " " +
                    str(el.get("id", ""))
                ).lower()
                is_donation_label = any(
                    kw in combined_text
                    for kw in ("donation", "charity", "optional", "contribution", "cause", "tip")
                )
                if is_checkbox and is_checked and is_donation_label:
                    logger.debug("Filtering pre-checked donation element from step %d: %s", step_idx, el)
                    continue

                orig_index = el["index"]
                new_index = len(filtered_elements)
                el_copy = dict(el)
                el_copy["index"] = new_index
                filtered_elements.append(el_copy)
                if orig_index in handle_map:
                    filtered_handle_map[new_index] = handle_map[orig_index]

            elements = filtered_elements
            handle_map = filtered_handle_map

            # Obtain next action from adapter
            try:
                action, _ = adapter._next_action(task, config, elements, trace_history)
            except Exception as exc:
                logger.warning("Step %d adapter action request failed: %s", step_idx, exc)
                stopped_reason = "error"
                break

            reasoning = str(action.get("reasoning", ""))
            action_type = str(action.get("action", "")).lower()

            # Guard: check if agent "fill" action value contains cancellation-related text
            cancellation_kw = ("cancelling", "cancel", "not satisfied", "reason for leaving")
            action_value = str(action.get("value", "")).lower() + " " + str(action.get("text", "")).lower()
            if action_type in ("fill", "type") and any(kw in action_value for kw in cancellation_kw):
                logger.warning("Guard triggered: Agent attempted to fill cancellation form at step %d. Replacing action with 'done'.", step_idx)
                action = {"action": "done", "reasoning": "Skipping cancellation form fill"}
                action_type = "done"
                reasoning = "Skipping cancellation form fill"

            step_record = {
                "step": step_idx,
                "reasoning": reasoning,
                "action": {k: v for k, v in action.items() if k != "reasoning"},
            }
            trace_history.append(step_record)

            # Execute action via adapter
            if action_type in ("done", "finish", "stop"):
                stopped_reason = "agent_done"
            elif action_type == "none":
                stopped_reason = "agent_done"
            else:
                try:
                    adapter._execute(action, handle_map)
                except (PlaywrightError, ValueError) as exc:
                    if isinstance(exc, ValueError) and "Invalid action index" in str(exc):
                        logger.info("Terminal step due to invalid action index at step %d: %s", step_idx, exc)
                        stopped_reason = "agent_done"
                        break
                    if isinstance(exc, PlaywrightError) and _is_terminal_click_error(exc):
                        logger.info("Terminal click failure at step %d: %s", step_idx, exc)
                        stopped_reason = "agent_done"
                        break
                    logger.warning("Step %d action execution error: %s", step_idx, exc)
                    stopped_reason = "error"
                    break

            # AFTER step: capture snapshot, screenshot, cart state, and archive evidence
            dom_snapshot = page.content()
            try:
                screenshot = page.screenshot()
            except Exception as exc:
                logger.warning("Screenshot capture failed at step %d: %s", step_idx, exc)
                screenshot = b""

            cart_state = parse_cart_state(page)
            step_timestamp = datetime.now(timezone.utc)

            audit_step = AuditStep(
                step_index=step_idx,
                url=page.url or current_url,
                dom_snapshot=dom_snapshot,
                screenshot=screenshot,
                action_taken={k: v for k, v in action.items() if k != "reasoning"},
                reasoning=reasoning,
                cart_state=cart_state,
                timestamp=step_timestamp,
            )
            trace.steps.append(audit_step)

            archive_evidence(
                site_id=config.site_id,
                timestamp_id=timestamp_id,
                step_index=step_idx,
                screenshot=screenshot,
                dom_snapshot=dom_snapshot,
                evidence_dir=config.evidence_dir,
            )

            if stopped_reason in ("agent_done", "error"):
                break

    except Exception as exc:
        logger.error("run_audit encountered unexpected error: %s", exc)
        stopped_reason = "error"
    finally:
        if own_browser:
            if browser_instance:
                browser_instance.close()
            if cm:
                cm.__exit__(None, None, None)

    trace.completed_at = datetime.now(timezone.utc)
    trace.stopped_reason = stopped_reason

    log_audit_end(config.site_id, trace, stopped_reason)
    return trace


def _is_terminal_click_error(exc: PlaywrightError) -> bool:
    msg = str(exc).lower()
    return any(
        marker in msg
        for marker in (
            "timeout",
            "element is not enabled",
            "execution context was destroyed",
            "target closed",
            "page closed",
            "frame was detached",
        )
    )
