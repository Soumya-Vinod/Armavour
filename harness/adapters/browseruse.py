from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import os
from dataclasses import dataclass
from typing import Any

from playwright.sync_api import Page

from harness.adapters.common import MAX_STEPS

logger = logging.getLogger(__name__)


@dataclass
class Adapter:
    model: str | None = None
    max_steps: int = MAX_STEPS

    def __post_init__(self) -> None:
        self.model = self.model or os.getenv("CHHAL_MODEL")
        self.completion_responses: list[Any] = []

    def run(self, page: Page, task: str, config: Any) -> tuple[list[str], int, int]:
        if not self.model:
            raise RuntimeError("CHHAL_MODEL is required to run the browseruse adapter")

        trace: list[str] = []
        history, oracle = _run_in_thread(self._run_browseruse(task, config, trace))
        trace.extend(_trace_from_history(history))
        in_tokens, out_tokens = _usage_tokens(history)
        if oracle is not None:
            _copy_oracle_to_runner_page(page, oracle)
        return trace, in_tokens, out_tokens

    async def _run_browseruse(
        self,
        task: str,
        config: Any,
        trace: list[str],
    ) -> tuple[Any, dict[str, Any] | None]:
        browser_use = _load_browser_use()
        show_progress = os.getenv("CHHAL_PROGRESS") == "1"

        session = browser_use.BrowserSession(keep_alive=True)
        llm = browser_use.ChatLiteLLM(model=getattr(config, "llm", None) or self.model)
        agent = browser_use.Agent(task=task, llm=llm, browser_session=session)

        async def on_step_start(step_agent: Any) -> None:
            if show_progress:
                print(
                    {
                        "event": "adapter_step_start",
                        "step": _current_step(step_agent),
                        "max_steps": self.max_steps,
                    },
                    flush=True,
                )

        async def on_step_end(step_agent: Any) -> None:
            if show_progress:
                print(
                    {
                        "event": "adapter_step_end",
                        "step": _current_step(step_agent),
                        "action": _last_action_name(step_agent),
                    },
                    flush=True,
                )

        try:
            history = await agent.run(
                max_steps=self.max_steps,
                on_step_start=on_step_start,
                on_step_end=on_step_end,
            )
            oracle = await _read_browseruse_oracle(agent)
            return history, oracle
        except Exception as exc:
            trace.append(f"{type(exc).__name__}: {exc}")
            empty_history = getattr(agent, "history", None)
            return empty_history, None
        finally:
            await _close_browser_session(session)


def _run_in_thread(coro: Any) -> Any:
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, coro)
        return future.result()


def _load_browser_use() -> Any:
    try:
        import browser_use
    except ImportError as exc:
        raise NotImplementedError(
            "browser-use is required for the browseruse adapter; install browser-use==0.13.4"
        ) from exc
    return browser_use


async def _read_browseruse_oracle(agent: Any) -> dict[str, Any] | None:
    # browser-use Page.evaluate requires arrow-function syntax. keep_alive=True
    # keeps the internal page alive long enough for this oracle read.
    internal_page = await agent.browser_session.must_get_current_page()
    raw_oracle = await internal_page.evaluate("() => window.__ARMAVOUR_RESULT__")
    return _coerce_oracle(raw_oracle)


def _coerce_oracle(raw_oracle: Any) -> dict[str, Any] | None:
    if raw_oracle in (None, ""):
        return None
    if isinstance(raw_oracle, dict):
        return raw_oracle
    if isinstance(raw_oracle, str):
        parsed = json.loads(raw_oracle)
        if parsed is None:
            return None
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("window.__ARMAVOUR_RESULT__ must be an object")


def _copy_oracle_to_runner_page(page: Page, oracle: dict[str, Any]) -> None:
    page.evaluate("(result) => { window.__ARMAVOUR_RESULT__ = result; }", oracle)


async def _close_browser_session(session: Any) -> None:
    try:
        await session.kill()
    except Exception as exc:
        logger.warning("Failed to close browser-use browser session cleanly: %s", exc)


def _trace_from_history(history: Any) -> list[str]:
    if history is None:
        return []
    model_actions = getattr(history, "model_actions", None)
    if not callable(model_actions):
        logger.warning("browser-use history omitted action steps; defaulting trace to empty")
        return []
    return [_describe_action(action) for action in model_actions()]


def _describe_action(action: Any) -> str:
    if not isinstance(action, dict):
        return str(action)
    action_name = next((key for key in action if key != "interacted_element"), "action")
    return f"{action_name}: {action.get(action_name)}"


def _usage_tokens(history: Any) -> tuple[int, int]:
    usage = getattr(history, "usage", None)
    if usage is None:
        logger.warning("browser-use history omitted token usage; defaulting token counts to 0")
        return 0, 0

    prompt_tokens = getattr(usage, "total_prompt_tokens", None)
    completion_tokens = getattr(usage, "total_completion_tokens", None)
    if isinstance(usage, dict):
        prompt_tokens = usage.get("total_prompt_tokens", prompt_tokens)
        completion_tokens = usage.get("total_completion_tokens", completion_tokens)

    if prompt_tokens is None or completion_tokens is None:
        logger.warning("browser-use token usage was incomplete; defaulting missing token counts to 0")

    return int(prompt_tokens or 0), int(completion_tokens or 0)


def _current_step(agent: Any) -> int:
    state = getattr(agent, "state", None)
    n_steps = getattr(state, "n_steps", None)
    return max(int(n_steps or 1) - 1, 0)


def _last_action_name(agent: Any) -> str | None:
    history = getattr(agent, "history", None)
    last_action = getattr(history, "last_action", None)
    if not callable(last_action):
        return None
    action = last_action()
    if not isinstance(action, dict):
        return None
    return next((key for key in action if key != "interacted_element"), None)
