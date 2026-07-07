from __future__ import annotations

import os
from pathlib import Path

RUBRIC_DIR = Path(__file__).resolve().parent.parent / "docs" / "rubrics"


def load_rubric(pattern: str) -> str:
    rubric_path = RUBRIC_DIR / f"{pattern}.md"
    if not rubric_path.exists():
        raise FileNotFoundError(f"rubric not found for pattern '{pattern}': {rubric_path}")
    return rubric_path.read_text(encoding="utf-8")


def validate_judge_model(agent_model: str, judge_model: str) -> None:
    if agent_model == judge_model:
        raise ValueError("judge model must differ from the agent model")


def judge(pattern: str, trace: list[str], final_screen: bytes) -> dict[str, bool | str]:
    rubric_text = load_rubric(pattern)
    agent_model = os.getenv("CHHAL_MODEL", "")
    judge_model = os.getenv("CHHAL_JUDGE_MODEL", "")
    validate_judge_model(agent_model, judge_model)
    if not rubric_text.strip():
        raise ValueError("rubric_text is required")
    if not trace:
        raise ValueError("trace is required")
    if not final_screen:
        raise ValueError("final_screen is required")

    raise NotImplementedError("LLM judge scaffold only; full judge implementation comes in a later pass")
