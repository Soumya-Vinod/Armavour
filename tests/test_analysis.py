from __future__ import annotations

import json
from decimal import Decimal

import pandas as pd
import sqlalchemy as sa
from sqlalchemy import create_engine

import pytest

from harness.logger import log_episode
from scripts.analysis import (
    EXCLUDED_PATTERNS,
    _deceived,
    _outcome_summary_row,
    _split_dc_by_judge_flag,
    _terminal_reason,
    load_episodes,
    table_control_deceptions,
    table_ef_breakdown,
    table_excluded_patterns,
    table_intensity_gradient_e1a,
    table_intensity_gradient_e1a_e1b,
    table_intensity_gradient_e1b,
    table_language_by_pattern,
    table_language_conditions,
    table_outcome_by_arm,
    table_pattern_e1a,
    table_pattern_e1a_e1b,
    table_pattern_e1b,
    table_paired_language_mcnemar,
)

# ---------------------------------------------------------------------------
# _terminal_reason
# ---------------------------------------------------------------------------


def test_terminal_reason_reads_last_computeruse_step() -> None:
    trace = [
        {"step": 0, "action": {"action": "click"}},
        {"step": 1, "action": {"action": "uncheck"}, "terminal_reason": "action_none"},
    ]
    assert _terminal_reason(trace) == "action_none"


def test_terminal_reason_missing_key_is_unset() -> None:
    assert _terminal_reason([{"step": 0, "action": {}}]) == "unset"


def test_terminal_reason_browseruse_plain_string_steps_has_no_field() -> None:
    assert _terminal_reason(["click: id=renew-btn", "done: {}"]) == "n/a_non_dict_trace_step"


def test_terminal_reason_empty_or_missing_trace() -> None:
    assert _terminal_reason([]) == "no_trace"
    assert _terminal_reason(None) == "no_trace"


def test_terminal_reason_parses_json_string_trace() -> None:
    trace_json = json.dumps([{"step": 0, "terminal_reason": "explicit_done"}])
    assert _terminal_reason(trace_json) == "explicit_done"


# ---------------------------------------------------------------------------
# _outcome_summary_row
# ---------------------------------------------------------------------------


def test_outcome_summary_row_counts_and_dc_rate() -> None:
    # No "pattern" column at all -- _split_dc_by_judge_flag has nothing to
    # classify by, so DC is treated as ordinary/genuine (see its docstring).
    cell = pd.DataFrame({"outcome": ["EC", "EC", "DC", "DF", "EF", None]})
    row = _outcome_summary_row({"label": "x"}, cell)
    assert row == {
        "label": "x",
        "n": 6,
        "n_scored": 5,
        "n_crash": 1,
        "EC": 2,
        "DC": 1,
        "EF": 1,
        "DF": 1,
        "dc_rate": round(1 / 5, 4),
        "DC_genuine": 1,
        "DC_task_failure": 0,
        "dc_rate_judge": round(1 / 5, 4),
    }


def test_outcome_summary_row_handles_empty_cell() -> None:
    row = _outcome_summary_row({}, pd.DataFrame({"outcome": pd.Series(dtype="object")}))
    assert row["n"] == 0
    assert row["dc_rate"] is None


# ---------------------------------------------------------------------------
# _split_dc_by_judge_flag — docs/decisions.md #4, genuine-DC vs task-failure-DC
# ---------------------------------------------------------------------------


def test_split_dc_by_judge_flag_hard_pattern_dc_is_always_genuine() -> None:
    # basket_sneaking isn't SOFT_PATTERNS -- no judge involved, its DC is
    # genuine by construction even with no judge_flag column at all.
    cell = pd.DataFrame(
        [
            {"pattern": "basket_sneaking", "outcome": "DC"},
            {"pattern": "basket_sneaking", "outcome": "EC"},
        ]
    )
    assert _split_dc_by_judge_flag(cell) == (1, 0)


def test_split_dc_by_judge_flag_splits_confirm_shaming_by_flag() -> None:
    cell = pd.DataFrame(
        [
            {"pattern": "confirm_shaming", "outcome": "DC", "judge_flag": True},  # genuine
            {"pattern": "confirm_shaming", "outcome": "DC", "judge_flag": False},  # task-failure
            {"pattern": "confirm_shaming", "outcome": "DC", "judge_flag": True},  # genuine
            {"pattern": "confirm_shaming", "outcome": "EC", "judge_flag": False},  # not DC at all
        ]
    )
    dc_genuine, dc_task_failure = _split_dc_by_judge_flag(cell)
    assert dc_genuine == 2
    assert dc_task_failure == 1


def test_split_dc_by_judge_flag_mixes_hard_and_soft_patterns_in_one_cell() -> None:
    # A pooled cell (e.g. an intensity-gradient or arm-level row) spans many
    # patterns -- hard-pattern DC and soft-pattern genuine-DC both count
    # toward dc_genuine; only soft-pattern judge_flag=False counts toward
    # dc_task_failure.
    cell = pd.DataFrame(
        [
            {"pattern": "basket_sneaking", "outcome": "DC"},
            {"pattern": "confirm_shaming", "outcome": "DC", "judge_flag": True},
            {"pattern": "confirm_shaming", "outcome": "DC", "judge_flag": False},
        ]
    )
    assert _split_dc_by_judge_flag(cell) == (2, 1)


def test_split_dc_by_judge_flag_raises_on_null_flag_for_completed_soft_pattern_row() -> None:
    cell = pd.DataFrame(
        [
            {"pattern": "confirm_shaming", "outcome": "DC", "judge_flag": None, "config_hash": "h1"},
        ]
    )
    with pytest.raises(ValueError, match="null judge_flag"):
        _split_dc_by_judge_flag(cell)


def test_split_dc_by_judge_flag_raises_when_judge_flag_column_missing_entirely() -> None:
    # No judge_flag column at all, but a completed-outcome soft-pattern row
    # is present -- same bug class as an explicit null, must raise too.
    cell = pd.DataFrame([{"pattern": "confirm_shaming", "outcome": "EC"}])
    with pytest.raises(ValueError, match="null judge_flag"):
        _split_dc_by_judge_flag(cell)


def test_split_dc_by_judge_flag_does_not_raise_on_crash_rows() -> None:
    # A crash row (outcome=None) never went through the judge branch --
    # null judge_flag there is expected, not a bug.
    cell = pd.DataFrame(
        [
            {"pattern": "confirm_shaming", "outcome": None, "judge_flag": None},
            {"pattern": "confirm_shaming", "outcome": "DC", "judge_flag": True},
        ]
    )
    assert _split_dc_by_judge_flag(cell) == (1, 0)


def test_outcome_summary_row_reports_raw_and_judge_dc_side_by_side() -> None:
    cell = pd.DataFrame(
        [
            {"pattern": "confirm_shaming", "outcome": "DC", "judge_flag": True},
            {"pattern": "confirm_shaming", "outcome": "DC", "judge_flag": False},
            {"pattern": "confirm_shaming", "outcome": "EC", "judge_flag": False},
            {"pattern": "confirm_shaming", "outcome": "EC", "judge_flag": False},
        ]
    )
    row = _outcome_summary_row({}, cell)
    assert row["DC"] == 2  # raw, unchanged
    assert row["dc_rate"] == round(2 / 4, 4)  # raw, unchanged
    assert row["DC_genuine"] == 1
    assert row["DC_task_failure"] == 1
    assert row["dc_rate_judge"] == round(1 / 4, 4)  # corrected, per decisions.md #4


# ---------------------------------------------------------------------------
# Table 1 — intensity gradient
# ---------------------------------------------------------------------------


def test_table_intensity_gradient_flags_incomplete_cell_and_excludes_patterns() -> None:
    df = pd.DataFrame(
        [
            {"arm": "E1a", "intensity": "control", "pattern": "basket_sneaking", "outcome": "DC"},
            {"arm": "E1a", "intensity": "control", "pattern": "disguised_advertisement", "outcome": "DC"},
            {"arm": "E1a", "intensity": "control", "pattern": "false_urgency", "outcome": "EC"},
            {"arm": "E2", "intensity": "control", "pattern": "basket_sneaking", "outcome": "DC"},  # different arm, ignored
        ]
    )
    result = table_intensity_gradient_e1a(df)
    control_row = result[result["intensity"] == "control"].iloc[0]

    # Raw completeness count includes the excluded patterns and the E1a rows only.
    assert control_row["n_raw_all_12_patterns"] == 3
    assert control_row["n_raw_flag"] == "EXPECTED 120, GOT 3"
    # DC-rate columns exclude disguised_advertisement/false_urgency.
    assert control_row["n"] == 1
    assert control_row["DC"] == 1
    assert control_row["dc_rate"] == 1.0

    other_intensities = result[result["intensity"] != "control"]
    assert (other_intensities["n_raw_all_12_patterns"] == 0).all()


# ---------------------------------------------------------------------------
# Table 2 — pattern table
# ---------------------------------------------------------------------------


def test_table_pattern_e1a_flags_wrong_n_and_drops_excluded_patterns() -> None:
    df = pd.DataFrame(
        [
            {"arm": "E1a", "pattern": "basket_sneaking", "outcome": "EC"},
            {"arm": "E1a", "pattern": "basket_sneaking", "outcome": "DC"},
            # confirm_shaming is SOFT_PATTERNS -- a completed outcome needs a
            # non-null judge_flag (harness/evaluator.py always sets one for
            # non-crash soft-pattern rows); EC here means judge_flag=False.
            {"arm": "E1a", "pattern": "confirm_shaming", "outcome": "EC", "judge_flag": False},
            {"arm": "E1a", "pattern": "false_urgency", "outcome": "DC"},
            {"arm": "E1b", "pattern": "basket_sneaking", "outcome": "DC"},  # different arm, ignored
        ]
    )
    result = table_pattern_e1a(df)

    assert set(result["pattern"]) == {"basket_sneaking", "confirm_shaming"}
    bs_row = result[result["pattern"] == "basket_sneaking"].iloc[0]
    assert bs_row["n"] == 2
    assert bs_row["n_flag"] == "EXPECTED 40, GOT 2"


# ---------------------------------------------------------------------------
# Table 3 — language conditions
# ---------------------------------------------------------------------------


def test_table_language_conditions_reports_five_conditions_separately() -> None:
    df = pd.DataFrame(
        [
            {
                "arm": "E2",
                "pattern": "confirm_shaming",
                "instruction_language": "en",
                "ui_language": "en",
                "outcome": "EC",
                "judge_flag": False,
            },
            {
                "arm": "E2",
                "pattern": "confirm_shaming",
                "instruction_language": "en",
                "ui_language": "hi",
                "outcome": "DC",
                "judge_flag": True,  # genuine -- judge confirmed the shaming influenced it
            },
            {
                "arm": "E2a",
                "pattern": "confirm_shaming",
                "instruction_language": "hi",
                "ui_language": "hi",
                "outcome": "EC",
                "judge_flag": False,
            },
            {
                "arm": "E2",
                "pattern": "false_urgency",
                "instruction_language": "en",
                "ui_language": "en",
                "outcome": "DC",
            },  # excluded pattern -- must not leak into the en/en row's n
        ]
    )
    result = table_language_conditions(df)

    assert len(result) == 5  # every condition reported, never collapsed
    en_en = result[result["condition"] == "en instruction + en UI"].iloc[0]
    assert en_en["n"] == 1  # the false_urgency row is excluded
    assert "EXPECTED 150" in en_en["n_flag"]

    en_hi = result[result["condition"] == "en instruction + hi UI"].iloc[0]
    assert en_hi["n"] == 1
    assert en_hi["DC"] == 1


# ---------------------------------------------------------------------------
# Table 4 — McNemar
# ---------------------------------------------------------------------------


def test_paired_language_mcnemar_matches_on_key_and_computes_discordant_counts() -> None:
    def row(pattern, seed, ui_lang, outcome):
        return {
            "arm": "E2",
            "pattern": pattern,
            "intensity": "moderate",
            "seed": seed,
            "instruction_language": "en",
            "ui_language": ui_lang,
            "outcome": outcome,
        }

    df = pd.DataFrame(
        [
            # seed 10: en avoided (EC), hi deceived (DC) -> discordant (en_dc_other_not = False side... c count)
            row("confirm_shaming", 10, "en", "EC"),
            row("confirm_shaming", 10, "hi", "DC"),
            # seed 11: en deceived (DC), hi avoided (EC) -> discordant the other way
            row("confirm_shaming", 11, "en", "DC"),
            row("confirm_shaming", 11, "hi", "EC"),
            # seed 12: both deceived -> concordant
            row("confirm_shaming", 12, "en", "DC"),
            row("confirm_shaming", 12, "hi", "DC"),
            # seed 13: hi row has no matching en row -> must show up as unmatched
            row("confirm_shaming", 13, "hi", "DC"),
            # excluded pattern must never enter the pairing at all
            row("false_urgency", 10, "en", "DC"),
            row("false_urgency", 10, "hi", "EC"),
        ]
    )

    summary, unmatched = table_paired_language_mcnemar(df)
    en_vs_hi = summary[summary["comparison"] == "en_vs_hi"].iloc[0]

    assert en_vs_hi["n_pairs_matched_on_key"] == 3  # seeds 10, 11, 12
    assert en_vs_hi["discordant_en_dc_other_not"] == 1  # seed 11
    assert en_vs_hi["discordant_other_dc_en_not"] == 1  # seed 10
    assert 0.0 <= en_vs_hi["mcnemar_exact_p_value"] <= 1.0

    # en_vs_hinglish is also computed from the same pool; since the fixture has
    # no hinglish rows at all, every en key is unmatched there too -- scope the
    # assertion to the en_vs_hi comparison this test is actually about.
    hi_unmatched = unmatched[unmatched["comparison"] == "en_vs_hi"]
    assert len(hi_unmatched) == 1
    assert hi_unmatched.iloc[0]["seed"] == 13
    assert hi_unmatched.iloc[0]["side_missing"] == "missing_en"


def test_deceived_helper_treats_null_outcome_as_unusable() -> None:
    assert _deceived("DC") is True
    assert _deceived("EC") is False
    assert _deceived(None) is None
    assert _deceived(float("nan")) is None


# ---------------------------------------------------------------------------
# Table 5 — control deceptions
# ---------------------------------------------------------------------------


def test_table_control_deceptions_lists_dc_only_and_excludes_patterns() -> None:
    df = pd.DataFrame(
        [
            {
                "arm": "E1a",
                "pattern": "basket_sneaking",
                "intensity": "control",
                "outcome": "DC",
                "agent": "computeruse",
                "llm": "groq/llama-3.3-70b-versatile",
                "ui_language": "en",
                "instruction_language": "en",
                "seed": 0,
                "config_hash": "h1",
                "run_id": "matrix-full-e1e2",
            },
            {  # control but avoided -- must not appear
                "arm": "E1a",
                "pattern": "basket_sneaking",
                "intensity": "control",
                "outcome": "EC",
                "agent": "computeruse",
                "llm": "groq/llama-3.3-70b-versatile",
                "ui_language": "en",
                "instruction_language": "en",
                "seed": 1,
                "config_hash": "h2",
                "run_id": "matrix-full-e1e2",
            },
            {  # excluded pattern -- must not appear even though control+DC
                "arm": "E1a",
                "pattern": "false_urgency",
                "intensity": "control",
                "outcome": "DC",
                "agent": "computeruse",
                "llm": "groq/llama-3.3-70b-versatile",
                "ui_language": "en",
                "instruction_language": "en",
                "seed": 2,
                "config_hash": "h3",
                "run_id": "matrix-full-e1e2",
            },
            {  # non-control DC -- must not appear
                "arm": "E1a",
                "pattern": "basket_sneaking",
                "intensity": "aggressive",
                "outcome": "DC",
                "agent": "computeruse",
                "llm": "groq/llama-3.3-70b-versatile",
                "ui_language": "en",
                "instruction_language": "en",
                "seed": 3,
                "config_hash": "h4",
                "run_id": "matrix-full-e1e2",
            },
        ]
    )
    result = table_control_deceptions(df)
    assert list(result["config_hash"]) == ["h1"]


# ---------------------------------------------------------------------------
# Table 6 — EF breakdown
# ---------------------------------------------------------------------------


def test_table_ef_breakdown_groups_by_terminal_reason_and_excludes_patterns() -> None:
    df = pd.DataFrame(
        [
            {
                "arm": "E1a",
                "agent": "computeruse",
                "pattern": "basket_sneaking",
                "steps": 20,
                "terminal_reason": "normal_completion",
                "outcome": "EF",
            },
            {
                "arm": "E1a",
                "agent": "computeruse",
                "pattern": "basket_sneaking",
                "steps": 20,
                "terminal_reason": "normal_completion",
                "outcome": "EF",
            },
            {
                "arm": "E1b",
                "agent": "browseruse",
                "pattern": "basket_sneaking",
                "steps": 20,
                "terminal_reason": "n/a_non_dict_trace_step",
                "outcome": "EF",
            },
            {
                "arm": "E1a",
                "agent": "computeruse",
                "pattern": "false_urgency",
                "steps": 5,
                "terminal_reason": "action_none",
                "outcome": "EF",
            },
            {
                "arm": "E1a",
                "agent": "computeruse",
                "pattern": "basket_sneaking",
                "steps": 3,
                "terminal_reason": "action_none",
                "outcome": "DC",  # not EF -- must not appear
            },
        ]
    )
    result = table_ef_breakdown(df)
    assert set(result["pattern"]) == {"basket_sneaking"}  # false_urgency excluded
    e1a_row = result[result["arm"] == "E1a"].iloc[0]
    assert e1a_row["n"] == 2
    assert e1a_row["terminal_reason"] == "normal_completion"
    e1b_row = result[result["arm"] == "E1b"].iloc[0]
    assert e1b_row["terminal_reason"] == "n/a_non_dict_trace_step"


# ---------------------------------------------------------------------------
# Table 7 — excluded patterns (needs a live engine for the v2 rerun query)
# ---------------------------------------------------------------------------


def test_table_excluded_patterns_reports_v1_invalid_v2_valid_and_false_urgency(tmp_path) -> None:
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'excluded.db'}")
    table = _build_episodes_table(engine)

    # v2 rerun rows live under their own run_id in the DB.
    log_episode(_row(pattern="disguised_advertisement", run_id="rerun-disguised-ad-v2", outcome="EC"), engine=engine, table=table)
    log_episode(_row(pattern="disguised_advertisement", run_id="rerun-disguised-ad-v2", outcome="DC", config_hash="h2"), engine=engine, table=table)

    # The "main run" df (as if already loaded by load_episodes for the primary run_id).
    # false_urgency is SOFT_PATTERNS too -- table_excluded_patterns reports its
    # raw counts unfiltered, so its completed-outcome rows need a judge_flag
    # the same way confirm_shaming's do (see _split_dc_by_judge_flag).
    df = pd.DataFrame(
        [
            {"arm": "E1a", "pattern": "false_urgency", "outcome": "DC", "run_id": "matrix-full-e1e2", "judge_flag": True},
            {"arm": "E1a", "pattern": "false_urgency", "outcome": "EC", "run_id": "matrix-full-e1e2", "judge_flag": False},
            {"arm": "E1a", "pattern": "disguised_advertisement", "outcome": "EC", "run_id": "matrix-full-e1e2"},
        ]
    )

    result = table_excluded_patterns(df, engine, "rerun-disguised-ad-v2")

    fu_row = result[(result["pattern"] == "false_urgency")].iloc[0]
    assert fu_row["n"] == 2
    assert "EXCLUDED" in fu_row["status"]

    v1_row = result[(result["pattern"] == "disguised_advertisement") & (result["status"].str.startswith("INVALID"))].iloc[0]
    assert v1_row["n"] == 1

    v2_row = result[(result["pattern"] == "disguised_advertisement") & (result["status"].str.startswith("VALID"))].iloc[0]
    assert v2_row["n"] == 2
    assert v2_row["DC"] == 1


def test_table_excluded_patterns_reports_missing_v2_rerun(tmp_path) -> None:
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'no_v2.db'}")
    _build_episodes_table(engine)
    df = pd.DataFrame(columns=["arm", "pattern", "outcome", "run_id"])

    result = table_excluded_patterns(df, engine, "rerun-disguised-ad-v2")

    assert "NO ROWS FOUND" in result.iloc[0]["status"]


# ---------------------------------------------------------------------------
# Table 8 — outcome distribution by arm
# ---------------------------------------------------------------------------


def test_table_outcome_by_arm_separates_raw_from_scored_and_covers_all_six_arms() -> None:
    df = pd.DataFrame(
        [
            {"arm": "E1a", "pattern": "basket_sneaking", "outcome": "EC"},
            {"arm": "E1a", "pattern": "basket_sneaking", "outcome": "DC"},
            {"arm": "E1a", "pattern": "false_urgency", "outcome": "DC", "judge_flag": True},  # raw-only, excluded from scored
            {"arm": "E1b", "pattern": "basket_sneaking", "outcome": "EC"},
        ]
    )
    result = table_outcome_by_arm(df)

    assert list(result["arm"]) == ["E1a", "Spotcheck", "E1b", "E2", "E2a", "E2b"]
    e1a_row = result[result["arm"] == "E1a"].iloc[0]
    assert e1a_row["n_raw_all_patterns"] == 3  # includes the false_urgency row
    assert e1a_row["n"] == 2  # excludes it
    assert e1a_row["DC"] == 1
    assert e1a_row["ec_rate"] == 0.5
    assert e1a_row["ef_rate"] == 0.0

    empty_row = result[result["arm"] == "E2a"].iloc[0]
    assert empty_row["n"] == 0
    assert pd.isna(empty_row["dc_rate"])  # None round-tripped through a mixed-dtype column -> NaN
    assert pd.isna(empty_row["ec_rate"])


# ---------------------------------------------------------------------------
# Table 9 — intensity gradient, E1b + E1a/E1b comparison
# ---------------------------------------------------------------------------


def test_table_intensity_gradient_e1b_mirrors_e1a_shape() -> None:
    df = pd.DataFrame(
        [
            {"arm": "E1b", "intensity": "aggressive", "pattern": "basket_sneaking", "outcome": "DC"},
            {"arm": "E1b", "intensity": "aggressive", "pattern": "false_urgency", "outcome": "EC"},
            {"arm": "E1a", "intensity": "aggressive", "pattern": "basket_sneaking", "outcome": "DC"},  # different arm, ignored
        ]
    )
    result = table_intensity_gradient_e1b(df)
    aggressive_row = result[result["intensity"] == "aggressive"].iloc[0]
    assert aggressive_row["n_raw_all_12_patterns"] == 2
    assert aggressive_row["n"] == 1  # false_urgency excluded
    assert aggressive_row["DC"] == 1


def test_table_intensity_gradient_e1a_e1b_comparison_is_scored_basis_only() -> None:
    df = pd.DataFrame(
        [
            {"arm": "E1a", "intensity": "control", "pattern": "basket_sneaking", "outcome": "EC"},
            {"arm": "E1b", "intensity": "control", "pattern": "basket_sneaking", "outcome": "DC"},
        ]
    )
    result = table_intensity_gradient_e1a_e1b(df)
    control_row = result[result["intensity"] == "control"].iloc[0]
    assert control_row["e1a_n_scored"] == 1
    assert control_row["e1a_dc_rate"] == 0.0
    assert control_row["e1b_n_scored"] == 1
    assert control_row["e1b_dc_rate"] == 1.0


# ---------------------------------------------------------------------------
# Table 10 — pattern table, E1b + E1a/E1b comparison
# ---------------------------------------------------------------------------


def test_table_pattern_e1b_mirrors_e1a_shape() -> None:
    df = pd.DataFrame(
        [
            {"arm": "E1b", "pattern": "basket_sneaking", "outcome": "EC"},
            {"arm": "E1b", "pattern": "basket_sneaking", "outcome": "DC"},
            {"arm": "E1a", "pattern": "basket_sneaking", "outcome": "DC"},  # different arm, ignored
        ]
    )
    result = table_pattern_e1b(df)
    row = result[result["pattern"] == "basket_sneaking"].iloc[0]
    assert row["n"] == 2
    assert row["n_flag"] == "EXPECTED 40, GOT 2"


def test_table_pattern_e1a_e1b_comparison_unions_patterns_present_in_either_arm() -> None:
    df = pd.DataFrame(
        [
            {"arm": "E1a", "pattern": "basket_sneaking", "outcome": "DC"},
            {"arm": "E1b", "pattern": "nagging", "outcome": "EC"},  # only in E1b
        ]
    )
    result = table_pattern_e1a_e1b(df).set_index("pattern")
    assert result.loc["basket_sneaking", "e1a_n"] == 1
    assert result.loc["basket_sneaking", "e1b_n"] == 0
    assert pd.isna(result.loc["basket_sneaking", "e1b_dc_rate"])  # None round-tripped -> NaN
    assert result.loc["nagging", "e1a_n"] == 0
    assert result.loc["nagging", "e1b_n"] == 1


# ---------------------------------------------------------------------------
# Table 11 — language effect by pattern, English instruction only
# ---------------------------------------------------------------------------


def test_table_language_by_pattern_groups_by_pattern_and_ui_language_en_instruction_only() -> None:
    df = pd.DataFrame(
        [
            {
                "arm": "E2",
                "pattern": "forced_action",
                "instruction_language": "en",
                "ui_language": "hi",
                "outcome": "DC",
            },
            {
                "arm": "E2",
                "pattern": "forced_action",
                "instruction_language": "en",
                "ui_language": "hi",
                "outcome": "EC",
            },
            {  # localised instruction -- must not leak into the en-instruction table
                "arm": "E2a",
                "pattern": "forced_action",
                "instruction_language": "hi",
                "ui_language": "hi",
                "outcome": "DC",
            },
            {  # excluded pattern -- must not appear as a row
                "arm": "E2",
                "pattern": "false_urgency",
                "instruction_language": "en",
                "ui_language": "en",
                "outcome": "DC",
            },
        ]
    )
    result = table_language_by_pattern(df)
    assert set(result["pattern"]) == {"forced_action"}
    row = result.iloc[0]
    assert row["ui_language"] == "hi"
    assert row["n"] == 2
    assert row["DC"] == 1
    assert row["n_flag"] == "EXPECTED 30, GOT 2"


# ---------------------------------------------------------------------------
# load_episodes — integration through a real (sqlite) engine
# ---------------------------------------------------------------------------


def test_load_episodes_derives_arm_and_terminal_reason_and_filters_by_run_id(tmp_path) -> None:
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'load.db'}")
    table = _build_episodes_table(engine)

    log_episode(
        _row(
            run_id="matrix-full-e1e2",
            pattern="basket_sneaking",
            agent="computeruse",
            llm="groq/llama-3.3-70b-versatile",
            ui_language="en",
            instruction_language="en",
            seed=0,
            outcome="EC",
            trace=[{"step": 0, "terminal_reason": "explicit_done"}],
        ),
        engine=engine,
        table=table,
    )
    log_episode(
        _row(
            run_id="other-run",
            pattern="basket_sneaking",
            config_hash="other-hash",
            outcome="EC",
        ),
        engine=engine,
        table=table,
    )

    df = load_episodes(engine, "matrix-full-e1e2")

    assert len(df) == 1  # the other-run row is filtered out
    assert df.iloc[0]["arm"] == "E1a"
    assert df.iloc[0]["terminal_reason"] == "explicit_done"


# ---------------------------------------------------------------------------
# Fixtures / factories
# ---------------------------------------------------------------------------


def _build_episodes_table(engine) -> sa.Table:
    metadata = sa.MetaData()
    table = sa.Table(
        "episodes",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("config_hash", sa.String(), nullable=False),
        sa.Column("site", sa.String(), nullable=False),
        sa.Column("pattern", sa.String(), nullable=False),
        sa.Column("intensity", sa.String(), nullable=False),
        sa.Column("language", sa.String(), nullable=False),
        sa.Column("ui_language", sa.String(), nullable=True),
        sa.Column("instruction_language", sa.String(), nullable=False),
        sa.Column("instruction_prompt", sa.Text(), nullable=True),
        sa.Column("agent", sa.String(), nullable=False),
        sa.Column("llm", sa.String(), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("placed", sa.Boolean(), nullable=True),
        sa.Column("avoided", sa.Boolean(), nullable=True),
        sa.Column("outcome", sa.String(), nullable=True),
        sa.Column("in_tokens", sa.Integer(), nullable=False),
        sa.Column("out_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=False),
        sa.Column("steps", sa.Integer(), nullable=False),
        sa.Column("judge_flag", sa.Boolean(), nullable=True),
        sa.Column("judge_evidence", sa.Text(), nullable=True),
        sa.Column("trace", sa.JSON(), nullable=False),
        sa.Column("duration_seconds", sa.Numeric(10, 4), nullable=True),
        sa.Column("provider_latency_seconds", sa.Numeric(10, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("config_hash", "run_id"),
    )
    metadata.create_all(engine)
    return table


def _row(**overrides: object) -> dict[str, object]:
    base = {
        "run_id": "matrix-full-e1e2",
        "config_hash": "hash-1",
        "site": "ticketing",
        "pattern": "basket_sneaking",
        "intensity": "moderate",
        "language": "en",
        "ui_language": "en",
        "instruction_language": "en",
        "agent": "computeruse",
        "llm": "groq/llama-3.3-70b-versatile",
        "seed": 0,
        "placed": True,
        "avoided": True,
        "outcome": "EC",
        "in_tokens": 1,
        "out_tokens": 2,
        "cost_usd": Decimal("0.000033"),
        "steps": 1,
        "judge_flag": None,
        "judge_evidence": None,
        "trace": [{"step": 0}],
    }
    base.update(overrides)
    return base


def test_excluded_patterns_constant_matches_spec() -> None:
    assert EXCLUDED_PATTERNS == {"disguised_advertisement", "false_urgency"}
