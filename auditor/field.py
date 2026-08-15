from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import urllib.parse
import urllib.request
import urllib.robotparser

from auditor.storage import save_step_evidence

logger = logging.getLogger(__name__)

MIN_REAL_SITE_DELAY_S = 2.0

PAYMENT_URL_PATTERNS = (
    "/payment",
    "/checkout/payment",
    "/pay",
    "/buy/checkout",
    "/checkout/pay",
    "/razorpay",
    "/stripe",
    "/paytm",
)

PAYMENT_TEXT_PATTERNS = (
    "enter card",
    "pay now",
    "debit/credit",
    "net banking",
    "pay via upi",
    "make payment",
    "complete order",
    "card number",
    "cvv",
    "expiry date",
    "enter upi id",
    "enter vpa",
)


@dataclass
class RobotsStatus:
    url: str
    robots_txt_url: str
    disallows_crawling: bool
    crawl_delay: float | None
    fetched_at: datetime
    raw_text: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "robots_txt_url": self.robots_txt_url,
            "disallows_crawling": self.disallows_crawling,
            "crawl_delay": self.crawl_delay,
            "fetched_at": self.fetched_at.isoformat(),
            "raw_text": self.raw_text,
        }


def check_robots_txt(url: str, user_agent: str = "Armavour-Auditor") -> RobotsStatus:
    """Fetch and parse robots.txt for the given domain."""
    parsed = urllib.parse.urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    fetched_at = datetime.now(timezone.utc)

    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)

    disallows_crawling = False
    crawl_delay: float | None = None
    raw_text = ""

    try:
        req = urllib.request.Request(
            robots_url,
            headers={"User-Agent": user_agent},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            content = resp.read().decode("utf-8", errors="replace")
            raw_text = content
            rp.parse(content.splitlines())

            disallows_crawling = not rp.can_fetch(user_agent, url)
            delay = rp.crawl_delay(user_agent)
            if delay is not None:
                crawl_delay = float(delay)

        logger.info(
            "robots_txt_checked: url=%s disallows=%s delay=%s",
            robots_url,
            disallows_crawling,
            crawl_delay,
        )
    except Exception as exc:
        logger.warning(
            "robots_txt_unreachable: url=%s error=%s (defaulting disallows_crawling=False)",
            robots_url,
            exc,
        )

    return RobotsStatus(
        url=url,
        robots_txt_url=robots_url,
        disallows_crawling=disallows_crawling,
        crawl_delay=crawl_delay,
        fetched_at=fetched_at,
        raw_text=raw_text,
    )


def is_payment_page(page: Any) -> bool:
    """Hard stop check: return True if page contains payment indicators."""
    try:
        current_url = (page.url or "").lower()
        if any(pattern in current_url for pattern in PAYMENT_URL_PATTERNS):
            logger.info("payment_page_detected_by_url: url=%s", current_url)
            return True

        # Check DOM input field names / labels / attributes
        has_payment_inputs = page.evaluate(
            """() => {
                const inputs = Array.from(document.querySelectorAll('input, select, textarea'));
                for (const input of inputs) {
                    const name = (input.name || '').toLowerCase();
                    const id = (input.id || '').toLowerCase();
                    const type = (input.type || '').toLowerCase();
                    const placeholder = (input.placeholder || '').toLowerCase();
                    const ariaLabel = (input.getAttribute('aria-label') || '').toLowerCase();

                    const combined = `${name} ${id} ${type} ${placeholder} ${ariaLabel}`;
                    if (combined.includes('cvv') || combined.includes('card_number') ||
                        combined.includes('cardnumber') || combined.includes('expiry') ||
                        combined.includes('exp_month') || combined.includes('exp_year') ||
                        combined.includes('upi') || combined.includes('vpa')) {
                        return true;
                    }
                    if (type === 'tel' && (combined.includes('card') || combined.includes('number'))) {
                        return true;
                    }
                }
                return false;
            }"""
        )
        if has_payment_inputs:
            logger.info("payment_page_detected_by_inputs: url=%s", current_url)
            return True

        # Check visible text for payment keywords
        content_text = page.evaluate("() => document.body ? document.body.innerText.toLowerCase() : ''")
        if any(text in content_text for text in PAYMENT_TEXT_PATTERNS):
            # Verify if text is actually present near buttons or forms
            if any("pay" in text or "card" in text or "cvv" in text or "net banking" in text for text in PAYMENT_TEXT_PATTERNS if text in content_text):
                logger.info("payment_page_detected_by_text: url=%s", current_url)
                return True

        return False
    except Exception as exc:
        logger.warning("is_payment_page_error: %s", exc)
        return False


def archive_evidence(
    site_id: str,
    timestamp_id: str,
    step_index: int,
    screenshot: bytes,
    dom_snapshot: str,
    evidence_dir: str | Path = "results/audits",
) -> tuple[Path, Path]:
    """Archive step screenshot and DOM snapshot with timestamped immutability."""
    return save_step_evidence(
        site_id=site_id,
        timestamp_id=timestamp_id,
        step_index=step_index,
        screenshot=screenshot,
        dom_snapshot=dom_snapshot,
        evidence_dir=evidence_dir,
    )


def log_audit_start(
    site_id: str,
    url: str,
    robots_status: RobotsStatus,
    config: Any,
) -> None:
    """Log structured audit start event."""
    event = {
        "event": "audit_start",
        "site_id": site_id,
        "url": url,
        "robots_txt_posture": robots_status.to_dict(),
        "user_agent": getattr(config, "user_agent", "Armavour-Auditor"),
        "is_real_site": getattr(config, "is_real_site", False),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    logger.info("AUDIT_START: %s", json.dumps(event))


def log_audit_end(
    site_id: str,
    audit_report: Any,
    stopped_reason: str,
) -> None:
    """Log structured audit end event."""
    report_dict = audit_report.to_dict() if hasattr(audit_report, "to_dict") else asdict(audit_report) if hasattr(audit_report, "__dataclass_fields__") else audit_report
    event = {
        "event": "audit_end",
        "site_id": site_id,
        "stopped_reason": stopped_reason,
        "patterns_detected": report_dict.get("summary", {}),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    logger.info("AUDIT_END: %s", json.dumps(event))
