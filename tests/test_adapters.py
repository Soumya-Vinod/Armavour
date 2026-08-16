from __future__ import annotations

import builtins
import importlib
import logging
from types import SimpleNamespace
from typing import Any

import pytest
from playwright.sync_api import sync_playwright

from harness.adapters import agente, browseruse, computeruse


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


def test_computeruse_readonly_checkbox_noop_continues_step_loop(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    html = """
    <label>
      <input id="locked-box" type="checkbox" checked readonly />
      Locked decoy
    </label>
    <button id="continue" onclick="window.continued = true">Continue</button>
    <script>
      document.querySelector("#locked-box").addEventListener("click", event => event.preventDefault());
    </script>
    """
    actions = [
        {"reasoning": "try locked checkbox", "action": "uncheck", "target_id": "locked-box"},
        {"reasoning": "continue after noop", "action": "click", "target_id": "continue"},
        {"reasoning": "finished", "action": "done", "index": 0},
    ]

    def fake_next_action(
        _self: computeruse.Adapter,
        _task: str,
        _config: Any,
        elements: list[dict[str, Any]],
        _trace: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], dict[str, int]]:
        action = actions.pop(0)
        if action["action"] != "done":
            target_index = next(element["index"] for element in elements if element["id"] == action["target_id"])
            action = {**action, "index": target_index}
            action.pop("target_id")
        return action, {"in_tokens": 1, "out_tokens": 1}

    monkeypatch.setattr(computeruse.Adapter, "_next_action", fake_next_action)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.set_content(html)
        adapter = computeruse.Adapter(model="model", max_steps=3)

        with caplog.at_level(logging.INFO, logger="harness.adapters.computeruse"):
            trace, in_tokens, out_tokens = adapter.run(page, "task", config())

        locked_checked = page.is_checked("#locked-box")
        continued = page.evaluate("() => window.continued === true")
        browser.close()

    assert locked_checked is True
    assert continued is True
    assert [step["action"]["action"] for step in trace] == ["uncheck", "click", "done"]
    assert (in_tokens, out_tokens) == (3, 3)
    assert any(
        "'event': 'checkbox_noop'" in record.message
        and "'id': 'locked-box'" in record.message
        and "'action': 'uncheck'" in record.message
        for record in caplog.records
    )


def test_computeruse_normal_checked_checkbox_uncheck_still_toggles(
    caplog: pytest.LogCaptureFixture,
) -> None:
    html = """
    <label>
      <input id="normal-box" type="checkbox" checked />
      Normal checkbox
    </label>
    """

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.set_content(html)
        handle = page.query_selector("#normal-box")
        assert handle is not None

        with caplog.at_level(logging.INFO, logger="harness.adapters.computeruse"):
            computeruse.Adapter(model="model")._execute({"action": "uncheck", "index": 0}, {0: handle})

        normal_checked = page.is_checked("#normal-box")
        browser.close()

    assert normal_checked is False
    assert not any("'event': 'checkbox_noop'" in record.message for record in caplog.records)


@pytest.mark.parametrize(
    ("action_dict", "expected_reason", "expected_log"),
    [
        ({"reasoning": "done now", "action": "done"}, "explicit_done", "Terminal completion via explicit 'done' action"),
        ({"reasoning": "finish now", "action": "finish"}, "explicit_finish", "Terminal completion via explicit 'finish' action"),
        ({"reasoning": "stop now", "action": "stop"}, "explicit_stop", "Terminal completion via explicit 'stop' action"),
        ({"reasoning": "none action", "action": "none"}, "action_none", "Terminal completion due to action='none'"),
    ],
)
def test_computeruse_terminal_action_reasons(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    action_dict: dict[str, Any],
    expected_reason: str,
    expected_log: str,
) -> None:
    monkeypatch.setattr(computeruse, "extract_elements", lambda _p: ([], {}))
    monkeypatch.setattr(
        computeruse.Adapter,
        "_next_action",
        lambda _self, _t, _c, _e, _tr: (action_dict, {"in_tokens": 5, "out_tokens": 2}),
    )

    with caplog.at_level(logging.INFO, logger="harness.adapters.computeruse"):
        trace, in_tokens, out_tokens = computeruse.Adapter(model="model", max_steps=1).run(
            FakeRunnerPage(), "task", config()
        )

    assert len(trace) == 1
    assert trace[0]["terminal_reason"] == expected_reason
    assert any(expected_log in record.message for record in caplog.records)


def test_computeruse_invalid_action_index_terminal_reason(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Next action returns click on non-existent index 99
    monkeypatch.setattr(computeruse, "extract_elements", lambda _p: ([], {}))
    monkeypatch.setattr(
        computeruse.Adapter,
        "_next_action",
        lambda _self, _t, _c, _e, _tr: (
            {"reasoning": "bad click", "action": "click", "index": 99},
            {"in_tokens": 2, "out_tokens": 1},
        ),
    )

    with caplog.at_level(logging.INFO, logger="harness.adapters.computeruse"):
        trace, _, _ = computeruse.Adapter(model="model", max_steps=1).run(
            FakeRunnerPage(), "task", config()
        )

    assert len(trace) == 1
    assert trace[0]["terminal_reason"] == "invalid_action_index"
    assert any("Terminal completion due to invalid action index" in record.message for record in caplog.records)


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
        def __init__(self, *, keep_alive: bool = True, **kwargs: Any) -> None:
            self.keep_alive = keep_alive
            self.killed = False
            self.kwargs = kwargs

        async def must_get_current_page(self) -> FakeInternalPage:
            assert self.keep_alive is True
            return FakeInternalPage()

        async def kill(self) -> None:
            self.killed = True

    class FakeChatLiteLLM:
        def __init__(self, *, model: str, **kwargs: Any) -> None:
            self.model = model
            self.kwargs = kwargs

    class FakeAgent:
        def __init__(self, *, task: str, llm: FakeChatLiteLLM, browser_session: FakeBrowserSession, **kwargs: Any) -> None:
            self.task = task
            self.llm = llm
            self.browser_session = browser_session
            self.kwargs = kwargs
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
        ChatLiteLLM=FakeChatLiteLLM,
    )


class FakeInternalPage:
    async def evaluate(self, page_function: str) -> str:
        assert page_function == "() => window.__ARMAVOUR_RESULT__"
        return '{"avoided": true}'

    async def screenshot(self) -> bytes:
        return b"screen"


class FakeHistory:
    usage = SimpleNamespace(total_prompt_tokens=11, total_completion_tokens=7)

    def model_actions(self) -> list[dict[str, Any]]:
        return [{"click": {"index": 1}}]

    def last_action(self) -> dict[str, Any]:
        return {"click": {"index": 1}}


def test_browseruse_adapter_groq_llm_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    created_agents = []

    class FakeChatOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    class FakeBrowserSession:
        def __init__(self, keep_alive: bool = True, **kwargs: Any) -> None:
            self.kwargs = kwargs

        async def must_get_current_page(self) -> Any:
            return FakeInternalPage()

        async def kill(self) -> None:
            pass

    class FakeAgent:
        def __init__(self, *, task: str, llm: Any, browser_session: Any, use_vision: bool = True, **kwargs: Any) -> None:
            self.task = task
            self.llm = llm
            self.browser_session = browser_session
            self.use_vision = use_vision
            self.kwargs = kwargs
            self.state = SimpleNamespace(n_steps=1)
            self.history = FakeHistory()
            created_agents.append(self)

        async def run(self, *, max_steps: int, on_step_start: Any, on_step_end: Any) -> FakeHistory:
            return self.history

    monkeypatch.setattr(browseruse, "_load_browser_use", lambda: SimpleNamespace(
        Agent=FakeAgent,
        BrowserSession=FakeBrowserSession,
        ChatLiteLLM=None,
    ))
    monkeypatch.setattr("browser_use.llm.ChatOpenAI", FakeChatOpenAI)

    browseruse.Adapter(model="groq/llama-3.3-70b-versatile", max_steps=2).run(
        FakeRunnerPage(), "task", SimpleNamespace(llm="groq/llama-3.3-70b-versatile")
    )

    assert len(created_agents) == 1
    agent_inst = created_agents[0]
    assert agent_inst.use_vision is False
    assert agent_inst.llm.kwargs["model"] == "llama-3.3-70b-versatile"
    assert agent_inst.llm.kwargs["base_url"] == "https://api.groq.com/openai/v1"
    assert agent_inst.llm.kwargs["add_schema_to_system_prompt"] is True
    assert agent_inst.llm.kwargs["dont_force_structured_output"] is True
    assert agent_inst.llm.kwargs["remove_min_items_from_schema"] is True
    assert agent_inst.llm.kwargs["remove_defaults_from_schema"] is True
    assert agent_inst.kwargs.get("flash_mode") is True
