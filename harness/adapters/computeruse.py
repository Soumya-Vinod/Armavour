from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

from playwright.sync_api import ElementHandle, Page
from playwright.sync_api import Error as PlaywrightError

from harness.providers import completion_with_rotation

from harness.adapters.common import (
    DEFAULT_ACTION_TIMEOUT_S,
    DEFAULT_PROVIDER_TIMEOUT_S,
    MAX_STEPS,
)
from harness.extract import PageExtractionError, extract_elements

logger = logging.getLogger(__name__)


@dataclass
class Adapter:
    model: str | None = None
    max_steps: int = MAX_STEPS

    def __post_init__(self) -> None:
        self.model = self.model or os.getenv("CHHAL_MODEL")
        self.completion_responses: list[Any] = []
        self.last_screenshot: bytes = b""
        self.last_elements: list[dict[str, Any]] = []

    def run(self, page: Page, task: str, config: Any) -> tuple[list[dict[str, Any]], int, int]:
        if not self.model:
            raise RuntimeError("CHHAL_MODEL is required to run the computeruse adapter")

        show_progress = os.getenv("CHHAL_PROGRESS") == "1"
        self.completion_responses = []
        self.provider_latency_seconds = 0.0
        trace: list[dict[str, Any]] = []
        in_tokens = 0
        out_tokens = 0

        terminal_reason: str | None = None
        for step in range(self.max_steps):
            if show_progress:
                print({"event": "adapter_step_start", "step": step, "max_steps": self.max_steps}, flush=True)
            try:
                elements, handle_map = extract_elements(page)
                self.last_elements = elements
            except PageExtractionError:
                if _last_action_was_click(trace):
                    terminal_reason = "post_click_extraction_failure"
                    if trace:
                        trace[-1]["terminal_reason"] = terminal_reason
                    logger.warning("Treating post-click page extraction failure as terminal")
                    break
                raise
            action, usage = self._next_action(task, config, elements, trace)
            in_tokens += usage.get("in_tokens", 0)
            out_tokens += usage.get("out_tokens", 0)

            reasoning = action.get("reasoning", "")
            step_record: dict[str, Any] = {
                "step": step,
                "reasoning": reasoning,
                "action": {key: value for key, value in action.items() if key != "reasoning"},
            }
            trace.append(step_record)

            if show_progress:
                print({"event": "adapter_step_end", "step": step, "action": action.get("action")}, flush=True)
            action_type = str(action.get("action", "")).lower()
            if action_type in ("done", "finish", "stop"):
                terminal_reason = f"explicit_{action_type}"
                step_record["terminal_reason"] = terminal_reason
                logger.info("Terminal completion via explicit '%s' action", action_type)
                break
            if action_type == "none":
                terminal_reason = "action_none"
                step_record["terminal_reason"] = terminal_reason
                logger.info("Terminal completion due to action='none'")
                break
            try:
                self._execute(action, handle_map)
                if action.get("action") == "click" and _oracle_result_is_set(page):
                    terminal_reason = "normal_completion"
                    step_record["terminal_reason"] = terminal_reason
                    logger.info("Normal agent completion: oracle result set after click")
                    break
            except (PlaywrightError, ValueError) as exc:
                if isinstance(exc, ValueError) and "Invalid action index" in str(exc):
                    terminal_reason = "invalid_action_index"
                    step_record["terminal_reason"] = terminal_reason
                    logger.warning("Terminal completion due to invalid action index: %s", exc)
                    break
                if action.get("action") == "click" and _terminal_click_error(exc):
                    terminal_reason = "terminal_click_failure"
                    step_record["terminal_reason"] = terminal_reason
                    logger.warning("Treating terminal click failure as end of adapter run: %s", exc)
                    break
                raise

        if terminal_reason is None and trace:
            terminal_reason = "normal_completion"
            trace[-1]["terminal_reason"] = terminal_reason
            logger.info("Normal agent completion")

        # Not part of Contract 5 return signature.
        # Accessed by evaluator.py via adapter.last_screenshot after run().
        try:
            self.last_screenshot = page.screenshot()
        except Exception as exc:  # noqa: BLE001 - screenshot is best-effort evidence.
            self.last_screenshot = b""
            logger.warning("computeruse: screenshot capture failed: %s", exc)

        return trace, in_tokens, out_tokens

    def _next_action(
        self,
        task: str,
        config: Any,
        elements: list[dict[str, Any]],
        trace: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], dict[str, int]]:
        # The episode config (pattern, intensity, seed, config_hash, ...) must never
        # reach the model: it names the manipulated condition. It stays on the row
        # via runner._base_row for logging.
        prompt = {
            "task": task,
            "elements": _elements_for_prompt(elements),
            "previous_steps": trace,
            "instructions": (
                "Choose exactly one next action. Return only JSON with keys: "
                "reasoning, action, index, value. action must be one of "
                "click, check, uncheck, fill, done."
            ),
        }
        # Deterministic inference settings: temperature=0 enforces greedy sampling.
        # Backend provider seed parameters are passed where supported by LiteLLM backends.
        t0 = time.time()
        max_tokens = int(os.getenv("CHHAL_MAX_TOKENS", "2048"))
        timeout = float(os.getenv("CHHAL_PROVIDER_TIMEOUT_S", str(DEFAULT_PROVIDER_TIMEOUT_S)))
        messages = [{"role": "user", "content": json.dumps(prompt, sort_keys=True)}]

        try:
            response = completion_with_rotation(
                model=self.model,
                temperature=0,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                drop_params=True,
                timeout=timeout,
                messages=messages,
            )
        except Exception as exc:
            err_msg = str(exc).lower()
            if "json_validate_failed" in err_msg or "failed to validate json" in err_msg:
                logger.warning("Groq json_validate_failed in computeruse adapter, retrying without response_format: %s", exc)
                response = completion_with_rotation(
                    model=self.model,
                    temperature=0,
                    max_tokens=max_tokens,
                    drop_params=True,
                    timeout=timeout,
                    messages=messages,
                )
            else:
                raise

        self.provider_latency_seconds += (time.time() - t0)
        self.completion_responses.append(response)
        text = _response_text(response)
        action = _parse_action_json(text)

        return action, _usage_tokens(response)

    def _execute(self, action: dict[str, Any], handle_map: dict[int, ElementHandle]) -> None:
        action_name = action.get("action")
        index = action.get("index")
        if not isinstance(index, int) or index not in handle_map:
            raise ValueError(f"Invalid action index: {index}")

        handle = handle_map[index]
        if action_name == "click":
            handle.click(timeout=_action_timeout_ms())
        elif action_name == "check":
            try:
                handle.check()
            except PlaywrightError as exc:
                if _checkbox_noop_error(exc):
                    _log_checkbox_noop(handle, index, action_name)
                    return
                try:
                    handle.click(timeout=_action_timeout_ms())
                except PlaywrightError:
                    raise exc from None
        elif action_name == "uncheck":
            try:
                handle.uncheck()
            except PlaywrightError as exc:
                if _checkbox_noop_error(exc):
                    _log_checkbox_noop(handle, index, action_name)
                    return
                try:
                    handle.click(timeout=_action_timeout_ms())
                except PlaywrightError:
                    raise exc from None
        elif action_name == "fill":
            handle.fill(str(action.get("value", "")))
        else:
            raise ValueError(f"Unsupported action: {action_name}")


def _response_text(response: Any) -> str:
    choice = response.choices[0]
    message = getattr(choice, "message", None)
    if message is None and isinstance(choice, dict):
        message = choice.get("message")

    content = getattr(message, "content", None)
    if content is None and isinstance(message, dict):
        content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            text = getattr(block, "text", None)
            if text is None and isinstance(block, dict):
                text = block.get("text")
            if text:
                parts.append(str(text))
        res = "\n".join(parts).strip()
        if res:
            return res

    # Fallback to reasoning fields for reasoning models (e.g. GPT-OSS / DeepSeek R1)
    reasoning = (
        getattr(message, "reasoning", None)
        or getattr(message, "reasoning_content", None)
        or (message.get("reasoning") if isinstance(message, dict) else None)
        or (message.get("reasoning_content") if isinstance(message, dict) else None)
    )
    if isinstance(reasoning, str) and reasoning.strip():
        return reasoning.strip()

    return ""


def _parse_action_json(raw: str) -> dict[str, Any]:
    stripped = raw.strip()
    # Strip markdown code fence if present
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        import re
        match = re.search(r"\{[\s\S]*\}", stripped)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        raise ValueError(f"Model did not return valid JSON: {raw}")


def _usage_tokens(response: Any) -> dict[str, int]:
    usage = getattr(response, "usage", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage")
    if usage is None:
        logger.warning("LiteLLM response omitted token usage; defaulting token counts to 0")
        return {"in_tokens": 0, "out_tokens": 0}

    prompt_tokens = getattr(usage, "prompt_tokens", None)
    completion_tokens = getattr(usage, "completion_tokens", None)
    if isinstance(usage, dict):
        prompt_tokens = usage.get("prompt_tokens", prompt_tokens)
        completion_tokens = usage.get("completion_tokens", completion_tokens)

    if prompt_tokens is None or completion_tokens is None:
        logger.warning("LiteLLM response usage was incomplete; defaulting missing token counts to 0")

    return {
        "in_tokens": int(prompt_tokens or 0),
        "out_tokens": int(completion_tokens or 0),
    }


def _elements_for_prompt(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prompt_elements: list[dict[str, Any]] = []
    for i, element in enumerate(elements):
        prompt_element = dict(element)
        prompt_element.pop("id", None)
        prompt_element["label"] = f"element-{i}"
        if not prompt_element.get("context_text"):
            prompt_element.pop("context_text", None)
        prompt_elements.append(prompt_element)
    return prompt_elements


def _last_action_was_click(trace: list[dict[str, Any]]) -> bool:
    if not trace:
        return False
    action = trace[-1].get("action")
    return isinstance(action, dict) and action.get("action") == "click"


def _terminal_click_error(exc: PlaywrightError) -> bool:
    message = str(exc).lower()
    return any(
        marker in message
        for marker in (
            "timeout",
            "element is not enabled",
            "execution context was destroyed",
            "target closed",
            "page closed",
            "frame was detached",
        )
    )


def _checkbox_noop_error(exc: PlaywrightError) -> bool:
    msg = str(exc).lower()
    return any(
        marker in msg
        for marker in (
            "clicking the checkbox did not change its state",
            "not a checkbox or radio button",
            "not a checkbox",
        )
    )


def _log_checkbox_noop(handle: ElementHandle, index: int, action_name: str) -> None:
    try:
        element_id = handle.evaluate("element => element.id || null")
    except PlaywrightError:
        element_id = None
    logger.info(
        "%s",
        {
            "event": "checkbox_noop",
            "id": element_id,
            "index": index,
            "action": action_name,
        },
    )


def _oracle_result_is_set(page: Page) -> bool:
    return bool(page.evaluate("() => !!window.__ARMAVOUR_RESULT__"))


def _action_timeout_ms() -> int:
    return int(float(os.getenv("CHHAL_ACTION_TIMEOUT_S", str(DEFAULT_ACTION_TIMEOUT_S))) * 1000)
