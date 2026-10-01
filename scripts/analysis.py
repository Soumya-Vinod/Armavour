#!/usr/bin/env python3
"""
scripts/analysis.py — Read-only Postgres analysis for the Armavour results tables.

Reads the `episodes` table via harness.logger's engine_from_env()/episodes_table()
and produces the seven analyses agreed for the paper. Never writes to the
database — every query is a SELECT. Prints each table to stdout and writes a
CSV per table to results/analysis/.

Tables produced:
  1. Intensity gradient, E1a only (DC rate by intensity)
  2. Pattern table, E1a only (DC rate by pattern, equal-n check)
  3. Language table — five conditions, reported separately (not pooled)
  4. Paired language comparison — McNemar's exact test, E2 seed-matched triplets
  5. Control-condition deceptions (should be none; every arm, listed not pooled)
  6. EF breakdown by arm / agent / pattern / steps / terminal_reason
  7. Excluded patterns — disguised_advertisement (v1 invalid, v2 from its own
     rerun run_id) and false_urgency, reported separately per spec v1 §10
  8. Outcome distribution by arm (all six arms; scored subset excludes
     disguised_advertisement/false_urgency same as every table above)
  9. Intensity gradient, E1b (parallel to table 1) + an E1a/E1b wide comparison
 10. Pattern table, E1b (parallel to table 2) + an E1a/E1b wide comparison
 11. Language effect by pattern, English instruction only (E2, per-pattern
     breakdown of table 3's en-instruction rows)

Tables 8-11 were added to close gaps identified against a specific paper
draft (docs/table_reconciliation.md): that draft's Table I (outcome by arm),
Table II/III's BrowserUse columns, and Table V (per-pattern language effect)
had no corresponding computation here. Same exclusion rule as tables 1-7 —
disguised_advertisement/false_urgency are dropped from every scored/dc_rate
column, never pooled back in for a subset of tables. See
docs/table_reconciliation.md for the discrepancies this was written to close.

Every table's "DC"/"dc_rate" columns also now carry "DC_genuine"/
"DC_task_failure"/"dc_rate_judge" alongside them (_outcome_summary_row),
splitting confirm_shaming's DC count by judge_flag per docs/decisions.md #4
instead of reporting the raw DC rate the paper's own Judge section says is
wrong for judge-scored patterns. "DC"/"dc_rate" are the old raw figures,
kept for comparison; "dc_rate_judge" (DC_genuine/n_scored) is the corrected
figure. false_urgency is excluded everywhere already, so confirm_shaming is
the only pattern this changes.

Arm classification (E1a / E1b / E2 / E2a / E2b / Spotcheck) is not a stored
column — it's derived per-row with the *same* classifier scripts/run_matrix.py
uses to build the matrix (imported, not reimplemented), so arm boundaries can't
drift between the runner and this analysis. Note the classifier's actual
string is "Spotcheck" (no hyphen); the paper spells it "Spot-check" in prose.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

# Ensure workspace root is on sys.path for harness/scripts imports, matching
# the convention used by scripts/run_matrix.py and scripts/rerun_disguised_ad.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from scipy import stats
from sqlalchemy import select
from sqlalchemy.engine import Engine

from harness.evaluator import SOFT_PATTERNS
from harness.logger import engine_from_env, episodes_table
from scripts.run_matrix import DEFAULT_RUN_ID, get_batch_name_for_config

DEFAULT_DISGUISED_AD_V2_RUN_ID = "rerun-disguised-ad-v2"
DEFAULT_OUT_DIR = Path("results/analysis")

# disguised_advertisement v1 is invalid (spec v1 §10 — the ad was never the
# cheapest item, so price-only reasoning avoided it by construction, not by
# detecting the disguise). false_urgency has the same structural problem with
# no v2 fix yet. Both are excluded from every aggregate below and reported
# only in table 7.
EXCLUDED_PATTERNS = {"disguised_advertisement", "false_urgency"}

# confirm_shaming is SOFT_PATTERNS' other member (harness/evaluator.py) and
# is NOT excluded -- it's a scored pattern in every table below. Its DC
# count is corrected against judge_flag per docs/decisions.md #4; see
# _split_dc_by_judge_flag.

# The E2 arm's six patterns (scripts/run_matrix.py's e2_patterns), minus the
# excluded false_urgency -> 5 patterns feed tables 3 and 4.
E2_PATTERN_COUNT_RAW = 6
E2_PATTERN_COUNT_SCORED = E2_PATTERN_COUNT_RAW - 1  # false_urgency excluded

OUTCOME_LABELS = ("EC", "DC", "EF", "DF")

# (display label, instruction_language, ui_language) for table 3's five
# conditions. Order matches the task's own listing; every condition is kept
# as its own row -- never collapsed together.
LANGUAGE_CONDITIONS: list[tuple[str, str, str]] = [
    ("en instruction + en UI", "en", "en"),
    ("en instruction + hinglish UI", "en", "hinglish"),
    ("en instruction + hi UI", "en", "hi"),
    ("hinglish instruction + hinglish UI", "hinglish", "hinglish"),
    ("hi instruction + hi UI", "hi", "hi"),
]

# --- instruction_language derivation for pre-migration-0005 data ----------
#
# migration 0005_add_instruction_language (part of the E2a/E2b runner-support
# commit) added `instruction_language`/`ui_language` as their own columns.
# The real matrix run (run_id=matrix-full-e1e2, restored from
# pgdump_armavour_e1_e2.sql) predates that migration -- the dump was taken
# 2026-08-16 11:04, the migration file is timestamped 2026-08-16 11:19 -- so
# the episodes table it came from only ever had a single `language` column
# (== ui_language; instruction_language was computed in-memory per episode
# but never persisted). Without it, hi/hinglish rows are ambiguous between
# E2 (English instruction, non-English UI) and E2a/E2b (matched
# instruction+UI), which share the same `language` value.
#
# It is recoverable for this run only, from seed + created_at, which are
# both persisted: the language-arm rows split into disjoint, date-clustered
# seed blocks --
#   seed 10-19, created 2026-08-08 -> English instruction  (E2)
#   seed 20-29 (hi) / 30-39 (hinglish), created 2026-08-12 -> matched
#     instruction+UI (E2a / E2b) -- run four days later, hence the
#     disjoint seed_start in the config generator
# -- confirmed both by an exact 08-08/08-12 date split on those exact seed
# boundaries, and independently by the fact that this mapping reproduces
# the paper's Table IV DC rates exactly (en/hi 30.0%, hi/hi 66.7%,
# en/hinglish 22.2%, hinglish/hinglish 25.0%). It is a fact about this one
# historical run, not a general fallback -- a row with hi/hinglish UI and a
# seed outside these blocks has no known instruction_language and is a hard
# error, not a guess.
E2_EN_INSTRUCTION_SEED_RANGE = range(10, 20)
E2A_HI_INSTRUCTION_SEED_RANGE = range(20, 30)
E2B_HINGLISH_INSTRUCTION_SEED_RANGE = range(30, 40)


def _derive_instruction_language(row: pd.Series) -> str:
    """Recover instruction_language for rows where it was never persisted.

    See the E2_*_SEED_RANGE comment above -- this is a documented, verified
    derivation for run_id=matrix-full-e1e2 specifically, not a general
    fallback. Raises if a hi/hinglish row falls outside the known seed
    blocks, so a future/different run can't silently get mislabelled.
    """
    ui_lang = row["ui_language"]
    seed = int(row["seed"])
    if ui_lang == "en":
        return "en"
    if ui_lang == "hi":
        if seed in E2_EN_INSTRUCTION_SEED_RANGE:
            return "en"
        if seed in E2A_HI_INSTRUCTION_SEED_RANGE:
            return "hi"
        raise ValueError(
            f"Cannot derive instruction_language for a ui_language='hi' row with "
            f"seed={seed} (run_id={row.get('run_id')!r}, id={row.get('id')!r}) -- "
            "outside the known E2 (seed 10-19) / E2a (seed 20-29) blocks this "
            "derivation was verified against. instruction_language must be read "
            "directly (migration 0005) for this row instead of inferred."
        )
    if ui_lang == "hinglish":
        if seed in E2_EN_INSTRUCTION_SEED_RANGE:
            return "en"
        if seed in E2B_HINGLISH_INSTRUCTION_SEED_RANGE:
            return "hinglish"
        raise ValueError(
            f"Cannot derive instruction_language for a ui_language='hinglish' row "
            f"with seed={seed} (run_id={row.get('run_id')!r}, id={row.get('id')!r}) "
            "-- outside the known E2 (seed 10-19) / E2b (seed 30-39) blocks this "
            "derivation was verified against. instruction_language must be read "
            "directly (migration 0005) for this row instead of inferred."
        )
    raise ValueError(
        f"Unrecognized ui_language={ui_lang!r} (run_id={row.get('run_id')!r}, "
        f"id={row.get('id')!r}) -- cannot derive instruction_language."
    )


# ---------------------------------------------------------------------------
# Data loading (read-only)
# ---------------------------------------------------------------------------


def load_episodes(engine: Engine, run_id: str | None) -> pd.DataFrame:
    """Read episode rows for `run_id` (or every row if run_id is None).

    SELECT only -- this never mutates the database.
    """
    table = episodes_table(engine)
    stmt = select(table)
    if run_id is not None:
        stmt = stmt.where(table.c.run_id == run_id)
    with engine.connect() as conn:
        df = pd.read_sql(stmt, conn)
    if df.empty:
        df["arm"] = pd.Series(dtype="object")
        df["terminal_reason"] = pd.Series(dtype="object")
        return df
    # Pre-migration-0005 data has neither column; ui_language is a direct
    # rename of the old single `language` column, instruction_language has
    # to be derived (see _derive_instruction_language). Only fill in what's
    # actually missing, so a post-migration run (which has both columns
    # for real) is read as-is, untouched.
    if "ui_language" not in df.columns:
        if "language" not in df.columns:
            raise KeyError(
                "episodes table has neither 'ui_language' nor 'language' -- "
                "can't determine UI language."
            )
        df["ui_language"] = df["language"]
    if "instruction_language" not in df.columns:
        df["instruction_language"] = df.apply(_derive_instruction_language, axis=1)
    df["arm"] = df.apply(_row_arm, axis=1)
    df["terminal_reason"] = df["trace"].apply(_terminal_reason)
    return df


def _row_arm(row: pd.Series) -> str:
    # get_batch_name_for_config only reads these five attributes off the
    # config it's given -- a duck-typed stand-in avoids reconstructing a full
    # EpisodeConfig (which also wants site/task_id/pattern/intensity we don't
    # need for classification).
    return get_batch_name_for_config(
        SimpleNamespace(
            llm=row["llm"],
            agent=row["agent"],
            instruction_language=row["instruction_language"],
            ui_language=row["ui_language"],
            seed=row["seed"],
        )
    )


def _terminal_reason(trace: Any) -> str:
    """Pull terminal_reason off the last trace step, where present.

    computeruse traces are lists of step dicts and carry terminal_reason on
    the last one (harness/adapters/computeruse.py). browseruse traces are
    lists of plain description strings (harness/adapters/browseruse.py) and
    never carry terminal_reason at all -- that asymmetry is itself relevant
    to the E1b investigation, so it's surfaced as its own label rather than
    silently defaulting to "unknown".
    """
    if trace is None:
        return "no_trace"
    if isinstance(trace, str):
        import json

        try:
            trace = json.loads(trace)
        except (json.JSONDecodeError, ValueError):
            return "unparseable_trace"
    if not isinstance(trace, list) or not trace:
        return "no_trace"
    last = trace[-1]
    if isinstance(last, dict):
        return str(last.get("terminal_reason") or "unset")
    return "n/a_non_dict_trace_step"  # e.g. browseruse's plain-string steps


# ---------------------------------------------------------------------------
# Shared outcome-summary helper
# ---------------------------------------------------------------------------


def _split_dc_by_judge_flag(cell: pd.DataFrame) -> tuple[int, int]:
    """Split a cell's DC count into genuine-DC and task-failure-DC, per
    docs/decisions.md #4: "Soft-pattern DPSR is defined as the
    judge_flag=True rate, not the raw DC rate ... Analysis must report soft
    patterns as three numbers: EC / genuine-DC (judge_flag=True) /
    task-failure-DC (judge_flag=False)."

    Returns (dc_genuine, dc_task_failure), where dc_genuine already includes
    every non-SOFT_PATTERNS DC row (deterministic patterns have no judge
    involved, so their DC is genuine by construction) plus SOFT_PATTERNS DC
    rows with judge_flag=True. dc_genuine + dc_task_failure always equals the
    cell's raw DC count.

    In this run, false_urgency is excluded from every table that reaches
    this function (EXCLUDED_PATTERNS, applied upstream), so confirm_shaming
    is the only pattern this split is ever non-trivial for -- but the check
    is written against SOFT_PATTERNS generally, not confirm_shaming
    specifically, so it stays correct if that changes.

    Raises ValueError, rather than coercing, if a SOFT_PATTERNS row has a
    completed (non-null) outcome but a null or missing judge_flag --
    harness/evaluator.py's SOFT_PATTERNS branch always sets judge_flag for
    any non-crash soft-pattern row (regardless of that row's own outcome),
    so a null here is a data-integrity bug, not a value to default around.
    """
    if cell.empty or "pattern" not in cell.columns:
        # No pattern column to classify by (e.g. _outcome_summary_row's own
        # generic unit tests, which exercise counting logic in isolation) --
        # nothing to split, so treat any DC present as ordinary/genuine.
        dc_all = int((cell["outcome"] == "DC").sum()) if "outcome" in cell.columns and not cell.empty else 0
        return dc_all, 0

    is_soft = cell["pattern"].isin(SOFT_PATTERNS)
    has_outcome = cell["outcome"].notna()
    judge_flag = cell["judge_flag"] if "judge_flag" in cell.columns else pd.Series(pd.NA, index=cell.index)

    bad = cell[is_soft & has_outcome & judge_flag.isna()]
    if not bad.empty:
        offending = bad["config_hash"].tolist() if "config_hash" in bad.columns else bad.index.tolist()
        raise ValueError(
            f"{len(bad)} SOFT_PATTERNS row(s) have a completed outcome but a null "
            f"judge_flag -- not coercing (docs/decisions.md #4). Patterns: "
            f"{sorted(bad['pattern'].unique())}. Offending rows: {offending}"
        )

    is_dc = cell["outcome"] == "DC"
    dc_hard = int((is_dc & ~is_soft).sum())
    dc_soft_genuine = int((is_dc & is_soft & (judge_flag == True)).sum())  # noqa: E712
    dc_soft_task_failure = int((is_dc & is_soft & (judge_flag == False)).sum())  # noqa: E712
    return dc_hard + dc_soft_genuine, dc_soft_task_failure


def _outcome_summary_row(keys: dict[str, Any], cell: pd.DataFrame) -> dict[str, Any]:
    n_total = len(cell)
    n_crash = int(cell["outcome"].isna().sum()) if n_total else 0
    n_scored = n_total - n_crash
    counts = cell["outcome"].value_counts() if n_total else pd.Series(dtype="int64")
    row = dict(keys)
    row["n"] = n_total
    row["n_scored"] = n_scored
    row["n_crash"] = n_crash
    for label in OUTCOME_LABELS:
        row[label] = int(counts.get(label, 0))
    row["dc_rate"] = round(row["DC"] / n_scored, 4) if n_scored else None

    # docs/decisions.md #4 -- DC_genuine/DC_task_failure/dc_rate_judge are
    # additive, not a replacement: "DC"/"dc_rate" above stay the raw figure
    # so callers (and docs/table_reconciliation.md) can show raw-DC vs.
    # judge-flag-DC side by side rather than silently swapping one for the
    # other.
    dc_genuine, dc_task_failure = _split_dc_by_judge_flag(cell)
    row["DC_genuine"] = dc_genuine
    row["DC_task_failure"] = dc_task_failure
    row["dc_rate_judge"] = round(dc_genuine / n_scored, 4) if n_scored else None
    return row


def emit(name: str, df: pd.DataFrame, out_dir: Path | None, *, write_csv: bool = True) -> None:
    print()
    print("=" * 88)
    print(name)
    print("=" * 88)
    if df.empty:
        print("(no rows)")
    else:
        print(df.to_string(index=False))
    if write_csv and out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        csv_path = out_dir / f"{_slugify(name)}.csv"
        df.to_csv(csv_path, index=False)
        print(f"-> wrote {csv_path}")


def _slugify(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name.lower()).strip("_")


# ---------------------------------------------------------------------------
# Table 1 — Intensity gradient, E1a only
# ---------------------------------------------------------------------------


def table_intensity_gradient_e1a(df: pd.DataFrame) -> pd.DataFrame:
    e1a_all = df[df["arm"] == "E1a"]
    e1a_scored = e1a_all[~e1a_all["pattern"].isin(EXCLUDED_PATTERNS)]
    rows = []
    for intensity in ("control", "subtle", "moderate", "aggressive"):
        n_raw = int((e1a_all["intensity"] == intensity).sum())
        cell = e1a_scored[e1a_scored["intensity"] == intensity]
        row = {"intensity": intensity, "n_raw_all_12_patterns": n_raw}
        row["n_raw_flag"] = "" if n_raw == 120 else f"EXPECTED 120, GOT {n_raw}"
        row.update(_outcome_summary_row({}, cell))
        rows.append(row)
    result = pd.DataFrame(rows)
    print(
        "Note: n_raw_all_12_patterns is a completeness check (expect 120: 12 "
        "patterns x 10 seeds) and includes disguised_advertisement/false_urgency. "
        "The DC-rate columns (n / n_scored / EC..DF / dc_rate) exclude both per "
        "spec v1 §10, so their expected n is 100 (10 patterns x 10 seeds), not "
        "120 -- see table 7 for the excluded patterns on their own."
    )
    return result


# ---------------------------------------------------------------------------
# Table 2 — Pattern table, E1a only
# ---------------------------------------------------------------------------


def table_pattern_e1a(df: pd.DataFrame) -> pd.DataFrame:
    e1a = df[(df["arm"] == "E1a") & (~df["pattern"].isin(EXCLUDED_PATTERNS))]
    rows = []
    for pattern, cell in e1a.groupby("pattern"):
        row = _outcome_summary_row({"pattern": pattern}, cell)
        row["n_flag"] = "" if row["n"] == 40 else f"EXPECTED 40, GOT {row['n']}"
        rows.append(row)
    return pd.DataFrame(rows).sort_values("pattern").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Table 3 — Language table (five conditions, reported separately)
# ---------------------------------------------------------------------------


def table_language_conditions(df: pd.DataFrame) -> pd.DataFrame:
    pool = df[df["arm"].isin({"E2", "E2a", "E2b"}) & (~df["pattern"].isin(EXCLUDED_PATTERNS))]
    expected_n = E2_PATTERN_COUNT_SCORED * 3 * 10  # patterns x intensities x seeds
    rows = []
    for label, instr_lang, ui_lang in LANGUAGE_CONDITIONS:
        cell = pool[(pool["instruction_language"] == instr_lang) & (pool["ui_language"] == ui_lang)]
        row = {"condition": label, "instruction_language": instr_lang, "ui_language": ui_lang}
        row.update(_outcome_summary_row({}, cell))
        row["n_flag"] = "" if row["n"] == expected_n else f"EXPECTED {expected_n}, GOT {row['n']}"
        rows.append(row)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Table 4 — Paired language comparison (McNemar's exact test)
# ---------------------------------------------------------------------------


def _deceived(outcome: Any) -> bool | None:
    if outcome is None or (isinstance(outcome, float) and pd.isna(outcome)):
        return None
    return outcome == "DC"


def table_paired_language_mcnemar(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """McNemar's exact test for en-vs-hi and en-vs-hinglish over the E2 arm's
    seed-matched (pattern, intensity, seed) triplets, English instruction only.

    Returns (summary, unmatched_keys) -- unmatched_keys lists any
    (pattern, intensity, seed) that did not have a row on both sides of a
    comparison, since the pairing is verified here, not assumed.
    """
    pool = df[
        (df["arm"] == "E2") & (df["instruction_language"] == "en") & (~df["pattern"].isin(EXCLUDED_PATTERNS))
    ]
    key_cols = ["pattern", "intensity", "seed"]
    baseline = pool[pool["ui_language"] == "en"][[*key_cols, "outcome"]].rename(columns={"outcome": "outcome_en"})

    summaries = []
    unmatched_frames = []
    for comparison_label, lang in (("en_vs_hi", "hi"), ("en_vs_hinglish", "hinglish")):
        other = pool[pool["ui_language"] == lang][[*key_cols, "outcome"]].rename(
            columns={"outcome": f"outcome_{lang}"}
        )
        merged = baseline.merge(other, on=key_cols, how="outer", indicator=True)
        unmatched = merged[merged["_merge"] != "both"].copy()
        if not unmatched.empty:
            unmatched["comparison"] = comparison_label
            unmatched["side_missing"] = unmatched["_merge"].map(
                {"left_only": f"missing_{lang}", "right_only": "missing_en"}
            )
            unmatched_frames.append(unmatched[[*key_cols, "comparison", "side_missing"]])

        matched = merged[merged["_merge"] == "both"].copy()
        matched["deceived_en"] = matched["outcome_en"].apply(_deceived)
        matched[f"deceived_{lang}"] = matched[f"outcome_{lang}"].apply(_deceived)
        usable = matched.dropna(subset=["deceived_en", f"deceived_{lang}"]).copy()

        dec_en = usable["deceived_en"].astype(bool)
        dec_other = usable[f"deceived_{lang}"].astype(bool)
        b = int((dec_en & ~dec_other).sum())
        c = int((~dec_en & dec_other).sum())
        discordant = b + c
        p_value = stats.binomtest(min(b, c), discordant, 0.5, alternative="two-sided").pvalue if discordant else None

        summaries.append(
            {
                "comparison": comparison_label,
                "n_pairs_matched_on_key": len(matched),
                "n_unmatched_keys": len(unmatched),
                "n_pairs_usable_both_scored": len(usable),
                "n_pairs_dropped_crash": len(matched) - len(usable),
                "discordant_en_dc_other_not": b,
                "discordant_other_dc_en_not": c,
                "mcnemar_exact_p_value": round(p_value, 6) if p_value is not None else None,
            }
        )

    unmatched_df = (
        pd.concat(unmatched_frames, ignore_index=True) if unmatched_frames else pd.DataFrame(columns=[*key_cols, "comparison", "side_missing"])
    )
    return pd.DataFrame(summaries), unmatched_df


# ---------------------------------------------------------------------------
# Table 5 — Control-condition deceptions
# ---------------------------------------------------------------------------


def table_control_deceptions(df: pd.DataFrame) -> pd.DataFrame:
    control_dc = df[
        (df["intensity"] == "control") & (df["outcome"] == "DC") & (~df["pattern"].isin(EXCLUDED_PATTERNS))
    ]
    cols = [
        "arm",
        "pattern",
        "agent",
        "llm",
        "ui_language",
        "instruction_language",
        "seed",
        "config_hash",
        "run_id",
    ]
    return control_dc[cols].sort_values(["arm", "pattern"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Table 6 — EF breakdown
# ---------------------------------------------------------------------------


def table_ef_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    ef = df[(df["outcome"] == "EF") & (~df["pattern"].isin(EXCLUDED_PATTERNS))]
    if ef.empty:
        return pd.DataFrame(columns=["arm", "agent", "pattern", "steps", "terminal_reason", "n"])
    grouped = ef.groupby(["arm", "agent", "pattern", "steps", "terminal_reason"]).size().reset_index(name="n")
    return grouped.sort_values(["arm", "agent", "pattern", "steps"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Table 7 — Excluded patterns
# ---------------------------------------------------------------------------


def table_excluded_patterns(df: pd.DataFrame, engine: Engine, disguised_ad_v2_run_id: str) -> pd.DataFrame:
    rows = []

    fu = df[df["pattern"] == "false_urgency"]
    for arm, cell in fu.groupby("arm"):
        row = _outcome_summary_row(
            {
                "pattern": "false_urgency",
                "source": f"main run ({cell['run_id'].iloc[0] if len(cell) else 'n/a'})",
                "status": "EXCLUDED -- structurally unmeasurable, spec v1 §10 (deferred, no v2 fix)",
                "arm": arm,
            },
            cell,
        )
        rows.append(row)

    da_v1 = df[df["pattern"] == "disguised_advertisement"]
    for arm, cell in da_v1.groupby("arm"):
        row = _outcome_summary_row(
            {
                "pattern": "disguised_advertisement",
                "source": f"main run ({cell['run_id'].iloc[0] if len(cell) else 'n/a'})",
                "status": "INVALID -- v1 measurability defect, spec v1 §10 (do not report)",
                "arm": arm,
            },
            cell,
        )
        rows.append(row)

    da_v2_df = load_episodes(engine, disguised_ad_v2_run_id)
    da_v2 = da_v2_df[da_v2_df["pattern"] == "disguised_advertisement"]
    if da_v2.empty:
        rows.append(
            {
                "pattern": "disguised_advertisement",
                "source": f"v2 rerun ({disguised_ad_v2_run_id})",
                "status": f"NO ROWS FOUND for run_id={disguised_ad_v2_run_id!r} -- v2 rerun may not exist yet",
                "arm": "",
                "n": 0,
                "n_scored": 0,
                "n_crash": 0,
                "EC": 0,
                "DC": 0,
                "EF": 0,
                "DF": 0,
                "dc_rate": None,
            }
        )
    else:
        for arm, cell in da_v2.groupby("arm"):
            row = _outcome_summary_row(
                {
                    "pattern": "disguised_advertisement",
                    "source": f"v2 rerun ({disguised_ad_v2_run_id})",
                    "status": "VALID -- ad is cheapest item, label is the deciding signal (spec v2)",
                    "arm": arm,
                },
                cell,
            )
            rows.append(row)

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Table 8 — Outcome distribution by arm (all six arms)
# ---------------------------------------------------------------------------

# Matrix order, matching scripts/run_matrix.py's get_batch_name_for_config
# return values exactly (note "Spotcheck", not "Spot-check").
ARMS_IN_MATRIX_ORDER = ("E1a", "Spotcheck", "E1b", "E2", "E2a", "E2b")


def table_outcome_by_arm(df: pd.DataFrame) -> pd.DataFrame:
    """Outcome distribution by arm, all six arms, one row each.

    n_raw_all_patterns counts every row for the arm, including
    disguised_advertisement/false_urgency (a completeness check, same role as
    table 1's n_raw_all_12_patterns column). Every other column — n, n_scored,
    n_crash, EC/DC/EF/DF, dc_rate — is computed on the scored subset with both
    excluded, same rule as every other table in this file. n_raw_all_patterns
    and n_scored will therefore differ for E1a/E1b (12 vs 10 patterns) and for
    E2/E2a/E2b (6 vs 5 patterns, false_urgency only — disguised_advertisement
    isn't one of E2's six language-sensitive patterns).
    """
    rows = []
    for arm in ARMS_IN_MATRIX_ORDER:
        arm_all = df[df["arm"] == arm]
        arm_scored = arm_all[~arm_all["pattern"].isin(EXCLUDED_PATTERNS)]
        row = {"arm": arm, "n_raw_all_patterns": len(arm_all)}
        row.update(_outcome_summary_row({}, arm_scored))
        row["ec_rate"] = round(row["EC"] / row["n_scored"], 4) if row["n_scored"] else None
        row["ef_rate"] = round(row["EF"] / row["n_scored"], 4) if row["n_scored"] else None
        rows.append(row)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Table 9 — Intensity gradient, E1b + E1a/E1b comparison
# ---------------------------------------------------------------------------


def table_intensity_gradient_e1b(df: pd.DataFrame) -> pd.DataFrame:
    """Same computation as table_intensity_gradient_e1a, for the E1b
    (BrowserUse) arm instead of E1a. Kept as a standalone function — not a
    refactor of table_intensity_gradient_e1a — so table 1's existing shape
    and the tests pinned to it (tests/test_analysis.py) are untouched.
    """
    e1b_all = df[df["arm"] == "E1b"]
    e1b_scored = e1b_all[~e1b_all["pattern"].isin(EXCLUDED_PATTERNS)]
    rows = []
    for intensity in ("control", "subtle", "moderate", "aggressive"):
        n_raw = int((e1b_all["intensity"] == intensity).sum())
        cell = e1b_scored[e1b_scored["intensity"] == intensity]
        row = {"intensity": intensity, "n_raw_all_12_patterns": n_raw}
        row["n_raw_flag"] = "" if n_raw == 120 else f"EXPECTED 120, GOT {n_raw}"
        row.update(_outcome_summary_row({}, cell))
        rows.append(row)
    return pd.DataFrame(rows)


def table_intensity_gradient_e1a_e1b(df: pd.DataFrame) -> pd.DataFrame:
    """Wide E1a-vs-E1b comparison, matching the shape of a paper table that
    reports both adapters' intensity gradients side by side.

    Both columns are the *scored* subset (disguised_advertisement/
    false_urgency excluded -> 10 patterns x 10 seeds = n=100 per cell), not
    the raw n=120 (12 patterns x 10 seeds) a paper draft may state — see
    docs/table_reconciliation.md. n_scored is reported explicitly per cell
    rather than assumed constant, so a shortfall is visible instead of silent.
    """
    e1a = table_intensity_gradient_e1a(df).set_index("intensity")
    e1b = table_intensity_gradient_e1b(df).set_index("intensity")
    rows = []
    for intensity in ("control", "subtle", "moderate", "aggressive"):
        rows.append(
            {
                "intensity": intensity,
                "e1a_n_scored": int(e1a.loc[intensity, "n_scored"]),
                "e1a_dc_rate": e1a.loc[intensity, "dc_rate"],
                "e1b_n_scored": int(e1b.loc[intensity, "n_scored"]),
                "e1b_dc_rate": e1b.loc[intensity, "dc_rate"],
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Table 10 — Pattern table, E1b + E1a/E1b comparison
# ---------------------------------------------------------------------------


def table_pattern_e1b(df: pd.DataFrame) -> pd.DataFrame:
    """Same computation as table_pattern_e1a, for the E1b (BrowserUse) arm.
    Standalone, same reasoning as table_intensity_gradient_e1b above.
    """
    e1b = df[(df["arm"] == "E1b") & (~df["pattern"].isin(EXCLUDED_PATTERNS))]
    rows = []
    for pattern, cell in e1b.groupby("pattern"):
        row = _outcome_summary_row({"pattern": pattern}, cell)
        row["n_flag"] = "" if row["n"] == 40 else f"EXPECTED 40, GOT {row['n']}"
        rows.append(row)
    return pd.DataFrame(rows).sort_values("pattern").reset_index(drop=True)


def table_pattern_e1a_e1b(df: pd.DataFrame) -> pd.DataFrame:
    """Wide E1a-vs-E1b comparison, matching the shape of a paper table that
    reports both adapters' per-pattern deception rates side by side.

    Both columns exclude disguised_advertisement/false_urgency (n=40 per
    cell, per pattern) — the prior session already fixed E1a's own column
    from a pooled n=135/45 figure down to this E1a-only n=40; this adds the
    E1b column on the same, un-pooled basis rather than reintroducing
    pooling to get it. Excluded patterns are not rows in this table at all
    (a paper draft may list them with "---" placeholders; do that at the
    presentation layer, not by feeding them into this function).
    """
    e1a = table_pattern_e1a(df).set_index("pattern")
    e1b = table_pattern_e1b(df).set_index("pattern")
    patterns = sorted(set(e1a.index) | set(e1b.index))
    rows = []
    for pattern in patterns:
        rows.append(
            {
                "pattern": pattern,
                "e1a_n": int(e1a.loc[pattern, "n"]) if pattern in e1a.index else 0,
                "e1a_dc_rate": e1a.loc[pattern, "dc_rate"] if pattern in e1a.index else None,
                "e1b_n": int(e1b.loc[pattern, "n"]) if pattern in e1b.index else 0,
                "e1b_dc_rate": e1b.loc[pattern, "dc_rate"] if pattern in e1b.index else None,
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Table 11 — Language effect by pattern, English instruction only
# ---------------------------------------------------------------------------


def table_language_by_pattern(df: pd.DataFrame) -> pd.DataFrame:
    """Per-pattern breakdown of table 3's three English-instruction rows
    (en/en, en/hinglish, en/hi) — E2 arm, instruction_language='en', grouped
    by (pattern, ui_language).

    false_urgency is dropped per EXCLUDED_PATTERNS, so this covers 5 of E2's
    6 patterns; expected n per (pattern, ui_language) cell is 30
    (3 intensities x 10 seeds), not a 6-pattern raw count.
    """
    pool = df[
        (df["arm"] == "E2") & (df["instruction_language"] == "en") & (~df["pattern"].isin(EXCLUDED_PATTERNS))
    ]
    rows = []
    for (pattern, ui_lang), cell in pool.groupby(["pattern", "ui_language"]):
        row = _outcome_summary_row({"pattern": pattern, "ui_language": ui_lang}, cell)
        row["n_flag"] = "" if row["n"] == 30 else f"EXPECTED 30, GOT {row['n']}"
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["pattern", "ui_language"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def print_header_summary(df: pd.DataFrame, run_id: str | None) -> None:
    print("=" * 88)
    print(f"Armavour results analysis -- run_id={run_id!r}")
    print("=" * 88)
    total = len(df)
    print(f"Total episodes loaded: {total}")
    if total != 1920:
        print(f"NOTE: expected 1,920 for the full matrix; got {total}.")
    if not df.empty:
        print(df["arm"].value_counts().rename("n").to_string())


def run_all(df: pd.DataFrame, engine: Engine, args: argparse.Namespace) -> dict[str, pd.DataFrame]:
    out_dir = None if args.no_csv else Path(args.out_dir)
    tables: dict[str, pd.DataFrame] = {}

    print_header_summary(df, args.run_id)

    tables["1_intensity_gradient_e1a"] = table_intensity_gradient_e1a(df)
    emit("Table 1 — Intensity gradient, E1a only", tables["1_intensity_gradient_e1a"], out_dir)

    tables["2_pattern_table_e1a"] = table_pattern_e1a(df)
    emit("Table 2 — Pattern table, E1a only", tables["2_pattern_table_e1a"], out_dir)

    tables["3_language_conditions"] = table_language_conditions(df)
    emit("Table 3 — Language table (five conditions)", tables["3_language_conditions"], out_dir)

    mcnemar_summary, mcnemar_unmatched = table_paired_language_mcnemar(df)
    tables["4_paired_language_mcnemar"] = mcnemar_summary
    tables["4_paired_language_mcnemar_unmatched_keys"] = mcnemar_unmatched
    emit("Table 4 — Paired language comparison (McNemar's exact test)", mcnemar_summary, out_dir)
    emit("Table 4b — Unmatched (pattern, intensity, seed) keys", mcnemar_unmatched, out_dir)

    tables["5_control_deceptions"] = table_control_deceptions(df)
    emit("Table 5 — Control-condition deceptions (comprehension/execution failures)", tables["5_control_deceptions"], out_dir)

    tables["6_ef_breakdown"] = table_ef_breakdown(df)
    emit("Table 6 — EF breakdown by arm/agent/pattern/steps/terminal_reason", tables["6_ef_breakdown"], out_dir)

    tables["7_excluded_patterns"] = table_excluded_patterns(df, engine, args.disguised_ad_v2_run_id)
    emit("Table 7 — Excluded patterns (disguised_advertisement, false_urgency)", tables["7_excluded_patterns"], out_dir)

    tables["8_outcome_by_arm"] = table_outcome_by_arm(df)
    emit("Table 8 — Outcome distribution by arm (all six arms)", tables["8_outcome_by_arm"], out_dir)

    tables["9a_intensity_gradient_e1b"] = table_intensity_gradient_e1b(df)
    emit("Table 9a — Intensity gradient, E1b only", tables["9a_intensity_gradient_e1b"], out_dir)
    tables["9b_intensity_gradient_e1a_e1b"] = table_intensity_gradient_e1a_e1b(df)
    emit("Table 9b — Intensity gradient, E1a vs E1b (scored, n=100/cell)", tables["9b_intensity_gradient_e1a_e1b"], out_dir)

    tables["10a_pattern_e1b"] = table_pattern_e1b(df)
    emit("Table 10a — Pattern table, E1b only", tables["10a_pattern_e1b"], out_dir)
    tables["10b_pattern_e1a_e1b"] = table_pattern_e1a_e1b(df)
    emit("Table 10b — Pattern table, E1a vs E1b (n=40/cell)", tables["10b_pattern_e1a_e1b"], out_dir)

    tables["11_language_by_pattern"] = table_language_by_pattern(df)
    emit("Table 11 — Language effect by pattern, English instruction (n=30/cell)", tables["11_language_by_pattern"], out_dir)

    return tables


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Armavour results-table analysis (read-only).")
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID, help="Primary matrix run_id to analyse.")
    parser.add_argument(
        "--disguised-ad-v2-run-id",
        default=DEFAULT_DISGUISED_AD_V2_RUN_ID,
        help="run_id holding the valid disguised_advertisement v2 rerun.",
    )
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="Directory to write CSVs into.")
    parser.add_argument("--no-csv", action="store_true", help="Print tables only; skip writing CSV files.")
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    engine = engine_from_env()
    df = load_episodes(engine, args.run_id)
    run_all(df, engine, args)


if __name__ == "__main__":
    main()
