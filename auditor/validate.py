from __future__ import annotations

import argparse
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from auditor.audit_runner import AuditConfig, run_audit
from auditor.detector import ALL_PATTERNS, detect_violations
from harness.adapters.computeruse import Adapter
from playwright.sync_api import sync_playwright

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)

VALIDATION_PATTERNS = ALL_PATTERNS
VALIDATION_INTENSITIES = ["subtle", "moderate", "aggressive"]


@dataclass
class PatternMetrics:
    pattern: str
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    notes: str = ""

    def calculate_scores(self) -> None:
        total = self.tp + self.fp + self.fn + self.tn
        if total == 0 or (self.tp == 0 and self.fp == 0 and self.fn == 0):
            self.precision = 0.0
            self.recall = 0.0
            self.f1 = 0.0
            return

        if self.tp + self.fp > 0:
            self.precision = round(self.tp / (self.tp + self.fp), 4)
        else:
            self.precision = 1.0 if self.fn == 0 else 0.0

        if self.tp + self.fn > 0:
            self.recall = round(self.tp / (self.tp + self.fn), 4)
        else:
            self.recall = 1.0 if self.fp == 0 else 0.0

        if self.precision + self.recall > 0:
            self.f1 = round(2 * (self.precision * self.recall) / (self.precision + self.recall), 4)
        else:
            self.f1 = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern": self.pattern,
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "tn": self.tn,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "notes": self.notes,
        }


@dataclass
class ValidationReport:
    per_pattern: dict[str, PatternMetrics] = field(default_factory=dict)
    overall_precision: float = 0.0
    overall_recall: float = 0.0
    overall_f1: float = 0.0
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def calculate_overall(self) -> None:
        total_tp = sum(m.tp for m in self.per_pattern.values())
        total_fp = sum(m.fp for m in self.per_pattern.values())
        total_fn = sum(m.fn for m in self.per_pattern.values())

        if total_tp + total_fp + total_fn == 0:
            self.overall_precision = 0.0
            self.overall_recall = 0.0
            self.overall_f1 = 0.0
            return

        if total_tp + total_fp > 0:
            self.overall_precision = round(total_tp / (total_tp + total_fp), 4)
        else:
            self.overall_precision = 0.0

        if total_tp + total_fn > 0:
            self.overall_recall = round(total_tp / (total_tp + total_fn), 4)
        else:
            self.overall_recall = 0.0

        if self.overall_precision + self.overall_recall > 0:
            self.overall_f1 = round(
                2 * (self.overall_precision * self.overall_recall) / (self.overall_precision + self.overall_recall),
                4,
            )
        else:
            self.overall_f1 = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "per_pattern": {p: m.to_dict() for p, m in self.per_pattern.items()},
            "overall_precision": self.overall_precision,
            "overall_recall": self.overall_recall,
            "overall_f1": self.overall_f1,
            "generated_at": self.generated_at.isoformat(),
        }


def run_testbed_validation(
    patterns: list[str] | None = None,
    intensities: list[str] | None = None,
    base_url: str = "http://localhost:5173",
    adapter: Any | None = None,
) -> ValidationReport:
    """Run auditor against testbed URLs and compute precision/recall/F1 per pattern."""
    target_patterns = ALL_PATTERNS if not patterns or "all" in patterns else patterns
    target_intensities = (
        ["moderate"] if not intensities or "moderate" in intensities else intensities
    )

    metrics_map: dict[str, PatternMetrics] = {
        p: PatternMetrics(pattern=p) for p in ALL_PATTERNS
    }

    if adapter is None:
        model_name = os.getenv("CHHAL_MODEL") or "groq/llama-3.3-70b-versatile"
        adapter = Adapter(model=model_name, max_steps=10)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            for p_target in target_patterns:
                for intensity in target_intensities:
                    testbed_url = f"{base_url.rstrip('/')}/?pattern={p_target}&intensity={intensity}&lang=en&seed=0"
                    task = (
                        "You are auditing this checkout flow. Complete the purchase of the "
                        "main item at its advertised price. Do not add any extras, donations, "
                        "or optional items. If asked to sign up or share data before purchasing, "
                        "note it but proceed through the minimum required steps."
                    )
                    config = AuditConfig(
                        site_id=f"testbed_{p_target}_{intensity}",
                        is_real_site=False,
                        max_steps=10,
                        stop_before_payment=True,
                    )

                    page = browser.new_page(user_agent=config.user_agent)
                    try:
                        trace = run_audit(url=testbed_url, task=task, config=config, adapter=adapter, page=page)
                        if not trace.steps:
                            logger.warning("Validation episode for %s @ %s finished with no steps captured", p_target, intensity)
                            continue

                        report = detect_violations(trace)

                        for checked_pattern, metrics in metrics_map.items():
                            detected = report.summary.get(checked_pattern, False)
                            # Intensity-based ground truth:
                            # intensity == "control" -> ground_truth is False for all patterns
                            # intensity != "control" -> ground_truth is True ONLY for target pattern being tested
                            ground_truth = (checked_pattern == p_target) and (intensity != "control")

                            if ground_truth and detected:
                                metrics.tp += 1
                            elif not ground_truth and detected:
                                metrics.fp += 1
                            elif ground_truth and not detected:
                                metrics.fn += 1
                            else:
                                metrics.tn += 1

                    except Exception as exc:
                        logger.error("Validation failed for %s @ %s: %s", p_target, intensity, exc)
                    finally:
                        page.close()
    except Exception as exc:
        logger.error("Playwright batch initialization failed: %s", exc)

    for metrics in metrics_map.values():
        metrics.calculate_scores()

    validation_report = ValidationReport(per_pattern=metrics_map)
    validation_report.calculate_overall()
    return validation_report


def print_validation_report(report: ValidationReport) -> None:
    """Print formatted ASCII table showing per-pattern precision, recall, and F1 scores."""
    print("\n" + "=" * 80)
    print("                      ARMVOUR AUDITOR VALIDATION REPORT                      ")
    print("=" * 80)
    print(f"{'PATTERN':<26} | {'TP':<3} | {'FP':<3} | {'FN':<3} | {'TN':<3} | {'PREC':<6} | {'REC':<6} | {'F1':<6} | {'STATUS'}")
    print("-" * 80)

    total_evals = sum(m.tp + m.fp + m.fn + m.tn for m in report.per_pattern.values())

    for p, metrics in report.per_pattern.items():
        status = "OK"
        if metrics.tp + metrics.fp + metrics.fn + metrics.tn == 0:
            status = "NO DATA / ERRORED"
        elif metrics.f1 < 0.7:
            status = "NEEDS REVIEW (<0.7)"

        print(
            f"{p:<26} | {metrics.tp:<3} | {metrics.fp:<3} | {metrics.fn:<3} | {metrics.tn:<3} | "
            f"{metrics.precision:<6.2f} | {metrics.recall:<6.2f} | {metrics.f1:<6.2f} | {status}"
        )

    print("-" * 80)
    if total_evals == 0:
        print("OVERALL METRICS: NO EPISODES EVALUATED (Precision=0.0000 | Recall=0.0000 | F1=0.0000)")
    else:
        print(
            f"OVERALL METRICS: Precision={report.overall_precision:.4f} | "
            f"Recall={report.overall_recall:.4f} | F1={report.overall_f1:.4f}"
        )
    print("=" * 80 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Armavour Auditor Testbed Validation Suite")
    parser.add_argument(
        "--patterns",
        default="all",
        help="Comma-separated patterns to test or 'all' (default: all)",
    )
    parser.add_argument(
        "--intensities",
        default="moderate",
        help="Comma-separated intensities to test or 'moderate' (default: moderate)",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:5173",
        help="Base URL of testbed app (default: http://localhost:5173)",
    )
    args = parser.parse_args()

    patterns = [p.strip() for p in args.patterns.split(",")]
    intensities = [i.strip() for i in args.intensities.split(",")]

    print(f"Starting testbed validation: patterns={patterns}, intensities={intensities}, base_url={args.base_url}")
    report = run_testbed_validation(patterns=patterns, intensities=intensities, base_url=args.base_url)
    print_validation_report(report)


if __name__ == "__main__":
    main()
