from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from anthropic import Anthropic
from playwright.sync_api import ElementHandle, Page

from harness.extract import extract_elements

MAX_STEPS = 20


@dataclass
class Adapter:
    model: str | None = None
    max_steps: int = MAX_STEPS

    def __post_init__(self) -> None:
        self.model = self.model or os.getenv("CHHAL_MODEL")
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY")) if os.getenv("ANTHROPIC_API_KEY") else None

    def run(self, page: Page, task: str, config: Any) -> tuple[list[dict[str, Any]], int, int]:
        if self.client is None:
            raise RuntimeError("ANTHROPIC_API_KEY is required to run the computeruse adapter")
        if not self.model:
            raise RuntimeError("CHHAL_MODEL is required to run the computeruse adapter")

        trace: list[dict[str, Any]] = []
        in_tokens = 0
        out_tokens = 0

        for step in range(self.max_steps):
            elements, handle_map = extract_elements(page)
            action, usage = self._next_action(task, config, elements, trace)
            in_tokens += usage.get("in_tokens", 0)
            out_tokens += usage.get("out_tokens", 0)

            reasoning = action.get("reasoning", "")
            trace.append(
                {
                    "step": step,
                    "reasoning": reasoning,
                    "action": {key: value for key, value in action.items() if key != "reasoning"},
                }
            )

            if action.get("action") == "done":
                break
            self._execute(action, handle_map)

        return trace, in_tokens, out_tokens

    def _next_action(
        self,
        task: str,
        config: Any,
        elements: list[dict[str, Any]],
        trace: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], dict[str, int]]:
        prompt = {
            "task": task,
            "config": _jsonable(config),
            "elements": elements,
            "previous_steps": trace,
            "instructions": (
                "Choose exactly one next action. Return only JSON with keys: "
                "reasoning, action, index, value. action must be one of "
                "click, check, uncheck, fill, done."
            ),
        }
        response = self.client.messages.create(
            model=self.model,
            max_tokens=500,
            messages=[{"role": "user", "content": json.dumps(prompt, sort_keys=True)}],
        )
        text = _response_text(response)
        try:
            action = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Model did not return valid JSON: {text}") from exc

        return action, {
            "in_tokens": getattr(response.usage, "input_tokens", 0),
            "out_tokens": getattr(response.usage, "output_tokens", 0),
        }

    def _execute(self, action: dict[str, Any], handle_map: dict[int, ElementHandle]) -> None:
        action_name = action.get("action")
        index = action.get("index")
        if not isinstance(index, int) or index not in handle_map:
            raise ValueError(f"Invalid action index: {index}")

        handle = handle_map[index]
        if action_name == "click":
            handle.click()
        elif action_name == "check":
            handle.check()
        elif action_name == "uncheck":
            handle.uncheck()
        elif action_name == "fill":
            handle.fill(str(action.get("value", "")))
        else:
            raise ValueError(f"Unsupported action: {action_name}")


def _response_text(response: Any) -> str:
    parts: list[str] = []
    for block in response.content:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts).strip()


def _jsonable(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "__dict__"):
        return value.__dict__
    return value
