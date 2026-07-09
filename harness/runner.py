from __future__ import annotations

import argparse
from contextlib import contextmanager
import logging
import os
import uuid
from collections.abc import Iterable
from typing import Any
from urllib.parse import urlencode

import litellm
from dotenv import load_dotenv

from harness.config import EpisodeConfig, demo_configs, load_task_prompt
from harness.evaluator import EvaluationResult, evaluate

DEFAULT_BASE_URL = "http://localhost:5173"
DEFAULT_TIMEOUT_S = 180
DEFAULT_PRICE_IN = 3.00
DEFAULT_PRICE_OUT = 15.00
DEFAULT_MAX_STEPS = 20
DEFAULT_DEMO_MAX_STEPS = 6
logger = logging.getLogger(__name__)
load_dotenv()


def build_episode_url(config: EpisodeConfig, *, base_url: str | None = None) -> str:
    base = (base_url or os.getenv("BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    params = {
        "site": config.site,
        "task_id": config.task_id,
        "pattern": config.pattern,
        "intensity": config.intensity,
        "lang": config.language,
        "seed": config.seed,
    }
    return f"{base}/?{urlencode(params)}"


def create_adapter(config: EpisodeConfig) -> Any:
    if config.agent != "computeruse":
        raise ValueError(f"unsupported agent '{config.agent}'; only 'computeruse' is implemented")
    from harness.adapters.computeruse import Adapter, MAX_STEPS

    max_steps = int(os.getenv("CHHAL_MAX_STEPS", str(MAX_STEPS)))
    return Adapter(model=config.llm, max_steps=max_steps)


def sync_playwright():
    from playwright.sync_api import sync_playwright as playwright_sync

    return playwright_sync()


def log_episode(row: dict[str, Any]) -> None:
    from harness.logger import log_episode as logger_log_episode

    logger_log_episode(row)


def calculate_cost_usd(
    in_tokens: int,
    out_tokens: int,
    completion_response: Any | Iterable[Any] | None = None,
) -> float:
    if "CHHAL_PRICE_IN" in os.environ or "CHHAL_PRICE_OUT" in os.environ:
        price_in = float(os.getenv("CHHAL_PRICE_IN", str(DEFAULT_PRICE_IN)))
        price_out = float(os.getenv("CHHAL_PRICE_OUT", str(DEFAULT_PRICE_OUT)))
        return (in_tokens / 1_000_000 * price_in) + (out_tokens / 1_000_000 * price_out)

    responses = _completion_responses(completion_response)
    if not responses:
        logger.warning("No LiteLLM response available for cost lookup; defaulting cost_usd to 0.0")
        return 0.0

    try:
        return sum(float(litellm.completion_cost(completion_response=response)) for response in responses)
    except Exception as exc:
        logger.warning("LiteLLM cost lookup failed; defaulting cost_usd to 0.0: %s", exc)
        return 0.0


def run_episode(config: EpisodeConfig, *, run_id: str, log: bool = True) -> dict[str, Any]:
    timeout_ms = int(float(os.getenv("CHHAL_EPISODE_TIMEOUT_S", str(DEFAULT_TIMEOUT_S))) * 1000)
    row_base = _base_row(config, run_id)
    trace: list[Any] = []
    in_tokens = 0
    out_tokens = 0

    try:
        task_prompt = load_task_prompt(config.task_id)
        adapter = create_adapter(config)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page()
                page.set_default_timeout(timeout_ms)
                page.goto(build_episode_url(config), wait_until="networkidle", timeout=timeout_ms)
                trace, in_tokens, out_tokens = adapter.run(page, task_prompt, config)
                completion_responses = getattr(adapter, "completion_responses", None)
                evaluation = evaluate(page, config.pattern, trace)
            finally:
                browser.close()

        row = _success_row(row_base, evaluation, trace, in_tokens, out_tokens, completion_responses)
    except Exception as exc:
        row = _crash_row(row_base, trace, in_tokens, out_tokens, exc)

    if log:
        log_episode(row)
    return row


def run_batch(
    configs: list[EpisodeConfig],
    *,
    run_id: str | None = None,
    log: bool = True,
) -> list[dict[str, Any]]:
    batch_run_id = run_id or f"run-{uuid.uuid4().hex}"
    return [run_episode(config, run_id=batch_run_id, log=log) for config in configs]


def _base_row(config: EpisodeConfig, run_id: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "config_hash": config.config_hash,
        "site": config.site,
        "pattern": config.pattern,
        "intensity": config.intensity,
        "language": config.language,
        "agent": config.agent,
        "llm": config.llm,
        "seed": config.seed,
    }


def _success_row(
    base: dict[str, Any],
    evaluation: EvaluationResult,
    trace: list[Any],
    in_tokens: int,
    out_tokens: int,
    completion_response: Any | Iterable[Any] | None = None,
) -> dict[str, Any]:
    return {
        **base,
        "placed": evaluation.placed,
        "avoided": evaluation.avoided,
        "outcome": evaluation.outcome,
        "in_tokens": in_tokens,
        "out_tokens": out_tokens,
        "cost_usd": calculate_cost_usd(in_tokens, out_tokens, completion_response),
        "steps": len(trace),
        "judge_flag": evaluation.judge_flag,
        "judge_evidence": evaluation.judge_evidence,
        "trace": trace,
    }


def _crash_row(
    base: dict[str, Any],
    trace: list[Any],
    in_tokens: int,
    out_tokens: int,
    exc: Exception,
) -> dict[str, Any]:
    return {
        **base,
        "placed": None,
        "avoided": None,
        "outcome": None,
        "in_tokens": in_tokens,
        "out_tokens": out_tokens,
        "cost_usd": calculate_cost_usd(in_tokens, out_tokens),
        "steps": len(trace),
        "judge_flag": None,
        "judge_evidence": None,
        "trace": [*trace, {"exception": f"{type(exc).__name__}: {exc}"}],
    }


def demo() -> None:
    configs = demo_configs()
    run_id = f"demo-{uuid.uuid4().hex}"
    rows = []
    with _temporary_env(
        CHHAL_MAX_STEPS=os.getenv("CHHAL_DEMO_MAX_STEPS", str(DEFAULT_DEMO_MAX_STEPS)),
        CHHAL_PROGRESS="1",
    ):
        for index, config in enumerate(configs, start=1):
            print(
                {
                    "event": "episode_start",
                    "index": index,
                    "total": len(configs),
                    "intensity": config.intensity,
                    "seed": config.seed,
                    "llm": config.llm,
                },
                flush=True,
            )
            row = run_episode(config, run_id=run_id, log=False)
            rows.append(row)
            print(
                {
                    "event": "episode_end",
                    "index": index,
                    "outcome": row["outcome"],
                    "steps": row["steps"],
                    "cost_usd": row["cost_usd"],
                },
                flush=True,
            )
    outcomes: dict[str | None, int] = {}
    for row in rows:
        outcomes[row["outcome"]] = outcomes.get(row["outcome"], 0) + 1
    print({"episodes": len(rows), "outcomes": outcomes})
    for row in rows:
        print({key: row[key] for key in ("config_hash", "pattern", "outcome", "cost_usd")})


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Armavour harness episodes.")
    parser.add_argument("--demo", action="store_true", help="Run a small demo batch.")
    args = parser.parse_args()
    if args.demo:
        demo()
    else:
        parser.print_help()


def _completion_responses(completion_response: Any | Iterable[Any] | None) -> list[Any]:
    if completion_response is None:
        return []
    if isinstance(completion_response, (str, bytes, dict)):
        return [completion_response]
    if isinstance(completion_response, Iterable):
        return list(completion_response)
    return [completion_response]


@contextmanager
def _temporary_env(**values: str):
    previous = {key: os.environ.get(key) for key in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


if __name__ == "__main__":
    main()
