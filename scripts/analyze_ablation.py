#!/usr/bin/env python3
"""
scripts/analyze_ablation.py — F6 config-leak ablation analysis.

PRIMARY (the F6 test): ablation-config-01 (config re-injected) vs
ablation-noconfig-01 (config absent). Same harness, model, budget, testbed,
configs and seeds; the only difference is the config block in the prompt.

SECONDARY: ablation-noconfig-01 vs matrix-full-e1e2 E1a. This is a
REPLICATION ACROSS CODE VERSIONS, NOT AN F6 TEST: besides the config, the
harness, evaluator, prompt labels and testbed ids changed between them
(SPRINT_REPORT.md §5.1). It is SKIPPED when the ablation's agent model differs
from the matrix's (llama-3.3-70b-versatile is retired, so with the default
qwen agent it is always skipped).

Also reported: per-pattern DC for confirm_shaming and interface_interference
in the noconfig arm -- a clean measurement with opaque ids and no config.

Pairing is on config_hash: scripts/run_leak_ablation.py enumerates
byte-identical EpisodeConfigs to the matrix's E1a cells in both arms, so a
shared hash means the same (pattern, intensity, seed, model, language) cell.
Primary metric is RAW ORACLE DC (outcome == 'DC'), no judge adjustment.
Exact McNemar = two-sided binomial test on the discordant pairs.

Both ablation arms are read from DATABASE_URL (or --ablation-db-url); the
matrix from the read-only audit restore. Every connection is opened with
default_transaction_read_only = on; this script never writes to a database.

Groups, each overall / control / aggressive:
  all                  the 10 scored patterns
  ids_unchanged (8)    patterns whose element ids the ID fix did not touch
  ids_changed (CS+II)  confirm_shaming + interface_interference (opaque-id fix)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
import os

import pandas as pd
from scipy import stats
from sqlalchemy import create_engine, event, select

from harness.logger import episodes_table

MATRIX_RUN_ID = "matrix-full-e1e2"
CONFIG_RUN_ID = "ablation-config-01"
NOCONFIG_RUN_ID = "ablation-noconfig-01"
DEFAULT_MATRIX_DB_URL = "postgresql+psycopg://armavour:armavour@localhost:5433/armavour_audit"
ID_CHANGED_PATTERNS = {"confirm_shaming", "interface_interference"}
SCORED_PATTERNS = {
    "basket_sneaking", "drip_pricing", "bait_and_switch", "forced_action", "subscription_trap",
    "nagging", "trick_question", "saas_billing", "confirm_shaming", "interface_interference",
}
COLUMNS = ["id", "run_id", "config_hash", "pattern", "intensity", "seed", "llm", "agent", "language", "outcome"]


def read_only_engine(url: str):
    engine = create_engine(url)
    if engine.dialect.name == "postgresql":
        @event.listens_for(engine, "connect")
        def _read_only(dbapi_connection, _record):  # noqa: ANN001
            cursor = dbapi_connection.cursor()
            cursor.execute("SET default_transaction_read_only = on")
            cursor.close()
    return engine


def load_run(url: str, run_id: str) -> pd.DataFrame:
    engine = read_only_engine(url)
    table = episodes_table(engine)
    stmt = select(*[table.c[c] for c in COLUMNS]).where(table.c.run_id == run_id)
    with engine.connect() as conn:
        return pd.read_sql(stmt, conn)


def pair_runs(ref: pd.DataFrame, test: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Inner-join `test` onto `ref` by config_hash over the scored patterns.

    `ref` is the run with the config in the prompt (config arm, or the matrix);
    `test` is the run without it. Crash rows (outcome NULL) are dropped pairwise.
    """
    test = test[test["pattern"].isin(SCORED_PATTERNS)]
    merged = test.merge(ref[["config_hash", "id", "outcome"]], on="config_hash", how="left", suffixes=("_test", "_ref"))
    info = {
        "test_rows": len(test),
        "unmatched_in_ref": int(merged["id_ref"].isna().sum()),
        "crash_test": int(merged["outcome_test"].isna().sum()),
        "crash_ref": int((merged["id_ref"].notna() & merged["outcome_ref"].isna()).sum()),
    }
    paired = merged[merged["outcome_test"].notna() & merged["outcome_ref"].notna()].copy()
    paired["dc_ref"] = paired["outcome_ref"] == "DC"
    paired["dc_test"] = paired["outcome_test"] == "DC"
    info["pairs"] = len(paired)
    return paired, info


def mcnemar_row(group: str, intensity: str, cell: pd.DataFrame) -> dict[str, object]:
    n = len(cell)
    b = int((cell["dc_ref"] & ~cell["dc_test"]).sum())  # DC only in the ref run
    c = int((~cell["dc_ref"] & cell["dc_test"]).sum())  # DC only in the test run
    p = float(stats.binomtest(b, b + c, 0.5).pvalue) if b + c else 1.0
    return {
        "group": group,
        "intensity": intensity,
        "n_pairs": n,
        "dc_ref": int(cell["dc_ref"].sum()),
        "dc_rate_ref": round(100 * cell["dc_ref"].mean(), 1) if n else None,
        "dc_test": int(cell["dc_test"].sum()),
        "dc_rate_test": round(100 * cell["dc_test"].mean(), 1) if n else None,
        "b_ref_only": b,
        "c_test_only": c,
        "mcnemar_exact_p": round(p, 6),
    }


def mcnemar_table(paired: pd.DataFrame) -> pd.DataFrame:
    groups = {
        "all": paired,
        "ids_unchanged (8)": paired[~paired["pattern"].isin(ID_CHANGED_PATTERNS)],
        "ids_changed (CS+II)": paired[paired["pattern"].isin(ID_CHANGED_PATTERNS)],
    }
    rows = []
    for name, df in groups.items():
        rows.append(mcnemar_row(name, "all", df))
        for intensity in ("control", "aggressive"):
            rows.append(mcnemar_row(name, intensity, df[df["intensity"] == intensity]))
    return pd.DataFrame(rows)


def outcome_shift(paired: pd.DataFrame) -> pd.DataFrame:
    """Full EC/DC/EF/DF transition counts (ref -> test)."""
    return pd.crosstab(paired["outcome_ref"], paired["outcome_test"]).rename_axis(index="ref", columns="test")


def cs_ii_table(noconfig: pd.DataFrame) -> pd.DataFrame:
    """Per-pattern outcome counts and raw DC for CS and II in the noconfig arm (opaque ids, no config)."""
    df = noconfig[noconfig["pattern"].isin(ID_CHANGED_PATTERNS)]
    rows = []
    for (pattern, intensity), cell in df.groupby(["pattern", "intensity"]):
        scored = cell[cell["outcome"].notna()]
        counts = scored["outcome"].value_counts()
        rows.append({
            "pattern": pattern, "intensity": intensity, "n": len(cell), "n_scored": len(scored),
            **{o: int(counts.get(o, 0)) for o in ("EC", "DC", "EF", "DF")},
            "dc_rate": round(100 * counts.get("DC", 0) / len(scored), 1) if len(scored) else None,
        })
    return pd.DataFrame(rows)


def run_models(df: pd.DataFrame) -> list[str]:
    return sorted(df["llm"].dropna().unique().tolist()) if not df.empty else []


def secondary_skip_reason(noconfig: pd.DataFrame, matrix_e1a: pd.DataFrame) -> str | None:
    """The matrix replication is only meaningful with the matrix's own agent model.

    `matrix_e1a` is the matrix restricted to the noconfig arm's config_hashes; the
    hash includes the llm, so a different ablation model leaves it empty.
    """
    ablation_models, matrix_models = run_models(noconfig), run_models(matrix_e1a)
    if matrix_e1a.empty or ablation_models != matrix_models:
        return (
            f"models differ (ablation {ablation_models} vs matrix E1a "
            f"{matrix_models or ['groq/llama-3.3-70b-versatile, no matching config_hash']}); "
            "a matrix-vs-ablation comparison is not meaningful."
        )
    return None


def report(title: str, ref_label: str, test_label: str, paired: pd.DataFrame, info: dict[str, int],
           out_dir: Path, slug: str) -> None:
    table = mcnemar_table(paired)
    table.to_csv(out_dir / f"mcnemar_{slug}.csv", index=False)
    paired.to_csv(out_dir / f"pairs_{slug}.csv", index=False)
    print("=" * 100)
    print(title)
    print(f"ref = {ref_label}   test = {test_label}")
    print("Pairing:", info)
    print("Raw oracle DC, seed-paired, exact McNemar (b = DC only in ref, c = DC only in test):")
    print(table.to_string(index=False))
    print("\nOutcome transitions (rows = ref, columns = test):")
    print(outcome_shift(paired).to_string())
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="F6 two-arm ablation analysis (read-only)")
    parser.add_argument("--matrix-db-url", default=os.getenv("MATRIX_DATABASE_URL", DEFAULT_MATRIX_DB_URL))
    parser.add_argument("--ablation-db-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--config-run-id", default=CONFIG_RUN_ID)
    parser.add_argument("--noconfig-run-id", default=NOCONFIG_RUN_ID)
    parser.add_argument("--out-dir", type=Path, default=Path("results/ablation"))
    args = parser.parse_args()
    if not args.ablation_db_url:
        raise SystemExit("--ablation-db-url or DATABASE_URL is required")

    noconfig = load_run(args.ablation_db_url, args.noconfig_run_id)
    if noconfig.empty:
        raise SystemExit(f"No rows for run_id {args.noconfig_run_id!r} at the ablation DB")
    config = load_run(args.ablation_db_url, args.config_run_id)
    matrix = load_run(args.matrix_db_url, MATRIX_RUN_ID)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    matrix_e1a = matrix[matrix["config_hash"].isin(set(noconfig["config_hash"]))]
    print("Agent models (llm) per run:")
    print(f"  {args.config_run_id:<24} {run_models(config) or ['(no rows)']}")
    print(f"  {args.noconfig_run_id:<24} {run_models(noconfig)}")
    print(f"  {MATRIX_RUN_ID + ' E1a':<24} "
          f"{run_models(matrix_e1a) or ['groq/llama-3.3-70b-versatile (no rows share these config_hashes)']}")
    print()
    if not config.empty and run_models(config) != run_models(noconfig):
        raise SystemExit("PRIMARY invalid: the two ablation arms used different agent models.")

    if config.empty:
        print(f"PRIMARY skipped: no rows for {args.config_run_id!r} yet.\n")
    else:
        paired, info = pair_runs(config, noconfig)
        report("PRIMARY (F6 test): config arm vs noconfig arm, same harness",
               args.config_run_id, args.noconfig_run_id, paired, info, args.out_dir, "primary_config_vs_noconfig")

    skip_reason = secondary_skip_reason(noconfig, matrix_e1a)
    if skip_reason:
        print("=" * 100)
        print(f"SECONDARY skipped: {skip_reason}\n")
    else:
        paired, info = pair_runs(matrix, noconfig)
        report("SECONDARY: replication across code versions, NOT an F6 test",
               f"{MATRIX_RUN_ID} E1a", args.noconfig_run_id, paired, info, args.out_dir, "secondary_matrix_vs_noconfig")

    cs_ii = cs_ii_table(noconfig)
    cs_ii.to_csv(args.out_dir / "cs_ii_noconfig.csv", index=False)
    print("=" * 100)
    print(f"CS and II in {args.noconfig_run_id} (opaque ids, no config): raw oracle DC per pattern x intensity")
    print(cs_ii.to_string(index=False))


if __name__ == "__main__":
    main()
