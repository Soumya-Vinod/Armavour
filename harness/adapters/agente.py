from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from typing import Any

from playwright.sync_api import Page

from harness.adapters.common import MAX_STEPS


@dataclass
class Adapter:
    model: str | None = None
    max_steps: int = MAX_STEPS

    def __post_init__(self) -> None:
        self.model = self.model or os.getenv("CHHAL_MODEL")
        self.completion_responses: list[Any] = []

    def run(self, page: Page, task: str, config: Any) -> tuple[list[str], int, int]:
        del page, task, config
        _load_agent_e()
        raise NotImplementedError("Agent-E adapter is not implemented yet")


def _load_agent_e() -> Any:
    try:
        return importlib.import_module("agent_e")
    except ImportError as exc:
        raise NotImplementedError(
            "Agent-E is not available as a PyPI package named agent-e or Agent-E; "
            "the Armavour agente adapter is stub-only and no VCS dependency is configured."
        ) from exc
