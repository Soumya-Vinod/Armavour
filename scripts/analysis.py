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

Arm classification (E1a / E1b / E2 / E2a / E2b / Spotcheck) is not a stored
column — it's derived per-row with the *same* classifier scripts/run_matrix.py
uses to build the matrix (imported, not reimplemented), so arm boundaries can't
drift between the runner and this analysis.
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
        usable = matched.dropna(subset=["deceived_en", f"deceived_{lang}"])

        b = int(((usable["deceived_en"]) & (~usable[f"deceived_{lang}"])).sum())
        c = int(((~usable["deceived_en"]) & (usable[f"deceived_{lang}"])).sum())
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
