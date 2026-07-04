from __future__ import annotations

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


def judge(
    dom_snapshot: str,
    screenshot: bytes | str,
    rubric_text: str,
    *,
    agent_model: str,
    judge_model: str,
) -> dict[str, bool | str]:
    validate_judge_model(agent_model, judge_model)
    if not rubric_text.strip():
        raise ValueError("rubric_text is required")
    if not dom_snapshot.strip():
        raise ValueError("dom_snapshot is required")
    if not screenshot:
        raise ValueError("screenshot is required")

    raise NotImplementedError("LLM judge scaffold only; full judge implementation comes in a later pass")
