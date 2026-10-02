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
from harness.providers import get_key_pool, is_rate_limit_error

logger = logging.getLogger(__name__)

# Attributes browser-use serializes into the model's DOM view. browser-use's
# DEFAULT_INCLUDE_ATTRIBUTES contains "id" (browser_use/dom/views.py), and
# testbed element ids can name the manipulation, so "id" is deliberately absent.
MODEL_VISIBLE_ATTRIBUTES = ["type", "name", "role", "aria-label", "placeholder", "value", "href"]


@dataclass
class Adapter:
    model: str | None = None
    max_steps: int = MAX_STEPS

    def __post_init__(self) -> None:
        self.model = self.model or os.getenv("CHHAL_MODEL")
        self.completion_responses: list[Any] = []
        self.last_screenshot: bytes = b""
        self.terminal_reason: str | None = None

    def run(self, page: Page, task: str, config: Any) -> tuple[list[str], int, int]:
        if not self.model:
            raise RuntimeError("CHHAL_MODEL is required to run the browseruse adapter")

        trace: list[str] = []
        target_url = page.url if (page and getattr(page, "url", None) and page.url != "about:blank") else ""
        history, oracle = _run_in_thread(self._run_browseruse(task, config, trace, target_url=target_url))
        trace.extend(_trace_from_history(history))
        in_tokens, out_tokens = _usage_tokens(history)
        self.terminal_reason = _terminal_reason(history, oracle, self.max_steps)
        if oracle is not None:
            _copy_oracle_to_runner_page(page, oracle)
        return trace, in_tokens, out_tokens

    async def _run_browseruse(
        self,
        task: str,
        config: Any,
        trace: list[str],
        target_url: str = "",
    ) -> tuple[Any, dict[str, Any] | None]:
        browser_use = _load_browser_use()
        show_progress = os.getenv("CHHAL_PROGRESS") == "1"

        # The episode URL carries ?pattern=&intensity= and must not be model-visible:
        # it is not put in the task text, and the harness navigates the session
        # before the agent starts instead of via initial_actions (whose
        # "Navigated to <url>" result is fed back to the model as step-0 memory).
        full_task = task

        is_headless = os.getenv("CHHAL_HEADLESS", "1") != "0"
        session = browser_use.BrowserSession(headless=is_headless, keep_alive=True)
        model_name = getattr(config, "llm", None) or self.model
        active_key = get_key_pool().current_key()
        is_groq = bool(model_name and any(k in model_name.lower() for k in ("groq", "llama", "gpt-oss", "openai")))
        if is_groq:
            clean_model = model_name.replace("groq/", "")
            from browser_use.llm import ChatOpenAI

            llm = ChatOpenAI(
                model=clean_model,
                api_key=active_key,
                base_url="https://api.groq.com/openai/v1",
                temperature=0,
                add_schema_to_system_prompt=True,
                dont_force_structured_output=True,
                remove_min_items_from_schema=True,
                remove_defaults_from_schema=True,
            )
            extend_msg = (
                "IMPORTANT: Output ONLY a single raw JSON object complying exactly with the provided schema. "
                "Do NOT include any conversational preamble, intro text, explanation, or markdown code blocks (such as ```json). "
                "Your response must begin directly with '{' and end with '}'."
            )
            agent = browser_use.Agent(
                task=full_task,
                llm=llm,
                browser_session=session,
                use_vision=False,
                flash_mode=True,
                use_judge=False,
                use_thinking=False,
                include_tool_call_examples=False,
                max_clickable_elements_length=12000,
                include_attributes=MODEL_VISIBLE_ATTRIBUTES,
                extend_system_message=extend_msg,
                directly_open_url=False,
            )
        else:
            llm_kwargs: dict[str, Any] = {"temperature": 0}
            if active_key:
                llm_kwargs["api_key"] = active_key
            llm = browser_use.ChatLiteLLM(model=model_name, **llm_kwargs)
            agent = browser_use.Agent(
                task=full_task,
                llm=llm,
                browser_session=session,
                use_vision=False,
                flash_mode=True,
                use_judge=False,
                use_thinking=False,
                include_tool_call_examples=False,
                max_clickable_elements_length=12000,
                include_attributes=MODEL_VISIBLE_ATTRIBUTES,
                directly_open_url=False,
            )

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
                oracle = await _read_browseruse_oracle(step_agent)
                if oracle is not None:
                    logger.info("browseruse: oracle result detected on step %s, stopping early", _current_step(step_agent))
                    step_agent.stop()
            except Exception as exc:  # noqa: BLE001
                logger.debug("browseruse: early oracle check: %s", exc)

        try:
            if target_url:
                # start() is idempotent (browser_use 0.13.4 BrowserSession.on_BrowserStartEvent),
                # so agent.run() reuses this already-navigated session.
                await session.start()
                await session.navigate_to(target_url)
            history = await agent.run(
                max_steps=self.max_steps,
                on_step_start=on_step_start,
                on_step_end=on_step_end,
            )
            if hasattr(history, "errors") and any(is_rate_limit_error(str(e)) for e in history.errors() if e):
                get_key_pool().rotate()
            oracle = await _read_browseruse_oracle(agent)
            await self._capture_last_screenshot(agent)
            return history, oracle
        except Exception as exc:  # noqa: BLE001 - preserve adapter failures as trace rows.
            trace.append(f"{type(exc).__name__}: {exc}")
            if is_rate_limit_error(exc):
                get_key_pool().rotate()
            empty_history = getattr(agent, "history", None)
            return empty_history, None
        finally:
            await _close_browser_session(session)

    async def _capture_last_screenshot(self, agent: Any) -> None:
        # Not part of Contract 5 return signature.
        # Accessed by evaluator.py via adapter.last_screenshot after run().
        try:
            internal_page = await agent.browser_session.must_get_current_page()
            self.last_screenshot = await internal_page.screenshot()
        except Exception as exc:  # noqa: BLE001 - screenshot is best-effort evidence.
            self.last_screenshot = b""
            logger.warning("browseruse: screenshot capture failed: %s", exc)


def _terminal_reason(history: Any, oracle: dict[str, Any] | None, max_steps: int) -> str:
    """Same vocabulary as the computeruse adapter (stored per row since migration 0007)."""
    if oracle is not None:
        return "normal_completion"
    try:
        if history is not None and history.is_done():
            return "explicit_done"
        if history is not None and history.number_of_steps() >= max_steps:
            return "step_cap"
    except Exception:  # noqa: BLE001 - a partial history must not fail the episode.
        pass
    return "silent_stop"


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
    raise TypeError("window.__ARMAVOUR_RESULT__ must be an object")


def _copy_oracle_to_runner_page(page: Page, oracle: dict[str, Any]) -> None:
    page.evaluate("(result) => { window.__ARMAVOUR_RESULT__ = result; }", oracle)


async def _close_browser_session(session: Any) -> None:
    try:
        await session.kill()
    except Exception as exc:  # noqa: BLE001 - best-effort cleanup should not mask the episode result.
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
