from __future__ import annotations

from collections import Counter

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine

from harness.adapters import computeruse
from scripts import run_rerun


def test_enumerates_400_configs_10_patterns_4_intensities_10_seeds() -> None:
    configs = run_rerun.enumerate_rerun_configs()
    assert len(configs) == 400
    assert len({c.config_hash for c in configs}) == 400
    assert {c.pattern for c in configs}.isdisjoint(run_rerun.EXCLUDED_PATTERNS)
    assert len({c.pattern for c in configs}) == 10
    assert Counter(c.intensity for c in configs) == {i: 100 for i in run_rerun.INTENSITIES}
    assert {c.seed for c in configs} == set(range(10))
    assert {(c.ui_language, c.instruction_language, c.agent, c.llm) for c in configs} == {
        ("en", "en", "computeruse", "groq/qwen/qwen3.8-27b")
    }


def test_episode_order_pairs_variants_back_to_back_and_alternates_first() -> None:
    configs = run_rerun.enumerate_rerun_configs()
    order = run_rerun.episode_order(configs)
    assert len(order) == 800
    for i in range(0, len(order), 2):
        (c1, v1), (c2, v2) = order[i], order[i + 1]
        assert c1.config_hash == c2.config_hash and {v1, v2} == {"baseline", "fixed"}
    firsts = Counter(order[i][1] for i in range(0, len(order), 2))
    assert firsts == {"baseline": 200, "fixed": 200}


def test_select_configs_only_filters() -> None:
    configs = run_rerun.enumerate_rerun_configs()
    one = run_rerun.select_configs(configs, ["saas_billing:aggressive:0"])
    assert [(c.pattern, c.intensity, c.seed) for c in one] == [("saas_billing", "aggressive", 0)]
    assert len(run_rerun.select_configs(configs, ["nagging"])) == 40
    assert len(run_rerun.select_configs(configs, ["nagging::3", "drip_pricing:control"])) == 4 + 10


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://u:p@localhost:5432/armavour_audit",
        "postgresql+psycopg://u:p@localhost:5432/armavour_ablation",
        "postgresql+psycopg://u:p@localhost:5432/armavour",
        "postgresql+psycopg://u:p@localhost:5432/armavour_matrix",
        "",
    ],
)
def test_refuses_any_database_but_armavour_rerun(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    monkeypatch.setenv("DATABASE_URL", url)
    with pytest.raises(SystemExit, match="armavour_rerun"):
        run_rerun.require_rerun_database()


def test_accepts_armavour_rerun(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/armavour_rerun")
    run_rerun.require_rerun_database()


def test_configure_environment_forces_settings_and_disables_leak(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(computeruse.CONFIG_LEAK_ENV, "1")
    monkeypatch.setenv("CHHAL_MODEL", "something-else")
    for key in ("CHHAL_JUDGE_MODEL", "CHHAL_MAX_STEPS", computeruse.TEMPERATURE_ENV):
        monkeypatch.delenv(key, raising=False)
    run_rerun.configure_environment()
    import os

    assert computeruse.CONFIG_LEAK_ENV not in os.environ
    assert os.environ["CHHAL_MODEL"] == "groq/qwen/qwen3.8-27b"
    assert os.environ["CHHAL_JUDGE_MODEL"] == "groq/openai/gpt-oss-120b"
    assert os.environ["CHHAL_MAX_STEPS"] == "20"
    assert computeruse.sampling_temperature() == 0.7


def test_use_variant_sets_base_url_variant_and_returns_run_id(monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    monkeypatch.delenv("BASE_URL", raising=False)
    assert run_rerun.use_variant("baseline") == "rerun-baseline-t07-01"
    assert os.environ["BASE_URL"] == "http://localhost:5174" and os.environ["ARMAVOUR_TESTBED_VARIANT"] == "baseline"
    assert run_rerun.use_variant("fixed") == "rerun-fixed-t07-01"
    assert os.environ["BASE_URL"] == "http://localhost:5173" and os.environ["ARMAVOUR_TESTBED_VARIANT"] == "fixed"


def _engine(with_new_columns: bool, llm: str | None = None):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    meta = sa.MetaData()
    cols = [sa.Column("id", sa.Integer, primary_key=True), sa.Column("run_id", sa.String), sa.Column("llm", sa.String)]
    if with_new_columns:
        cols += [sa.Column(c, sa.String) for c in run_rerun.NEW_COLUMNS]
    table = sa.Table("episodes", meta, *cols)
    meta.create_all(engine)
    if llm:
        with engine.begin() as conn:
            conn.execute(table.insert(), [{"run_id": "rerun-fixed-t07-01", "llm": llm}])
    return engine


def test_require_schema_needs_migration_0007() -> None:
    with pytest.raises(SystemExit, match="0007"):
        run_rerun.require_schema(_engine(False))
    run_rerun.require_schema(_engine(True))


def test_refuses_mixed_models() -> None:
    run_rerun.refuse_mixed_models(_engine(True, "groq/qwen/qwen3.8-27b"))
    with pytest.raises(SystemExit, match="another model"):
        run_rerun.refuse_mixed_models(_engine(True, "groq/llama-3.1-8b-instant"))


# ---- CHHAL_TEMPERATURE (opt-in) ---------------------------------------------


def test_temperature_defaults_to_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(computeruse.TEMPERATURE_ENV, raising=False)
    assert computeruse.sampling_temperature() == 0
    monkeypatch.setenv(computeruse.TEMPERATURE_ENV, "")
    assert computeruse.sampling_temperature() == 0


@pytest.mark.parametrize("bad", ["-0.1", "2.5", "warm"])
def test_temperature_rejects_bad_values(monkeypatch: pytest.MonkeyPatch, bad: str) -> None:
    monkeypatch.setenv(computeruse.TEMPERATURE_ENV, bad)
    with pytest.raises(ValueError):
        computeruse.sampling_temperature()


def test_temperature_reaches_the_provider_call(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    seen: list[float] = []

    def fake_completion(**kwargs):
        seen.append(kwargs["temperature"])
        message = SimpleNamespace(content='{"reasoning": "", "action": "done", "index": 0, "value": null}')
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=None)

    monkeypatch.setattr(computeruse, "completion_with_rotation", fake_completion)
    adapter = computeruse.Adapter(model="groq/qwen/qwen3.8-27b")
    adapter.provider_latency_seconds = 0.0
    monkeypatch.setenv(computeruse.TEMPERATURE_ENV, "0.7")
    adapter._next_action("task", SimpleNamespace(), [], [])
    monkeypatch.delenv(computeruse.TEMPERATURE_ENV)
    adapter._next_action("task", SimpleNamespace(), [], [])
    assert seen == [0.7, 0]


def test_smoke_run_ids_are_separate(monkeypatch: pytest.MonkeyPatch) -> None:
    import copy

    monkeypatch.setattr(run_rerun, "VARIANTS", copy.deepcopy(run_rerun.VARIANTS))
    run_rerun.use_smoke_run_ids()
    assert {v["run_id"] for v in run_rerun.VARIANTS.values()} == {"smoke-rerun-01-baseline", "smoke-rerun-01-fixed"}
    assert run_rerun.use_variant("fixed") == "smoke-rerun-01-fixed"


# ---- git / dirty-tree / code_sha guards ----------------------------------------


def test_allow_dirty_is_rejected_without_smoke(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Fails in argument parsing, before any guard, database or provider is touched.
    monkeypatch.setattr(run_rerun, "configure_environment", lambda: pytest.fail("must stop before setup"))
    with pytest.raises(SystemExit) as exc:
        run_rerun.main(["--allow-dirty"])
    assert exc.value.code == 2
    assert "--allow-dirty is only for the smoke test" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        run_rerun.main(["--allow-dirty", "--only", "saas_billing:aggressive:0"])


def test_full_run_refuses_dirty_tree_before_any_episode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/armavour_rerun")
    monkeypatch.setattr(run_rerun, "require_git", lambda: "abc123")
    monkeypatch.setattr(run_rerun, "_git", lambda *a: " M harness/runner.py")
    monkeypatch.setattr(run_rerun, "run_episode", lambda *a, **k: pytest.fail("no episode may run"))
    with pytest.raises(SystemExit, match="uncommitted changes"):
        run_rerun.main([])
    with pytest.raises(SystemExit, match="uncommitted changes"):
        run_rerun.main(["--smoke"])  # smoke without --allow-dirty is refused too


def test_dirty_check_ignores_untracked_files_and_lists_tracked_ones(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_git(*args: str) -> str:
        calls.append(args)
        return ""

    monkeypatch.setattr(run_rerun, "_git", fake_git)
    assert run_rerun.require_clean_tree() == []
    assert calls == [("status", "--porcelain", "--untracked-files=no")]
    monkeypatch.setattr(run_rerun, "_git", lambda *a: " M testbed/src/i18n.ts\nM  scripts/run_rerun.py")
    with pytest.raises(SystemExit, match="testbed/src/i18n.ts"):
        run_rerun.require_clean_tree()
    assert run_rerun.require_clean_tree(allow_dirty=True) == [" M testbed/src/i18n.ts", "M  scripts/run_rerun.py"]


def test_refuses_when_git_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_git(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(run_rerun.subprocess, "check_output", no_git)
    with pytest.raises(SystemExit, match="git is unavailable"):
        run_rerun.require_git()


def test_require_git_returns_head_when_git_works() -> None:
    import re

    assert re.fullmatch(r"[0-9a-f]{40}", run_rerun.require_git())


def test_code_sha_change_mid_run_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_rerun, "code_sha", lambda: "abc123")
    run_rerun.require_code_sha("abc123")
    monkeypatch.setattr(run_rerun, "code_sha", lambda: "abc123-dirty")
    with pytest.raises(SystemExit, match="code_sha changed"):
        run_rerun.require_code_sha("abc123")
    monkeypatch.setattr(run_rerun, "code_sha", lambda: None)  # git vanished mid-run
    with pytest.raises(SystemExit, match="code_sha changed"):
        run_rerun.require_code_sha("abc123")


def test_connected_database_must_be_armavour_rerun() -> None:
    from types import SimpleNamespace

    def engine_named(name: str):
        class Conn:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def execute(self, stmt):
                return SimpleNamespace(scalar=lambda: name)

        return SimpleNamespace(connect=Conn)

    run_rerun.require_connected_database(engine_named("armavour_rerun"))
    for other in ("armavour", "armavour_audit", "armavour_ablation", "armavour_matrix"):
        with pytest.raises(SystemExit, match="armavour_rerun"):
            run_rerun.require_connected_database(engine_named(other))


def test_completed_hashes_skips_crashes_and_does_not_swallow_errors() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    meta = sa.MetaData()
    table = sa.Table(
        "episodes", meta, sa.Column("id", sa.Integer, primary_key=True), sa.Column("run_id", sa.String),
        sa.Column("config_hash", sa.String), sa.Column("outcome", sa.String),
    )
    meta.create_all(engine)
    with engine.begin() as conn:
        conn.execute(table.insert(), [
            {"run_id": "rerun-fixed-t07-01", "config_hash": "a", "outcome": "avoided"},
            {"run_id": "rerun-fixed-t07-01", "config_hash": "b", "outcome": None},
            {"run_id": "rerun-baseline-t07-01", "config_hash": "c", "outcome": "deceived"},
        ])
    assert run_rerun.completed_hashes("rerun-fixed-t07-01", engine) == {"a"}
    with pytest.raises(Exception):
        run_rerun.completed_hashes("rerun-fixed-t07-01", create_engine("sqlite+pysqlite:///:memory:"))
