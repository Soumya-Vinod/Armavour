from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_EVIDENCE_DIR = "results/audits"


def generate_timestamp_id() -> str:
    """Generate ISO-like timestamp string suitable for directory names."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ensure_evidence_dir(evidence_dir: str | Path = DEFAULT_EVIDENCE_DIR) -> Path:
    """Ensure the base evidence directory exists."""
    path = Path(evidence_dir).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_step_dir(
    site_id: str,
    timestamp_id: str,
    step_index: int,
    evidence_dir: str | Path = DEFAULT_EVIDENCE_DIR,
) -> Path:
    """Return directory path for a specific step's evidence, creating it if needed."""
    base_path = ensure_evidence_dir(evidence_dir)
    step_path = base_path / site_id / timestamp_id / f"step_{step_index}"
    step_path.mkdir(parents=True, exist_ok=True)
    return step_path


def save_step_evidence(
    site_id: str,
    timestamp_id: str,
    step_index: int,
    screenshot: bytes,
    dom_snapshot: str,
    evidence_dir: str | Path = DEFAULT_EVIDENCE_DIR,
) -> tuple[Path, Path]:
    """Save screenshot (.png) and DOM snapshot (.html) without overwriting existing files."""
    step_dir = get_step_dir(site_id, timestamp_id, step_index, evidence_dir)
    screenshot_path = step_dir / f"step_{step_index}.png"
    dom_path = step_dir / f"step_{step_index}.html"

    if screenshot_path.exists():
        raise FileExistsError(f"Screenshot file already exists: {screenshot_path}")
    if dom_path.exists():
        raise FileExistsError(f"DOM snapshot file already exists: {dom_path}")

    screenshot_path.write_bytes(screenshot)
    dom_path.write_text(dom_snapshot, encoding="utf-8")

    return screenshot_path, dom_path


def save_audit_report(
    site_id: str,
    timestamp_id: str,
    report_data: dict[str, Any] | Any,
    evidence_dir: str | Path = DEFAULT_EVIDENCE_DIR,
) -> Path:
    """Save AuditReport dictionary or dataclass to report.json in the audit directory."""
    base_path = ensure_evidence_dir(evidence_dir)
    audit_dir = base_path / site_id / timestamp_id
    audit_dir.mkdir(parents=True, exist_ok=True)
    report_path = audit_dir / "report.json"

    if hasattr(report_data, "to_dict"):
        data = report_data.to_dict()
    elif hasattr(report_data, "__dataclass_fields__"):
        data = asdict(report_data)
    elif isinstance(report_data, dict):
        data = report_data
    else:
        raise TypeError(f"Unsupported report_data type: {type(report_data)}")

    def _default_serializer(obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, "to_dict"):
            return obj.to_dict()
        if hasattr(obj, "__dataclass_fields__"):
            return asdict(obj)
        return str(obj)

    report_json = json.dumps(data, indent=2, default=_default_serializer)
    report_path.write_text(report_json, encoding="utf-8")
    return report_path
