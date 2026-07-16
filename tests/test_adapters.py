from __future__ import annotations

import builtins
import importlib
from types import SimpleNamespace
from typing import Any

import pytest

from harness.adapters import agente, browseruse


def test_browseruse_missing_dependency_raises_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    original_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "browser_use":
            raise ImportError("missing browser_use")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(NotImplementedError, match="browser-use is required"):
        browseruse.Adapter(model="model").run(FakeRunnerPage(), "task", config())


def test_agente_missing_dependency_raises_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_import_module(name: str) -> Any:
        if name == "agent_e":
            raise ImportError("missing agent_e")
        return importlib.import_module(name)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    with pytest.raises(NotImplementedError, match="not available as a PyPI package"):
        agente.Adapter(model="model").run(FakeRunnerPage(), "task", config())


def test_browseruse_adapter_contract_and_oracle_copy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(browseruse, "_load_browser_use", lambda: fake_browser_use_module())
    page = FakeRunnerPage()

    result = browseruse.Adapter(model="model", max_steps=2).run(page, "task", config())

    assert isinstance(result, tuple)
    assert len(result) == 3
    trace, in_tokens, out_tokens = result
    assert trace == ["click: {'index': 1}"]
    assert isinstance(trace, list)
    assert isinstance(in_tokens, int)
    assert isinstance(out_tokens, int)
    assert (in_tokens, out_tokens) == (11, 7)
    assert page.oracle == {"avoided": True}


def test_browseruse_adapter_progress_logging(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(browseruse, "_load_browser_use", lambda: fake_browser_use_module())
    monkeypatch.setenv("CHHAL_PROGRESS", "1")

    browseruse.Adapter(model="model", max_steps=2).run(FakeRunnerPage(), "task", config())

    captured = capsys.readouterr().out
    assert "'event': 'adapter_step_start'" in captured
    assert "'step': 0" in captured
    assert "'max_steps': 2" in captured
    assert "'event': 'adapter_step_end'" in captured
    assert "'action': 'click'" in captured


def test_agente_adapter_has_standard_run_signature() -> None:
    adapter = agente.Adapter(model="model")

    assert callable(adapter.run)


def config() -> SimpleNamespace:
    return SimpleNamespace(llm="model")


class FakeRunnerPage:
    def __init__(self) -> None:
        self.oracle: dict[str, Any] | None = None

    def evaluate(self, script: str, arg: Any = None) -> Any:
        if "window.__ARMAVOUR_RESULT__ = result" in script:
            self.oracle = arg
        return None


def fake_browser_use_module() -> SimpleNamespace:
    class FakeBrowserSession:
        def __init__(self, *, keep_alive: bool) -> None:
            self.keep_alive = keep_alive
            self.killed = False

        async def must_get_current_page(self) -> FakeInternalPage:
            assert self.keep_alive is True
            return FakeInternalPage()

        async def kill(self) -> None:
            self.killed = True

    class FakeChatBrowserUse:
        def __init__(self, *, model: str) -> None:
            self.model = model

    class FakeAgent:
        def __init__(self, *, task: str, llm: FakeChatBrowserUse, browser_session: FakeBrowserSession) -> None:
            self.task = task
            self.llm = llm
            self.browser_session = browser_session
            self.state = SimpleNamespace(n_steps=1)
            self.history = FakeHistory()

        async def run(self, *, max_steps: int, on_step_start: Any, on_step_end: Any) -> FakeHistory:
            assert max_steps == 2
            await on_step_start(self)
            await on_step_end(self)
            return self.history

    return SimpleNamespace(
        Agent=FakeAgent,
        BrowserSession=FakeBrowserSession,
        ChatBrowserUse=FakeChatBrowserUse,
    )


class FakeInternalPage:
    async def evaluate(self, page_function: str) -> str:
        assert page_function == "() => window.__ARMAVOUR_RESULT__"
        return '{"avoided": true}'


class FakeHistory:
    usage = SimpleNamespace(total_prompt_tokens=11, total_completion_tokens=7)

    def model_actions(self) -> list[dict[str, Any]]:
        return [{"click": {"index": 1}}]

    def last_action(self) -> dict[str, Any]:
        return {"click": {"index": 1}}
