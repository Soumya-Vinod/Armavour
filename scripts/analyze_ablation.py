#!/usr/bin/env python3
"""
scripts/analyze_ablation.py — seed-paired comparison of the F6 config-leak
ablation (run_id ablation-noconfig-01) against matrix-full-e1e2 E1a.

Pairs rows on config_hash: scripts/run_leak_ablation.py enumerates byte-identical
EpisodeConfigs to the matrix's E1a cells, so a shared hash means the same
(pattern, intensity, seed, model, language) cell. Primary metric is RAW ORACLE
DC (outcome == 'DC'), no judge adjustment. Exact McNemar = two-sided binomial
test on the discordant pairs.

Matrix and ablation rows can live in different databases (the matrix restore
armavour_audit is read-only), hence two URLs. Every connection is opened with
default_transaction_read_only = on; this script never writes to a database.

Groups reported, overall and per intensity:
  all            the 10 scored patterns
  ids_unchanged  8 patterns whose element ids the ID fix did not touch: the
                 only model-visible difference is the config in the prompt
  ids_changed    confirm_shaming + interface_interference: config removal is
                 confounded with the opaque-ID fix (docs/identifier_audit.md)
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
ABLATION_RUN_ID = "ablation-noconfig-01"
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


def pair_runs(matrix: pd.DataFrame, ablation: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Inner-join on config_hash over the scored patterns; crash rows (outcome NULL) are dropped pairwise."""
    ablation = ablation[ablation["pattern"].isin(SCORED_PATTERNS)]
    merged = ablation.merge(
        matrix[["config_hash", "id", "outcome"]], on="config_hash", how="left", suffixes=("_abl", "_mat")
    )
    info = {
        "ablation_rows": len(ablation),
        "unmatched_in_matrix": int(merged["id_mat"].isna().sum()),
        "crash_ablation": int(merged["outcome_abl"].isna().sum()),
        "crash_matrix": int((merged["id_mat"].notna() & merged["outcome_mat"].isna()).sum()),
    }
    paired = merged[merged["outcome_abl"].notna() & merged["outcome_mat"].notna()].copy()
    paired["dc_mat"] = paired["outcome_mat"] == "DC"
    paired["dc_abl"] = paired["outcome_abl"] == "DC"
    info["pairs"] = len(paired)
    return paired, info


def mcnemar_row(group: str, intensity: str, cell: pd.DataFrame) -> dict[str, object]:
    n = len(cell)
    b = int((cell["dc_mat"] & ~cell["dc_abl"]).sum())  # deceived with config, not without
    c = int((~cell["dc_mat"] & cell["dc_abl"]).sum())  # deceived without config, not with
    p = float(stats.binomtest(b, b + c, 0.5).pvalue) if b + c else 1.0
    return {
        "group": group,
        "intensity": intensity,
        "n_pairs": n,
        "dc_matrix": int(cell["dc_mat"].sum()),
        "dc_rate_matrix": round(100 * cell["dc_mat"].mean(), 1) if n else None,
        "dc_ablation": int(cell["dc_abl"].sum()),
        "dc_rate_ablation": round(100 * cell["dc_abl"].mean(), 1) if n else None,
        "b_matrix_only": b,
        "c_ablation_only": c,
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
    """Secondary: full EC/DC/EF/DF transition counts (matrix -> ablation)."""
    return pd.crosstab(paired["outcome_mat"], paired["outcome_abl"]).rename_axis(
        index="matrix", columns="ablation"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--matrix-db-url", default=os.getenv("MATRIX_DATABASE_URL", DEFAULT_MATRIX_DB_URL))
    parser.add_argument("--ablation-db-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--ablation-run-id", default=ABLATION_RUN_ID)
    parser.add_argument("--out-dir", type=Path, default=Path("results/ablation"))
    args = parser.parse_args()
    if not args.ablation_db_url:
        raise SystemExit("--ablation-db-url or DATABASE_URL is required")

    matrix = load_run(args.matrix_db_url, MATRIX_RUN_ID)
    ablation = load_run(args.ablation_db_url, args.ablation_run_id)
    if ablation.empty:
        raise SystemExit(f"No rows for run_id {args.ablation_run_id!r} at the ablation DB")

    paired, info = pair_runs(matrix, ablation)
    table = mcnemar_table(paired)
    shift = outcome_shift(paired)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    table.to_csv(args.out_dir / f"mcnemar_{args.ablation_run_id}.csv", index=False)
    paired.to_csv(args.out_dir / f"pairs_{args.ablation_run_id}.csv", index=False)

    print("Pairing:", info)
    print("\nRaw oracle DC, seed-paired, exact McNemar (b = DC only with config, c = DC only without):")
    print(table.to_string(index=False))
    print("\nOutcome transitions (rows = matrix-full-e1e2, columns = ablation):")
    print(shift.to_string())


if __name__ == "__main__":
    main()
