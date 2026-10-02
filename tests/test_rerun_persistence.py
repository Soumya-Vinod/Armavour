"""Phase 1 of the corrected rerun: raw oracle payload, testbed variant and
terminal reason are persisted per episode (migration 0007), while the legacy
`outcome` column is still the unchanged evaluator (v1) score."""
from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, select

from harness.adapters import browseruse, computeruse
from harness.config import EpisodeConfig
from harness.evaluator import EvaluationResult
from harness.logger import log_episode
from harness.runner import run_episode

REPO = Path(__file__).resolve().parent.parent
MIGRATION = REPO / "infra" / "migrations" / "versions" / "0007_oracle_result_variant.py"


def _load_migration() -> Any:
    spec = importlib.util.spec_from_file_location("m0007", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_migration_0007_chain_and_revision_length() -> None:
    m = _load_migration()
    assert len(m.revision) <= 32
    assert m.down_revision == "0006_judge_model_code_sha"


def test_migration_0007_adds_nullable_columns_without_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    m = _load_migration()
    added: list[sa.Column] = []
    monkeypatch.setattr(m.op, "add_column", lambda table, column: added.append(column), raising=False)
    m.upgrade()
    by_name = {c.name: c for c in added}
    assert set(by_name) == {"oracle_result", "testbed_variant", "terminal_reason"}
    for column in added:
        assert column.nullable is True
        assert column.server_default is None
        assert column.default is None
    assert by_name["testbed_variant"].type.length == 32
    assert type(by_name["oracle_result"].type).__name__ == "JSONB"


# ---- runner ---------------------------------------------------------------


class _FakePage:
    def __init__(self, oracle: Any) -> None:
        self._oracle = oracle

    def set_default_timeout(self, timeout_ms: int) -> None:
        pass

    def goto(self, url: str, *, wait_until: str, timeout: int) -> None:
        pass

    def evaluate(self, script: str) -> Any:
        assert "__ARMAVOUR_RESULT__" in script
        return self._oracle


def _patch_browser(monkeypatch: pytest.MonkeyPatch, page: _FakePage, adapter: Any, evaluation: Any) -> list[dict]:
    class Browser:
        def new_page(self):
            return page

        def close(self) -> None:
            pass

    class Context:
        def __enter__(self):
            return SimpleNamespace(chromium=SimpleNamespace(launch=lambda: Browser()))

        def __exit__(self, *exc: Any) -> None:
            pass

    logged: list[dict] = []
    monkeypatch.setattr("harness.runner.load_task_prompt", lambda task_id: "task")
    monkeypatch.setattr("harness.runner.create_adapter", lambda config: adapter)
    monkeypatch.setattr("harness.runner.sync_playwright", lambda: Context())
    monkeypatch.setattr("harness.runner.build_episode_url", lambda config: "http://example.test/")
    monkeypatch.setattr("harness.runner.evaluate", evaluation)
    monkeypatch.setattr("harness.runner.log_episode", lambda row: logged.append(row))
    return logged


def _config() -> EpisodeConfig:
    return EpisodeConfig(
        site="ticketing", task_id="sb_free", pattern="saas_billing", intensity="aggressive",
        language="en", agent="computeruse", llm="model", seed=0,
    )


class _Adapter:
    terminal_reason = "explicit_done"

    def run(self, page: Any, task: str, config: Any):
        return [{"step": 0, "action": {"action": "done"}, "terminal_reason": "explicit_done"}], 1, 1


def _ok_eval(*args: Any, **kwargs: Any) -> EvaluationResult:
    return EvaluationResult(placed=True, avoided=False, outcome="DC", judge_flag=None,
                            judge_evidence=None, oracle_result={"avoided": False})


def test_run_episode_stores_raw_oracle_variant_and_terminal_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    oracle = {"pattern": "saas_billing", "avoided": False, "completed": True, "recurring": True}
    logged = _patch_browser(monkeypatch, _FakePage(oracle), _Adapter(), _ok_eval)
    monkeypatch.setenv("ARMAVOUR_TESTBED_VARIANT", "fixed")

    row = run_episode(_config(), run_id="r")

    assert row["oracle_result"] == oracle
    assert row["testbed_variant"] == "fixed"
    assert row["terminal_reason"] == "explicit_done"
    assert row["outcome"] == "DC"  # legacy evaluator score, untouched
    assert logged and logged[0]["oracle_result"] == oracle


def test_run_episode_unset_oracle_and_variant_are_null(monkeypatch: pytest.MonkeyPatch) -> None:
    def ef_eval(*args: Any, **kwargs: Any) -> EvaluationResult:
        return EvaluationResult(placed=False, avoided=True, outcome="EF", judge_flag=None,
                                judge_evidence=None, oracle_result=None)

    _patch_browser(monkeypatch, _FakePage(None), _Adapter(), ef_eval)
    monkeypatch.delenv("ARMAVOUR_TESTBED_VARIANT", raising=False)

    row = run_episode(_config(), run_id="r")

    # v1 still scores the no-oracle episode EF/avoided; the raw column keeps it NULL.
    assert row["outcome"] == "EF"
    assert row["oracle_result"] is None
    assert row["testbed_variant"] is None


def test_crash_after_adapter_keeps_oracle_and_marks_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args: Any, **kwargs: Any) -> EvaluationResult:
        raise RuntimeError("judge exploded")

    oracle = {"avoided": True, "completed": True}
    _patch_browser(monkeypatch, _FakePage(oracle), _Adapter(), boom)

    row = run_episode(_config(), run_id="r")

    assert row["outcome"] is None
    assert row["oracle_result"] == oracle
    assert row["terminal_reason"] == "crash"


def test_terminal_reason_falls_back_to_trace(monkeypatch: pytest.MonkeyPatch) -> None:
    class NoAttrAdapter:
        def run(self, page: Any, task: str, config: Any):
            return [{"step": 0}, {"step": 1, "terminal_reason": "step_cap"}], 1, 1

    _patch_browser(monkeypatch, _FakePage(None), NoAttrAdapter(), _ok_eval)
    assert run_episode(_config(), run_id="r")["terminal_reason"] == "step_cap"


def test_oracle_snapshot_failure_never_fails_episode(monkeypatch: pytest.MonkeyPatch) -> None:
    class BadPage(_FakePage):
        def evaluate(self, script: str) -> Any:
            raise RuntimeError("page closed")

    _patch_browser(monkeypatch, BadPage(None), _Adapter(), _ok_eval)
    row = run_episode(_config(), run_id="r")
    assert row["outcome"] == "DC"
    assert row["oracle_result"] is None


# ---- adapters -------------------------------------------------------------


class _CUPage:
    def evaluate(self, script: str, arg: Any = None) -> Any:
        return None

    def screenshot(self) -> bytes:
        return b""


def test_computeruse_step_budget_exhaustion_is_step_cap(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setattr(computeruse, "extract_elements", lambda _p: ([], {}))
    monkeypatch.setattr(
        computeruse.Adapter, "_next_action",
        lambda _s, _t, _c, _e, _tr: ({"reasoning": "scroll", "action": "scroll", "direction": "down"}, {}),
    )
    monkeypatch.setattr(computeruse.Adapter, "_execute", lambda _s, _a, _h: None)
    adapter = computeruse.Adapter(model="model", max_steps=3)
    with caplog.at_level(logging.INFO, logger="harness.adapters.computeruse"):
        trace, _, _ = adapter.run(_CUPage(), "task", SimpleNamespace(llm="model"))
    assert len(trace) == 3
    assert trace[-1]["terminal_reason"] == "step_cap"
    assert adapter.terminal_reason == "step_cap"


def test_computeruse_explicit_done_sets_adapter_terminal_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(computeruse, "extract_elements", lambda _p: ([], {}))
    monkeypatch.setattr(
        computeruse.Adapter, "_next_action",
        lambda _s, _t, _c, _e, _tr: ({"reasoning": "decline", "action": "done"}, {}),
    )
    adapter = computeruse.Adapter(model="model", max_steps=5)
    adapter.run(_CUPage(), "task", SimpleNamespace(llm="model"))
    assert adapter.terminal_reason == "explicit_done"


@pytest.mark.parametrize(
    ("history", "oracle", "expected"),
    [
        (SimpleNamespace(is_done=lambda: True, number_of_steps=lambda: 2), {"avoided": True}, "normal_completion"),
        (SimpleNamespace(is_done=lambda: True, number_of_steps=lambda: 2), None, "explicit_done"),
        (SimpleNamespace(is_done=lambda: False, number_of_steps=lambda: 5), None, "step_cap"),
        (SimpleNamespace(is_done=lambda: False, number_of_steps=lambda: 2), None, "silent_stop"),
        (None, None, "silent_stop"),
    ],
)
def test_browseruse_terminal_reason(history: Any, oracle: Any, expected: str) -> None:
    assert browseruse._terminal_reason(history, oracle, 5) == expected


# ---- logger ---------------------------------------------------------------


def _table(metadata: sa.MetaData, *, new_columns: bool) -> sa.Table:
    cols = [
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("config_hash", sa.String(), nullable=False),
        sa.Column("outcome", sa.String(), nullable=True),
        sa.Column("trace", sa.JSON(), nullable=False),
        sa.UniqueConstraint("config_hash", "run_id"),
    ]
    if new_columns:
        cols += [
            sa.Column("oracle_result", sa.JSON(), nullable=True),
            sa.Column("testbed_variant", sa.String(32), nullable=True),
            sa.Column("terminal_reason", sa.String(64), nullable=True),
        ]
    return sa.Table("episodes", metadata, *cols)


def _row() -> dict[str, Any]:
    return {
        "run_id": "r", "config_hash": "h", "outcome": "EF", "trace": [],
        "oracle_result": {"avoided": True, "completed": False, "abandoned": True},
        "testbed_variant": "baseline", "terminal_reason": "normal_completion",
    }


def test_logger_persists_new_columns() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    table = _table(sa.MetaData(), new_columns=True)
    table.metadata.create_all(engine)
    log_episode(_row(), engine=engine, table=table)
    with engine.begin() as conn:
        stored = conn.execute(select(table)).mappings().one()
    assert stored["oracle_result"] == {"avoided": True, "completed": False, "abandoned": True}
    assert stored["testbed_variant"] == "baseline"
    assert stored["terminal_reason"] == "normal_completion"


def test_logger_drops_new_keys_on_pre_0007_schema() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    table = _table(sa.MetaData(), new_columns=False)
    table.metadata.create_all(engine)
    log_episode(_row(), engine=engine, table=table)
    with engine.begin() as conn:
        assert conn.execute(select(table.c.outcome)).scalar_one() == "EF"
