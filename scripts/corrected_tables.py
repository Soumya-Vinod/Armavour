#!/usr/bin/env python3
"""
scripts/corrected_tables.py — paper tables recomputed after the spec-divergence
audit (docs/audit/SPEC_DIVERGENCE.md), RAW and CORRECTED side by side.

RAW is produced by calling scripts/analysis.py's own table functions on the
full matrix-full-e1e2 data, so it is the paper's numbers by construction; a
regression check against results/analysis/*.csv must pass before anything is
written. CORRECTED is the same functions on a filtered copy of the data:

  --exclude-breaking   drop the BREAKING cells (every arm, every language):
                       drip_pricing aggressive, saas_billing aggressive,
                       trick_question moderate + aggressive
  --st-abandon MODE    subscription_trap rows that ended unplaced (EF):
                       as-is   keep the evaluator's EF/avoided (default)
                       exclude drop them
                       as-dc   spec-faithful: subscription still active, so
                               not avoided (subscription_trap.md §5) -> DC

DA and FU stay excluded exactly as scripts/analysis.py:79. Primary metric is raw
oracle DC; analysis.py's judge-adjusted dc_rate_judge is carried as a secondary
column where analysis.py reports it. Reads armavour_audit through a read-only
engine (scripts/analyze_ablation.py); never writes to a database.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
import contextlib
import io
import json
import os
from typing import Any, Callable

import pandas as pd
from scipy import stats

from scripts import analysis
from scripts.analysis import EXCLUDED_PATTERNS
from scripts.analyze_ablation import DEFAULT_MATRIX_DB_URL, read_only_engine

RUN_ID = "matrix-full-e1e2"
REPO = Path(__file__).resolve().parent.parent
PAPER_CSV_DIR = REPO / "results" / "analysis"
OUT_DIR = REPO / "results" / "analysis_corrected"
TEX_DIR = REPO / "docs" / "paper" / "tables"

# SPEC_DIVERGENCE.md §2/§11/§12. Trick question aggressive is BREAKING in all
# three languages (author's native-speaker check of the hinglish label).
BREAKING_CELLS = {
    ("drip_pricing", "aggressive"),
    ("saas_billing", "aggressive"),
    ("trick_question", "moderate"),
    ("trick_question", "aggressive"),
}
ST_ABANDON_MODES = ("as-is", "exclude", "as-dc")
INTENSITIES = ("control", "subtle", "moderate", "aggressive")
ARMS = ("E1a", "Spotcheck", "E1b", "E2", "E2a", "E2b")


# --- filters -------------------------------------------------------------------


def breaking_mask(df: pd.DataFrame) -> pd.Series:
    return pd.Series([(p, i) in BREAKING_CELLS for p, i in zip(df["pattern"], df["intensity"])], index=df.index, dtype=bool)


def st_abandon_mask(df: pd.DataFrame) -> pd.Series:
    """subscription_trap rows that ended without the oracle firing (scored EF/avoided)."""
    return (df["pattern"] == "subscription_trap") & (df["outcome"] == "EF")


def apply_filters(df: pd.DataFrame, *, exclude_breaking: bool = False, st_abandon: str = "as-is") -> pd.DataFrame:
    if st_abandon not in ST_ABANDON_MODES:
        raise ValueError(f"st_abandon must be one of {ST_ABANDON_MODES}, got {st_abandon!r}")
    out = df.copy()
    if exclude_breaking:
        out = out[~breaking_mask(out)]
    abandon = st_abandon_mask(out)
    if st_abandon == "exclude":
        out = out[~abandon]
    elif st_abandon == "as-dc":
        out.loc[abandon, "outcome"] = "DC"
        out.loc[abandon, "avoided"] = False
    return out


def quiet(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """analysis.py's table functions print notes; keep stdout clean."""
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


# --- regression check ------------------------------------------------------------


REGRESSION = {
    "table_1___intensity_gradient__e1a_only.csv": lambda d: analysis.table_intensity_gradient_e1a(d),
    "table_2___pattern_table__e1a_only.csv": lambda d: analysis.table_pattern_e1a(d),
    "table_3___language_table__five_conditions.csv": lambda d: analysis.table_language_conditions(d),
    "table_4___paired_language_comparison__mcnemar_s_exact_test.csv": lambda d: analysis.table_paired_language_mcnemar(d)[0],
    "table_5___control_condition_deceptions__comprehension_execution_failures.csv": lambda d: analysis.table_control_deceptions(d),
    "table_8___outcome_distribution_by_arm__all_six_arms.csv": lambda d: analysis.table_outcome_by_arm(d),
    "table_9a___intensity_gradient__e1b_only.csv": lambda d: analysis.table_intensity_gradient_e1b(d),
    "table_9b___intensity_gradient__e1a_vs_e1b__scored__n_100_cell.csv": lambda d: analysis.table_intensity_gradient_e1a_e1b(d),
    "table_10b___pattern_table__e1a_vs_e1b__n_40_cell.csv": lambda d: analysis.table_pattern_e1a_e1b(d),
    "table_11___language_effect_by_pattern__english_instruction__n_30_cell.csv": lambda d: analysis.table_language_by_pattern(d),
}


def _as_strings(frame: pd.DataFrame) -> pd.DataFrame:
    return pd.read_csv(io.StringIO(frame.to_csv(index=False)), dtype=str, keep_default_na=False)


def regression_check(df: pd.DataFrame, csv_dir: Path = PAPER_CSV_DIR) -> list[str]:
    """Return a list of mismatches between RAW (recomputed) and results/analysis/*.csv; empty = pass."""
    problems: list[str] = []
    for name, fn in REGRESSION.items():
        expected = pd.read_csv(csv_dir / name, dtype=str, keep_default_na=False)
        got = _as_strings(quiet(fn, df))
        if list(expected.columns) != list(got.columns):
            problems.append(f"{name}: columns differ {list(expected.columns)} vs {list(got.columns)}")
            continue
        if len(expected) != len(got):
            problems.append(f"{name}: {len(expected)} rows expected, {len(got)} recomputed")
            continue
        for col in expected.columns:
            for row, (a, b) in enumerate(zip(expected[col], got[col])):
                if a == b:
                    continue
                try:
                    if float(a) == float(b):
                        continue
                except ValueError:
                    pass
                problems.append(f"{name}: row {row} column {col}: csv={a!r} recomputed={b!r}")
    return problems


# --- tables ---------------------------------------------------------------------


def scored(df: pd.DataFrame) -> pd.DataFrame:
    return df[~df["pattern"].isin(EXCLUDED_PATTERNS)]


def t1_outcome(df: pd.DataFrame) -> pd.DataFrame:
    return quiet(analysis.table_outcome_by_arm, df)


def t2_control(df: pd.DataFrame) -> pd.DataFrame:
    cell = scored(df)
    cell = cell[(cell["intensity"] == "control") & cell["outcome"].notna()]
    rows = []
    for (arm, ui, instr), g in cell.groupby(["arm", "ui_language", "instruction_language"]):
        rows.append({"arm": arm, "ui_language": ui, "instruction_language": instr, "n_scored": len(g),
                     "DC": int((g["outcome"] == "DC").sum()), "dc_rate": round(float((g["outcome"] == "DC").mean()), 4)})
    return pd.DataFrame(rows)


def t3_intensity(df: pd.DataFrame) -> pd.DataFrame:
    a = quiet(analysis.table_intensity_gradient_e1a, df).assign(arm="E1a")
    b = quiet(analysis.table_intensity_gradient_e1b, df).assign(arm="E1b")
    return pd.concat([a, b], ignore_index=True)


def t4_pattern(df: pd.DataFrame) -> pd.DataFrame:
    """Pattern x arm (E1a, E1b): DC / n_scored over the cells present."""
    s = scored(df)
    rows = []
    for pattern in sorted(set(scored(df)["pattern"]) | {p for p, _ in BREAKING_CELLS}):
        row: dict[str, Any] = {"pattern": pattern}
        for arm in ("E1a", "E1b"):
            g = s[(s["arm"] == arm) & (s["pattern"] == pattern) & s["outcome"].notna()]
            row[f"{arm}_n"] = len(g)
            row[f"{arm}_DC"] = int((g["outcome"] == "DC").sum())
            row[f"{arm}_dc_rate"] = round(float((g["outcome"] == "DC").mean()), 4) if len(g) else None
        rows.append(row)
    return pd.DataFrame(rows)


def t4b_pattern_intensity(df: pd.DataFrame) -> pd.DataFrame:
    """Pattern x intensity per arm, so excluded cells are visible as empty (n=0)."""
    s = scored(df)
    rows = []
    for arm in ("E1a", "E1b"):
        for pattern in sorted(scored(df)["pattern"].unique()):
            for intensity in INTENSITIES:
                g = s[(s["arm"] == arm) & (s["pattern"] == pattern) & (s["intensity"] == intensity) & s["outcome"].notna()]
                rows.append({"arm": arm, "pattern": pattern, "intensity": intensity, "n": len(g), "DC": int((g["outcome"] == "DC").sum())})
    return pd.DataFrame(rows)


def t5_language(df: pd.DataFrame) -> pd.DataFrame:
    return quiet(analysis.table_language_conditions, df)


def mcnemar(b: int, c: int) -> float | None:
    """Exact McNemar = two-sided binomial test on the discordant pairs."""
    return float(stats.binomtest(min(b, c), b + c, 0.5, alternative="two-sided").pvalue) if b + c else None


def e2_pairs(df: pd.DataFrame, other: str) -> pd.DataFrame:
    pool = scored(df)
    pool = pool[(pool["arm"] == "E2") & (pool["instruction_language"] == "en") & pool["outcome"].notna()]
    key = ["pattern", "intensity", "seed"]
    en = pool[pool["ui_language"] == "en"][[*key, "outcome"]].rename(columns={"outcome": "outcome_en"})
    ot = pool[pool["ui_language"] == other][[*key, "outcome"]].rename(columns={"outcome": "outcome_other"})
    pairs = en.merge(ot, on=key, how="inner")
    pairs["dc_en"] = pairs["outcome_en"] == "DC"
    pairs["dc_other"] = pairs["outcome_other"] == "DC"
    return pairs


def t6_mcnemar(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(analysis.py summary, discordant pairs by cell, cell-level sign test)."""
    summary = quiet(analysis.table_paired_language_mcnemar, df)[0]
    by_cell, sign_rows = [], []
    for other in ("hi", "hinglish"):
        pairs = e2_pairs(df, other)
        for (pattern, intensity), g in pairs.groupby(["pattern", "intensity"]):
            b = int((g["dc_en"] & ~g["dc_other"]).sum())
            c = int((~g["dc_en"] & g["dc_other"]).sum())
            by_cell.append({"comparison": f"en_vs_{other}", "pattern": pattern, "intensity": intensity,
                            "n_pairs": len(g), "DC_en": int(g["dc_en"].sum()), "DC_other": int(g["dc_other"].sum()),
                            "b_en_only": b, "c_other_only": c})
        cells = pd.DataFrame([r for r in by_cell if r["comparison"] == f"en_vs_{other}"])
        other_more = int((cells["DC_other"] > cells["DC_en"]).sum()) if len(cells) else 0
        en_more = int((cells["DC_en"] > cells["DC_other"]).sum()) if len(cells) else 0
        ties = int(len(cells) - other_more - en_more)
        sign_rows.append({"comparison": f"en_vs_{other}", "n_cells": len(cells), "cells_other_gt_en": other_more,
                          "cells_en_gt_other": en_more, "cells_tied": ties,
                          "sign_test_p": round(mcnemar(en_more, other_more), 6) if en_more + other_more else None})
    return summary, pd.DataFrame(by_cell), pd.DataFrame(sign_rows)


def t7_language_pattern(df: pd.DataFrame) -> pd.DataFrame:
    return quiet(analysis.table_language_by_pattern, df)


def t8_attribution(raw: pd.DataFrame) -> pd.DataFrame:
    """Share of each arm's raw DC by failure class, plus ST abandon (EF, would be DC under as-dc)."""
    s = scored(raw)
    rows = []
    for arm in ARMS:
        g = s[s["arm"] == arm]
        dc = g[g["outcome"] == "DC"]
        total = len(dc)
        row: dict[str, Any] = {"arm": arm, "raw_DC": total}
        accounted = 0
        for p, i in sorted(BREAKING_CELLS):
            k = int(((dc["pattern"] == p) & (dc["intensity"] == i)).sum())
            row[f"{p}:{i}"] = k
            accounted += k
        row["everything_else"] = total - accounted
        row["breaking_share"] = round(accounted / total, 4) if total else None
        row["st_abandon_EF_rows"] = int(st_abandon_mask(g).sum())
        rows.append(row)
    return pd.DataFrame(rows)


def c2_counts(raw: pd.DataFrame) -> pd.DataFrame:
    """C2 (reported, not reclassified): abandon controls that emit an oracle and score EC."""
    s = raw[raw["outcome"].notna()]
    rows = []
    # forced_action aggressive: Enrol is disabled until phone+email are filled (ForcedAction.tsx:52),
    # so an EC there can only come from "Leave" (abandon-btn) -> every EC is a C2 case.
    fa = s[(s["pattern"] == "forced_action") & (s["intensity"] == "aggressive")]
    for arm, g in fa.groupby("arm"):
        rows.append({"case": "forced_action aggressive 'Leave' scored EC", "arm": arm, "n": len(g),
                     "c2_count": int((g["outcome"] == "EC").sum()), "basis": "exact (only Leave can yield EC)"})
    # bait_and_switch control: EC is either Buy (advertised item) or 'No thanks'. ComputerUse traces
    # carry the element index: in the cart, bs-buy is index 0 and bs-abandon index 1.
    bns = s[(s["pattern"] == "bait_and_switch") & (s["intensity"] == "control") & (s["outcome"] == "EC")]
    for arm, g in bns.groupby("arm"):
        if (g["agent"] == "computeruse").all():
            n_abandon = int(sum(_cu_last_click_index(t) == 1 for t in g["trace"]))
            rows.append({"case": "bait_and_switch control 'No thanks' scored EC", "arm": arm, "n": len(g),
                         "c2_count": n_abandon, "basis": "ComputerUse last click on cart index 1 (bs-abandon)"})
        else:
            rows.append({"case": "bait_and_switch control 'No thanks' scored EC", "arm": arm, "n": len(g),
                         "c2_count": None, "basis": "not determinable: BrowserUse trace has only page-specific click indices"})
    out = pd.DataFrame(rows)
    out["c2_count"] = out["c2_count"].astype("Int64")
    return out


def _cu_last_click_index(trace: Any) -> int | None:
    steps = trace if isinstance(trace, list) else json.loads(trace)
    clicks = [s["action"].get("index") for s in steps
              if isinstance(s, dict) and isinstance(s.get("action"), dict) and s["action"].get("action") == "click"]
    return clicks[-1] if len(clicks) >= 2 else None  # >= 2: add-to-cart, then a cart action


# --- output helpers ----------------------------------------------------------------


def pct(x: Any) -> str:
    return "" if x is None or (isinstance(x, float) and pd.isna(x)) else f"{100 * float(x):.1f}"


def md_table(frame: pd.DataFrame) -> str:
    cols = list(frame.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in frame.iterrows():
        lines.append("| " + " | ".join("" if pd.isna(v) else str(v) for v in r.tolist()) + " |")
    return "\n".join(lines)


def tex_table(frame: pd.DataFrame, caption: str, label: str, colspec: str, wide: bool = False) -> str:
    env = "table*" if wide else "table"
    def esc(v):
        return "" if pd.isna(v) else str(v).replace("_", r"\_").replace("%", r"\%").replace("&", r"\&")
    head = " & ".join(rf"\textbf{{{esc(c)}}}" for c in frame.columns) + r" \\"
    body = "\n".join(" & ".join(esc(v) for v in r.tolist()) + r" \\" for _, r in frame.iterrows())
    return (f"% Generated by scripts/corrected_tables.py -- do not edit by hand.\n"
            f"\\begin{{{env}}}[htbp]\n\\caption{{{esc(caption)}}}\n\\label{{{label}}}\n\\centering\n\\small\n"
            + (f"\\resizebox{{\\textwidth}}{{!}}{{%\n" if wide else "")
            + f"\\begin{{tabular}}{{{colspec}}}\n\\toprule\n{head}\n\\midrule\n{body}\n\\bottomrule\n\\end{{tabular}}\n"
            + ("}\n" if wide else "") + f"\\end{{{env}}}\n")


def cell(n: int, dc: int) -> str:
    return f"{dc}/{n} ({100 * dc / n:.1f}%)" if n else "—"


# --- presentation tables (raw vs corrected side by side) -----------------------------


def present(raw: pd.DataFrame, cor: pd.DataFrame) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}

    r1, c1 = t1_outcome(raw).set_index("arm"), t1_outcome(cor).set_index("arm")
    out["T1"] = pd.DataFrame([{
        "Arm": arm,
        "n raw": int(r1.at[arm, "n_scored"]), "EC raw": pct(r1.at[arm, "ec_rate"]), "DC raw": pct(r1.at[arm, "dc_rate"]),
        "EF raw": pct(r1.at[arm, "ef_rate"]), "DC_judge raw": pct(r1.at[arm, "dc_rate_judge"]),
        "n corr": int(c1.at[arm, "n_scored"]), "EC corr": pct(c1.at[arm, "ec_rate"]), "DC corr": pct(c1.at[arm, "dc_rate"]),
        "EF corr": pct(c1.at[arm, "ef_rate"]), "DC_judge corr": pct(c1.at[arm, "dc_rate_judge"]),
    } for arm in r1.index])

    r2, c2 = t2_control(raw), t2_control(cor)
    m2 = r2.merge(c2, on=["arm", "ui_language", "instruction_language"], how="outer", suffixes=(" raw", " corr")).fillna(0)
    out["T2"] = pd.DataFrame([{
        "Arm": r.arm, "Interface": r.ui_language, "Instruction": r.instruction_language,
        "control DC raw": cell(int(r["n_scored raw"]), int(r["DC raw"])),
        "control DC corr": cell(int(r["n_scored corr"]), int(r["DC corr"])),
    } for _, r in m2.iterrows()])

    r3, c3 = t3_intensity(raw), t3_intensity(cor)
    out["T3"] = pd.DataFrame([{
        "Arm": a, "Intensity": i,
        "DC raw": cell(int(rr.n_scored), int(rr.DC)),
        "DC corr": cell(int(cc.n_scored), int(cc.DC)),
    } for a in ("E1a", "E1b") for i in INTENSITIES
        for rr in [r3[(r3.arm == a) & (r3.intensity == i)].iloc[0]]
        for cc in [c3[(c3.arm == a) & (c3.intensity == i)].iloc[0]]])

    r4, c4 = t4_pattern(raw).set_index("pattern"), t4_pattern(cor).set_index("pattern")
    out["T4"] = pd.DataFrame([{
        "Pattern": p,
        "E1a raw": cell(int(r4.at[p, "E1a_n"]), int(r4.at[p, "E1a_DC"])),
        "E1a corr": cell(int(c4.at[p, "E1a_n"]), int(c4.at[p, "E1a_DC"])),
        "E1b raw": cell(int(r4.at[p, "E1b_n"]), int(r4.at[p, "E1b_DC"])),
        "E1b corr": cell(int(c4.at[p, "E1b_n"]), int(c4.at[p, "E1b_DC"])),
        "excluded cells": ", ".join(i for (pp, i) in sorted(BREAKING_CELLS) if pp == p) or "",
    } for p in r4.index])
    r4b, c4b = t4b_pattern_intensity(raw), t4b_pattern_intensity(cor)
    m4b = r4b.merge(c4b, on=["arm", "pattern", "intensity"], suffixes=(" raw", " corr"))
    rows = []
    for (arm, pattern), g in m4b.groupby(["arm", "pattern"]):
        row = {"Arm": arm, "Pattern": pattern}
        for _, r in g.iterrows():
            row[f"{r.intensity} raw"] = cell(int(r["n raw"]), int(r["DC raw"]))
            row[f"{r.intensity} corr"] = cell(int(r["n corr"]), int(r["DC corr"]))
        rows.append(row)
    out["T4b"] = pd.DataFrame(rows)[["Arm", "Pattern", *[f"{i} {k}" for i in INTENSITIES for k in ("raw", "corr")]]]

    r5, c5 = t5_language(raw), t5_language(cor)
    out["T5"] = pd.DataFrame([{
        "Instruction": rr.instruction_language, "Interface": rr.ui_language,
        "DC raw": cell(int(rr.n_scored), int(rr.DC)), "DC_judge raw": pct(rr.dc_rate_judge),
        "DC corr": cell(int(cc.n_scored), int(cc.DC)), "DC_judge corr": pct(cc.dc_rate_judge),
    } for (_, rr), (_, cc) in zip(r5.iterrows(), c5.iterrows())])

    (r6, r6c, r6s), (c6, c6c, c6s) = t6_mcnemar(raw), t6_mcnemar(cor)
    out["T6"] = pd.DataFrame([{
        "Comparison": rr.comparison,
        "pairs raw": int(rr.n_pairs_usable_both_scored), "b raw (en only)": int(rr.discordant_en_dc_other_not),
        "c raw (other only)": int(rr.discordant_other_dc_en_not), "p raw": f"{mcnemar(int(rr.discordant_en_dc_other_not), int(rr.discordant_other_dc_en_not)):.3g}",
        "pairs corr": int(cc.n_pairs_usable_both_scored), "b corr": int(cc.discordant_en_dc_other_not),
        "c corr": int(cc.discordant_other_dc_en_not), "p corr": f"{mcnemar(int(cc.discordant_en_dc_other_not), int(cc.discordant_other_dc_en_not)):.3g}",
    } for (_, rr), (_, cc) in zip(r6.iterrows(), c6.iterrows())])
    sign = r6s.merge(c6s, on="comparison", suffixes=(" raw", " corr"))
    out["T6_sign"] = sign
    disc = r6c[(r6c.b_en_only + r6c.c_other_only) > 0].merge(
        c6c[["comparison", "pattern", "intensity"]].assign(kept_in_corrected="yes"),
        on=["comparison", "pattern", "intensity"], how="left").fillna({"kept_in_corrected": "no (excluded)"})
    out["T6_cells"] = disc

    r7, c7 = t7_language_pattern(raw), t7_language_pattern(cor)
    m7 = r7.merge(c7, on=["pattern", "ui_language"], how="left", suffixes=(" raw", " corr"))
    out["T7"] = pd.DataFrame([{
        "Pattern": r.pattern, "Interface": r.ui_language,
        "DC raw": cell(int(r["n_scored raw"]), int(r["DC raw"])),
        "DC corr": cell(int(r["n_scored corr"]), int(r["DC corr"])) if not pd.isna(r["n_scored corr"]) else "—",
    } for _, r in m7.iterrows()])

    out["T8"] = t8_attribution(raw)
    return out


def sensitivity(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """T1/T3/T4 under every --exclude-breaking x --st-abandon combination."""
    t1s, t3s, t4s = [], [], []
    for exclude in (False, True):
        for mode in ST_ABANDON_MODES:
            d = apply_filters(df, exclude_breaking=exclude, st_abandon=mode)
            tag = {"exclude_breaking": exclude, "st_abandon": mode}
            t1s.append(t1_outcome(d).assign(**tag))
            t3s.append(t3_intensity(d).assign(**tag))
            t4s.append(t4_pattern(d).assign(**tag))
    return {"S1_outcome": pd.concat(t1s), "S3_intensity": pd.concat(t3s), "S4_pattern": pd.concat(t4s)}


# --- main ---------------------------------------------------------------------------


def load_matrix(url: str) -> pd.DataFrame:
    return quiet(analysis.load_episodes, read_only_engine(url), RUN_ID)


def main() -> None:
    parser = argparse.ArgumentParser(description="RAW vs CORRECTED paper tables (read-only)")
    parser.add_argument("--matrix-db-url", default=os.getenv("MATRIX_DATABASE_URL", DEFAULT_MATRIX_DB_URL))
    parser.add_argument("--exclude-breaking", action="store_true")
    parser.add_argument("--st-abandon", choices=ST_ABANDON_MODES, default="as-is")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--tex-dir", type=Path, default=TEX_DIR)
    args = parser.parse_args()

    raw = load_matrix(args.matrix_db_url)
    problems = regression_check(raw)
    if problems:
        print("REGRESSION CHECK FAILED -- RAW does not reproduce results/analysis/*.csv; nothing written:")
        for p in problems:
            print("  -", p)
        raise SystemExit(1)
    print(f"Regression check PASSED: {len(REGRESSION)} tables in results/analysis/ reproduced exactly from {RUN_ID}.")

    cor = apply_filters(raw, exclude_breaking=args.exclude_breaking, st_abandon=args.st_abandon)
    mode = f"exclude_breaking={args.exclude_breaking}, st_abandon={args.st_abandon}"
    # Paper captions: plain words for the default corrected mode, the raw mode string otherwise.
    caption_mode = "breaking cells excluded" if (args.exclude_breaking and args.st_abandon == "as-is") else mode
    print(f"Corrected = {mode}: {len(raw)} -> {len(cor)} rows")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    args.tex_dir.mkdir(parents=True, exist_ok=True)
    raw_frames = {"T1": t1_outcome(raw), "T2": t2_control(raw), "T3": t3_intensity(raw), "T4": t4_pattern(raw),
                  "T4b": t4b_pattern_intensity(raw), "T5": t5_language(raw), "T7": t7_language_pattern(raw)}
    cor_frames = {"T1": t1_outcome(cor), "T2": t2_control(cor), "T3": t3_intensity(cor), "T4": t4_pattern(cor),
                  "T4b": t4b_pattern_intensity(cor), "T5": t5_language(cor), "T7": t7_language_pattern(cor)}
    r6, c6 = t6_mcnemar(raw), t6_mcnemar(cor)
    for i, part in enumerate(("summary", "cells", "sign")):
        raw_frames[f"T6_{part}"], cor_frames[f"T6_{part}"] = r6[i], c6[i]
    for key in raw_frames:
        raw_frames[key].to_csv(args.out_dir / f"{key}_raw.csv", index=False)
        cor_frames[key].to_csv(args.out_dir / f"{key}_corrected.csv", index=False)
    t8_attribution(raw).to_csv(args.out_dir / "T8_attribution_raw.csv", index=False)
    c2 = c2_counts(raw)
    c2.to_csv(args.out_dir / "C2_counts.csv", index=False)
    sens = sensitivity(raw)
    for key, frame in sens.items():
        frame.to_csv(args.out_dir / f"{key}_sensitivity.csv", index=False)

    shown = present(raw, cor)
    captions = {
        "T1": ("Outcome distribution by arm (scored episodes), raw vs corrected", "tab:corr-outcome", "l" + "r" * 10, True),
        "T2": ("Control-condition deceptions by arm and language, raw vs corrected", "tab:corr-control", "lllrr", False),
        "T3": ("Intensity dose-response (DC/n), raw vs corrected", "tab:corr-intensity", "llrr", False),
        "T4": ("Pattern-level DC (E1a, E1b), raw vs corrected", "tab:corr-patterns", "lrrrrl", True),
        "T5": ("Language conditions (DC/n), raw vs corrected", "tab:corr-lang", "llrrrr", False),
        "T6": ("Paired McNemar, English vs Hindi/Hinglish interface, raw vs corrected", "tab:corr-mcnemar", "lrrrrrrrr", True),
        "T7": ("DC by pattern and interface language (English instruction), raw vs corrected", "tab:corr-langpattern", "llrr", False),
    }
    names = {"T1": "T1_outcome", "T2": "T2_control", "T3": "T3_intensity", "T4": "T4_patterns",
             "T5": "T5_language", "T6": "T6_mcnemar", "T7": "T7_language_pattern"}
    for key, (cap, label, colspec, wide) in captions.items():
        (args.tex_dir / f"{names[key]}.tex").write_text(
            tex_table(shown[key], f"{cap} ({caption_mode}).", label, colspec, wide), encoding="utf-8")

    md = [f"Corrected mode: `{mode}`. Cells are DC/n (DC%).\n"]
    for key in ("T1", "T2", "T3", "T4", "T4b", "T5", "T6", "T6_sign", "T6_cells", "T7", "T8"):
        md.append(f"### {key}\n\n{md_table(shown[key])}\n")
    md.append(f"### C2 (reported, not reclassified)\n\n{md_table(c2)}\n")
    for key, frame in sens.items():
        compact = frame
        if key == "S1_outcome":
            compact = frame[["exclude_breaking", "st_abandon", "arm", "n_scored", "DC", "EF", "dc_rate", "ef_rate"]]
        elif key == "S3_intensity":
            compact = frame[["exclude_breaking", "st_abandon", "arm", "intensity", "n_scored", "DC", "dc_rate"]]
        elif key == "S4_pattern":
            compact = frame[["exclude_breaking", "st_abandon", "pattern", "E1a_n", "E1a_DC", "E1b_n", "E1b_DC"]]
        md.append(f"### Sensitivity {key}\n\n{md_table(compact)}\n")
    (args.out_dir / "tables.md").write_text("\n".join(md), encoding="utf-8")
    print(f"Wrote {args.out_dir} and {args.tex_dir}")


if __name__ == "__main__":
    main()
