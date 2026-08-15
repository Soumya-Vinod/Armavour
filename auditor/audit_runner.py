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
                let total = null;
                let items = [];

                // Attempt to read window.__ARMAVOUR_CART__ or window.cart if available
                if (window.__ARMAVOUR_CART__) {
                    return window.__ARMAVOUR_CART__;
                }

                // Look for price elements with id/class containing total, subtotal, price
                const totalElements = Array.from(document.querySelectorAll('#total, .total, .subtotal, [id*="total"], [class*="total"]'));
                for (const el of totalElements) {
                    const text = (el.innerText || '').trim();
                    const match = text.match(/(?:(?:₹|Rs\\.?|INR|\\$)\\s*)?(\\d+(?:,\\d+)*(?:\\.\\d+)?)/i);
                    if (match) {
                        const parsedVal = parseFloat(match[1].replace(/,/g, ''));
                        if (!isNaN(parsedVal) && parsedVal > 0) {
                            total = parsedVal;
                            break;
                        }
                    }
                }

                // Look for cart items
                const itemElements = Array.from(document.querySelectorAll('.cart-item, .item, [data-item], [id*="cart-item"]'));
                for (const itemEl of itemElements) {
                    const text = (itemEl.innerText || '').trim();
                    if (text) {
                        items.push(text.split('\\n')[0]);
                    }
                }

                if (total !== null || items.length > 0) {
                    return { total: total, items: items };
                }
                return null;
            }"""
        )
        return cart_info
    except Exception as exc:
        logger.debug("cart_state_parse_failed: %s", exc)
        return None


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

    own_browser = False
    playwright_instance = None
    browser_instance = None

    if page is None:
        own_browser = True
        playwright_instance = sync_playwright().start()
        browser_instance = playwright_instance.chromium.launch(headless=True)
        context = browser_instance.new_context(user_agent=config.user_agent)
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded")

    trace = AuditTrace(
        site_id=config.site_id,
        url=url,
        timestamp_id=timestamp_id,
        started_at=started_at,
    )
    stopped_reason = "max_steps"
    trace_history: list[dict[str, Any]] = []

    try:
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

            # Obtain next action from adapter
            action, _ = adapter._next_action(task, config, elements, trace_history)
            reasoning = str(action.get("reasoning", ""))
            action_type = str(action.get("action", "")).lower()

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
                    logger.warning("Step %d action execution error: %s", step_idx, exc)
                    stopped_reason = "error"

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
            if playwright_instance:
                playwright_instance.stop()

    trace.completed_at = datetime.now(timezone.utc)
    trace.stopped_reason = stopped_reason

    log_audit_end(config.site_id, trace, stopped_reason)
    return trace
