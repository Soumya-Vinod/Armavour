from __future__ import annotations

import pytest

from harness.config import EpisodeConfig
from harness.evaluator import EvaluationResult
from harness.runner import calculate_cost_usd, create_adapter, run_episode


def test_create_adapter_rejects_unsupported_agent() -> None:
    config = config_with(agent="unknown")

    with pytest.raises(NotImplementedError, match="computeruse, browseruse, agente"):
        create_adapter(config)


def test_calculate_cost_uses_chhal_price_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHHAL_PRICE_IN", "2")
    monkeypatch.setenv("CHHAL_PRICE_OUT", "10")

    assert calculate_cost_usd(1_000_000, 500_000) == 7.0


def test_run_episode_logs_crash_row(monkeypatch: pytest.MonkeyPatch) -> None:
    logged: list[dict[str, object]] = []

    def boom(_config: EpisodeConfig):
        raise RuntimeError("adapter broke")

    monkeypatch.setattr("harness.runner.load_task_prompt", lambda task_id: "task")
    monkeypatch.setattr("harness.runner.create_adapter", boom)
    monkeypatch.setattr("harness.runner.log_episode", lambda row: logged.append(row))

    row = run_episode(config_with(), run_id="run-1")

    assert logged == [row]
    assert row["placed"] is None
    assert row["avoided"] is None
    assert row["outcome"] is None
    assert "RuntimeError: adapter broke" in str(row["trace"][-1])


def test_success_row_shape_via_mocked_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAdapter:
        def run(self, page, task_prompt: str, config: EpisodeConfig):
            return [{"reasoning": "done"}], 10, 20

    class FakeBrowser:
        def new_page(self):
            return object()

        def close(self) -> None:
            pass

    class FakeChromium:
        def launch(self):
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    class FakePlaywrightContext:
        def __enter__(self):
            return FakePlaywright()

        def __exit__(self, exc_type, exc, tb):
            pass

    monkeypatch.setattr("harness.runner.load_task_prompt", lambda task_id: "task")
    monkeypatch.setattr("harness.runner.create_adapter", lambda config: FakeAdapter())
    monkeypatch.setattr("harness.runner.sync_playwright", lambda: FakePlaywrightContext())
    monkeypatch.setattr("harness.runner.build_episode_url", lambda config: "http://example.test/")
    monkeypatch.setattr(
        "harness.runner.evaluate",
        lambda page, pattern, trace: EvaluationResult(
            placed=True,
            avoided=True,
            outcome="EC",
            judge_flag=None,
            judge_evidence=None,
            oracle_result={"avoided": True},
        ),
    )
    monkeypatch.setattr("harness.runner.log_episode", lambda row: None)

    # Fake page needs methods assigned dynamically because object() does not.
    class FakePage:
        def set_default_timeout(self, timeout_ms: int) -> None:
            pass

        def goto(self, url: str, *, wait_until: str, timeout: int) -> None:
            pass

    FakeBrowser.new_page = lambda self: FakePage()  # type: ignore[method-assign]

    row = run_episode(config_with(), run_id="run-1")

    assert row["placed"] is True
    assert row["avoided"] is True
    assert row["outcome"] == "EC"
    assert row["steps"] == 1


def config_with(**overrides: object) -> EpisodeConfig:
    values = {
        "site": "ticketing",
        "task_id": "bs_ticket",
        "pattern": "basket_sneaking",
        "intensity": "moderate",
        "language": "en",
        "agent": "computeruse",
        "llm": "model",
        "seed": 0,
    }
    values.update(overrides)
    return EpisodeConfig(**values)  # type: ignore[arg-type]
